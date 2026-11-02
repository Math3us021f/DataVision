# Testes manuais da API

> Exemplos de `curl` para testar cada endpoint à mão, fora do `pytest`. Útil para explorar a API, depurar algo específico ou simplesmente ver a resposta real.
>
> Pré-requisito: a aplicação precisa estar de pé (`docker compose up -d`). Rode os comandos de um terminal com `curl` disponível (no Windows, o PowerShell já traz um `curl` compatível com os exemplos abaixo; se preferir, use Git Bash).
>
> Credenciais do admin: estão no seu `.env` local (`ADMIN_USERNAME` / `ADMIN_PASSWORD`). Não estão reproduzidas aqui de propósito.
>
> **Nota:** o `pytest` roda contra o mesmo banco de desenvolvimento (não há banco de testes separado ainda), então rodar a suíte repetidamente vai deixando usuários de teste (`user_xxxxxxxx`) acumulados na tabela `users`. Isso é inofensivo, mas se quiser limpar: `docker compose exec db psql -U datavision_app -d datavision -c "DELETE FROM users WHERE username LIKE 'user_%';"` (cuidado: isso é uma exclusão real, confirme antes de rodar).

## Health check

```bash
curl -s http://localhost:8000/health
```

Esperado: `{"status":"ok","application":"DataVision"}`

## Login

```bash
curl -s -i -c cookies.txt -X POST http://localhost:8000/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"SUA_SENHA_AQUI"}'
```

- `-c cookies.txt` salva o cookie de sessão recebido num arquivo, para reaproveitar nos próximos comandos.
- Esperado: `200 OK`, com um `set-cookie: session=...` no cabeçalho.
- Senha errada ou usuário inexistente → `401` (mesma mensagem genérica nos dois casos, de propósito — não revela se a conta existe).

## Ver o próprio usuário (`/me`)

```bash
curl -s -b cookies.txt http://localhost:8000/me
```

- `-b cookies.txt` reenvia o cookie salvo no login.
- Esperado: `{"username":"admin","is_admin":true}`.
- Sem `-b cookies.txt` (ou com cookie inválido/expirado) → `401`.

## Logout

```bash
curl -s -i -b cookies.txt -c cookies.txt -X POST http://localhost:8000/logout
```

Depois disso, repetir o comando do `/me` deve voltar a dar `401`.

## Criar usuário (só admin)

```bash
curl -s -i -b cookies.txt -X POST http://localhost:8000/users \
  -H "Content-Type: application/json" \
  -d '{"username":"novo_usuario","password":"senha-de-teste","is_admin":false}'
```

- Esperado: `201`, com o usuário criado (sem a senha/hash na resposta).
- Username repetido → `409`.
- Sem estar logado como admin → `403` (logado, mas não-admin) ou `401` (nem logado).

## Listar usuários (só admin)

```bash
curl -s -b cookies.txt "http://localhost:8000/users?search=admin&status=active&page=1&page_size=20"
```

- Resposta: `{"items": [...], "total": N, "page": 1, "page_size": 20}`.
- `status`: `all`, `active` ou `inactive`. `page_size` acima de 100 → `422`.

## Excluir usuário (só admin)

```bash
curl -s -i -b cookies.txt -X DELETE http://localhost:8000/users/ID_DO_USUARIO
```

- Esperado: `204`. A própria conta → `400`. Usuário com datasets → `409`. Inexistente → `404`.
- A exclusão fica registrada em `audit_logs` (`delete_user`, com id e nome em `details`).
- Na tela: marque usuários pelas caixas de seleção para ativar, desativar ou excluir em lote.

## Excluir usuário com datasets, forçando (só admin)

```bash
curl -s -i -b cookies.txt -X DELETE "http://localhost:8000/users/ID_DO_USUARIO?force=true"
```

- Apaga os datasets do usuário (arquivo no MinIO incluído) e depois a conta. **Irreversível.**
- Na tela: o botão "Excluir" do menu "⋯" pede duas confirmações quando o usuário tem datasets — a segunda é explícita sobre apagar tudo.
- **Em lote:** selecione vários usuários (alguns com dataset, outros não) e clique em "Excluir" na barra de ações. Quem não tem dataset é excluído na hora; para quem tem, aparece uma segunda confirmação oferecendo forçar só esses.

