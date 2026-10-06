#!/bin/sh
# Backup diário (formato custom do pg_dump, compactado) com retenção de 14 dias.
# Copie a pasta de backups para fora do servidor (ver PRODUCAO.md).
set -eu
while true; do
  file="/backups/pelada-$(date -u +%Y%m%d-%H%M).dump"
  pg_dump -h db -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc -f "$file.tmp" && mv "$file.tmp" "$file" && echo "backup ok: $file"
  find /backups -name 'pelada-*.dump' -mtime +14 -delete
  sleep 86400
done
