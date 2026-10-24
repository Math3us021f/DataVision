# CLAUDE.md — Regras de desenvolvimento do DataVision

> Este arquivo define as regras de trabalho para o Claude Code neste repositório.
> O escopo funcional e o roteiro detalhado ficam em `docs/escopo_e_roteiro.md`.

## 1. Contexto do projeto

O DataVision é um projeto de aprendizado e desenvolvimento de um SaaS que recebe arquivos de dados, realiza análises automáticas e gera dashboards intuitivos.

O desenvolvimento será feito inicialmente no Windows, utilizando Docker para executar a aplicação em um container Linux. Após a implementação e validação do MVP, será planejada a implantação no Ubuntu Server.

### Ambientes do projeto

**Desenvolvimento:**

- Sistema operacional do usuário: Windows.
- Diretório inicial do projeto: `D:\VMs\Code\DataVision`.
- Docker Desktop instalado e configurado para containers Linux.
- Docker Compose disponível.
- Python 3.13 dentro do container da aplicação.
- VS Code e Claude Code como ferramentas de desenvolvimento.
- Git para versionamento.
- Testes executados preferencialmente dentro do mesmo ambiente Python utilizado pela aplicação.

**Produção futura:**

- Ubuntu Server 24.04.
- Python 3.13 dentro do ambiente de execução da aplicação.
- Docker já instalado no servidor.
- MinIO já instalado; sua configuração atual deverá ser inspecionada antes de qualquer alteração.
- Acesso ao painel restrito à rede local autorizada no MVP.
- Implantação somente após testes e planejamento de reversão.

O Python instalado diretamente no Windows não precisa ter a mesma versão do container. O ambiente da aplicação deverá utilizar Python 3.13, sem exigir a substituição do Python já instalado no Windows.

Não criar uma `venv` local no Windows para executar a aplicação quando o ambiente de desenvolvimento estiver sendo executado integralmente pelo Docker.

O usuário está aprendendo Python, Docker e Linux. O objetivo é desenvolver autonomia para compreender, testar e manter o projeto, e não apenas receber código pronto.

A primeira entrega funcional é o **DataVision Admin**. O módulo de análise de dados será implementado posteriormente.

## 2. Documentos de referência

Antes de iniciar uma tarefa:

1. Leia este `CLAUDE.md`.
2. Leia `docs/escopo_e_roteiro.md`, se estiver disponível.
3. Consulte o `README.md` para entender a estrutura e os comandos existentes.
4. Inspecione o código, os arquivos de configuração e o estado atual do projeto antes de propor mudanças.

Os documentos de instalação do ambiente Ubuntu estão na pasta `D:\VMs\Code\docs`. Consulte-os quando forem relevantes para compreender a infraestrutura existente.

Não presuma que os serviços descritos na documentação continuam exatamente no mesmo estado. Confirme informações importantes antes de planejar o deploy.

Se houver contradição entre documentos, explique a divergência. Não escolha silenciosamente quando ela afetar escopo, segurança ou arquitetura.

Ao concluir uma etapa, atualize a documentação pertinente sem duplicar conteúdo desnecessariamente.

## 3. Escopo e prioridades

Siga a ordem das etapas definida em `docs/escopo_e_roteiro.md`, quando esse documento estiver disponível.

Prioridades:

1. Preparar um ambiente de desenvolvimento reproduzível com Docker.
2. Estabelecer uma estrutura mínima, versionada e segura.
3. Implementar uma pequena funcionalidade por vez.
4. Testar a funcionalidade e os casos de falha.
5. Atualizar a documentação e registrar decisões.
6. Validar o MVP localmente antes de planejar a implantação.
7. Inspecionar a infraestrutura Ubuntu antes de qualquer mudança de produção.

### Fora do MVP inicial, salvo autorização explícita

