# DataVision

SaaS de aprendizado: recebe arquivos de dados, realiza análises automáticas e gera dashboards.
Regras de desenvolvimento completas em [CLAUDE.md](CLAUDE.md). Roteiro de etapas em [docs/escopo_e_roteiro.md](docs/escopo_e_roteiro.md).

## Status atual

Etapa 2 concluída: API FastAPI mínima rodando em container Docker, com endpoint de verificação de saúde.

## Ambiente

- Windows + Docker Desktop (containers Linux).
- Python 3.13 dentro do container (não é necessário instalar no Windows).
- Dependências em `requirements.txt`.

## Preparar o ambiente

```bash
docker compose build
```

## Iniciar a aplicação

```bash
docker compose up
```

A API fica disponível em `http://localhost:8000`. Documentação interativa (Swagger) em `http://localhost:8000/docs`.

## Verificar se está funcionando

```bash
curl http://localhost:8000/health
```

Resposta esperada:

```json
{"status":"ok","application":"DataVision"}
```

## Executar os testes

Ainda não há suíte de testes automatizados no projeto. Quando existir, o comando esperado será:

```bash
docker compose run --rm app python -m pytest -q
```

## Encerrar os serviços

```bash
docker compose down
```
