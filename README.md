# DataVision

SaaS de aprendizado: recebe arquivos de dados, realiza análises automáticas e gera dashboards.
Regras de desenvolvimento completas em [CLAUDE.md](CLAUDE.md). Roteiro de etapas em [docs/escopo_e_roteiro.md](docs/escopo_e_roteiro.md). Exemplos de uso manual da API em [docs/testes_manuais.md](docs/testes_manuais.md).

## Status atual

Etapas 0 a 11 concluídas: DataVision Admin + datasets (MinIO) + perfilamento + dashboards automáticos e personalizáveis (regras determinísticas em Python, gráficos com Apache ECharts), login em dois passos por e-mail e sessão com expiração por inatividade. **O backend foi migrado do FastAPI para Django** (plano e decisões em [docs/migracao_django.md](docs/migracao_django.md)); a interface é toda em React. Testado: testes de integração do Django (`pytest`) e 100 de interface (Playwright). Etapa 12 (validação do MVP e planejamento de deploy) em andamento: ver [docs/etapa12_validacao_mvp.md](docs/etapa12_validacao_mvp.md).

## Estrutura

```
backend/    Django 5.2 LTS + Django Ninja (API em JSON e casca da interface); testes em backend/tests
frontend/   Interface em React + TypeScript + Tailwind (o resultado do build vai para backend/static_src/app)
tests_e2e/  Testes de interface (Playwright), contra a aplicação de pé
db-init/    Scripts de criação do usuário e dos bancos do Postgres (só em volume novo)
docs/       Roteiro, decisões, plano de deploy e exemplos de uso
```

## Ambiente

- Windows + Docker Desktop (containers Linux).
- Python 3.13 dentro do container (não é necessário instalar no Windows).
- PostgreSQL como serviço separado (`db`) no Docker Compose; MinIO (`minio`) para os arquivos; Mailpit (`mailpit`) para os e-mails de desenvolvimento.
- Dependências em `backend/requirements.txt` (versões exatas); `backend/constraints.txt` fixa também as indiretas, para o build ser reproduzível. Rascunho de produção (não aprovado) em `compose.prod.yaml` — ver `docs/etapa12_validacao_mvp.md`.

## Configurar variáveis de ambiente

Antes da primeira subida, copie `.env.example` para `.env` e preencha com valores reais (nunca commitados — `.env` está no `.gitignore`):

```bash
cp .env.example .env
```

Variáveis:

- `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` — credenciais de **manutenção** do Postgres (superusuário; usadas só para conexão manual/DBeaver, não pela aplicação).
- `APP_DB_USER`, `APP_DB_PASSWORD` — credenciais que a **aplicação** usa de verdade (privilégio limitado, não é superusuário).
- `SECRET_KEY` — chave para assinar cookies e códigos de verificação.
- `ADMIN_USERNAME`, `ADMIN_PASSWORD` — admin inicial do DataVision (não confundir com o usuário do Postgres), criado automaticamente na primeira subida se não houver nenhum usuário (`python manage.py ensure_admin`).
- `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`, `MINIO_BUCKET` — MinIO local de dev (onde os datasets enviados são armazenados). Credenciais próprias deste ambiente, nunca as de produção.

## Preparar e iniciar a aplicação

```bash
docker compose build
docker compose --profile frontend run --rm frontend   # gera a interface React (primeira vez e a cada mudança em frontend/src)
docker compose up -d
```

Ao subir, o contêiner `app` aplica as migrações do banco, garante o administrador inicial e o bucket do MinIO, e inicia o servidor (que recarrega sozinho quando o código muda). A aplicação fica em `http://localhost:8000` (a interface em `/app`); a documentação interativa da API (Swagger), só fora de produção, em `http://localhost:8000/docs`.

O Postgres também fica acessível de fora do Docker em `localhost:15432` (só localhost). O console web do MinIO fica em `http://localhost:9001`.

## Verificar se está funcionando

```bash
curl http://localhost:8000/health
```

Resposta esperada:

```json
{"status": "ok", "application": "DataVision"}
```

Para testar login, gestão de usuários e métricas manualmente, veja [docs/testes_manuais.md](docs/testes_manuais.md) (as requisições que alteram dados exigem o token CSRF, explicado lá).

## Executar os testes

```bash
docker compose exec -T app python -m pytest -q
```

Os testes usam um banco próprio (`datavision_dj_test`, criado em `db-init/`) e um MinIO de mentira em memória. `backend/tests/contract/` reúne os testes de comportamento herdados do FastAPI, que rodam por um adaptador (`backend/tests/compat.py`) e servem de prova de paridade da migração.

## Executar os testes de interface (Playwright)

Testes end-to-end reais, num serviço Docker separado (profile `test`, com os navegadores já instalados — por isso não entra na imagem da aplicação). Exigem a aplicação de pé e a interface gerada:

```bash
docker compose up -d
docker compose --profile test run --rm e2e
```

**E-mail:** o login em dois passos envia um código por e-mail. Sem `SMTP_*` no `.env`, tudo vai para o **Mailpit**, um coletor local que sobe junto com o Compose (códigos em `http://localhost:8025`; nada é entregue de verdade). Com `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` e `SMTP_FROM` definidos (ver `.env.example`), endereços **reais** recebem o e-mail de verdade; endereços de mentira (`exemplo.com`, `example.com`, `.test` etc., usados pelos testes) continuam indo só para o Mailpit, então a suíte de interface pode rodar com o envio real ativo. Depois de mudar o `.env`: `docker compose up -d app`.

## Banco de dados

As tabelas vêm das **migrações** do Django (`backend/*/migrations`); elas são aplicadas ao subir. Depois de mudar um modelo: `docker compose exec -T app python manage.py makemigrations` e commitar o arquivo gerado (migração já aplicada não se edita). Para ver o SQL de uma migração: `python manage.py sqlmigrate <app> <número>`.

## Interface (React) — desenvolvimento

A interface vive em `frontend/` e abre em `http://localhost:8000/app` (é a única interface: o login em `/login` e as telas de administração em `/app/admin/...` também são dela; os endereços antigos — `/`, `/meus-datasets`, `/account` e `/admin/...` — redirecionam). O Node roda **só em container**; não precisa instalar nada no Windows.

```bash
docker compose --profile frontend run --rm frontend
```

Esse comando confere os tipos (TypeScript) e gera os arquivos em `backend/static_src/app/` (não versionados). Rode-o depois de mudar algo em `frontend/src`. Para instalar ou atualizar uma dependência: `docker compose --profile frontend run --rm frontend npm install <pacote>` (isso atualiza `frontend/package-lock.json`, que deve ser commitado).

Na imagem de produção (`docker build --target production .`) o build do frontend acontece automaticamente num estágio à parte, e a imagem final não contém Node.

## Encerrar os serviços

```bash
docker compose down
```