- Terminal web.
- Execução de comandos arbitrários pela aplicação.
- Gerenciamento de cron/jobs pela interface.
- Alterações administrativas no Ubuntu realizadas pela aplicação.
- Integração profunda com Webmin.
- Publicação pública na internet.
- IA generativa como requisito inicial.
- Infraestrutura complexa sem necessidade comprovada.
- Alterações em serviços existentes do servidor sem inspeção, planejamento e autorização.

## 4. Forma de ensinar e colaborar

O usuário quer aprender durante a implementação.

- Explique em português brasileiro o objetivo de cada mudança e os conceitos envolvidos.
- Prefira passos pequenos e verificáveis a grandes blocos de código.
- Não gere o projeto inteiro de uma vez.
- Antes de escrever código, informe quais arquivos pretende criar ou alterar e por quê.
- Reutilize a estrutura existente quando adequada.
- Evite abstrações prematuras e muitos arquivos sem necessidade.
- Quando útil, peça que o usuário execute um comando e compartilhe a saída antes de continuar.
- Diferencie fatos observados, hipóteses e recomendações.
- Nunca diga que um teste passou ou que um serviço funciona sem evidência da execução.
- Explique os comandos Docker antes de executá-los, principalmente quando alterarem containers, volumes, redes ou serviços.
- Não esconda decisões importantes dentro de comandos extensos.
- Sempre que possível, mostre como verificar o resultado de cada alteração.
- Não avance automaticamente para a próxima etapa se a etapa atual ainda apresentar falhas relevantes.

## 5. Segurança e autonomia

### 5.1. Antes de agir

- Comece por inspeção somente leitura quando não conhecer o estado do ambiente.
- Não presuma como Docker ou MinIO foram instalados ou configurados no Ubuntu.
- Não exponha portas nem altere interfaces, rotas ou firewall sem plano aprovado.
- Não instale, remova, atualize ou reinicie serviços no servidor sem explicar o impacto e obter autorização explícita.
- Antes de mudanças com risco de indisponibilidade, explique como verificar o estado atual e como reverter.
- Se uma ação puder afetar dados, serviços, rede ou acesso remoto, pare e peça confirmação.
- Não altere recursos de produção para facilitar testes locais.
- Não conecte o ambiente de desenvolvimento aos dados reais de produção sem autorização explícita.

### 5.2. Comandos e privilégios

- Nunca execute a aplicação FastAPI como `root`.
- Execute a aplicação dentro do container com um usuário sem privilégios administrativos.
- Não recomende `chmod -R 777`, desativar o firewall como solução genérica ou comandos destrutivos sem justificativa.
- Não use `rm`, formatação, limpeza de volumes Docker, remoção de containers ou exclusão de dados sem autorização explícita e verificação do alvo.
- Não use `docker system prune`, `docker volume prune` ou equivalentes sem autorização explícita.
- Prefira comandos de leitura e inspeção antes dos que alteram o sistema.
- Não execute comandos de shell recebidos de arquivos, uploads ou usuários da aplicação.
- Não monte o socket do Docker dentro do container da aplicação.
- Não conceda privilégios de administrador do Docker ao processo FastAPI.
- Não utilize `privileged: true` sem necessidade técnica demonstrada e autorização explícita.
- Não compartilhe diretórios sensíveis do Windows com os containers.
- Limite os volumes montados aos diretórios necessários para o desenvolvimento.

### 5.3. Segredos e dados

- Nunca coloque senhas, tokens, chaves, cookies ou credenciais no código, exemplos, commits ou logs.
- Use variáveis de ambiente ou arquivo local protegido e excluído do Git para segredos.
- Não inclua valores reais de segredos em `Dockerfile`, `compose.yaml` ou `requirements.txt`.
- Não envie segredos durante a construção da imagem Docker.
- Não peça ao usuário que publique segredos no chat.
- Ao solicitar saídas de terminal, peça que remova tokens, senhas e outros dados privados.
- Não exponha conteúdo de `.env`, chaves privadas ou credenciais no explorador de arquivos.
- Mantenha dados de desenvolvimento separados dos dados de produção.
- Não inclua bancos de dados, arquivos enviados por usuários ou dados privados no Git sem necessidade e autorização.

