# Una sola imagen para api, worker y cron: el mismo código, distinto comando.
FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

# pg_dump 16 (igual que el servidor) para respaldos + rclone para copiarlos fuera del VPS
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates gnupg rclone \
 && install -d /usr/share/postgresql-common/pgdg \
 && curl -fsSL -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc https://www.postgresql.org/media/keys/ACCC4CF8.asc \
 && echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt bookworm-pgdg main" \
      > /etc/apt/sources.list.d/pgdg.list \
 && apt-get update && apt-get install -y --no-install-recommends postgresql-client-16 \
 && rm -rf /var/lib/apt/lists/*

ARG TARGETARCH
ARG SUPERCRONIC_VERSION=v0.2.33
RUN curl -fsSLo /usr/local/bin/supercronic \
      "https://github.com/aptible/supercronic/releases/download/${SUPERCRONIC_VERSION}/supercronic-linux-${TARGETARCH}" \
 && chmod +x /usr/local/bin/supercronic

COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --no-install-project
COPY . .
RUN uv sync --no-dev

ENV PATH="/app/.venv/bin:$PATH" RASTROHG_CONFIG_DIR=/app/config
RUN useradd -m app && mkdir -p /data/uploads /data/tiles /backups && chown -R app /data /backups
USER app
EXPOSE 8000
CMD ["uvicorn", "rastrohg.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
