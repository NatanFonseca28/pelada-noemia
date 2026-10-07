#!/bin/sh
# Restaura um backup diário (artifact .gpg do GitHub Actions) num banco Postgres.
# Uso:
#   BACKUP_PASSPHRASE='...' DESTINO_URL='postgresql://...' sh deploy/restaurar-backup.sh [id-da-execução]
# Sem id, usa o backup mais recente. DESTINO_URL deve ser um banco VAZIO (ex.: um branch novo no Neon ou um
# Postgres local); nunca restaure por cima da produção sem antes conferir o arquivo.
set -eu
: "${BACKUP_PASSPHRASE:?defina BACKUP_PASSPHRASE}"
: "${DESTINO_URL:?defina DESTINO_URL (banco vazio de destino)}"
REPO="${REPO:-NatanFonseca28/pelada-noemia}"
RUN="${1:-$(gh run list -R "$REPO" -w "Backup do banco" -s success -L 1 --json databaseId -q '.[0].databaseId')}"
DIR="$(mktemp -d)"
trap 'rm -rf "$DIR"' EXIT

echo ">> Baixando o backup da execução $RUN"
gh run download "$RUN" -R "$REPO" -D "$DIR"
GPG="$(find "$DIR" -name '*.dump.gpg' | head -1)"
echo ">> Descriptografando $(basename "$GPG")"
printf '%s' "$BACKUP_PASSPHRASE" | docker run --rm -i -v "$DIR:/b" alpine:3 sh -c \
  "apk add -q gnupg >/dev/null && gpg --batch --pinentry-mode loopback --passphrase-fd 0 -d -o /b/backup.dump /b/$(basename "$GPG")"
echo ">> Restaurando em DESTINO_URL"
docker run --rm -v "$DIR:/b" postgres:16-alpine pg_restore --no-owner --no-privileges -d "$DESTINO_URL" /b/backup.dump
docker run --rm postgres:16-alpine psql "$DESTINO_URL" -At -c "select 'jogadores: ' || count(*) from players; select 'mensalidades: ' || count(*) from monthly_fees"
echo ">> Pronto."
