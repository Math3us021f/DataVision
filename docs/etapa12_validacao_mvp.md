# Etapa 12 — Validação do MVP e planejamento de deploy

> Estado em 2026-11-02. A parte **local** (revisão de segurança, persistência, testes) está feita e o **inventário somente leitura do servidor foi executado** (resultados na seção 3.1; roteiro em [inventario_ubuntu.md](inventario_ubuntu.md)). Nada foi alterado no servidor. O plano de deploy (seção 5) continua em rascunho, **não aprovado**.

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
| 7 | Média | **Sem CSP** (2026-11-02). As páginas antigas tinham `<script>` inline; com a interface toda em React sobrou um só (o tema). | O tema virou arquivo externo (`theme-init.js`) e toda resposta (exceto `/docs`, que só existe em desenvolvimento) leva `Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'`. Testado: nenhuma tela viola a política, e um script injetado na página é bloqueado pelo navegador. `'unsafe-inline'` só em estilo (o React usa o atributo `style`). |
| 8 | Média | **Consulta analítica sem limite** (2026-11-02): relia o arquivo do MinIO a cada requisição e qualquer usuário logado podia ocupar o servidor. | No máximo 3 consultas ao mesmo tempo (espera 5 s por uma vaga, senão **503**); a resposta tem prazo de 15 s (**504**); a thread que estourou o prazo não pode ser interrompida, mas segura a vaga até terminar, então o limite nunca é ultrapassado; cache dos 3 últimos arquivos lidos (chave = `object_key`, único e imutável), liberado ao apagar o dataset. |
| 9 | Baixa | **Log sem rotação e lido inteiro** (2026-11-02). | `RotatingFileHandler` (5 MB × 5 arquivos) e `GET /logs/app` lê só o final do arquivo, de trás para frente. |
| 10 | Baixa | **Dependências sem versão fixa** (2026-11-02). | `requirements.txt` com versões exatas + `constraints.txt` com **todas** as versões da imagem validada (diretas e indiretas); o `Dockerfile` instala com `-c constraints.txt`. Conferido: uma imagem construída do zero ficou com pacotes idênticos ao `constraints.txt` (e sem `jinja2`). |

| 11 | Média | **Sessão de 8 h sem expirar por inatividade** (2026-11-02, pedido do usuário): um computador deixado logado ficava aberto o dia todo. | Prazo de **15 min sem atividade**, contado no servidor (cookie reassinado a cada requisição da pessoa; chamadas automáticas não renovam); limite absoluto de 8 h mantido; aviso com confirmação aos 14 min e desconexão se não confirmar. Detalhes em `docs/escopo_e_roteiro.md`. |

| 12 | Média | **Login só com senha** (2026-11-02, pedido do usuário): senha vazada = conta tomada. | Verificação em dois passos por e-mail para quem tem e-mail cadastrado (código de 6 dígitos em HMAC, 10 min, uso único, 5 tentativas, reenvio com pausa e teto por hora; sem sessão antes do código; falha de envio bloqueia o login). Troca do próprio e-mail exige senha atual + código ao endereço novo; o admin pode alterar sem confirmação (auditado e notificado no sistema). Detalhes em `docs/escopo_e_roteiro.md`. **Para o servidor:** o SMTP precisa funcionar (variáveis `SMTP_*` em `.env.prod`, saída na porta 587/465) — sem ele, contas com e-mail não entram; a conta de envio deve ser dedicada ao sistema, com senha de aplicativo. |

### Risco residual (não corrigido)

