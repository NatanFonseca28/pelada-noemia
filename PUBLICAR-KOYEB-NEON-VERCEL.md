# Publicar na Vercel + Koyeb + Neon

Passo a passo para colocar a Pelada no ar sem servidor próprio, usando os planos gratuitos.

```
navegador ──► Vercel (site)  ──/api/*──►  Koyeb (API FastAPI)  ──►  Neon (Postgres)
              pelada-noemia.vercel.app     pelada-api-….koyeb.app      ep-….neon.tech
```

O navegador só conversa com a Vercel. As chamadas para `/api/...` são repassadas por ela para o Koyeb. Por isso o site e a
API ficam no **mesmo endereço**: o cookie de login funciona sem configuração extra e não há problema de CORS.

Tempo total: uns 40 minutos. Siga na ordem, porque cada etapa usa um valor da anterior.

---

## 0. Antes de começar

1. Crie as três contas, todas com **"Continue with GitHub"** (usando a conta `NatanFonseca28`):
   - <https://console.neon.tech/signup>
   - <https://app.koyeb.com/auth/signup>
   - <https://vercel.com/signup>
2. Deixe o Docker Desktop aberto e o ambiente de dev rodando (`docker compose up -d` na raiz do projeto). Os seus dados
   reais saem dele.
3. No terminal (WSL), na pasta do projeto, gere os dois segredos. Guarde-os num gerenciador de senhas:
   ```bash
   cd /mnt/d/Projeto-pelada
   echo "JWT_SECRET=$(openssl rand -base64 48 | tr -d '/+=' | cut -c1-48)"
   echo "APP_DB_PASSWORD=$(openssl rand -base64 32 | tr -d '/+=')"
   ```
4. Envie o código atual para o GitHub (o Koyeb e a Vercel puxam de lá):
   ```bash
   git push
   ```

---

## 1. Neon (banco de dados)

1. Em <https://console.neon.tech>, clique em **New Project** e preencha:
   - **Project name:** `pelada-noemia`
   - **Postgres version:** `16`
   - **Region:** `AWS US East 1 (N. Virginia)`. Fica perto da região do Koyeb que vamos usar.
   - Clique em **Create project**.
2. Na página do projeto, clique em **Connect** e preencha:
   - **Branch:** `main`
   - **Database:** `neondb`
   - **Role:** `neondb_owner`
   - **Desligue "Connection pooling"**. A API não funciona com o endereço que tem `-pooler`, e a própria API recusa
     subir se ele for usado.
   - Copie a connection string. Ela tem este formato:
     `postgresql://neondb_owner:XXXX@ep-algo-123456.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require`
3. No terminal, carregue os dados reais e crie o usuário da aplicação. Cole a connection string e o `APP_DB_PASSWORD` do
   passo 0 entre aspas simples:
   ```bash
   NEON_OWNER_URL='postgresql://neondb_owner:XXXX@ep-algo-123456.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require' \
   APP_DB_PASSWORD='COLE-AQUI' \
   sh deploy/neon/preparar-neon.sh
   ```
   O script faz o seguinte:
   - gera uma cópia dos dados do dev **sem as contas de teste** e marca a troca de senha obrigatória para todos;
   - carrega essa cópia no Neon;
   - cria o usuário `pelada_app`, que só lê e grava dados (não consegue apagar nem criar tabelas).

   No final ele mostra a **`DATABASE_URL`** para o Koyeb. Copie-a.
4. Apague a cópia local com dados pessoais (o próprio script lembra):
   ```bash
   shred -u deploy/seed/prod-seed.sql
   ```

> Se quiser começar com o banco **vazio**, rode o mesmo comando com `SEED=nao` na frente. Nesse caso você vai precisar
> criar o primeiro admin depois (veja "Problemas comuns").

---

## 2. Koyeb (API)

1. Em <https://app.koyeb.com>, clique em **Create Service → Web service → GitHub**. Na primeira vez, autorize o app do
   Koyeb no GitHub e dê acesso ao repositório `pelada-noemia`.
2. Escolha o repositório **`NatanFonseca28/pelada-noemia`** e a branch **`main`**.
3. Em **Builder**, escolha **Dockerfile** e preencha:
   - **Dockerfile location:** `Dockerfile.prod`
   - **Work directory:** `backend`
   - Deixe *Entrypoint*, *Command* e *Target* em branco.
4. Em **Instance**, escolha **Free**. Em **Region**, escolha **Washington, D.C.**
5. Em **Environment variables**, adicione as variáveis da tabela abaixo. Use o botão de **Secret** nas que estão marcadas
   como secretas, para não ficarem visíveis no painel.

   | Nome | Valor | Secreta? |
   |---|---|---|
   | `ENVIRONMENT` | `production` | não |
   | `DATABASE_URL` | a URL com `pelada_app` que o script mostrou | **sim** |
   | `MIGRATIONS_DATABASE_URL` | a connection string do Neon (com `neondb_owner`) | **sim** |
   | `JWT_SECRET` | o `JWT_SECRET` do passo 0 | **sim** |
   | `COOKIE_SECURE` | `true` | não |
   | `CORS_ORIGINS` | `https://pelada-noemia.vercel.app` | não |
   | `ALLOWED_HOSTS` | `pelada-api-SUAORG.koyeb.app,pelada-noemia.vercel.app` (veja o passo 7) | não |
   | `WEB_CONCURRENCY` | `1` | não |
   | `PORT` | `8000` | não |

