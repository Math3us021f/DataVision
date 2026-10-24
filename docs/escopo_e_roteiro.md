# Escopo e roteiro do DataVision

> Este documento registra o status real de cada etapa. Não marcar uma etapa como concluída sem verificação executada.

## Escopo

DataVision Admin (primeira entrega) + módulo de análise de dados (posterior). Arquitetura: FastAPI, SQLite, MinIO, psutil, Docker/Docker Compose. Regras completas em [../CLAUDE.md](../CLAUDE.md).

## Status das etapas

| Etapa | Descrição | Status |
|---|---|---|
| 0 | Preparação do ambiente local | Concluída |
| 1 | Estrutura mínima do projeto | Concluída |
| 2 | Aplicação web mínima (FastAPI + `/health`) | Concluída — verificado em 2026-10-24: container ativo, `GET /health` retornou 200 |
| 3 | Autenticação e autorização | Não iniciada |
| 4 | Gestão de usuários e auditoria | Não iniciada |
| 5 | Métricas | Não iniciada |
| 6 | Estado de serviços e logs | Não iniciada |
| 7 | Explorador de arquivos | Não iniciada |
| 8 | Estabilização do DataVision Admin | Não iniciada |
| 9 | Recepção e armazenamento de arquivos | Não iniciada |
| 10 | Perfilamento de dados | Não iniciada |
| 11 | Dashboards automáticos | Não iniciada |
| 12 | Validação do MVP e planejamento de deploy | Não iniciada |

## Decisões técnicas registradas

- 2026-10-24: Git inicializado neste momento (o projeto já existia sem controle de versão). Primeiro commit inclui o estado atual da Etapa 2.
- 2026-10-24: `requirements.txt` ainda sem versões fixadas (`fastapi`, `uvicorn[standard]`). Fixar versões é uma pendência antes de avançar muito no desenvolvimento, para reprodutibilidade do build.

## Riscos e pendências conhecidos

- Nenhuma suíte de testes automatizados existe ainda (pendente desde a Etapa 2).
- Porta 8000 publicada em todas as interfaces do host (aceitável em desenvolvimento local, revisar antes de qualquer exposição além da rede local).

## Próximo passo recomendado

Etapa 3 — autenticação e autorização, seguindo a skill `datavision-security` desde o início da implementação.
