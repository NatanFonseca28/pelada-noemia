#!/bin/sh
# Carga inicial de produção (dados reais, sem contas de teste). Roda só na 1ª subida do volume.
set -e
if [ -f /seed/prod-seed.sql ]; then
  echo ">> Restaurando /seed/prod-seed.sql"
  psql -v ON_ERROR_STOP=1 -q -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /seed/prod-seed.sql
  # garante os privilégios do app também nos objetos restaurados
  psql -v ON_ERROR_STOP=1 -q -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO ${APP_DB_USER}; GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO ${APP_DB_USER};"
  echo ">> Seed restaurado. Apague o arquivo do servidor: deploy/seed/prod-seed.sql"
else
  echo ">> Sem seed: banco vazio (as migrations criam o schema)"
fi
