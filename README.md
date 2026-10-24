# DataVision

SaaS de aprendizado: recebe arquivos de dados, realiza análises automáticas e gera dashboards.
Regras de desenvolvimento completas em [CLAUDE.md](CLAUDE.md). Roteiro de etapas em [docs/escopo_e_roteiro.md](docs/escopo_e_roteiro.md). Exemplos de uso manual da API em [docs/testes_manuais.md](docs/testes_manuais.md).

## Status atual

Etapas 0 a 10 concluídas: DataVision Admin estabilizado + recepção/armazenamento de datasets (MinIO) + perfilamento de dados (detecção de tipo de coluna, valores ausentes, duplicidades via `pandas`) — tudo testado (`pytest`, 54 testes) e documentado. Próximo passo: dashboards automáticos (Etapa 11).

## Ambiente

- Windows + Docker Desktop (containers Linux).
- Python 3.13 dentro do container (não é necessário instalar no Windows).
- PostgreSQL como serviço separado (`db`) no Docker Compose.
- Dependências em `requirements.txt`.

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

## Encerrar os serviços

```bash
docker compose down
```