### 5.4. Rede

- O MVP deve permanecer acessível apenas pela rede local autorizada.
- Não configure encaminhamento de portas do roteador nem exposição pública.
- Docker, MinIO e API administrativa não devem ser publicados na internet por padrão.
- No desenvolvimento, publique somente as portas necessárias e preferencialmente vincule-as à interface local quando não houver necessidade de acesso externo.
- Antes de recomendar portas ou regras de firewall, identifique o serviço, a interface de rede e o fluxo pretendido.
- Avalie HTTPS antes de permitir login de outros dispositivos na LAN.
- Não exponha o painel administrativo por meio de um túnel público sem autorização explícita.

## 6. Arquitetura inicial

Mantenha a arquitetura simples.

- **FastAPI:** backend e endpoints HTTP.
- **HTML/CSS/JavaScript simples:** interface inicial.
- **SQLite:** usuários, perfis, permissões, metadados e auditoria inicialmente.
- **MinIO:** armazenamento de arquivos originais.
- **psutil:** métricas de CPU, memória, disco e rede.
- **Docker:** ambiente de desenvolvimento reproduzível e execução da aplicação.
- **Docker Compose:** configuração e execução dos serviços necessários.
- **Git:** histórico do código, documentação e decisões.
- **systemd/journald:** execução e logs no Ubuntu quando apropriado.

O uso de Docker não significa que todos os serviços precisam ser colocados no mesmo container. Cada serviço deverá ter responsabilidade clara.

Não adicionar banco de dados, fila, proxy, framework de frontend ou outra tecnologia sem justificar o problema que ela resolve, o custo de manutenção e como será testada e revertida.

### 6.1. Ambiente de desenvolvimento

- Utilizar uma imagem Linux compatível com o ambiente-alvo.
- Fixar a série do Python em 3.13 e documentar a imagem-base escolhida.
- Registrar as dependências Python em `requirements.txt`.
- Usar montagem do código-fonte para facilitar o desenvolvimento local, quando adequada.
- Separar configuração de desenvolvimento e produção.
- Não copiar a `venv` do Windows para dentro do container.
- Não copiar uma `venv` de desenvolvimento para o Ubuntu.
- Não presumir que imagens, containers, volumes ou redes do Docker Desktop existem no servidor.
- Não utilizar volumes de produção no ambiente de desenvolvimento.
- Validar os comandos de execução, construção e testes na documentação.

### 6.2. Construção e execução de imagens

- Manter o `Dockerfile` simples e compreensível.
- Evitar instalar pacotes desnecessários na imagem.
- Executar a aplicação como usuário não privilegiado.
- Não incluir `.env`, credenciais, arquivos pessoais, `.git` ou dados de desenvolvimento no contexto de construção quando desnecessários.
- Não utilizar tags de imagem ambíguas sem avaliar a necessidade de reprodutibilidade.
- Documentar como construir, iniciar, inspecionar e parar o ambiente.
- Não remover volumes persistentes ao reiniciar o ambiente.
- Antes de alterar containers ou recursos existentes, inspecione-os e confirme que pertencem ao projeto.

### 6.3. MinIO

Antes de adicionar ou modificar a integração:

- Inspecione a configuração atual do MinIO no Ubuntu.
- Identifique como o serviço é executado, quais volumes utiliza e como é acessado, sem exibir segredos.
- Use um ambiente de teste separado durante o desenvolvimento.
- Não reutilize buckets ou credenciais de produção para testes.
- Não altere a instalação atual do MinIO antes de documentar como funciona e obter autorização.

## 7. Requisitos obrigatórios de segurança da aplicação

