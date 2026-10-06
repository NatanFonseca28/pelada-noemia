#!/bin/sh
# Carrega o seed de desenvolvimento (dump do ambiente anterior), se existir.
# Roda só na primeira subida do volume do banco (comportamento padrão do postgres).
set -e
if [ -f /seed/dev-seed.sql ]; then
  echo ">> Restaurando seed de desenvolvimento (/seed/dev-seed.sql)"
  psql -v ON_ERROR_STOP=1 -q -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /seed/dev-seed.sql
else
  echo ">> Sem seed em /seed/dev-seed.sql — banco vazio (as migrations rodam ao subir a API)"
fi