| Prioridade | Risco | Observação / recomendação |
|---|---|---|
| Média | **Rate limit do login em memória**, chave `(ip, usuário)`. Atrás de proxy reverso, o IP seria o do proxy. | Aceitável com 1 processo e sem proxy; se houver proxy, ler `X-Forwarded-For` só de proxy confiável. O `compose.prod.yaml` não define `--workers`, então roda 1 processo (necessário por isso). |
| Baixa | Sem token CSRF explícito. | `SameSite=Lax` + API em JSON cobre o cenário do MVP; revisar se houver login de outros dispositivos. |
| Baixa | MinIO acessado sem TLS (`secure=False`, fixo no código). | Aceitável se tráfego ficar na mesma máquina/rede isolada (a aplicação alcança o MinIO por `host.docker.internal`); decidir no plano de deploy. |
| Baixa | Limites das consultas são valores fixos no código (`services/analytics/runtime.py`), calibrados por estimativa, sem teste de carga. | Medir no servidor real antes de ajustar. |
| Informativa | Sem Alembic: mudanças de schema são `IF NOT EXISTS` no `init_db()`. | Adiado de propósito; reavaliar antes de qualquer migração destrutiva. |

## 3. Divergências entre documentos (para você decidir)

- `CLAUDE.md` diz que os documentos do Ubuntu estão em `D:\VMs\Code\docs`; essa pasta **não existe** — eles estão em `DataVision/docs/` (ignorados pelo Git).
- A documentação do servidor cita **Ubuntu 24.04** em um ponto e **26.04** em outro. **Resolvido pelo inventário: o servidor é Ubuntu 26.04.1 LTS** (kernel 7.0). O `CLAUDE.md` ainda diz 24.04 e precisa ser corrigido.
- `CLAUDE.md` pede inventário do MinIO *existente*: ver seção 3.1 (confirmado: imagem `:latest`, portas em todas as interfaces).

## 3.1 Resultado do inventário somente leitura (2026-11-02)

| Item | Observado | Avaliação |
|---|---|---|
| Sistema | Ubuntu 26.04.1 LTS, relógio sincronizado (UTC), `unattended-upgrades` ativo, nenhuma atualização pendente | OK |
| Recursos da VM | 2 vCPU, 3072 MB configurados (2,6 GiB visíveis, ~2,1 GiB livres), **sem swap**; disco 147 GB com 133 GB livres | **Memória apertada** para app + Postgres + MinIO + consultas Pandas: sem swap, um pico vira OOM-kill |
| Portas em escuta | só `22` (SSH), `9000` e `9001` (MinIO), todas em `0.0.0.0` e `[::]` | MinIO exposto em todas as interfaces da VM |
| Firewall (UFW) | **inativo** | Sem barreira local; hoje o isolamento vem só da topologia de rede |
| Rede da VM | adaptador host-only (comunicação com o Windows) + NAT, **sem regras de redirecionamento de porta** no NAT; 3º a 8º adaptadores desligados | Bom: nada do servidor é alcançável de fora da máquina física |
| SSH | nenhuma diretiva em `sshd_config`/`sshd_config.d` (valores padrão) | Provável login por senha ativo (padrão); **confirmar** com `sudo sshd -T` |
| Docker | 29.9.2, daemon em modo normal (não rootless), só `daemon.json` com DNS, **nenhum volume nomeado**, só a rede padrão | OK |
| MinIO | imagem `cgr.dev/chainguard/minio:latest` (sem tag fixa; digest atual anotado abaixo), versão 2026-09-22, usuário **65532 (não root)**, sem `privileged`, `restart=always`, dados em bind mount no home, saúde OK, log sem segredos | Imagem sem versão fixa; resto bom |
| Dados no MinIO | diretório com **~104 KB** (só metadados internos do MinIO) | **Não há dados reais a preservar** — risco de convivência é baixo |
| Backups / agendamentos | **sem `crontab`**, nenhum timer de backup (só os do sistema) | Não há backup nenhum hoje |
| Snapshots da VM | **nenhum** | Precisa existir um antes do deploy (reversão) |

Digest da imagem do MinIO em uso: `sha256:d88920d6a50bd0b088223b688be3b76c63e6205dbe494437f67ba1240ea12880`.

