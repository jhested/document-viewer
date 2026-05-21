# Monitoring

This document describes what the application emits, how to collect it,
and what to alert on. The defaults are deliberately conservative; tune
thresholds to your environment.

## Structured logs

The API and worker both configure structured JSON logging on stdout via
`document_viewer.shared.logging.configure_logging`. Each log line is a
JSON object containing at least:

- `event`: short kebab-case identifier for the log event.
- `timestamp`: ISO-8601 UTC.
- `level`: `info`, `warning`, or `error`.

`event="render.completed"` is the audit line every successful render
emits. It carries:

- `request_id`: the `X-Request-ID` correlation header set by
  `RequestIdMiddleware` (auto-generated when the client does not provide
  one).
- `sub`: the JWT `sub` claim — the back-office user who initiated the
  view.
- `obj`: the source document key (S3 key or filesystem path).
- `page`: page number requested (`1`-indexed).
- `width`: clamped image width in pixels (after `MAX_PAGE_WIDTH` cap).
- `ms`: wall-clock duration of the render call in milliseconds.
- `status`: `ok` on success; the error category (e.g. `parser_error`,
  `timeout`, `unsupported_mime`) on failure.

JWTs are redacted from arbitrary log strings via the
`_JWT_PATTERN` regex in `document_viewer.shared.logging` — but the
practical rule is: do not log payloads or tokens. Log events with named
fields.

## Health endpoints

- `GET /healthz` — liveness. Returns `200 OK` immediately. Used by the
  Kubernetes liveness probe and any external uptime check.
- `GET /readyz` — readiness. Returns `200 OK` once the API can reach
  Redis; `503` otherwise. Used by the Kubernetes readiness probe and any
  external load-balancer health check.

## Metrics

The chart includes an optional `ServiceMonitor` for the Prometheus
Operator:

```yaml
monitoring:
  serviceMonitor:
    enabled: true
    namespace: monitoring
    interval: 30s
```

It scrapes the API's `/metrics` endpoint. The endpoint is opt-in: enable
it only on clusters running the Prometheus Operator. If you do not run
Prometheus, leave the `ServiceMonitor` disabled (the default).

Worker queue depth (`arq` queue length) is read directly from Redis with
`LLEN arq:queue` (or your queue name); export it via a redis_exporter
sidecar rather than from the API process.

## Suggested Prometheus alerts

These are starting points. Adjust thresholds to your traffic profile and
SLOs. The expressions assume standard `prometheus`, `redis_exporter`, and
`kube-state-metrics` metric names.

### High render latency (p99 > 5s)

```yaml
- alert: ViewerRenderLatencyHigh
  expr: histogram_quantile(0.99, sum by (le) (rate(viewer_render_duration_seconds_bucket[5m]))) > 5
  for: 10m
  labels: { severity: warning }
  annotations:
    summary: "p99 render latency above 5s for 10m"
    description: "Investigate worker CPU saturation, Gotenberg queue, or pathological inputs."
```

p99 above 5 seconds for ten minutes means either workers are CPU-bound,
Gotenberg is degraded, or sources are unusually large. Check worker CPU
saturation first; see [tuning.md](tuning.md).

### Redis memory pressure

```yaml
- alert: ViewerRedisMemoryHigh
  expr: redis_memory_used_bytes / redis_memory_max_bytes > 0.80
  for: 15m
  labels: { severity: warning }
  annotations:
    summary: "Redis memory usage above 80% of max for 15m"
    description: "Lower CACHE_TTL_SECONDS or scale Redis. Cache eviction will start at the configured maxmemory-policy."
```

When Redis hits 80% of its configured `maxmemory`, the eviction policy
starts triggering and cache hit ratio drops fast. The reactive lever is
`CACHE_TTL_SECONDS`; the structural lever is more Redis memory.

### Gotenberg restart loop

```yaml
- alert: ViewerGotenbergRestartLoop
  expr: increase(kube_pod_container_status_restarts_total{container="gotenberg"}[10m]) > 3
  for: 5m
  labels: { severity: critical }
  annotations:
    summary: "Gotenberg restarted more than 3 times in 10m"
    description: "Office conversion is down. PDFs and images still render; office files will fail."
```

More than three Gotenberg restarts in ten minutes typically means OOMKill
loops (the per-pod memory limit is too tight for the office file mix
being thrown at it) or a malformed input that triggers a panic. Bump the
Gotenberg memory limit or quarantine the offending input.

### Worker queue backlog

```yaml
- alert: ViewerWorkerQueueBacklog
  expr: redis_list_length{key="arq:queue"} > 100
  for: 5m
  labels: { severity: warning }
  annotations:
    summary: "Worker queue depth > 100 for 5m"
    description: "Scale worker replicas or increase WORKER_CONCURRENCY."
```

A persistent queue depth above 100 jobs for five minutes means workers
are under-provisioned for the offered load. Either scale `worker.replicas`
horizontally, increase `WORKER_CONCURRENCY` vertically (only useful if
CPU headroom exists), or enable the HPA (`worker.autoscaling.enabled`).

## What not to alert on

- Individual render failures. A `status != ok` render line is normal:
  malformed input, MIME outside the allowlist, page out of range. Alert
  on the failure rate, not single failures.
- 4xx response counts. They reflect bad clients, not service health.
- Cache miss bursts immediately after a deploy or Redis restart. Cold
  caches recover within a few minutes of normal traffic.
