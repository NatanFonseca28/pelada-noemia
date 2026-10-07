# Publicar na Vercel + Render + Neon

Passo a passo para colocar a Pelada no ar sem servidor próprio, usando os planos gratuitos.

> **Publicado em 2026-10-06:**
> - site: <https://pelada-noemia.vercel.app>
> - API: <https://pelada-api-9vwk.onrender.com>
> - banco: projeto Neon `pelada-noemia`
>
> Os dados foram carregados com `COPIA_IDENTICA=sim`: cópia fiel da homologação, inclusive as contas de teste e as
> senhas. Sem essa opção, o script leva só contas reais e exige senha nova.

```
navegador ──► Vercel (site)  ──/api/*──►  Render (API FastAPI)  ──►  Neon (Postgres)
              pelada-noemia.vercel.app     pelada-api.onrender.com      ep-….neon.tech
```

O navegador só conversa com a Vercel. As chamadas para `/api/...` são repassadas por ela para o Render. Por isso o site e
a API ficam no **mesmo endereço**: o cookie de login funciona sem configuração extra e não há problema de CORS.

Tempo total: uns 40 minutos. Siga na ordem, porque cada etapa usa um valor da anterior.

> **Comandos de terminal:** copie só as linhas **de dentro** dos blocos. As linhas com ```` ``` ```` não fazem parte do
> comando.

---

## 0. Antes de começar

1. Crie as três contas, todas com **"Continue with GitHub"** (usando a conta `NatanFonseca28`):
   - <https://console.neon.tech/signup>
   - <https://dashboard.render.com/register>
   - <https://vercel.com/signup>
2. Deixe o Docker Desktop aberto e o ambiente de dev rodando (`docker compose up -d` na raiz do projeto). Os seus dados
   reais saem dele.
3. No terminal (WSL), na pasta do projeto, gere os dois segredos. Guarde-os num gerenciador de senhas:
   ```bash
   cd /mnt/d/Projeto-pelada
   echo "JWT_SECRET=$(openssl rand -base64 48 | tr -d '/+=' | cut -c1-48)"
   echo "APP_DB_PASSWORD=$(openssl rand -base64 32 | tr -d '/+=')"
   ```
4. Envie o código atual para o GitHub (o Render e a Vercel puxam de lá):
   ```bash
   git push
   ```

---

## 1. Neon (banco de dados)

1. Em <https://console.neon.tech>, clique em **New Project** e preencha:
   - **Project name:** `pelada-noemia`
   - **Postgres version:** `16`
   - **Region:** `AWS US East 1 (N. Virginia)`. É a mesma região do Render que vamos usar.
   - Clique em **Create project**.
2. Na página do projeto, clique em **Connect** e preencha:
   - **Branch:** `main`
   - **Database:** `neondb`
   - **Role:** `neondb_owner`
   - **Desligue "Connection pooling"**. A API não funciona com o endereço que tem `-pooler`, e a própria API recusa
     subir se ele for usado.
   - Copie a connection string. Ela tem este formato:
     `postgresql://neondb_owner:XXXX@ep-algo-123456.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require`
3. No terminal, carregue os dados reais e crie o usuário da aplicação. Troque os dois valores entre aspas simples (é
   **um comando só**, em 3 linhas):
   ```bash
   NEON_OWNER_URL='postgresql://neondb_owner:XXXX@ep-algo-123456.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require' \
   APP_DB_PASSWORD='COLE-AQUI' \
   sh deploy/neon/preparar-neon.sh
   ```
   O script faz o seguinte:
   - gera uma cópia dos dados do dev **sem as contas de teste** e marca a troca de senha obrigatória para todos;
   - carrega essa cópia no Neon;
   - cria o usuário `pelada_app`, que só lê e grava dados (não consegue apagar nem criar tabelas).

   No final ele mostra a **`DATABASE_URL`** para o Render. Copie-a.
4. Apague a cópia local com dados pessoais (o próprio script lembra):
   ```bash
   shred -u deploy/seed/prod-seed.sql
   ```

> Se quiser começar com o banco **vazio**, rode o mesmo comando com `SEED=nao` na frente. Nesse caso você vai precisar
> criar o primeiro admin depois (veja "Problemas comuns").

