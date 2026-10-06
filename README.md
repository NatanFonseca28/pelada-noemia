# ⚽ Pelada de Quarta

Sistema web para gerenciar a pelada de futebol society semanal: jogadores, confirmação de presença,
sorteio auditável, campeonato da rodada, mesa ao vivo (WebSocket) e estatísticas.

**Stack:** FastAPI · SQLAlchemy 2.0 (async) · Alembic · Pydantic v2 · PostgreSQL 16 · React + Vite + TypeScript ·
TanStack Query · React Router · Tailwind CSS · Docker Compose.

> **Produção:** veja [PRODUCAO.md](PRODUCAO.md) (HTTPS, segredos, backups e checklist de segurança).

## Como rodar (dev)

O ambiente de desenvolvimento é o projeto Docker **`noemia-cup-pelada-de-quarta`**
("Noemia Cup - Pelada de quarta"), com três containers:

| Container | Serviço | Porta no host |
|---|---|---|
| `noemia-cup-web` | React + Vite (hot reload) | http://localhost:5173 |
| `noemia-cup-api` | FastAPI (hot reload, roda as migrations ao subir) | http://localhost:8000/api/docs |
| `noemia-cup-db` | PostgreSQL 16 | `localhost:5434` (usuário/senha `pelada`) |

```bash
cp .env.example .env          # na primeira vez
docker compose up -d --build  # sobe tudo
docker compose logs -f api    # acompanhar a API
docker compose down           # para (os dados ficam no volume)
```

### Seed de desenvolvimento

Na **primeira subida** do volume do banco, `db/init/02-restore-seed.sh` restaura `db/seed/dev-seed.sql`, se o
arquivo existir. Esse arquivo é um dump do ambiente com dados reais (elenco, financeiro, rodadas, súmulas). Por isso
**não é versionado** (`.gitignore`).

```bash
# Gerar um novo seed a partir do banco atual do container
docker exec noemia-cup-db pg_dump -U pelada -d pelada --no-owner --no-privileges --clean --if-exists > db/seed/dev-seed.sql

# Recriar o banco do zero a partir do seed (APAGA os dados atuais do volume)
docker compose down -v && docker compose up -d
```

Sem `dev-seed.sql`, o banco sobe vazio. Nesse caso, rode `docker compose exec api python -m scripts.seed`
(usuários de teste) e importe a planilha:

```bash
docker compose cp "PELADA DE QUARTA CONTROLE.xlsx" api:/tmp/planilha.xlsx
docker compose exec api python -m scripts.import_planilha /tmp/planilha.xlsx
```

`python -m scripts.seed --demo` cria também 30 jogadores fictícios (útil para testar sorteio e campeonato).

### Usuários do seed

| Papel | E-mail | Senha |
|---|---|---|
| Admin | `admin@pelada.app` | `admin123` |
| Mesário | `mesario@pelada.app` | `mesario123` |
| Jogador | `carlao@pelada.app` | `jogador123` |
| Autocadastro pendente | `novato@pelada.app` | `jogador123` |

## Testes

```bash
docker compose exec api pytest
```

Os testes de API usam o banco `pelada_test` (criado por `db/init/01-test-db.sql` na primeira subida do
Postgres) e nunca tocam no banco `pelada` de desenvolvimento. O schema é recriado a cada execução **rodando as migrations do Alembic**, o que também valida as migrations.

> Se o volume `pgdata` já existia antes desse script, crie o banco manualmente:
> `docker compose exec db psql -U pelada -c "CREATE DATABASE pelada_test"`.

## Estrutura

```
backend/
  app/core/          config, segurança (argon2, JWT), dependências de auth/RBAC, erros
  app/models/        ORM SQLAlchemy
  app/schemas/       Pydantic (entrada/saída)
  app/repositories/  acesso a dados
  app/services/      regras de aplicação + auditoria
  app/domain/        regras puras (sorteio, formatos, classificação), sem banco
  app/routers/       endpoints REST (/api/...)
  alembic/           migrations
  scripts/seed.py    dados fictícios
  tests/             pytest (domain = unitários puros; api = integração)
frontend/src/
  api/               cliente HTTP (refresh automático) + hooks TanStack Query
  auth/              contexto de sessão e rotas protegidas por papel
  pages/gestao/      área do ADMIN
  pages/pelada/      área de todos os usuários logados
```

## Autenticação

- Login com e-mail e senha (hash **argon2**).
- **Access token** JWT de 15 minutos, mantido só em memória no front e enviado no header `Authorization`.
- **Refresh token** opaco de 7 dias, em cookie `httpOnly` restrito a `/api/auth`, com **rotação** a cada uso.
  Reutilizar um refresh já revogado derruba todas as sessões do usuário (detecção de vazamento).
- Papéis: `ADMIN`, `MESARIO` e `JOGADOR`. Autocadastro fica `PENDENTE` até a aprovação de um ADMIN.
- Bloquear um usuário ou trocar a senha revoga as sessões ativas.

## Financeiro (somente ADMIN)

Substitui a planilha *PELADA DE QUARTA CONTROLE*:

- **Mensalidades:** grade jogador × mês. Toque numa célula para marcar "Pagou R$ 50", outro valor (parcial) ou uma
  anotação (ex.: "F").
- **Caixa:** entradas (diaristas, colete) e saídas (campo, churrasco, bola…). O saldo é o saldo de abertura
  ("Saldo mês anterior" da planilha) somado às mensalidades e entradas e subtraído das saídas, a partir do mês de abertura.
- **Cobranças avulsas:** vaquinhas como "Coletes novos", com quem já pagou. Ficam fora do saldo do caixa.
- **Importar planilha:** lê o .xlsx no formato atual. Jogadores novos entram como mensalistas com posição a definir.
  Reimportar a mesma planilha não duplica nada.

Todas as edições aparecem na auditoria.

## Variáveis de ambiente

Veja `.env.example`. As principais são `DATABASE_URL`, `TEST_DATABASE_URL`, `JWT_SECRET`, `ACCESS_TOKEN_MINUTES`,
`REFRESH_TOKEN_DAYS`, `COOKIE_SECURE` (use `true` atrás de HTTPS), `MEDIA_DIR` e `MAX_PHOTO_MB`.

## Rodando sem Docker (desenvolvimento)

```bash
# backend (Python 3.12 + Postgres local)
cd backend && python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
export DATABASE_URL=postgresql+asyncpg://pelada:pelada@localhost:5432/pelada
alembic upgrade head && python -m scripts.seed
uvicorn app.main:app --reload

# frontend (Node 18+)
cd frontend && npm install && npm run dev   # proxy /api → http://localhost:8000
```

## Etapas

- [x] 1. Plano, modelo de dados e dúvidas
- [x] 2. Infra Docker, autenticação, usuários e jogadores
- [ ] 3. Rodadas, confirmação de presença e sorteio
- [ ] 4. Campeonato: formatos, tempo, classificação e chaveamento
- [ ] 5. Partida ao vivo e WebSocket
- [ ] 6. Estatísticas, rankings e resumo
