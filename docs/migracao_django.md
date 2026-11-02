# Migração do backend para Django

> Iniciada em 2026-11-02, a pedido do usuário ("vamos ter mais controle do que o FastAPI"). O FastAPI continua funcionando em `src/` (porta 8000) até o Django alcançar a **paridade**: mesma API, mesmas respostas, mesmos testes. O React continua sendo só a interface e quase não muda.

## Decisões

| Tema | Decisão | Por quê |
|---|---|---|
| Versão | **Django 5.2 LTS** (suporte de longo prazo) | Estabilidade; a 6.x é mais nova, sem suporte longo. |
| API | **Django Ninja** (não Django REST Framework) | Reaproveita os esquemas Pydantic atuais (`src/schemas/analytics.py`) e o estilo com tipos do FastAPI; menos código. As rotas ficam **na raiz** (`/health`, `/me`, `/users`...), iguais às de hoje. |
| Dados | **ORM** nos cadastros e consultas simples; SQL direto só onde for agregação complexa | Migrações versionadas no lugar do `init_db()` com `ALTER TABLE IF NOT EXISTS`. |
| Usuário | **Modelo próprio** (`accounts.User`) desde o começo: `username`, `email` (opcional, único sem diferenciar maiúsculas), `display_name`, `preferences`, `is_admin`, `is_active` | Trocar o modelo depois, com dados, é muito difícil. `is_staff`/`is_superuser` = `is_admin`. |
| Sessão | Sessões no banco, cookie **`session`** (mesmo nome), HttpOnly, SameSite=Lax, 8 h absolutas; inatividade de 15 min em middleware próprio (a fazer) | O React e os testes não percebem a troca. |
| CSRF | Ligado (cookie `csrftoken` legível pelo React, devolvido em `X-CSRFToken`) | O Django exige; é a única mudança prevista no React. |
| Servidor | **gunicorn com 1 processo e 8 threads** (produção) e `runserver` (desenvolvimento) | O Django sob ASGI executa views síncronas numa única thread compartilhada, o que serializaria as consultas pesadas; com threads elas rodam em paralelo. Um processo só porque o limite de tentativas de login e o de consultas vivem na memória. |
| Estáticos | **WhiteNoise** entrega o build do React em `/static/app/` | Sem nginx por enquanto. |
| CSP | Middleware próprio, mesma política do FastAPI | O Django 5.2 não tem CSP embutida. |
| Banco | `datavision_dj` (e `datavision_dj_test`), no mesmo Postgres, separado do atual | Convivência até a troca. O usuário da aplicação **não** cria bancos (de propósito), então o banco de teste é criado em `db-init/` e reaproveitado (`pytest --reuse-db`). |
| Dados | **Nada a preservar**: não há dados de produção | Por isso é melhor migrar agora. O banco de desenvolvimento só tem dados de teste. |
| Painel admin do Django | Disponível só como emergência (`is_staff` = administrador); a administração de verdade continua no React | Opcional; ainda não ligado. |

## Contrato congelado

`docs/contrato_api_fastapi.json` é o OpenAPI do FastAPI de hoje (42 caminhos, 49 operações). O Django precisa responder igual. Para regenerar: `docker compose exec -T app python -c "import json; from src.main import app; print(json.dumps(app.openapi(), ensure_ascii=False, indent=2, sort_keys=True))"`.

## Etapas

| # | Etapa | Estado |
|---|---|---|
| 1 | Congelar o contrato da API atual | **feito** |
| 2 | Esqueleto: projeto, settings por variáveis de ambiente, Docker, Postgres, logs com rotação, `/health`, `/docs` só fora de produção | **feito** |
| 3 | Casca do React (`/login`, `/app/...`), `/static/app/`, CSP e cabeçalhos de segurança | **feito** |
| 4 | Modelos e migrações das demais tabelas (datasets, perfil, colunas, dashboards, auditoria, acessos, códigos de e-mail, notificações) | a fazer |
| 5 | Login, logout, `/me`, sessão com inatividade, limite de tentativas, dois passos por e-mail | a fazer |
| 6 | Usuários, auditoria, conta (perfil, senha, e-mail, sessões) e notificações | a fazer |
| 7 | Datasets: upload, MinIO, perfilamento, amostra | a fazer |
| 8 | Consultas, dashboards salvos e painel padrão (o motor de análise é reaproveitado) | a fazer |
| 9 | Métricas, logs, explorador de arquivos, resumo do painel | a fazer |
| 10 | Troca: React com CSRF, suíte Playwright inteira contra o Django, Django na porta 8000, remoção do FastAPI, Dockerfile e `compose.prod.yaml` | a fazer |

## Comportamentos a reproduzir (paridade)

Login em duas etapas (cookie `pending_login`, código em HMAC, 5 tentativas, pausa de 30 s, teto por hora, falha de envio = 503) · sessão que cai com 15 min de inatividade, com chamadas marcadas `X-Background-Request` que não renovam · limite de tentativas de login por (IP, usuário) · mensagem única para usuário/senha inválidos e gasto de tempo igual para usuário inexistente · senha de no máximo 72 bytes (limite do bcrypt, se mantivermos bcrypt) · auditoria das ações administrativas, sem dados pessoais inteiros · e-mail sempre mascarado na API · exclusão de usuário com datasets exige confirmação forçada · uploads limitados a 10 MB com validação de conteúdo · consultas com no máximo 3 simultâneas, prazo de 15 s e cache de 3 arquivos · `/docs` fora do ar em produção · logs com rotação, sem segredos.

## Como rodar (etapa atual)

```bash
docker compose up -d django                      # http://localhost:8001 (o FastAPI segue em :8000)
docker compose exec -T django python manage.py migrate
docker compose exec -T django python -m pytest -q
docker compose exec -T django python manage.py makemigrations   # depois de mudar um modelo
```

## Riscos acompanhados

Reproduzir exatamente a expiração por inatividade e o login em duas etapas · token CSRF no React · concorrência das consultas (threads, não ASGI) · Dockerfile/compose de produção · os 2.600 testes de backend atuais usam o `TestClient` do FastAPI e precisam de um adaptador (a suíte Playwright já é independente do backend).