6. Em **Exposed ports**, use a porta `8000`, protocolo `HTTP`, path `/`. Em **Health checks**, deixe o padrão (**TCP**
   na porta 8000). Não troque para HTTP, porque a checagem HTTP seria recusada pela proteção de host.
7. Em **Service name** / **App name**, escreva `pelada-api`. O endereço público fica
   `https://pelada-api-<sua-organização>.koyeb.app` e aparece nessa mesma tela. Coloque esse domínio, sem `https://`, na
   variável `ALLOWED_HOSTS`.
8. Clique em **Deploy**. O primeiro build leva de 3 a 5 minutos. Em **Logs**, espere aparecer:
   ```
   INFO:     Application startup complete.
   ```
9. Teste (troque pelo seu domínio):
   ```bash
   curl https://pelada-api-SUAORG.koyeb.app/api/health
   # {"status":"ok"}
   ```

---

## 3. Vercel (site)

1. No arquivo `frontend/vercel.json`, troque `SUBSTITUA-PELO-DOMINIO-DO-KOYEB` pelo domínio do Koyeb, sem `https://`:
   ```json
   { "source": "/api/:path*", "destination": "https://pelada-api-SUAORG.koyeb.app/api/:path*" },
   ```
   Depois envie a mudança:
   ```bash
   git add frontend/vercel.json && git commit -m "Aponta o site para a API no Koyeb" && git push
   ```
2. Em <https://vercel.com/new>, clique em **Import** ao lado de `pelada-noemia` e preencha:
   - **Project Name:** `pelada-noemia`
   - **Root Directory:** clique em **Edit** e escolha `frontend`
   - **Framework Preset:** `Vite` (detectado sozinho)
   - **Environment Variables:** nenhuma
   - Clique em **Deploy**.
3. Ao terminar, o site fica em **`https://pelada-noemia.vercel.app`**. Se a Vercel der outro endereço (porque o nome já
   estava em uso), coloque o novo endereço em `CORS_ORIGINS` e em `ALLOWED_HOSTS` no Koyeb e clique em **Redeploy**.

---

## 4. Primeiro acesso

1. Abra o site e entre com o **seu e-mail e a senha que você já usa**.
2. O sistema pede uma **senha nova**. Use uma com 10 caracteres ou mais. Isso vale para todo usuário que veio da cópia.
3. Confira os pontos abaixo:
   - [ ] **Dashboard** mostra o saldo e os inadimplentes iguais aos do dev.
   - [ ] **Elenco** lista os jogadores.
   - [ ] Enviar uma foto de jogador funciona, e a foto continua lá depois de um novo deploy no Koyeb (as fotos ficam no
     banco).
   - [ ] Sair e entrar de novo funciona, assim como recarregar a página continuando logado.

---

## Atualizações

Basta `git push` na branch `main`:
- a **Vercel** publica o site de novo sozinha;
- o **Koyeb** reconstrói a API e roda as migrations do banco ao subir.

## Backups

O plano gratuito do Neon guarda pouco histórico para restauração. Faça uma cópia sua **uma vez por mês**:
```bash
mkdir -p backups
docker run --rm postgres:16-alpine pg_dump 'COLE-A-NEON_OWNER_URL' -Fc > backups/pelada-$(date +%F).dump
```
A pasta `backups/` está no `.gitignore`. Guarde os arquivos fora do computador também (Google Drive, por exemplo).

## Bom saber

- **Hibernação:** nos planos gratuitos, a API (Koyeb) e o banco (Neon) dormem depois de um tempo sem uso. O primeiro
  acesso depois disso demora alguns segundos; os seguintes ficam rápidos.
- **Domínio próprio:** para usar um domínio próprio, adicione-o em Vercel → Settings → Domains. Depois inclua o domínio
  em `CORS_ORIGINS` e `ALLOWED_HOSTS` no Koyeb e faça **Redeploy**.
- **Segredo vazado:** se um segredo vazar, gere outro e troque no Koyeb.
  - **`JWT_SECRET`:** todos precisam entrar de novo.
  - **Senha do banco:** troque em Neon → Roles e atualize as URLs no Koyeb.

## Problemas comuns

| Sintoma | Causa e correção |
|---|---|
| Log do Koyeb: `Configuração insegura para produção` | A mensagem lista a variável com problema (segredo curto, `COOKIE_SECURE` falso, `localhost`…). Corrija no Koyeb e faça **Redeploy**. |
| Log do Koyeb menciona `pooler` | A URL é a do pooling do Neon. Copie de novo com "Connection pooling" **desligado**. |
| Site abre, mas o login dá erro ou `/api/...` retorna 404 | O `frontend/vercel.json` ainda tem `SUBSTITUA-PELO-DOMINIO-DO-KOYEB`, ou o domínio está errado (passo 3.1). |
| `Invalid host header` (400) | O domínio do Koyeb ou da Vercel não está em `ALLOWED_HOSTS`. |
| Banco começou vazio (`SEED=nao`) e não há admin | Crie o admin pelo terminal: `docker compose run --rm -e DATABASE_URL='COLE-A-NEON_OWNER_URL' -e ADMIN_EMAIL='seu@email' -e ADMIN_PASSWORD='SenhaForte-123' api python -m scripts.seed --admin-only`. Depois do 1º login, troque a senha em **Conta**. |
