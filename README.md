# DataVision

SaaS de aprendizado: recebe arquivos de dados, realiza análises automáticas e gera dashboards.
Regras de desenvolvimento completas em [CLAUDE.md](CLAUDE.md). Roteiro de etapas em [docs/escopo_e_roteiro.md](docs/escopo_e_roteiro.md). Exemplos de uso manual da API em [docs/testes_manuais.md](docs/testes_manuais.md).

## Status atual

Etapas 0 a 11 concluídas: DataVision Admin + datasets (MinIO) + perfilamento + dashboards automáticos e personalizáveis (regras determinísticas em Python, gráficos com Apache ECharts). Testado: 202 testes de integração (`pytest`) e 13 de interface (Playwright). Etapa 12 (validação do MVP e planejamento de deploy) em andamento: ver [docs/etapa12_validacao_mvp.md](docs/etapa12_validacao_mvp.md).

## Ambiente

- Windows + Docker Desktop (containers Linux).
- Python 3.13 dentro do container (não é necessário instalar no Windows).
- PostgreSQL como serviço separado (`db`) no Docker Compose.
- Dependências em `requirements.txt` (versões exatas); `constraints.txt` fixa também as indiretas, para o build ser reproduzível. Rascunho de produção (não aprovado) em `compose.prod.yaml` — ver `docs/etapa12_validacao_mvp.md`.

## Configurar variáveis de ambiente

Antes da primeira subida, copie `.env.example` para `.env` e preencha com valores reais (nunca commitados — `.env` está no `.gitignore`):

```bash
cp .env.example .env
```

Variáveis:

- `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` — credenciais de **manutenção** do Postgres (superusuário; usadas só para conexão manual/DBeaver, não pela aplicação).
- `APP_DB_USER`, `APP_DB_PASSWORD` — credenciais que a **aplicação** usa de verdade (privilégio limitado, não é superusuário).
- `SECRET_KEY` — chave para assinar os cookies de sessão.
- `ADMIN_USERNAME`, `ADMIN_PASSWORD` — admin inicial do DataVision (não confundir com o usuário do Postgres), criado automaticamente na primeira subida se a tabela `users` estiver vazia.
- `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`, `MINIO_BUCKET` — MinIO local de dev (onde os datasets enviados são armazenados). Credenciais próprias deste ambiente, nunca as de produção.

## Preparar o ambiente

```bash
docker compose build
```

## Iniciar a aplicação

```bash
docker compose up -d
```

A API fica disponível em `http://localhost:8000`. Documentação interativa (Swagger) em `http://localhost:8000/docs`.

O Postgres também fica acessível de fora do Docker em `localhost:15432` (só localhost), útil para conectar com DBeaver ou outro cliente SQL. O console web do MinIO fica em `http://localhost:9001`.

## Verificar se está funcionando

```bash
curl http://localhost:8000/health
```

Resposta esperada:

```json
{"status":"ok","application":"DataVision"}
```

Para testar login, gestão de usuários e métricas manualmente, veja [docs/testes_manuais.md](docs/testes_manuais.md).

## Executar os testes

```bash
docker compose exec app python -m pytest -v
```

(Se os containers ainda não estiverem rodando, use `docker compose run --rm app python -m pytest -v` no lugar.)

## Executar os testes de interface (Playwright)

Testes end-to-end reais, num serviço Docker separado (profile `test`, com os navegadores já instalados — por isso não entra na imagem principal da aplicação). Exigem a aplicação de pé:

```bash
docker compose up -d
docker compose --profile test run --rm e2e
```

**E-mail em desenvolvimento:** o login em dois passos envia e-mails para o **Mailpit**, um coletor local que sobe junto com o Compose. Veja os códigos em `http://localhost:8025` (nada é entregue de verdade). Os testes de interface leem os códigos de lá. As variáveis `SMTP_*` do `.env` valem só no servidor; para testar um envio real em desenvolvimento use `DEV_SMTP_*` (ver `.env.example`) e não rode a suíte de interface nesse período.

## Interface nova (React) — desenvolvimento

A interface nova vive em `frontend/` e abre em `http://localhost:8000/app` (é a única interface: o login em `/login` e as telas de administração em `/app/admin/...` também são dela; os endereços antigos — `/`, `/meus-datasets`, `/account` e `/admin/...` — redirecionam). O Node roda **só em container**; não precisa instalar nada no Windows.

```bash
docker compose --profile frontend run --rm frontend
```

Esse comando confere os tipos (TypeScript) e gera os arquivos em `src/static/app/` (não versionados). Rode-o depois de mudar algo em `frontend/src`. Para instalar ou atualizar uma dependência: `docker compose --profile frontend run --rm frontend npm install <pacote>` (isso atualiza `frontend/package-lock.json`, que deve ser commitado).

Na imagem de produção (`docker compose build`) o build do frontend acontece automaticamente num estágio à parte, e a imagem final não contém Node.

## Encerrar os serviços

```bash
docker compose down
```
