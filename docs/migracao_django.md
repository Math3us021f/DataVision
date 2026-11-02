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
| 4 | Modelos e migrações das demais tabelas (datasets, perfil, colunas, dashboards, auditoria, acessos, códigos de e-mail, notificações) | **feito** |
| 5 | Login, logout, `/me`, sessão com inatividade, limite de tentativas, dois passos por e-mail | **feito** |
| 6 | Usuários, auditoria, conta (perfil, senha, e-mail, sessões) e notificações | **feito** |
| 7 | Datasets: upload, MinIO, perfilamento, amostra | **feito** |
| 8 | Consultas, dashboards salvos e painel padrão (o motor de análise é reaproveitado) | **feito** |
| 9 | Métricas, logs, explorador de arquivos, resumo do painel | **feito** |
| 10 | Troca: React com CSRF, suíte Playwright inteira contra o Django, Django na porta 8000, remoção do FastAPI, Dockerfile e `compose.prod.yaml` | a fazer |

## Modelos (etapa 4)

Três apps, um por assunto: `accounts` (`User`, `LoginEvent`, `EmailCode`, `Notification`), `audit` (`AuditLog`) e `datasets` (`Dataset`, `DatasetProfile`, `DatasetColumn`, `DatasetColumnTopValue`, `Dashboard`). As tabelas do banco novo têm o prefixo do app (`accounts_user`, `datasets_dataset`...).

| Regra | Como ficou no Django |
|---|---|
| Excluir usuário que tem datasets | `Dataset.owner` com `on_delete=PROTECT` (antes: chave estrangeira sem `ON DELETE`); a exclusão forçada apaga os datasets antes, pelo código, e depois a conta |
| Apagar um dataset | `CASCADE` leva perfil, colunas, valores frequentes e dashboard (antes: o código apagava tudo à mão, linha por linha) |
| Auditoria ao excluir um usuário | `SET_NULL` em `actor` e `target`: o registro e o texto em `details` permanecem |
| Acessos, códigos de e-mail e notificações | `CASCADE` com o usuário |
| Um código pendente por usuário e finalidade | restrição única `(user, purpose)` |
| Um perfil e um dashboard por dataset | `OneToOneField` |
| Números não negativos | `PositiveIntegerField` (o Postgres recusa com `CHECK`) |
| Ações de auditoria | `AuditLog.Action` (`TextChoices`), as mesmas 10 do FastAPI |
| `session_version` | continua no usuário (senha trocada ou "encerrar outras sessões" invalidam cookies antigos) |

Observações: (1) o `CASCADE` e o `SET_NULL` são executados pelo ORM em Python, **não** viram `ON DELETE` no SQL — por isso apagar deve ser sempre por `.delete()` do ORM; (2) `accounts_user` tem a coluna extra `last_login` (vem do modelo base do Django); (3) a migração `0001` do usuário já estava commitada, então os ajustes (`date_joined` → `created_at`, `session_version`) entraram na `0002`: **migração já aplicada não se reescreve**. O esquema novo foi comparado coluna por coluna com o antigo: as 10 tabelas são equivalentes (só `last_login` a mais).

## Autenticação (etapa 5)

Rotas: `GET /login` (a tela), `POST /login`, `POST /login/verify`, `POST /login/resend`, `POST /logout` e `GET /me`, com as mesmas respostas e mensagens do FastAPI.

| Peça | Onde | Como funciona |
|---|---|---|
| Política de sessão | `accounts/session_policy.py` (middleware) | A sessão guarda `start`, `act` e `v`. 15 min sem atividade → 401 "Sessão encerrada por inatividade"; 8 h desde o login → "Sessão expirada"; `session_version` do usuário mudou → "Sessão encerrada". Chamadas com `X-Background-Request` e páginas (`/app`, `/login`, `/static`) não renovam. |
| Autenticação da API | `accounts/auth.py` | `CsrfProtected` (rotas públicas), `SessionAuth` e `AdminAuth` (403 para comum). Todas checam CSRF nas requisições que alteram dados. |
| Login em dois passos | `accounts/login_flow.py`, `accounts/api.py`, `accounts/verification.py` | Cookie `pending_login` assinado (`django.core.signing`, 10 min) que nenhuma rota aceita como sessão; código em HMAC, 10 min, uso único, 5 tentativas, pausa de 30 s, teto de 10 por hora; falha no envio = 503. |
| Limite de tentativas | `core/rate_limit.py` | Copiado do FastAPI (Python puro): 5 erros por (IP, usuário) bloqueiam por 60 s. |
| E-mail | `core/mailer.py` | Copiado: provedor real, ou Mailpit; endereços de mentira sempre ao Mailpit. |
| Acessos registrados | `accounts/events.py` | Resultado e "Chrome · Windows", sem IP; só os 50 mais recentes. |

