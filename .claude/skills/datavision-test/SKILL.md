---
name: datavision-test
description: Define como criar, executar e analisar testes automatizados do DataVision usando pytest, incluindo testes unitários, integração, API e casos negativos. Use ao implementar funcionalidades, corrigir bugs ou validar alterações.
---

# DataVision Test — Estratégia de testes

## 1. Objetivo

Garantir que cada funcionalidade do DataVision funcione conforme esperado e que mudanças não quebrem recursos já existentes.

Priorize testes pequenos, determinísticos, fáceis de entender e rápidos de executar.

## 2. Antes de testar

Antes de escrever ou executar testes:

1. Inspecione a estrutura atual dos testes.
2. Verifique as dependências e a configuração do pytest.
3. Identifique o comportamento esperado da funcionalidade.
4. Consulte os testes existentes para manter a convenção do projeto.
5. Escolha a menor suíte que valide adequadamente a alteração.

Não crie uma nova estrutura de testes sem verificar se já existe uma.

## 3. Tipos de testes

### Testes unitários

Teste funções e componentes isoladamente.

Exemplos:

- Validação de dados.
- Conversões e regras de negócio.
- Cálculo de métricas.
- Identificação de tipos de colunas.
- Tratamento de valores ausentes.

### Testes de integração

Verifique se componentes funcionam corretamente em conjunto.

Exemplos:

- API e banco SQLite.
- Serviço de autenticação e armazenamento de usuários.
- Backend e MinIO.
- Leitura e processamento de arquivos.

Prefira recursos temporários e ambientes isolados. Não utilize dados reais de produção.

### Testes da API

Verifique endpoints e seus contratos.

Exemplos:

- Código HTTP esperado.
- Estrutura da resposta.
- Validação de parâmetros.
- Tratamento de erros.
- Autenticação e autorização.
- Acesso permitido e negado conforme o perfil.

Utilize o cliente de testes do FastAPI quando adequado, sem iniciar um servidor externo desnecessariamente.

### Testes negativos

Verifique explicitamente situações inválidas ou inesperadas.

Exemplos:

- Campos obrigatórios ausentes.
- Tipos de dados incorretos.
- Usuário não autenticado.
- Usuário sem permissão.
- Arquivo inválido ou excessivamente grande.
- Caminho de arquivo proibido.
- Serviço externo indisponível.

## 4. Isolamento dos testes

- Utilize fixtures do pytest quando simplificarem a preparação e a limpeza dos testes.
- Utilize banco temporário ou banco em memória quando compatível com a implementação.
- Não dependa da ordem de execução dos testes.
- Não dependa de credenciais reais, serviços públicos ou rede externa para testes unitários.
- Utilize mocks ou fakes somente quando apropriado e sem esconder o comportamento que precisa ser validado.
- Garanta que arquivos temporários e recursos de teste sejam limpos corretamente.
- Não conecte os testes a bancos ou buckets de produção.

Se um teste exigir Docker, MinIO ou outro serviço real, identifique claramente essa dependência.

## 5. Execução

Execute os comandos no ambiente apropriado do projeto, preferencialmente no container que utiliza Python 3.13.

Exemplos, caso o Compose tenha um serviço chamado `app`:

```bash
docker compose run --rm app python -m pytest -q
```

Para executar um arquivo específico:

```bash
docker compose run --rm app python -m pytest tests/test_exemplo.py -q
```

Os comandos são exemplos. Confirme os nomes dos serviços, arquivos e configurações existentes antes de utilizá-los. Se o container já estiver em execução, considere a forma de execução mais adequada ao ambiente atual.

Não altere a configuração do projeto apenas para fazer um comando de exemplo funcionar.

## 6. Como analisar falhas

Quando um teste falhar:

1. Leia a mensagem de erro e o traceback relevante.
2. Identifique se a causa está no código, no teste, na configuração ou no ambiente.
3. Reproduza a falha com o menor comando possível.
4. Corrija a causa real, sem enfraquecer o teste.
5. Execute novamente o teste afetado.
6. Execute os testes relacionados para verificar regressões.

Não:

- Apague testes que falham apenas para obter sucesso.
- Substitua asserções importantes por verificações mais fracas sem justificativa.
- Ignore falhas dizendo que são irrelevantes sem investigar.
- Declare que todos os testes passaram quando apenas parte deles foi executada.

## 7. Critérios de aceitação

Cada funcionalidade deve ter critérios verificáveis antes de ser considerada concluída.

Exemplos:

- O endpoint retorna a resposta prevista.
- Uma entrada inválida é rejeitada corretamente.
- Um usuário sem permissão não consegue executar uma ação administrativa.
- Um erro externo não expõe credenciais.
- Um arquivo fora da área permitida não pode ser acessado.
- Um upload inválido não é tratado como bem-sucedido.

Os critérios devem refletir o comportamento esperado, não apenas detalhes internos da implementação.

## 8. Relatório dos testes

Ao terminar, informe:

- Comando executado.
- Quantidade de testes executados, se disponível.
- Quantidade de testes aprovados e falhos, se disponível.
- Falhas e limitações encontradas.
- Se os testes foram unitários, de integração ou de outra categoria.
- Quais verificações ainda não foram executadas.

Diferencie claramente:

- Teste executado e aprovado.
- Teste executado e reprovado.
- Teste não executado.
- Comportamento não coberto por testes.

## 9. Economia de tokens

- Execute primeiro os testes diretamente relacionados à alteração.
- Execute a suíte completa quando o risco, o escopo ou os critérios da etapa justificarem.
- Evite reproduzir tracebacks inteiros quando as linhas relevantes forem suficientes.
- Não crie testes redundantes que validem exatamente o mesmo comportamento.
- Reutilize fixtures e utilitários existentes quando fizer sentido.
- Resuma resultados com números e falhas relevantes.

A redução de testes executados nunca deve comprometer uma validação necessária de segurança ou regressão.

## 10. Critério de sucesso

A validação só está concluída quando os testes pertinentes foram realmente executados, seus resultados são conhecidos e eventuais falhas relevantes foram investigadas.