## Excluir um dataset

```bash
curl -s -i -b cookies.txt -X DELETE http://localhost:8000/datasets/ID_DO_DATASET
```

- Esperado: `204`. Apaga o arquivo no MinIO, o perfilamento e o registro. Dataset de outro usuário ou inexistente → `404`.

## Redefinir senha de outro usuário (só admin)

```bash
curl -s -i -b cookies.txt -X PUT http://localhost:8000/users/2/password \
  -H "Content-Type: application/json" -d '{"new_password":"nova-senha-123"}'
```

- Esperado: `204`. Sessões abertas desse usuário deixam de valer. Senha com menos de 8 caracteres → `400`.

## Trocar a própria senha

```bash
curl -s -i -b cookies.txt -c cookies.txt -X PUT http://localhost:8000/me/password \
  -H "Content-Type: application/json" -d '{"current_password":"SENHA_ATUAL","new_password":"NOVA_SENHA"}'
```

- Esperado: `204` e um cookie novo (`-c cookies.txt` guarda). Senha atual errada → `400`. Outras sessões do mesmo usuário passam a receber `401`.

## Ativar/desativar usuário (só admin)

```bash
curl -s -i -b cookies.txt -X PATCH http://localhost:8000/users/2 \
  -H "Content-Type: application/json" \
  -d '{"is_active": false}'
```

- Troque `2` pelo `id` real do usuário (veja na listagem acima).
- Depois de desativar, tente logar com esse usuário: deve dar `401`.
- Tentar desativar a própria conta do admin logado → `400`.

## Métricas do sistema (só admin)

```bash
curl -s -b cookies.txt http://localhost:8000/metrics/system
```

Esperado: JSON com `cpu_percent`, `memory`, `disk`, `network` e o campo `aviso_escopo` explicando a limitação de container vs host.

## Rate limiting no login

```bash
for i in 1 2 3 4 5; do
  curl -s -o /dev/null -w "%{http_code} " -X POST http://localhost:8000/login \
    -H "Content-Type: application/json" -d '{"username":"admin","password":"senha-errada"}'
done
echo
# A 6a tentativa, mesmo com a senha CERTA, deve dar 429:
curl -s -i -X POST http://localhost:8000/login -H "Content-Type: application/json" -d '{"username":"admin","password":"SUA_SENHA_AQUI"}' | head -1
```

- 5 tentativas erradas seguidas (mesmo IP + mesmo username) → a próxima tentativa, por 60 segundos, retorna `429` independente da senha estar certa.
- Login bem-sucedido reseta o contador.
- **Limitação conhecida:** o contador é em memória, no processo da aplicação — reinicia se o container reiniciar, e não seria compartilhado se a aplicação rodasse em múltiplas réplicas (não é o caso hoje).

## Explorador de arquivos (só admin, só leitura)

```bash
# Listar a raiz de data/
curl -s -b cookies.txt "http://localhost:8000/files"

# Listar uma subpasta
curl -s -b cookies.txt "http://localhost:8000/files?path=subpasta"

# Ler um arquivo permitido (.csv, .txt, .json)
curl -s -b cookies.txt "http://localhost:8000/files/content?path=exemplo.csv"
```

- Extensão fora da allowlist (ex: `.env`) → `403`.
- Tentativa de path traversal (`../../etc`, caminho absoluto `/etc`, symlink apontando pra fora) → `400`, nunca revela conteúdo de fora de `data/`.
- Arquivo inexistente → `404`.
- Sem ser admin → `403` (não-admin) ou `401` (anônimo).
- `data/` é a única pasta acessível — não existe parâmetro para apontar pra outro lugar do sistema.

## Logs da aplicação (só admin)

```bash
curl -s -b cookies.txt "http://localhost:8000/logs/app?limit=20"
```

- Esperado: `{"lines": [...]}` com as últimas linhas do log (padrão 20, máximo 1000).
- Caminho do arquivo é fixo no código (`logs/app.log`) — não existe parâmetro de caminho, então não há risco de path traversal aqui.
- Sem estar logado → `401`. Logado mas não-admin → `403`.
- Eventos registrados hoje: aplicação iniciada, login bem-sucedido/falho/negado (conta inativa), criação de usuário, ativação/desativação de usuário.