**Aprendizados desta etapa (para lembrar nas próximas):**
1. **O Ninja não checa CSRF sozinho** e marca as views como isentas; a verificação mora na classe de autenticação. Por isso até as rotas públicas (login) usam `CsrfProtected`. O cookie `csrftoken` é entregue pelas páginas (`GET /login`, `/app`) e o React deve devolvê-lo em `X-CSRFToken` (etapa 10). O Django troca o token ao entrar.
2. **Uma URL do Django não distingue o método HTTP.** `GET /login` (a tela) e `POST /login` (a ação) precisam ser registradas no mesmo roteador do Ninja; em lugares diferentes, o primeiro responde 405 ao outro.
3. **Exceção dentro de `transaction.atomic()` desfaz tudo**, inclusive o contador de tentativas de um código. `check_code` calcula o resultado dentro da transação e levanta o erro depois dela (há teste de regressão).
4. `get_session_auth_hash` do usuário foi fixado: quem derruba sessões por troca de senha é a `session_version` (mantém a mensagem "Sessão encerrada"), não o hash padrão do Django.
5. Senha: hash **PBKDF2** do Django (lento de propósito). Nos testes usa-se um hasher rápido (a suíte caiu de 79 s para 6 s) e há um teste que confere o PBKDF2 real. Senha com mais de 1024 bytes não é verificada (conta como errada).
6. As respostas JSON usam UTF-8 puro (`config/renderers.py`), como o FastAPI.

**Fora desta etapa (propositalmente):** criar o administrador inicial a partir de `ADMIN_USERNAME`/`ADMIN_PASSWORD` (comando de gestão, etapa 6), as rotas protegidas de dados (etapas 6 a 9) e o envio do token CSRF pelo React (etapa 10).

## Usuários, auditoria, conta e notificações (etapa 6)

**Rotas migradas (15 novas; 24 das 49 do contrato no total):** `POST/GET /users`, `GET /users/summary`, `PATCH /users/{id}`, `DELETE /users/{id}?force`, `PUT /users/{id}/password`, `PATCH /users/{id}/email` · `GET /audit-logs`, `GET /audit-logs/actions` · `GET/PUT /me/profile`, `GET /me/logins`, `POST /me/sessions/revoke-others`, `PUT /me/password`, `POST /me/email/request`, `POST /me/email/confirm` · `GET /me/notifications`, `POST /me/notifications/read`.

**Organização:** regras de negócio em serviços (`accounts/services.py`, `accounts/account.py`, `accounts/notifications.py`, `audit/services.py`, `datasets/services.py`) e a camada HTTP em roteadores finos (`accounts/users_api.py`, `accounts/account_api.py`, `audit/api.py`). Cada alteração roda numa transação (`transaction.atomic()`); se algo falha no meio, nada fica pela metade. O administrador inicial é criado pelo comando `python manage.py ensure_admin` (só se não houver usuários), executado pelo Compose ao subir, depois de `migrate`.

**Aprendizados:**
1. `Query[Schema]` com `Field(ge=1, le=100)` reproduz a validação dos parâmetros (422 com a lista de erros, como no FastAPI).
2. `username__icontains` escapa `%` e `_` sozinho: a busca é literal, sem o código manual de escape que existia.
3. Rotas com `{int:user_id}` só casam com números (`/users/abc` dá 404) e `summary` não é confundido com um id.
4. O `Status(204, None)` substitui o retorno em tupla (obsoleto no Ninja).
5. **Armadilha de teste:** `force_login` não grava `start`, `act` e `v` da nossa política de sessão; a sessão é "inicializada" na primeira chamada. O auxiliar `logged_client` grava as anotações como o login de verdade, senão testes de "derrubar a sessão" dão falso negativo.
6. A exclusão forçada apaga os arquivos no MinIO **dentro** da transação do banco: se algo falhar depois, o arquivo já se foi (igual ao FastAPI). Falha do MinIO não trava a exclusão (fica um objeto órfão, com aviso no log).
7. Mudar a senha ou encerrar as outras sessões grava a `session_version` nova **na sessão atual** (`request.session["v"]`), que continua válida; as demais caem.

**Ferramenta de contrato:** `docker compose exec -T django python manage.py shell < backend/scripts/contract_diff.py` compara a API do Django com o contrato congelado (rotas migradas, rotas que faltam, rotas sobrando e campos das respostas). No fim da etapa 6: 24 de 49 migradas, nenhuma sobrando; as duas "diferenças" (`/me`, `/users/summary`) são melhorias (o FastAPI não declarava o formato dessas respostas). Faltam os datasets, a consulta e o painel (etapas 7 e 8), métricas, logs, arquivos e o resumo (etapa 9) e os redirecionamentos das páginas antigas (etapa 10).