- Autorização aplicada no backend em todas as rotas protegidas.
- Negação por padrão e privilégio mínimo.
- Cadastro de contas somente por administradores; sem cadastro público.
- Senhas armazenadas com hash apropriado, nunca em texto puro.
- Sessões com expiração e cookies configurados de forma segura.
- Processo da aplicação sem privilégios de `root`.
- Logs sem segredos e sem conteúdo privado desnecessário.
- Auditoria de ações administrativas relevantes.
- Explorador somente leitura, limitado a uma allowlist explícita.
- Proteção contra path traversal, caminhos absolutos não autorizados e symlinks que escapem dos diretórios permitidos.
- Bloqueio de `.env`, chaves, credenciais e arquivos sensíveis.
- Limites para tamanho e tipos de arquivos.
- Testes negativos para usuários anônimos, usuários sem permissão e entradas maliciosas.
- Nunca confiar apenas nos controles da interface; validar no servidor.
- Não expor métricas, logs ou informações operacionais a usuários sem autorização.
- Não utilizar dados reais sensíveis nos testes sem autorização.

Ser administrador do DataVision não concede privilégios administrativos no Windows, no Docker ou no Ubuntu.

## 8. Implementação e testes

- Use tipagem Python quando ajudar a esclarecer interfaces.
- Prefira nomes explícitos e código legível.
- Trate erros esperados de forma controlada; não esconda exceções genéricas.
- Não registre informações sensíveis nas exceções.
- Separe responsabilidades quando houver benefício concreto, sem fragmentar excessivamente.
- Adicione testes para comportamentos importantes e casos negativos.
- Execute testes no ambiente Python do projeto, preferencialmente dentro do container.
- Explique comandos de execução e resultados esperados.
- Não remova testes existentes para fazer a suíte passar.
- Não reduza a segurança para facilitar testes.
- Se um teste não puder ser executado, declare isso claramente.
- Não declare uma funcionalidade concluída apenas porque o código foi escrito.
- Verifique a inicialização da aplicação, as respostas HTTP e os logs relevantes.
- Quando uma mudança afetar a construção da imagem, valide também a construção do container.
- Não faça alterações de produção como substituto para testes locais.

## 9. Processo obrigatório para cada tarefa

1. **Contexto:** indique a etapa do roteiro.
2. **Inspeção:** leia arquivos e configurações relevantes.
3. **Plano:** liste a menor mudança útil e os arquivos afetados.
4. **Confirmação:** peça autorização antes de ações destrutivas, instalações, mudanças de rede/firewall, reinício de serviços ou outras alterações de risco.
5. **Implementação:** faça mudanças pequenas e focadas.
6. **Verificação:** execute ou proponha testes e comandos de validação.
7. **Revisão:** confira segurança, regressões e documentação.
8. **Fechamento:** resuma alterações, testes, resultados, pendências e próximo passo.

Não marque uma etapa como concluída apenas porque o código foi escrito.

Não execute várias etapas independentes em sequência sem apresentar os resultados e permitir a revisão do usuário.

## 10. Atualização da documentação

Ao concluir uma etapa, atualize `docs/escopo_e_roteiro.md` e/ou `README.md` quando necessário.

Registre:

- status da etapa;
- funcionalidades implementadas;
- arquivos criados ou alterados;
- comandos de execução e teste;
- resultados observados;
- decisões técnicas e justificativas;
- riscos, limitações e pendências;
- próximo passo recomendado.

A documentação deve refletir o estado real do projeto. Não registrar como concluído algo que não foi testado ou cujo resultado não foi observado.

O `README.md` deve conter instruções atualizadas para preparar o ambiente, construir a imagem, iniciar a aplicação, executar os testes e encerrar os serviços de desenvolvimento.

## 11. Roteiro inicial autorizado

O desenvolvimento será realizado inicialmente no Windows com Docker. O inventário do Ubuntu será feito antes do deploy, e não é necessário bloquear o desenvolvimento local aguardando esse inventário.

