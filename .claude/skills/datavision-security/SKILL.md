---
name: datavision-security
description: Revisa e orienta a segurança do DataVision, incluindo autenticação, sessões, RBAC, SQLite, uploads, MinIO, logs, métricas e explorador de arquivos. Use ao implementar ou modificar funcionalidades que envolvam acesso, dados, permissões, arquivos, segredos ou infraestrutura.
---

# DataVision Security — Segurança por padrão

## 1. Objetivo

Identificar e prevenir vulnerabilidades no DataVision desde o início do desenvolvimento.

A segurança deve fazer parte de cada implementação, e não ser tratada como uma correção posterior.

Esta skill orienta revisões e implementação segura, mas não garante que uma aplicação esteja livre de vulnerabilidades.

## 2. Regras gerais

Antes de modificar uma funcionalidade sensível:

1. Identifique os ativos protegidos.
2. Determine quem pode acessar cada recurso.
3. Analise entradas controladas pelo usuário.
4. Verifique os limites de confiança entre interface, API, banco, filesystem e serviços externos.
5. Considere como a funcionalidade pode falhar ou ser abusada.
6. Implemente as proteções necessárias.
7. Crie ou execute testes negativos.
8. Informe os riscos que permanecerem sem tratamento.

Não presuma que uma funcionalidade está segura apenas porque funciona normalmente.

## 3. Autenticação e sessões

Ao implementar login, logout ou gerenciamento de sessões:

- Armazene senhas utilizando uma função de hash apropriada para senhas, com salt e parâmetros seguros.
- Nunca armazene ou registre senhas em texto puro.
- Não crie algoritmos criptográficos próprios.
- Valide credenciais no backend.
- Implemente expiração e invalidação de sessões.
- Proteja cookies de sessão com atributos adequados, como `HttpOnly`, `SameSite` e `Secure` quando aplicável ao ambiente HTTPS.
- Considere proteção contra CSRF quando a autenticação utilizar cookies e a arquitetura exigir essa defesa.
- Evite mensagens de login que revelem desnecessariamente se determinado usuário existe.
- Não exponha tokens, senhas ou identificadores de sessão em logs e mensagens de erro.
- Não permita que o usuário escolha ou altere privilégios administrativos por meio de campos enviados pelo cliente.

Escolha bibliotecas e mecanismos de sessão adequados à arquitetura existente antes de introduzir uma solução própria.

## 4. Autorização e RBAC

A autorização deve ser aplicada no backend, em todas as operações protegidas.

- Adote negação por padrão: o acesso não é permitido até que exista autorização explícita.
- Não confie em botões ocultos ou verificações feitas apenas no frontend.
- Restrinja a criação e o gerenciamento de usuários a administradores autorizados.
- Verifique permissões em cada endpoint e operação sensível.
- Não permita que um usuário eleve o próprio perfil.
- Diferencie autenticação (quem é o usuário) de autorização (o que ele pode fazer).
- Evite verificações de permissão inconsistentes entre endpoints.
- Registre ações administrativas relevantes sem armazenar segredos.

Crie testes para acessos autorizados e negados.

## 5. Proteção de arquivos e diretórios

O explorador de arquivos do MVP deve ser estritamente somente leitura.

- Restrinja o acesso a diretórios explicitamente permitidos.
- Resolva e valide caminhos no backend antes de acessar arquivos.
- Previna path traversal, inclusive variantes codificadas e caminhos absolutos.
- Trate symlinks com cuidado para impedir escapes da área permitida.
- Não permita leitura, escrita, exclusão, renomeação ou execução de arquivos por meio do explorador.
- Bloqueie arquivos de configuração sensíveis, credenciais, chaves privadas, `.env` e equivalentes.
- Não confie exclusivamente no nome ou na extensão de um arquivo para classificá-lo como seguro.
- Evite revelar caminhos internos completos, informações de infraestrutura ou conteúdo sensível nas respostas.
- Limite tamanho de listagens, leitura de arquivos e volume de dados retornados quando necessário.

O frontend nunca deve ser a única barreira para impedir o acesso a arquivos.

## 6. Uploads e MinIO

Ao implementar o recebimento de arquivos:

- Defina limites de tamanho e tipos de arquivo aceitos.
- Valide a entrada no backend.
- Não confie exclusivamente no `Content-Type` enviado pelo cliente.
- Gere nomes de armazenamento seguros, evitando utilizar caminhos arbitrários fornecidos pelo usuário.
- Não interprete arquivos enviados como código executável.
- Trate erros de armazenamento sem expor credenciais ou detalhes internos.
- Utilize credenciais com privilégios mínimos para o serviço.
- Separe, quando adequado, os dados originais dos dados derivados do processamento.
- Evite disponibilizar buckets publicamente sem uma decisão explícita e justificada.
- Não registre tokens, chaves ou conteúdo sensível dos arquivos.
- Considere limites de processamento e arquivos malformados que possam consumir recursos excessivos.

Não presuma que MinIO está configurado de determinada forma. Inspecione a configuração disponível antes de recomendar alterações.

