#!/bin/sh
# Prepara o banco do Neon: carrega os dados reais (opcional) e cria o usuário da aplicação com privilégio mínimo.
# Usa o psql de uma imagem Docker (não precisa instalar nada). Rode na raiz do projeto:
#
#   NEON_OWNER_URL='postgresql://neondb_owner:...@ep-xxx.us-east-1.aws.neon.tech/neondb?sslmode=require' \
#   APP_DB_PASSWORD='senha-gerada-com-openssl' \
#   sh deploy/neon/preparar-neon.sh
#
# Com SEED=nao, pula a carga de dados (banco começa vazio; as migrations criam as tabelas no 1º deploy da API).
set -eu
: "${NEON_OWNER_URL:?defina NEON_OWNER_URL (connection string do Neon, SEM pooling)}"
: "${APP_DB_PASSWORD:?defina APP_DB_PASSWORD (gere com: openssl rand -base64 32 | tr -d /+=)}"
APP_DB_USER="${APP_DB_USER:-pelada_app}"
SEED="${SEED:-sim}"
SEED_FILE="deploy/seed/prod-seed.sql"

case "$NEON_OWNER_URL" in
  *-pooler.*) echo "ERRO: use a connection string SEM pooling (o host não pode ter '-pooler')."; exit 1 ;;
esac

OWNER=$(printf '%s' "$NEON_OWNER_URL" | sed -E 's#^[a-z+]+://([^:]+):.*#\1#')
HOSTPART=$(printf '%s' "$NEON_OWNER_URL" | sed -E 's#^[a-z+]+://[^@]+@##')
DBNAME=$(printf '%s' "$HOSTPART" | sed -E 's#^[^/]+/([^?]+).*#\1#')

psql() { docker run --rm -i postgres:16-alpine psql "$NEON_OWNER_URL" -v ON_ERROR_STOP=1 -q "$@"; }

echo ">> Testando a conexão com o Neon (usuário $OWNER, banco $DBNAME)"
psql -At -c "select 'ok: ' || version()" | cut -c1-60

if [ "$SEED" = "sim" ]; then
  TABLES=$(psql -At -c "select count(*) from information_schema.tables where table_schema='public'")
  if [ "$TABLES" != "0" ]; then
    echo "ERRO: o banco do Neon já tem $TABLES tabelas. A carga só roda em banco vazio (use SEED=nao para só criar o usuário)."
    exit 1
  fi
  echo ">> Gerando $SEED_FILE a partir do banco de dev (sempre do zero, com os dados atuais)"
  sh deploy/export_prod_seed.sh
  echo ">> Carregando $SEED_FILE no Neon"
  psql < "$SEED_FILE"
fi

echo ">> Criando o usuário da aplicação ($APP_DB_USER) com permissão só de ler/escrever dados"
psql <<SQL
DO \$\$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '${APP_DB_USER}') THEN
    CREATE ROLE ${APP_DB_USER} LOGIN PASSWORD '${APP_DB_PASSWORD}';
  ELSE
    ALTER ROLE ${APP_DB_USER} PASSWORD '${APP_DB_PASSWORD}';
  END IF;
END \$\$;
REVOKE ALL ON DATABASE ${DBNAME} FROM PUBLIC;
GRANT CONNECT ON DATABASE ${DBNAME} TO ${APP_DB_USER};
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO ${APP_DB_USER};
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO ${APP_DB_USER};
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO ${APP_DB_USER};
ALTER DEFAULT PRIVILEGES FOR ROLE ${OWNER} IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO ${APP_DB_USER};
ALTER DEFAULT PRIVILEGES FOR ROLE ${OWNER} IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO ${APP_DB_USER};
SQL

if [ "$SEED" = "sim" ]; then
  psql -At -c "select 'jogadores: ' || count(*) from players; select 'usuários: ' || string_agg(email, ', ') from users"
fi

APP_URL=$(printf '%s' "$NEON_OWNER_URL" | sed -E "s#^([a-z+]+://)[^@]+@#\1${APP_DB_USER}:${APP_DB_PASSWORD}@#")
echo
echo ">> Pronto. Use no Koyeb:"
echo "   DATABASE_URL            = $APP_URL"
echo "   MIGRATIONS_DATABASE_URL = (a NEON_OWNER_URL que você usou aqui)"
[ "$SEED" = "sim" ] && echo ">> Agora apague o arquivo com dados pessoais:  shred -u $SEED_FILE"