**Consequências para o plano:** (1) como o MinIO existente está praticamente vazio, a opção mais simples e segura é manter o container como está e criar *bucket e usuário novos* para a aplicação; (2) a memória é o gargalo real — aumentar a VM para 4 GB e/ou criar swap, e definir limites de memória nos containers; (3) ativar o UFW é uma mudança de risco (pode trancar o SSH) e só deve ser feita com regra de SSH liberada antes e com aprovação; (4) criar o snapshot e o primeiro backup antes de qualquer mudança.

## 4. Pontos de atenção da documentação local do servidor (hipóteses a confirmar no inventário)

Os dois documentos de instalação (fora do Git) contêm **credenciais em texto puro** (SSH e usuário root do MinIO), ambas fracas. Se esses valores ainda valem no servidor: trocar **antes** de qualquer deploy, preferir login SSH por chave com `PasswordAuthentication no`, e criar para a aplicação um usuário/bucket próprios no MinIO em vez de usar o root. (Os valores não são reproduzidos aqui; este repositório é público.)

## 5. Plano de deploy — **RASCUNHO, não aprovado**

Nada abaixo deve ser executado antes de: (a) o inventário ser feito e revisado, (b) as decisões da seção 6 serem tomadas, (c) você aprovar explicitamente.

**Rascunho já escrito no repositório (2026-11-02): [`compose.prod.yaml`](../compose.prod.yaml) e [`.env.prod.example`](../.env.prod.example).** Contém: imagem com tag de versão (`APP_VERSION`), sem `--reload` nem montagem de código, `APP_ENV=production`, sistema de arquivos somente leitura (`read_only` + `/tmp` em memória), `cap_drop: ALL`, `no-new-privileges`, limites (app 1 GB / 1,5 CPU; Postgres 768 MB), reinício automático, verificação de saúde, logs do Docker com rotação, Postgres fixado pelo digest da imagem testada e **sem porta publicada**, aplicação escutando só em `127.0.0.1` por padrão (`APP_BIND_ADDRESS` para mudar), MinIO existente alcançado por `host.docker.internal` (o MinIO **não** está no arquivo).

**Atualização (2026-11-02, backend agora em Django):** o `compose.prod.yaml` usa `target: production` do `Dockerfile` (imagem completa: Django, interface gerada, estáticos coletados, gunicorn com 1 processo e 8 threads, usuário `app`). Ao subir, o contêiner aplica as migrações, cria o administrador inicial a partir de `ADMIN_USERNAME`/`ADMIN_PASSWORD` (só se não houver usuários) e garante o bucket do MinIO. Novidades de configuração: `ALLOWED_HOSTS` (obrigatório: os endereços pelos quais a aplicação é acessada, ex. o IP da VM na rede host-only), `DJANGO_DATABASE_URL` (monta o `POSTGRES_DB`) e `LOG_DIR`. O banco novo de produção nasce vazio pelas migrações (não há dados a migrar). Com HTTPS, ligar `SESSION_COOKIE_SECURE=true` também liga o cabeçalho `Cross-Origin-Opener-Policy`. **O ensaio abaixo foi refeito com a imagem Django** e achou (e corrigiu) dois erros reais: o arquivo de log criado como root no build (o contêiner reiniciava em ciclo) e o socket de controle do gunicorn em diretório somente leitura; depois disso: aplicação e banco `healthy`, `/docs` e `/openapi.json` 404, CSP presente, código somente leitura, estáticos servidos, banco sem porta publicada, e login, upload (MinIO real), perfil, consulta, painel sugerido, logs, métricas, exclusão e logout funcionando (logout sem token CSRF: 403). A pilha de ensaio e o bucket de teste foram removidos.

**Ensaio local feito antes (com a imagem FastAPI, sem tocar no servidor):** o arquivo foi subido numa pilha isolada (projeto `datavision-prod`, porta 18000, segredos aleatórios, bucket de teste no MinIO de dev). Resultado: aplicação e banco `healthy`; `/health` e `/login` 200; `/docs` e `/openapi.json` **404**; cabeçalhos de segurança e CSP presentes; o banco aparece só como `5432/tcp` (nada publicado); o processo roda como `app` e **não consegue gravar** em `/app/src` (somente leitura); o volume de logs é gravável; login, upload, perfil e consulta (`SP=30, RJ=5`) funcionaram contra o MinIO via `host.docker.internal`; uso de memória ~84 MB (app) e ~37 MB (banco). Tudo isso foi removido depois (contêineres, volumes, imagem e bucket de teste). **Não foi testado:** o MinIO *do servidor* (só o de dev), HTTPS, backup do MinIO, e o comportamento com a VM de 4 GB sob carga.

