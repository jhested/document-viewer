# syntax=docker/dockerfile:1.7
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends \
        libmagic1 fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

FROM base AS build
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .

FROM base AS runtime
WORKDIR /app
RUN groupadd -r app && useradd -r -g app -d /app app
COPY --from=build /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=build /usr/local/bin/viewer-worker /usr/local/bin/viewer-worker
USER app
CMD ["viewer-worker"]