---

## 2. Render (API)

1. Em <https://dashboard.render.com>, clique em **+ New → Web Service**.
2. Em **Git Provider**, escolha **GitHub**. Na primeira vez, autorize o Render e dê acesso ao repositório
   `pelada-noemia`. Selecione **`NatanFonseca28/pelada-noemia`** e clique em **Connect**.
3. Preencha o formulário:
   - **Name:** `pelada-api`. Ele define o endereço `https://pelada-api.onrender.com`; se o nome já existir, o Render
     acrescenta letras, e o endereço real aparece no topo da página do serviço depois de criado.
   - **Language:** `Docker`
   - **Branch:** `main`
   - **Region:** `Virginia (US East)`
   - **Root Directory:** `backend`
   - **Instance Type:** `Free`
4. Abra **Advanced** e preencha:
   - **Dockerfile Path:** `./Dockerfile.prod`. Se o campo já vier com o prefixo `backend/`, deixe
     `backend/Dockerfile.prod`.
   - **Docker Build Context Directory:** deixe o padrão (`backend` / `.`).
   - **Health Check Path:** deixe **vazio**.
   - **Auto-Deploy:** `On Commit`.
5. Em **Environment Variables**, adicione as variáveis abaixo. **Não** crie `PORT`, porque o Render define sozinho.

   | Nome | Valor |
   |---|---|
   | `ENVIRONMENT` | `production` |
   | `DATABASE_URL` | a URL com `pelada_app` que o script mostrou |
   | `MIGRATIONS_DATABASE_URL` | a connection string do Neon (com `neondb_owner`) |
   | `JWT_SECRET` | o `JWT_SECRET` do passo 0 |
   | `COOKIE_SECURE` | `true` |
   | `CORS_ORIGINS` | `https://pelada-noemia.vercel.app` |
   | `ALLOWED_HOSTS` | `pelada-api.onrender.com,pelada-noemia.vercel.app` |
   | `WEB_CONCURRENCY` | `1` |

   Os valores ficam visíveis só para você no painel do Render.
6. Clique em **Deploy Web Service**. O primeiro build leva de 3 a 6 minutos. Na aba **Logs**, espere aparecer:
   ```
   INFO:     Application startup complete.
   ```
   e depois `Your service is live`.
7. Confira o endereço no topo da página. Se não for exatamente `pelada-api.onrender.com`, faça assim:
   - corrija `ALLOWED_HOSTS` em **Environment**;
   - clique em **Save, rebuild, and deploy**.
8. Teste (troque pelo seu endereço):
   ```bash
   curl https://pelada-api.onrender.com/api/health
   ```
   A resposta deve ser `{"status":"ok"}`.

---

## 3. Vercel (site)

1. No arquivo `frontend/vercel.json`, troque `SUBSTITUA-PELO-DOMINIO-DO-RENDER` pelo endereço do Render, sem `https://`:
   ```json
   { "source": "/api/:path*", "destination": "https://pelada-api.onrender.com/api/:path*" },
   ```
   Depois envie a mudança:
   ```bash
   git add frontend/vercel.json && git commit -m "Aponta o site para a API no Render" && git push
   ```
2. Em <https://vercel.com/new>, clique em **Import** ao lado de `pelada-noemia` e preencha:
   - **Project Name:** `pelada-noemia`
   - **Root Directory:** clique em **Edit** e escolha `frontend`
   - **Framework Preset:** `Vite` (detectado sozinho)
   - **Environment Variables:** nenhuma
   - Clique em **Deploy**.
3. Ao terminar, o site fica em **`https://pelada-noemia.vercel.app`**. Se a Vercel der outro endereço (porque o nome já
   estava em uso), faça assim no Render:
   - coloque o novo endereço em `CORS_ORIGINS` e em `ALLOWED_HOSTS`;
   - clique em **Save, rebuild, and deploy**.

---

## 4. Manter a API acordada

O plano gratuito do Render **desliga a API depois de 15 minutos sem acesso**, e a primeira visita depois disso leva até
1 minuto. O workflow `.github/workflows/manter-api-acordada.yml` chama `/api/health` a cada 10 minutos pelo GitHub
Actions, que é gratuito em repositório público. Se você trocar o endereço do Render, atualize a URL nesse arquivo.