**Pré-requisitos**
1. Inventário somente leitura concluído e revisado.
2. Segredos novos (nunca reaproveitar os de dev nem os atuais do servidor) em arquivo `.env` no servidor com `chmod 600`.
3. `compose.prod.yaml` separado do de dev: **sem** `--reload`, **sem** bind mounts de código, `APP_ENV=production`, versões de imagem fixas (digest), e portas publicadas **só** na interface necessária (nunca `0.0.0.0` sem decisão explícita). Postgres sem porta publicada.
4. MinIO: **não alterar o container existente**. Criar bucket e usuário de serviço novos (política só nesse bucket); testar a conectividade container→MinIO do host antes.
5. ~~Dependências fixadas (lock) e imagem construída e testada localmente.~~ **Feito** (`constraints.txt`; imagem do zero idêntica ao lock; ensaio acima). Para atualizar uma dependência: suba a imagem, rode os testes, regenere o `constraints.txt` (`docker compose exec -T app pip list --format=freeze`, sem `pip`/`setuptools`/`wheel`) e confira com um build limpo.

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
4. Corrigir o `CLAUDE.md` (Ubuntu 26.04 em vez de 24.04, e o caminho dos documentos do servidor)? É um arquivo de regras seu, então só altero com seu OK.
5. ~~Memória da VM: aumentar de 3 GB para 4 GB~~ — **feito em 2026-11-02 com sua aprovação** (ver seção 7). Ainda em aberto: criar swap dentro do Ubuntu?
6. Ativar o firewall (UFW) no servidor, liberando antes o SSH só para a rede host-only? (Mudança no servidor: só com sua aprovação e no momento do deploy.)

7. **E-mail de envio (login em dois passos):** conta dedicada criada pelo usuário (Gmail, com senha de aplicativo), a ser usada só no `.env.prod`. A VM precisa alcançar o SMTP do provedor (porta 587) — conferir no deploy. Plano B se o Gmail não servir: um serviço de envio com SMTP próprio (ex.: Brevo). Ainda **não** testado com envio real.

## 7. Alterações já feitas na VM (com aprovação explícita)

Única mudança feita até aqui, em 2026-11-02, na **configuração da VM** (nada dentro do Ubuntu foi alterado):

1. Desligamento limpo pelo botão ACPI (20 s, sem forçar).
2. **Snapshot `base-limpa-antes-do-deploy`**, com a VM desligada: estado limpo (só o MinIO) e 3 GB de RAM. É o ponto de retorno para o deploy e para esta própria mudança.
3. Memória aumentada de 3072 para **4096 MB** (`VBoxManage modifyvm --memory 4096`); 2 vCPU mantidas.
4. VM religada em modo headless. Verificado: SSH respondendo e MinIO saudável (HTTP 200) cerca de 80 s após o boot, sem nenhuma intervenção — `restart=always` e o Docker habilitado no boot funcionam.

**Reverter esta mudança:** desligar a VM e restaurar o snapshot (`VBoxManage snapshot "<vm>" restore base-limpa-antes-do-deploy`), ou só voltar a memória com `VBoxManage modifyvm "<vm>" --memory 3072`.

**Atenção no Windows:** a máquina tem ~16 GB e estava com ~2,3 GB livres antes do aumento; o Docker Desktop (WSL2) também consome bastante. Se o Windows ficar lento com a VM, o ganho de memória do servidor não compensa — nesse caso reduzir o WSL2 ou usar swap no Ubuntu em vez de mais RAM.
