# PostgreSQL 16 + PostGIS 3 + pgvector, desde los paquetes oficiales de PGDG.
# (La imagen postgis/postgis no trae pgvector y no es multi-arquitectura.)
FROM postgres:16-bookworm
RUN apt-get update \
 && apt-get install -y --no-install-recommends postgresql-16-postgis-3 postgresql-16-pgvector \
 && rm -rf /var/lib/apt/lists/*
