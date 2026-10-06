#!/bin/sh
# Gera deploy/seed/prod-seed.sql a partir do banco de DEV, sem contas de teste nem sessões.
# Uso (na máquina de dev, com o ambiente noemia-cup rodando):  sh deploy/export_prod_seed.sh
# Depois: copie o arquivo para o servidor, suba a produção e APAGUE o arquivo (contém dados pessoais).
set -eu
DB_CONTAINER="${DB_CONTAINER:-noemia-cup-db}"
DB_USER="${DB_USER:-pelada}"
SRC_DB="${SRC_DB:-pelada}"
TMP_DB="pelada_export_$(date +%s)"
OUT="$(dirname "$0")/seed/prod-seed.sql"

echo ">> Copiando $SRC_DB para $TMP_DB"
docker exec "$DB_CONTAINER" createdb -U "$DB_USER" "$TMP_DB"
trap 'docker exec "$DB_CONTAINER" dropdb -U "$DB_USER" --if-exists "$TMP_DB" >/dev/null 2>&1 || true' EXIT
docker exec "$DB_CONTAINER" sh -c "pg_dump -U $DB_USER $SRC_DB | psql -q -U $DB_USER $TMP_DB" >/dev/null

echo ">> Removendo contas de teste e sessões"
docker exec -i "$DB_CONTAINER" psql -v ON_ERROR_STOP=1 -q -U "$DB_USER" "$TMP_DB" <<'SQL'
DELETE FROM refresh_tokens;
DELETE FROM users WHERE email LIKE '%@pelada.app' OR email LIKE '%@test.com';
-- todo usuário que for para produção define uma senha nova no 1º acesso
UPDATE users SET must_change_password = true, failed_logins = 0, locked_until = NULL;
SQL
docker exec "$DB_CONTAINER" psql -At -U "$DB_USER" "$TMP_DB" -c "SELECT 'usuários exportados: ' || string_agg(email || ' (' || role || ')', ', ') FROM users"

echo ">> Gerando $OUT"
docker exec "$DB_CONTAINER" pg_dump -U "$DB_USER" --no-owner --no-privileges "$TMP_DB" > "$OUT"
chmod 600 "$OUT"
echo ">> Pronto: $(wc -c < "$OUT") bytes. Não versione nem deixe este arquivo no servidor depois da carga."
