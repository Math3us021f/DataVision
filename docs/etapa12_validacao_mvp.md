# Etapa 12 — Validação do MVP e planejamento de deploy

> Estado em 2026-11-02. A parte **local** (revisão de segurança, persistência, testes) está feita. A parte do **servidor Ubuntu** ainda é só planejamento: nada foi inspecionado nem alterado lá. O inventário (somente leitura) está em [inventario_ubuntu.md](inventario_ubuntu.md) e depende de você executá-lo.

## 1. Resultado da validação local

- Testes: 202 de integração (`pytest`) e 13 de interface (Playwright), todos passando.
- Persistência: backup e restauração do Postgres **ensaiados** num banco temporário de dev (`pg_dump -Fc` → `pg_restore`): as 7 tabelas da aplicação voltaram com contagens idênticas (ex.: 1577 usuários, 538 datasets, 4602 registros de auditoria). Backup do MinIO **não foi ensaiado** (ver seção 5).
- Histórico do Git (repositório **público**): varredura sem achar credenciais, `.env` ou os documentos de instalação do servidor — estes últimos estão no `.gitignore` e nunca foram commitados.

## 2. Revisão de segurança

Escopo: autenticação/sessão, autorização, uploads, consulta analítica, logs, headers, configuração. **Não é uma auditoria completa** (sem teste de carga, sem análise de dependências, sem revisão do servidor).

### Corrigido nesta etapa (todos com teste)

| # | Prioridade | Achado (confirmado) | Correção |
|---|---|---|---|
| 1 | Média | `POST /login` com senha > 72 bytes: o bcrypt 5 levanta `ValueError` → **500 para usuário existente e 401 para inexistente**, revelando quais contas existem (e enchendo o log de tracebacks). | `verify_password` recusa > 72 bytes (nenhuma senha cadastrada passa disso). |
| 2 | Baixa | Login de usuário inexistente não executava o bcrypt: resposta bem mais rápida que senha errada de usuário existente (oráculo de tempo). | `burn_password_check` gasta a mesma verificação. |
| 3 | Média | Upload lia o arquivo **inteiro** antes de checar o limite de 10 MB (qualquer usuário logado podia mandar arquivos enormes). | Lê no máximo `limite + 1` byte → 413. (O Starlette ainda grava o corpo em arquivo temporário; um limite de corpo no proxy reverso continua recomendado em produção.) |
| 4 | Baixa | Sem cabeçalhos de segurança. | `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: same-origin` em todas as respostas. |
| 5 | Baixa | `/docs`, `/redoc` e `/openapi.json` públicos (sem login) listam todas as rotas, inclusive as de admin. | Somem com `APP_ENV=production`. |
| 6 | Informativa | Cookie de sessão sem `Secure` e configurado em dois lugares. | `set_session_cookie` único; `SESSION_COOKIE_SECURE=true` liga o `Secure` (usar quando houver HTTPS). |

### Risco residual (não corrigido)

| Prioridade | Risco | Observação / recomendação |
|---|---|---|
| Média | **Sem CSP.** | As páginas têm `<script>` inline (tema, `DATASET_ID`); uma CSP exige nonces. Mitigado por: `textContent` em todo texto de usuário e tooltip do ECharts sem HTML (testado com `<img onerror>` real). |
| Média | **Consulta analítica sem limite de tempo** e relê o arquivo do MinIO a cada requisição; qualquer usuário logado pode sobrecarregar o worker. | Definir timeout, limitar concorrência e/ou cachear o DataFrame; no proxy, limitar taxa. |
| Média | **Rate limit do login em memória**, chave `(ip, usuário)`. Atrás de proxy reverso, o IP seria o do proxy. | Aceitável com 1 processo e sem proxy; se houver proxy, ler `X-Forwarded-For` só de proxy confiável. |
| Baixa | Sem token CSRF explícito. | `SameSite=Lax` + API em JSON cobre o cenário do MVP; revisar se houver login de outros dispositivos. |
| Baixa | `GET /logs/app` lê o arquivo de log inteiro a cada chamada; sem rotação. | Rotacionar logs (`RotatingFileHandler`) e ler só o final. |
| Baixa | Dependências sem versão fixa (`requirements.txt`). | Fixar versões (lock) antes do deploy, para o build ser reproduzível. |
| Baixa | MinIO acessado sem TLS (`secure=False`). | Aceitável se tráfego ficar na mesma máquina/rede isolada; decidir no plano de deploy. |
| Informativa | Sem Alembic: mudanças de schema são `IF NOT EXISTS` no `init_db()`. | Adiado de propósito; reavaliar antes de qualquer migração destrutiva. |

