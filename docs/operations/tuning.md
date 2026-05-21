# Tuning

The viewer is CPU-bound. Almost every performance question reduces to
"how many concurrent renders can a worker pod sustain, and how big is
each render?" This document gives the rules of thumb and explains when
to turn each knob.

All numbers below are starting points from a development workload; the
only way to size your deployment correctly is to load-test with your own
document mix.

## `WORKER_CONCURRENCY`

`WORKER_CONCURRENCY` (default `4`) controls how many render jobs a single
worker process executes in parallel. It is passed straight to arq as
`max_jobs` (`document_viewer.worker.settings.main`).

Render work is CPU-bound: pikepdf clean, pypdfium2 rasterization, Pillow
resize, WebP encode are all CPU-heavy. Reasonable starting points:

- Set `WORKER_CONCURRENCY` to the number of CPU cores available to the
  worker pod, then halve it if you also run Gotenberg co-tenant.
- In Helm, the chart wires `WORKER_CONCURRENCY` from `worker.concurrency`
  and the pod's CPU limit from `worker.resources.limits.cpu`. Keep the
  two aligned: there is no benefit to `concurrency=8` on a pod with
  `cpu: 1000m` — the kernel scheduler will just stack jobs on top of
  each other.

When to raise it:

- Worker CPU utilization stays below 60% under steady load.
- Queue backlog is non-trivial but workers are not saturated.

When to lower it:

- p99 render latency rises without queue depth rising (workers are
  thrashing).
- Memory limits trip — concurrent renders multiply RAM usage; see
  expected RAM below.

## `MAX_PAGE_WIDTH`

`MAX_PAGE_WIDTH` (default `2400`) is the hard ceiling on rendered image
width. Client requests above this are clamped silently in
`RenderPipeline.render_page`.

Raising it costs RAM and CPU per render — both scale roughly with
width-squared (area). Going from 2400 → 3200 (a ~33% width increase) is
~75% more pixels and roughly that much more RAM and encode time.

When to raise it:

- Users complain about pixelation when zooming on dense PDFs (small font
  on tax forms, ID cards).
- You have headroom: per-worker RAM is at <50% of the limit at peak.

When to lower it:

- Worker pods are OOMKilling under load.
- You are willing to trade rendering fidelity for throughput.

`MAX_PAGE_WIDTH` is the cap, not the default. Clients still send a
`width` query parameter; the cap only matters when a client requests
something above it.

## Cache hit ratio

Hit ratio target: **>80% in steady state** with normal repeat-viewer
traffic (back-office reviewers paging through the same KYC case).

Cache key derivation lives in
`document_viewer.shared.cache_keys`: page images are keyed by the source
content hash plus page index and width. A request that matches a key
that exists in Redis skips the entire render pipeline.

Levers:

- **`CACHE_TTL_SECONDS`** (default `900` = 15 min). Raising it improves
  hit ratio for slow-burn review sessions; costs Redis memory linearly.
  Reasonable upper bound: 3600 (1h) for review workflows that span
  pauses.
- **Redis memory**. If `maxmemory` is too small, the eviction policy
  drops cache entries before TTL — hit ratio drops independent of
  `CACHE_TTL_SECONDS`. The [Redis memory alert in monitoring.md](monitoring.md#redis-memory-pressure)
  catches this.

When hit ratio is low:

- Check Redis memory: hit ratio < 50% with healthy traffic often means
  evictions, not TTL expiry.
- Check the client: a UI that fetches different widths per scroll event
  will defeat caching. Pin width to a small set of values (e.g. 800,
  1200, 1600, 2400) so caches accumulate.

## Expected CPU/RAM per concurrent render

Rough numbers per concurrent render, measured on a dev workstation
(single physical core, no swap pressure):

| Pipeline | Peak RAM | Wall time |
|---|---|---|
| PDF page (single page, 2400px, native PDF input) | ~150 MB | ~300–800 ms |
| Image (JPEG/PNG → WebP, 2400px) | ~80 MB | ~100–300 ms |
| Office (DOCX/XLSX/PPTX) through Gotenberg | ~500 MB during conversion + ~150 MB per page render | ~1.5–4 s for conversion + per-page time |

These are peaks, not sustained averages. The pipeline reuses buffers
where possible; the peak is roughly two times the decoded image size
during the WebP encode.

Sizing rule of thumb for the worker pod:

```text
worker_pod_memory >= WORKER_CONCURRENCY * peak_render_memory + 100MB overhead
```

For `WORKER_CONCURRENCY=4` and a PDF-heavy load, that is `4 * 150 + 100 =
700 MB`. The chart default `worker.resources.limits.memory: 2Gi` covers
this with room for an office-heavy spike.

Office workloads need a separate budget for Gotenberg. The chart's
default `gotenberg.resources.limits.memory: 2Gi` is enough for two
concurrent conversions of small office files; large spreadsheets can
push it higher.

## When to scale out vs up

- **Scale out** (`worker.replicas` ↑, optionally enable the HPA): when
  total queue throughput needs to rise and you already have appropriate
  `WORKER_CONCURRENCY` for the pod size.
- **Scale up** (`worker.concurrency` ↑, larger CPU/memory limits): when
  each individual render is the bottleneck and you have CPU/memory
  headroom on the existing pods.
- **Scale Gotenberg separately**: office conversion is independent.
  `gotenberg.replicas: 2` is usually enough until your office volume
  meaningfully exceeds your PDF volume.

The HPA in the chart targets CPU utilization. Enable it
(`worker.autoscaling.enabled: true`) once you have a feel for steady-state
CPU; the HPA is fine for diurnal spikes but adds latency to large step
changes.
