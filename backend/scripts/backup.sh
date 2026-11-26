#!/bin/sh
# Respaldo diario: base (pg_dump -Fc) + archivos subidos. Se guardan 7 copias locales y,
# si BACKUP_REMOTE está definido (p. ej. "b2:rastrohg-backups"), se copian fuera del VPS
# con rclone (configurar el remoto con variables RCLONE_CONFIG_<NOMBRE>_* en .env).
set -eu
STAMP=$(date -u +%Y%m%dT%H%M)
OUT=/backups
pg_dump "$PG_DSN" -Fc -f "$OUT/rastrohg-$STAMP.dump"
tar -czf "$OUT/uploads-$STAMP.tgz" -C /data uploads
ls -1t "$OUT"/rastrohg-*.dump | tail -n +8 | xargs -r rm -f
ls -1t "$OUT"/uploads-*.tgz  | tail -n +8 | xargs -r rm -f
if [ -n "${BACKUP_REMOTE:-}" ]; then
  rclone copy "$OUT/rastrohg-$STAMP.dump" "$BACKUP_REMOTE/"
  rclone copy "$OUT/uploads-$STAMP.tgz" "$BACKUP_REMOTE/"
  echo "respaldo $STAMP copiado a $BACKUP_REMOTE"
else
  echo "AVISO: BACKUP_REMOTE no definido; respaldo $STAMP solo local" >&2
fi