## Consulta analítica para dashboards (dono do dataset)

Pré-requisito: o dataset precisa estar perfilado (`POST /datasets/{id}/profile`).

```bash
curl -s -b cookies.txt -X POST http://localhost:8000/datasets/1/query \
  -H "Content-Type: application/json" \
  -d '{"chart":"bar","dimension":{"column":"cidade"},"metrics":[{"column":"valor","agg":"sum"}]}'
```

- Esperado: `{"categories":["MG","SP","RJ"],"series":[{"name":"Soma de valor","data":[100.0,30.0,20.0]}],"total_rows_matched":5,"truncated":false}` (para um CSV com cidades SP/RJ/MG e valores 10, 20, 5, 15, 100).
- `chart`: `bar`, `line`, `pie` ou `kpi` (kpi não tem `dimension` e tem 1 métrica). `agg`: `sum`, `mean`, `count`, `min`, `max`, `count_distinct`. `time_grain` (`day`/`month`/`year`) só em coluna de data. Filtros: `{"column","op","value"}` com `op` em `eq`, `ne`, `gt`, `gte`, `lt`, `lte`, `in` (valor é lista), `contains`.
- `limit` (1–50, padrão 20) corta as categorias; `truncated: true` avisa que havia mais.
- Dataset sem perfil → `409`. Coluna inexistente ou agregação incompatível (ex: `sum` em texto) → `422` com a explicação. Chave desconhecida no JSON → `422`. Dataset de outro usuário → `404`. Sem login → `401`.
- Colunas de data só são reconhecidas em datasets **perfilados depois** desta mudança — reperfile datasets antigos. Formato `dd/mm/aaaa` é lido com dia primeiro; `aaaa-mm-dd` é lido como ISO.

## Minha conta (perfil, acessos e sessões)

```bash
curl -s -b cookies.txt http://localhost:8000/me/profile
curl -s -b cookies.txt -X PUT http://localhost:8000/me/profile   -H "Content-Type: application/json"   -d '{"display_name":"Maria Souza","avatar_color":"violet"}'
curl -s -b cookies.txt http://localhost:8000/me/logins
curl -s -b cookies.txt -c cookies.txt -X POST http://localhost:8000/me/sessions/revoke-others -w "%{http_code}
"
```

- `PUT /me/profile` substitui nome e cor de uma vez; enviar `null`/vazio limpa. Nome: até 60 caracteres, sem caracteres de controle. Cor: `orange`, `green`, `blue`, `violet`, `rose`, `amber`, `teal` ou `slate` (outra → `422`; chave desconhecida, ex. `is_admin` → `422`).
- `GET /me/profile` traz também `member_since` e `usage` (datasets, espaço, perfilados, dashboards salvos).
- `GET /me/logins`: últimos 20 acessos da própria conta, do mais novo para o mais antigo — só `success`, `browser` (resumo, ex. "Chrome · Windows") e `created_at`. **Não existe IP.**
- `revoke-others` responde `204`: as outras sessões passam a receber `401`; a atual continua válida (use `-c cookies.txt` para guardar o cookie novo). Fica na auditoria como `revoke_other_sessions`.
- Sem login → `401` em todos. Na interface: `http://localhost:8000/app/account`.

## Dashboard salvo (dono do dataset)

```bash
# salvar (substitui o anterior)
curl -s -b cookies.txt -X PUT http://localhost:8000/datasets/1/dashboard \
  -H "Content-Type: application/json" \
  -d '{"widgets":[{"chart":"kpi","metrics":[{"column":"valor","agg":"mean"}]}],"filters":[{"column":"valor","op":"gte","value":10}]}'

curl -s -b cookies.txt http://localhost:8000/datasets/1/dashboard          # ler (null se não houver)
curl -s -b cookies.txt -X DELETE http://localhost:8000/datasets/1/dashboard -w "%{http_code}\n"   # 204
```