## Datasets (etapa 7)

**Rotas migradas (6 novas; 30 das 49 no total):** `POST /datasets/upload`, `GET /datasets`, `DELETE /datasets/{id}`, `POST` e `GET /datasets/{id}/profile`, `GET /datasets/{id}/sample`. Nenhum campo das respostas diverge do contrato do FastAPI.

**Organização:** `datasets/profiling.py` é a cópia do perfilador (Pandas), trocando só de onde vem o cliente do MinIO; `datasets/services.py` tem upload com validação, listagem, exclusão, perfil e amostra; `datasets/api.py` é a camada HTTP. `analytics/runtime.py` (limite de consultas e cache de arquivos) já foi copiado porque a exclusão do dataset libera esse cache; o restante do app `analytics` chega na etapa 8. Comando novo `ensure_bucket` (o FastAPI criava o bucket ao iniciar), chamado pelo Compose depois de `migrate` e `ensure_admin`. Dependências novas: `pandas`, `numpy`, `openpyxl`.

**Aprendizados:**
1. **O tamanho é conferido antes de ler o conteúdo:** o Django sabe o tamanho do arquivo recebido (`file.size`), então acima de 10.000.000 bytes a resposta é 413 sem carregar o arquivo na memória. Atenção: o Django já gravou o corpo da requisição num arquivo temporário antes da rota rodar (o FastAPI também); um limite de tamanho no proxy continua recomendado em produção.
2. O Django limpa o nome do arquivo enviado (fica só o último pedaço: `../../etc/passwd.csv` vira `passwd.csv`), e o nome de armazenamento no MinIO é sempre gerado pelo servidor (`<uuid>.csv`).
3. `Exists()` do ORM calcula o `profiled` da listagem numa consulta só; `bulk_create` devolve os ids no Postgres, então colunas e valores frequentes são gravados em duas consultas, não em uma por linha; apagar o dataset apaga perfil, colunas, valores e dashboard **em cascata** (antes: três `DELETE` manuais).
4. Nos testes, um **MinIO de mentira em memória** substitui o de verdade (testes isolados e rápidos); o código chama `storage.get_minio_client()` pelo módulo, assim um único `monkeypatch` vale em todo lugar. O MinIO real foi validado por `curl`: upload (403 sem CSRF), objeto realmente no bucket com o nome gerado, perfil, amostra e exclusão que remove o objeto.
5. Perfis de dados continuam com os mesmos números (ex.: linha repetida conta em `duplicate_row_count`, mediana 12,5 de `5,10,10,15,20,100`).

## Consultas, dashboards, painel e administração (etapas 8 e 9)

**Rotas migradas (10 novas; 40 das 49):** `POST /datasets/{id}/query`, `GET /datasets/{id}/suggested-dashboard`, `GET/PUT/DELETE /datasets/{id}/dashboard`, `GET /dashboard/summary`, `GET /metrics/system`, `GET /logs/app`, `GET /files`, `GET /files/content`. As 9 restantes do contrato são páginas (etapa 10).

**Reaproveitado quase sem mudança:** o motor de análise (`analytics/engine.py`, `validator.py`, `suggestions.py`, `schemas.py`, `runtime.py`), só com os `import` ajustados. Novos: `analytics/dashboards.py` (ORM), `adminpanel/` (`files.py` com a defesa contra path traversal, `logtail.py`, `summary.py`).

**Consulta (`analytics/api.py`):** o Django não tem `anyio.fail_after`; a consulta roda num `ThreadPoolExecutor` próprio e a resposta espera `future.result(timeout=15)`. A vaga real continua sendo o semáforo de `run_limited` (no máximo 3 simultâneas): quem não consegue vaga em 5 s recebe **503**; quem estoura o prazo recebe **504** e a thread abandonada segue segurando a vaga até acabar. As threads do `ThreadPoolExecutor` não tocam no banco (o dataset e os tipos são lidos antes).

**Estratégia de testes — o aprendizado mais importante:** em vez de reescrever os testes de HTTP do FastAPI, o adaptador `backend/tests/compat.py` (um `TestClient` com a mesma interface, em cima do cliente de teste do Django) os faz rodar **contra o Django, quase sem mudança** (`backend/tests/contract/`). São 85 testes de comportamento (motor de análise com números conferidos à mão, painel sugerido, dashboards salvos, resumo, arquivos, métricas, limites 503/504 e cache) que passaram de primeira ou com ajustes mínimos: é a prova de paridade. Foram deixados de fora os testes que dependem de detalhes internos do FastAPI (`src.core.db`, `src.main`...): o que eles cobriam já tem testes nativos do Django (login, sessão, dois passos, usuários, auditoria, conta, datasets).

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
