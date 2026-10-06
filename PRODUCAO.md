# Produção — Pelada de Quarta

> Hospedagem gerenciada (Vercel + Render + Neon), sem servidor próprio: veja [PUBLICAR-RENDER-NEON-VERCEL.md](PUBLICAR-RENDER-NEON-VERCEL.md).
Este guia cobre a opção com VPS própria (Docker Compose + Caddy).

Guia para colocar o sistema no ar com segurança. O ambiente de produção (`docker-compose.prod.yml`) é **separado** do
ambiente de desenvolvimento (`docker-compose.yml`, projeto `noemia-cup-pelada-de-quarta`).

## Como fica no servidor

| Serviço | Papel | Exposto? |
|---|---|---|
| `web` (Caddy) | Site estático + proxy `/api` + **HTTPS automático** (Let's Encrypt) + headers de segurança | Portas 80 e 443 |
| `api` (FastAPI) | Usuário não-root, sistema de arquivos somente leitura, sem capabilities, 2 workers | Não (só o Caddy alcança) |
| `db` (Postgres 16) | A API usa um usuário que só lê e escreve dados; migrations rodam com o dono do schema | Não |
| `backup` | `pg_dump` diário com retenção de 14 dias (volume `backups`) | Não |

## Pré-requisitos
- VPS Linux com Docker e Docker Compose.
- Um domínio apontando (registro A/AAAA) para o IP do servidor.
- Firewall liberando **só** 22 (SSH), 80 e 443:
  ```bash
  ufw default deny incoming && ufw allow OpenSSH && ufw allow 80,443/tcp && ufw allow 443/udp && ufw enable
  ```
- SSH só com chave (`PasswordAuthentication no`) e atualizações automáticas do sistema (`unattended-upgrades`).

## Primeiro deploy

1. **Na máquina de dev**, gere a carga de dados reais. Ela sai sem contas de teste e sem sessões, e todos precisam trocar a
   senha no 1º acesso:
   ```bash
   sh deploy/export_prod_seed.sh        # cria deploy/seed/prod-seed.sql
   ```
2. Copie o projeto para o servidor, incluindo `deploy/seed/prod-seed.sql`, que tem dados pessoais. Use `scp`; **nunca**
   use git.
3. No servidor, crie o `.env.prod` a partir do exemplo e gere **um segredo diferente para cada campo**:
   ```bash
   cp .env.prod.example .env.prod && chmod 600 .env.prod
   openssl rand -base64 48 | tr -d '/+=' | cut -c1-48   # rode uma vez para cada segredo
   ```
   Preencha `DOMAIN`, `ACME_EMAIL`, as duas senhas do banco e o `JWT_SECRET`. A API **se recusa a subir** se algum valor
   for fraco ou padrão (segredo curto, cookie sem HTTPS, domínio `localhost`, senha de banco padrão).
4. Suba:
   ```bash
   docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
   docker compose -f docker-compose.prod.yml --env-file .env.prod logs -f api   # aguarde "Application startup complete"
   ```
5. **Apague o seed do servidor** (os dados já estão no banco):
   ```bash
   shred -u deploy/seed/prod-seed.sql
   ```
6. Acesse `https://SEU_DOMINIO` com o seu e-mail de admin e a sua senha atual. O sistema pede uma **senha nova** antes de
   liberar o resto.

## O que está protegido

- **Transporte:** só HTTPS, com HSTS de 1 ano. HTTP redireciona para HTTPS. O cookie de sessão é `Secure`, `HttpOnly`,
  `SameSite=Lax` e restrito a `/api/auth`.
- **Navegador:** CSP sem scripts inline nem de terceiros (as fontes são servidas pelo próprio site), `frame-ancestors 'none'`,
  `nosniff`, `Referrer-Policy` e `Permissions-Policy`.
- **Login:**
  - limite por IP de 5 tentativas por minuto e 30 por hora (cadastro: 3 por hora). Passou disso, a resposta é 429;
  - a conta fica bloqueada por 15 minutos depois de 10 senhas erradas seguidas, com registro na auditoria;
  - o tempo de resposta é o mesmo para e-mail inexistente;
  - senhas novas precisam de 10 ou mais caracteres e não podem estar na lista de senhas comuns;
  - quando o admin cria um usuário ou redefine uma senha, a troca é obrigatória no próximo acesso.
- **Uploads:**
  - a foto é validada pelo conteúdo real e regravada como WEBP, com no máximo 1024 px e **sem EXIF/GPS**. Arquivo
    disfarçado é recusado;
  - os limites são lidos em blocos (3 MB por foto e 6 MB por requisição no Caddy);
  - a planilha é lida com `defusedxml` e tem limite de linhas e de tamanho descompactado.
- **API:** documentação (`/api/docs`) desligada; só aceita o `Host` do domínio; não expõe a versão do servidor.
- **Banco:** fora da internet; a API não consegue criar, alterar nem apagar tabelas.
- **Logs:** eventos de segurança em JSON no stdout (`login_failed`, `account_locked`, `login_blocked`, `rate_limited`,
  `role_changed`). Os logs nunca contêm senhas ou tokens e são rotacionados a 10 MB × 5.

## Backups
- O serviço `backup` grava `pelada-AAAAMMDD-HHMM.dump` todo dia no volume `backups` e mantém 14 dias.
- **Copie para fora do servidor** (um backup que só existe no próprio servidor não protege contra a perda dele):
  ```bash
  docker compose -f docker-compose.prod.yml --env-file .env.prod cp backup:/backups ./backups-$(date +%F)
  ```
- **Teste a restauração** pelo menos uma vez por mês:
  ```bash
  C="docker compose -f docker-compose.prod.yml --env-file .env.prod"
  $C exec backup sh -c 'createdb -h db -U "$POSTGRES_USER" restore_test && pg_restore -h db -U "$POSTGRES_USER" -d restore_test --no-owner "$(ls -t /backups/*.dump | head -1)"'
  $C exec backup sh -c 'psql -h db -U "$POSTGRES_USER" -d restore_test -c "select count(*) from players"; dropdb -h db -U "$POSTGRES_USER" restore_test'
  ```
- As fotos ficam no volume `media`. Inclua esse volume na cópia externa.

## Atualizações
```bash
git pull   # ou copie a nova versão
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build   # migrations rodam sozinhas ao subir a API
```
Uma vez por mês, verifique as dependências. As versões atuais foram conferidas sem avisos em 2026-10-06:
```bash
docker compose exec web npm audit --omit=dev     # no ambiente de dev
# Python: consulte https://osv.dev para as versões de backend/requirements.txt
```
**Risco aceito:** o `npm audit` completo aponta 7 avisos em ferramentas de build (`braces` e `postcss-selector-parser`,
dependências do Tailwind 3). Elas só processam o CSS do próprio projeto durante o build e não vão para o site publicado.
Resolver exige migrar para o Tailwind 4.

## Se um segredo vazar
- **`JWT_SECRET`:** gere outro, atualize o `.env.prod` e rode `up -d api`. Todos os tokens antigos deixam de valer, e as
  pessoas entram de novo.
- **Senha do banco:** troque com `ALTER ROLE ... PASSWORD '...'` (dentro de `docker compose exec db psql -U <dono>`),
  atualize o `.env.prod` e reinicie a API.
- **Conta de um usuário:** em Gestão → Usuários, bloqueie o usuário (as sessões caem na hora) ou redefina a senha (a troca
  fica obrigatória).

## Testar a produção localmente
```bash
# .env.prod.local: copie do exemplo com DOMAIN=pelada.test, HTTP_PORT=8080, HTTPS_PORT=8443, CADDY_EXTRA_GLOBAL=local_certs
docker compose -p pelada-prod-local -f docker-compose.prod.yml --env-file .env.prod.local up -d --build
curl -kI --resolve pelada.test:8443:127.0.0.1 https://pelada.test:8443/
docker compose -p pelada-prod-local -f docker-compose.prod.yml --env-file .env.prod.local down -v   # apaga tudo
```
`CADDY_EXTRA_GLOBAL=local_certs` serve **só** para teste local. Em produção, deixe vazio para o Caddy emitir o certificado
público.