- `PUT` devolve o que foi salvo mais `updated_at`. Cada widget é uma spec do `/query`; os `filters` valem para todos eles.
- Coluna inexistente, agregação incompatível ou filtro inválido → `422` e **nada é gravado**. Dataset sem perfil → `409`. Mais de 12 widgets ou chave desconhecida → `422`. Dataset de outro usuário → `404`. Sem login → `401`.
- Apagar o dataset apaga o dashboard salvo junto.

## Painel padrão sugerido (dono do dataset)

```bash
curl -s -b cookies.txt http://localhost:8000/datasets/1/suggested-dashboard
```

- Esperado (CSV com data/cidade/valor): lista de widgets `{"title", "spec"}` — aqui, `Soma de valor` (kpi), `Soma de valor por dia` (line) e `Soma de valor por cidade` (pie). Cada `spec` pode ser enviado como está para `POST /datasets/{id}/query`.
- Regras (determinísticas, sobre o perfil salvo): até 3 KPIs de soma das colunas numéricas (ignora identificadores: nome com `id`/`cod`/`codigo`, ou inteiro único sem nulos em tabelas com 20+ linhas); 1 gráfico de linha pela primeira coluna de data (por dia se há até 31 datas distintas, senão por mês); até 3 gráficos por coluna de texto com 2–50 valores distintos (pizza até 5, barras acima). Sem coluna numérica, usa contagem.
- Dataset sem perfil → `409`. Dataset de outro usuário → `404`. Sem login → `401`.

## Auditoria (só admin)

```bash
curl -s -b cookies.txt "http://localhost:8000/audit-logs?search=admin&page_size=2"
```

- Esperado: `{"items": [...], "total": N, "page": 1, "page_size": 2}`, cada item com `action`, `details`, `created_at`, `actor_username` (quem fez) e `target_username` (quem sofreu a ação) — qualquer um dos dois pode vir `null` se o usuário correspondente já foi excluído.
- `search` busca tanto em `actor_username` quanto em `target_username` (ILIKE, com `%`/`_` escapados). `action` filtra por uma ação exata (ver lista em `GET /audit-logs/actions`). `page`/`page_size` paginam (`page_size` máx. 100).
- Sem estar logado → `401`. Logado mas não-admin → `403`.
- Eventos registrados hoje: `create_user`, `activate_user`, `deactivate_user`, `delete_user`, `force_delete_user_datasets`, `reset_password`, `change_own_password`. Eventos de login (sucesso/falha) ficam no log da aplicação (`GET /logs/app`), não aqui — esta tabela é só para ações administrativas sobre contas.

## Upload de datasets (qualquer usuário logado, não só admin)

```bash
# Enviar um arquivo
curl -s -b cookies.txt -X POST http://localhost:8000/datasets/upload -F "file=@caminho/para/arquivo.csv"

# Listar só os meus uploads
curl -s -b cookies.txt http://localhost:8000/datasets
```

- Formatos aceitos: `.csv`, `.xlsx`. Outra extensão → `403`.
- O conteúdo precisa bater com a extensão (ex: um `.xlsx` precisa começar com a assinatura real de ZIP) → senão `400`, mesmo que a extensão esteja certa.
- Acima de 10 MB → `413`.
- Sem login → `401`. Cada usuário só vê os próprios datasets na listagem.
- O arquivo é salvo no MinIO com um nome gerado pelo servidor (UUID), nunca o nome original — evita colisões e qualquer truque com o nome do arquivo.
- Console web do MinIO (dev): `http://localhost:9001`, login com `MINIO_ROOT_USER`/`MINIO_ROOT_PASSWORD` do seu `.env`.

## Perfilamento de datasets

```bash
# Depois de ter o id de um dataset (resposta do upload ou de GET /datasets)
curl -s -X POST -b cookies.txt "http://localhost:8000/datasets/ID_DO_DATASET/profile"

# Consultar o resultado já calculado, sem reprocessar
curl -s -b cookies.txt "http://localhost:8000/datasets/ID_DO_DATASET/profile"
```

- Resposta: `row_count`, `duplicate_row_count` e, por coluna, `inferred_type` (`text`/`integer`/`float`/`boolean`/`datetime`), `null_count`, `distinct_count`.
- Perfilar de novo substitui o resultado anterior, não duplica.
- Dataset de outro usuário ou inexistente → `404` (mesma resposta nos dois casos, não revela se existe).
- `GET` antes de qualquer `POST` → `404` ("ainda não foi perfilado").

