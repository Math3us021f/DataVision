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
- `http://localhost:8000/` — home. Sem sessão, redireciona para o login. Admin vê o botão "Módulo administrador".
- `http://localhost:8000/admin/users` — gestão de usuários (só admin). Usuário comum é redirecionado para a home.
- `http://localhost:8000/admin/metrics` — métricas (só admin). O horário "Atualizado às" deve mudar a cada ~5 segundos com a aba aberta.
- `http://localhost:8000/admin/files` — explorador de arquivos (só admin). Clique numa pasta para entrar, use o breadcrumb para voltar. Abrir `exemplo.env` deve mostrar "Tipo de arquivo não permitido".
- `http://localhost:8000/admin/logs` — logs (só admin). Teste de XSS via log: tente logar (sem sucesso) com o usuário `<img src=x onerror=alert(1)>`; na página de logs ele deve aparecer como texto, sem disparar alerta.
- Teste de XSS: crie pela tela um usuário chamado `<img src=x onerror=alert(1)>`. Ele deve aparecer na tabela como texto, sem disparar alerta.

## Documentação interativa (Swagger)

Em vez de `curl`, também dá para explorar e testar tudo isso visualmente em:

```
http://localhost:8000/docs
```

O Swagger permite montar o corpo da requisição, enviar e ver a resposta direto no navegador — bom para quando você não lembra a sintaxe exata do `curl`.