## 3. Divergências entre documentos (para você decidir)

- `CLAUDE.md` diz que os documentos do Ubuntu estão em `D:\VMs\Code\docs`; essa pasta **não existe** — eles estão em `DataVision/docs/` (ignorados pelo Git).
- A documentação do servidor cita **Ubuntu 24.04** em um ponto e **26.04** em outro: confirmar a versão real no inventário.
- `CLAUDE.md` pede inventário do MinIO *existente*; a documentação o descreve com imagem `:latest` (sem digest), usuário **root** do MinIO e portas publicadas em todas as interfaces. O estado real precisa ser confirmado.

## 4. Pontos de atenção da documentação local do servidor (hipóteses a confirmar no inventário)

Os dois documentos de instalação (fora do Git) contêm **credenciais em texto puro** (SSH e usuário root do MinIO), ambas fracas. Se esses valores ainda valem no servidor: trocar **antes** de qualquer deploy, preferir login SSH por chave com `PasswordAuthentication no`, e criar para a aplicação um usuário/bucket próprios no MinIO em vez de usar o root. (Os valores não são reproduzidos aqui; este repositório é público.)

## 5. Plano de deploy — **RASCUNHO, não aprovado**

Nada abaixo deve ser executado antes de: (a) o inventário ser feito e revisado, (b) as decisões da seção 6 serem tomadas, (c) você aprovar explicitamente.

**Pré-requisitos**
1. Inventário somente leitura concluído e revisado.
2. Segredos novos (nunca reaproveitar os de dev nem os atuais do servidor) em arquivo `.env` no servidor com `chmod 600`.
3. `compose.prod.yaml` separado do de dev: **sem** `--reload`, **sem** bind mounts de código, `APP_ENV=production`, versões de imagem fixas (digest), e portas publicadas **só** na interface necessária (nunca `0.0.0.0` sem decisão explícita). Postgres sem porta publicada.
4. MinIO: **não alterar o container existente**. Criar bucket e usuário de serviço novos (política só nesse bucket); testar a conectividade container→MinIO do host antes.
5. Dependências fixadas (lock) e imagem construída e testada localmente.

**Reversão (preparar antes de começar)**
- Como o servidor é uma VM VirtualBox: **snapshot da VM** imediatamente antes (`VBoxManage snapshot "<vm>" take pre-deploy-datavision`) — reversão completa e rápida.
- `pg_dump -Fc` do banco antes de qualquer migração (procedimento ensaiado na seção 1).
- Reverter a aplicação = `docker compose -f compose.prod.yaml down` **sem** `-v` e voltar à tag de imagem anterior; o MinIO e seus dados não são tocados.

**Verificação pós-deploy**: `GET /health`, login, upload de CSV pequeno, perfil, dashboard, e conferência de que `/docs` responde 404 e de que as portas abertas (`ss -tlnp`) são só as planejadas.

**Backup do MinIO (a ensaiar)**: cópia do diretório de dados com o container parado, ou `mc mirror` do bucket da aplicação para outro destino. Ainda não testado.

## 6. Decisões que precisam de você

1. **HTTPS**: o painel será acessado só por esta máquina (host-only) ou por outros dispositivos da LAN? O `CLAUDE.md` pede avaliar HTTPS antes de login a partir de outros dispositivos.
2. **Como a aplicação alcança o MinIO existente** (IP do host? rede Docker própria?) e se aceita-se criar bucket/usuário novos nele.
3. **Retenção de backup** (quantos, onde, com que frequência).
4. Confirmar a versão do Ubuntu (24.04 × 26.04).