## Interface web (navegador)

- `http://localhost:8000/login` — tela de login. Senha errada mostra a mensagem de erro na própria tela.
- `http://localhost:8000/` — home com painel de resumo. Sem sessão, redireciona para o login. Admin vê cartões de usuários/CPU/memória e a atividade administrativa; usuário comum vê só os próprios datasets.
- `GET /dashboard/summary` — confira que a resposta para um usuário comum (`curl -s -b cookies.txt http://localhost:8000/dashboard/summary`) não tem a chave `"admin"` em nenhuma hipótese.
- `http://localhost:8000/meus-datasets/{id}/dashboard` — dashboard do dataset (também acessível pelo botão "Dashboard" em cada linha de `/meus-datasets`; o dataset precisa estar **perfilado**). Deve mostrar KPIs e gráficos gerados automaticamente. Teste: abrir "Personalizar" num gráfico e trocar tipo/coluna/agregação; adicionar um filtro global e ver todos os números mudarem. Dataset de outro usuário ou sem perfil mostra mensagem de erro em vez de gráficos. "Salvar dashboard" guarda gráficos e filtros; ao recarregar, a tela mostra "Dashboard salvo em …". "Restaurar painel padrão" apaga o salvo.
- `http://localhost:8000/app` — **nova interface (React), Home.** Sem sessão, redireciona ao login. Confira: indicadores com contagem animada, gráfico de uploads e donut de status, listas com horário relativo ("há 5 minutos"), botão de recolher o menu (a escolha fica salva), botão de tema (vale também nas páginas atuais), e que a página não rola em tela cheia. Se aparecer "Nova interface ainda não gerada", rode `docker compose --profile frontend run --rm frontend`.
- `http://localhost:8000/app/datasets` — **Datasets na nova interface (React).** Teste: arrastar um `.csv` (a fila mostra o progresso e aparece um aviso), tentar um `.png` e um arquivo > 10 MB (recusados na hora), buscar pelo nome, abrir "Perfil" de um dataset (números, amostra e gráficos por coluna; em um pendente, "Calcular perfil"), excluir (pede confirmação). Compare com `/meus-datasets` (versão atual).
- `http://localhost:8000/admin/users` — gestão de usuários (só admin). Usuário comum é redirecionado para a home.
- `http://localhost:8000/admin/metrics` — métricas (só admin). O horário "Atualizado às" deve mudar a cada ~5 segundos com a aba aberta.
- `http://localhost:8000/admin/files` — explorador de arquivos (só admin). Clique numa pasta para entrar, use o breadcrumb para voltar. Abrir `exemplo.env` deve mostrar "Tipo de arquivo não permitido".
- `http://localhost:8000/admin/logs` — logs (só admin). Teste de XSS via log: tente logar (sem sucesso) com o usuário `<img src=x onerror=alert(1)>`; na página de logs ele deve aparecer como texto, sem disparar alerta.
- Teste de XSS: crie pela tela um usuário chamado `<img src=x onerror=alert(1)>`. Ele deve aparecer na tabela como texto, sem disparar alerta.

- `http://localhost:8000/meus-datasets` — enviar e perfilar datasets (todo usuário logado, não só admin). Arraste um `.csv` ou clique na área para escolher; a barra de progresso deve avançar durante o envio. Clique em "Perfil" num dataset recém-enviado: deve mostrar "Ainda não perfilado" com o botão "Calcular perfil", e a "Amostra dos dados" (primeiras linhas) deve aparecer mesmo antes de calcular o perfil.
- Após calcular o perfil: colunas numéricas mostram Mín./Máx./Média/Mediana e um histograma (gráfico de barras real, via Chart.js); colunas de texto mostram os 5 valores mais frequentes, tanto em barra CSS quanto em gráfico Chart.js.

## Documentação interativa (Swagger)

Em vez de `curl`, também dá para explorar e testar tudo isso visualmente em:

```
http://localhost:8000/docs
```

O Swagger permite montar o corpo da requisição, enviar e ver a resposta direto no navegador — bom para quando você não lembra a sintaxe exata do `curl`.