---

## 5. Primeiro acesso

1. Abra o site e entre com o **seu e-mail e a senha que você já usa**.
2. O sistema pede uma **senha nova**. Use uma com 10 caracteres ou mais. Isso vale para todo usuário que veio da cópia.
3. Confira os pontos abaixo:
   - [ ] **Dashboard** mostra o saldo e os inadimplentes iguais aos do dev.
   - [ ] **Elenco** lista os jogadores.
   - [ ] Enviar uma foto de jogador funciona, e a foto continua lá depois de um novo deploy no Render (as fotos ficam no
     banco).
   - [ ] Sair e entrar de novo funciona, assim como recarregar a página continuando logado.

---

## Atualizações

Basta `git push` na branch `main`:
- a **Vercel** publica o site de novo sozinha;
- o **Render** reconstrói a API e roda as migrations do banco ao subir.

## Backups

**Automático:** o workflow `.github/workflows/backup-banco.yml` roda todo dia às 03:00 (horário de Brasília).
- Faz uma cópia do banco com o usuário `pelada_app`, que só lê dados.
- **Criptografa** a cópia com a `BACKUP_PASSPHRASE` antes de sair do servidor do GitHub.
- Guarda cada cópia por 30 dias em Actions → "Backup do banco" → Artifacts.
- Sem a senha, o arquivo não serve para nada. **Guarde a `BACKUP_PASSPHRASE` no seu gerenciador de senhas**: sem ela não
  dá para restaurar.

**Restaurar** num banco vazio, por exemplo um branch novo no Neon ou um Postgres local:
```bash
BACKUP_PASSPHRASE='...' DESTINO_URL='postgresql://...' sh deploy/restaurar-backup.sh   # usa o backup mais recente
```
- Para restaurar um dia específico, passe o id da execução como argumento.
- O script mostra no final quantos jogadores e mensalidades foram restaurados, para conferir.

Para guardar uma cópia fora do GitHub, baixe um artifact de vez em quando e guarde no Google Drive. Ele já vem
criptografado.

## Bom saber

- **Domínio próprio:** para usar um domínio próprio, adicione-o em Vercel → Settings → Domains. Depois inclua o domínio
  em `CORS_ORIGINS` e `ALLOWED_HOSTS` no Render e faça um novo deploy.
- **Segredo vazado:** se um segredo vazar, gere outro e troque no Render.
  - **`JWT_SECRET`:** todos precisam entrar de novo.
  - **Senha do banco:** troque em Neon → Roles e atualize as URLs no Render.

## Problemas comuns

| Sintoma | Causa e correção |
|---|---|
| Log do Render: `Configuração insegura para produção` | A mensagem lista a variável com problema (segredo curto, `COOKIE_SECURE` falso, `localhost`…). Corrija em **Environment** e faça um novo deploy. |
| Log do Render menciona `pooler` | A URL é a do pooling do Neon. Copie de novo com "Connection pooling" **desligado**. |
| Build falha com `Dockerfile not found` | Ajuste o **Dockerfile Path** em Settings para `./Dockerfile.prod` (com Root Directory `backend`) ou para `backend/Dockerfile.prod`. |
| Site abre, mas o login dá erro ou `/api/...` retorna 404 | O `frontend/vercel.json` ainda tem `SUBSTITUA-PELO-DOMINIO-DO-RENDER`, ou o endereço está errado (passo 3.1). |
| `Invalid host header` (400) | O endereço do Render ou da Vercel não está em `ALLOWED_HOSTS`. |
| Primeiro acesso do dia dá erro e depois funciona | A API estava dormindo. Configure o passo 4. |
| Banco começou vazio (`SEED=nao`) e não há admin | Crie o admin pelo terminal: `docker compose run --rm -e DATABASE_URL='COLE-A-NEON_OWNER_URL' -e ADMIN_EMAIL='seu@email' -e ADMIN_PASSWORD='SenhaForte-123' api python -m scripts.seed --admin-only`. Depois do 1º login, troque a senha em **Conta**. |