## 7. Banco de dados

Para SQLite e demais bancos utilizados no projeto:

- Utilize consultas parametrizadas ou mecanismos equivalentes do ORM.
- Não concatene entradas do usuário em comandos SQL.
- Aplique restrições de integridade adequadas.
- Proteja operações administrativas.
- Não exponha dados de usuários além do necessário.
- Evite armazenar segredos em tabelas sem uma necessidade justificada.
- Considere migrações, backups e recuperação antes de mudanças estruturais relevantes.
- Não apague bancos ou dados existentes como tentativa genérica de corrigir problemas.

## 8. Segredos e configurações

- Não coloque senhas, tokens, chaves ou credenciais diretamente no código.
- Não inclua `.env` ou outros arquivos com segredos no Git.
- Utilize variáveis de ambiente ou mecanismos apropriados de gerenciamento de segredos.
- Mantenha arquivos de exemplo sem credenciais reais.
- Evite imprimir configurações completas em logs ou respostas.
- Não peça ao usuário que compartilhe segredos desnecessariamente.
- Se um segredo aparecer em uma saída, não o reproduza na resposta ou na documentação.
- Considere que um segredo exposto pode precisar ser revogado e substituído.

## 9. Logs e auditoria

- Registre eventos relevantes de autenticação e administração.
- Evite armazenar senhas, tokens, cookies, cabeçalhos de autorização ou conteúdo sensível.
- Neutralize entradas não confiáveis que possam forjar linhas de log.
- Diferencie logs operacionais de registros de auditoria.
- Restrinja o acesso aos logs.
- Evite retornar tracebacks e detalhes internos ao cliente em produção.
- Mantenha mensagens de erro úteis sem revelar segredos ou detalhes exploráveis.

## 10. Docker e infraestrutura

Durante o desenvolvimento local:

- Prefira executar a aplicação como usuário não privilegiado dentro do container.
- Utilize apenas as permissões e os volumes necessários.
- Não monte o socket do Docker dentro da aplicação sem autorização e justificativa específicas.
- Não inclua credenciais nas imagens.
- Não exponha portas desnecessariamente.
- Não use `privileged: true` sem necessidade aprovada.
- Inspecione os volumes e os dados antes de alterações no Compose.
- Não remova containers, imagens, volumes ou dados sem autorização explícita.

O servidor Ubuntu permanece fora do escopo de alterações até a fase de implantação autorizada. Inspeções e mudanças no ambiente devem respeitar o processo documentado no `CLAUDE.md`.

## 11. Métricas e serviços do servidor

As funcionalidades administrativas não devem se transformar em uma interface de execução arbitrária de comandos.

- Exponha somente métricas necessárias.
- Restrinja endpoints administrativos.
- Utilize APIs e bibliotecas apropriadas para coletar informações.
- Não execute comandos montados a partir de entradas do usuário.
- Não implemente terminal web, execução arbitrária, gerenciamento irrestrito de serviços ou administração geral do sistema no MVP inicial.
- Evite divulgar informações sensíveis de rede, processos, usuários ou infraestrutura a perfis não autorizados.

## 12. Dependências e erros

- Prefira dependências conhecidas e mantidas.
- Evite adicionar bibliotecas quando os recursos existentes forem suficientes.
- Não desative validações ou controles de segurança apenas para resolver erros.
- Trate exceções de maneira explícita e apropriada.
- Não silencie falhas de autorização, validação ou armazenamento.
- Considere limites de requisições e consumo de recursos nas operações expostas ao usuário.

## 13. Revisão de segurança

Ao revisar uma implementação, classifique os achados por prioridade:

- **Crítica:** risco imediato de comprometimento grave.
- **Alta:** vulnerabilidade relevante que exige correção prioritária.
- **Média:** risco que deve ser tratado de acordo com o impacto.
- **Baixa:** melhoria ou risco limitado.
- **Informativa:** observação sem vulnerabilidade confirmada.

Para cada achado, informe:

- Arquivo ou componente afetado.
- Comportamento vulnerável.
- Cenário de exploração plausível.
- Impacto.
- Correção recomendada.
- Teste que valida a correção.

Diferencie vulnerabilidades confirmadas de hipóteses que precisam de investigação. Não afirme que uma revisão superficial constitui uma auditoria completa.

## 14. Economia de tokens

- Concentre a revisão na funcionalidade alterada e em suas fronteiras de segurança.
- Reutilize os padrões seguros já estabelecidos no projeto.
- Evite repetir a checklist inteira em cada resposta.
- Apresente primeiro os achados mais importantes.
- Não proponha refatorações extensas quando uma correção localizada resolver o risco.
- Expanda a análise quando a mudança afetar autenticação, autorização, uploads, arquivos, segredos ou infraestrutura.

## 15. Critério de sucesso

Uma implementação sensível só deve ser considerada validada quando os controles relevantes foram inspecionados, os testes de segurança pertinentes foram executados e os riscos residuais foram documentados.