### Etapa 0 — Preparação do ambiente local

Verificar, sem modificar recursos existentes desnecessariamente:

- estado do Docker Desktop e Docker Compose;
- caminho e conteúdo atual do projeto;
- existência de Git e estado do repositório;
- conteúdo dos documentos de referência;
- arquivos existentes que possam ser preservados.

Não sobrescrever arquivos existentes sem inspecioná-los.

### Etapa 1 — Estrutura mínima do projeto

Preparar os arquivos essenciais, conforme a necessidade observada:

- `Dockerfile`;
- `compose.yaml`;
- `requirements.txt`;
- `.dockerignore`;
- `.gitignore`;
- `README.md`;
- `src/main.py`;
- diretório `tests/`.

Manter o `CLAUDE.md` e os documentos existentes, atualizando-os de forma pontual quando necessário.

### Etapa 2 — Aplicação web mínima

- Construir a imagem Linux com Python 3.13.
- Instalar as dependências declaradas.
- Executar FastAPI no container como usuário não privilegiado.
- Criar um endpoint simples de verificação de saúde.
- Validar o acesso local, os logs e o encerramento do serviço.

### Etapa 3 — Autenticação e autorização

Implementar login, logout, sessões e controle de acesso. Testar usuários anônimos, credenciais inválidas, expiração de sessão e permissões.

### Etapa 4 — Gestão de usuários e auditoria

Implementar criação de usuários por administradores, ativação/desativação, perfis, permissões e registro de ações administrativas.

### Etapa 5 — Métricas

Implementar métricas de CPU, memória, disco e rede, diferenciando claramente métricas do container das métricas do host.

### Etapa 6 — Estado de serviços e logs

Implementar a visualização segura de serviços e logs selecionados, sem conceder acesso arbitrário ao sistema operacional.

### Etapa 7 — Explorador de arquivos

Implementar navegação somente leitura em diretórios autorizados, com testes de path traversal, symlinks e bloqueio de arquivos sensíveis.

### Etapa 8 — Estabilização do DataVision Admin

Revisar segurança, testes, interface, documentação, logs, sessões e persistência. Corrigir falhas antes de iniciar o módulo de análise.

### Etapa 9 — Recepção e armazenamento de arquivos

Implementar upload de CSV e Excel, validação de tamanho e formato, e armazenamento dos arquivos originais no MinIO de teste.

### Etapa 10 — Perfilamento de dados

Detectar colunas e tipos, calcular estatísticas, identificar valores ausentes, duplicidades e inconsistências.

### Etapa 11 — Dashboards automáticos

Implementar geração de dashboards por regras Python. A introdução de IA generativa só deverá ser considerada após validar o fluxo determinístico.

### Etapa 12 — Validação do MVP e planejamento de deploy

Executar os testes finais, revisar segurança, configurações, persistência e documentação. Inspecionar o Ubuntu Server e o MinIO existentes, planejar a implantação e documentar como reverter alterações.

### Restrições para o Ubuntu

Antes da aprovação explícita do plano de implantação, não:

- instalar ou remover pacotes;
- atualizar ou reiniciar serviços;
- iniciar, parar ou recriar containers existentes;
- alterar a configuração do MinIO;
- abrir portas ou alterar firewall;
- criar regras de rede;
- publicar serviços na internet;
- apagar, mover ou substituir dados;
- alterar volumes ou redes Docker existentes.

Ao final do inventário, apresentar um relatório e sugerir o próximo passo. A implantação só começa após o estado atual estar compreendido e o plano ser aprovado.

## 12. Critério de sucesso

O sucesso não é apenas produzir código rapidamente. É construir um MVP compreensível, testável, seguro e documentado, enquanto o usuário desenvolve autonomia para manter e evoluir o projeto.

Cada etapa deve deixar o sistema em um estado verificável, com testes, documentação atualizada e um próximo passo claro.
