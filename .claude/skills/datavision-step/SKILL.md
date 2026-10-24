---
name: datavision-step
description: Orienta o desenvolvimento incremental do DataVision, explicando conceitos, inspecionando o projeto antes de alterar arquivos e validando cada etapa antes de avançar. Use ao iniciar funcionalidades, corrigir problemas ou planejar a próxima etapa.
---

# DataVision Step — Desenvolvimento incremental

## 1. Objetivo

Desenvolver o DataVision em pequenas etapas, mantendo o código compreensível para o desenvolvedor e evitando implementações excessivas ou prematuras.

O desenvolvedor está aprendendo Python, APIs, bancos de dados e Docker. Priorize aprendizado prático, autonomia e compreensão das decisões técnicas.

## 2. Contexto do projeto

O DataVision é um SaaS de análise automática de arquivos de dados.

Ambiente planejado:

- Desenvolvimento no Windows.
- Docker Desktop com containers Linux.
- Python 3.13 dentro do container.
- FastAPI para a API e backend.
- HTML, CSS e JavaScript para a interface inicial.
- SQLite para dados administrativos do MVP.
- MinIO para armazenar os arquivos originais.
- pytest para testes.
- Ubuntu Server 24.04 como ambiente de implantação futura.

Consulte o `CLAUDE.md` e a documentação disponível antes de assumir que uma funcionalidade já foi implementada.

## 3. Fluxo obrigatório de trabalho

Para cada tarefa:

1. Entenda o objetivo e os critérios de conclusão.
2. Inspecione os arquivos relevantes antes de propor mudanças.
3. Identifique a implementação existente e suas dependências.
4. Apresente um plano curto, preferencialmente com até cinco passos.
5. Explique os conceitos novos antes de utilizá-los.
6. Implemente somente o necessário para a etapa atual.
7. Execute os testes e as verificações pertinentes.
8. Analise os resultados e corrija os problemas encontrados dentro do escopo autorizado.
9. Apresente um resumo do que foi feito, dos arquivos alterados e dos resultados.
10. Indique o próximo passo, mas não o execute automaticamente.

Se a tarefa for simples e de baixo risco, não exija confirmação para cada pequena alteração. Para mudanças arquiteturais, destrutivas ou de alto risco, explique o impacto e peça autorização antes de prosseguir.

## 4. Como ensinar

Ao apresentar uma implementação, explique de maneira objetiva:

- O que estamos construindo.
- Qual problema essa parte resolve.
- Por que a abordagem foi escolhida.
- Qual é a responsabilidade de cada arquivo ou função.
- Como executar e validar o resultado.
- Quais conceitos novos merecem atenção.

Prefira exemplos pequenos e progressivos. Evite entregar uma aplicação completa quando uma função ou um endpoint for suficiente para ensinar o conceito.

Não esconda decisões importantes em abstrações desnecessárias. Evite criar arquivos, classes, interfaces, camadas ou dependências sem uma justificativa concreta.

Quando houver alternativas, apresente a recomendação principal e explique brevemente o motivo.

## 5. Economia de tokens

- Não repita o contexto inteiro do projeto em cada resposta.
- Consulte somente os arquivos relevantes para a tarefa.
- Evite reler arquivos extensos quando uma inspeção localizada for suficiente.
- Não reproduza arquivos completos quando um trecho ou diff resolver o problema.
- Prefira comandos curtos e agrupados quando isso não prejudicar a compreensão.
- Não explique novamente conceitos que o desenvolvedor já demonstrou compreender, salvo quando necessário.
- Não produza documentação duplicada.
- Não implemente funcionalidades futuras apenas porque poderiam ser úteis.
- Não execute verificações redundantes sem uma razão técnica.
- Ao final, registre o próximo passo de maneira concisa.

Economize tokens sem omitir explicações necessárias para o aprendizado, riscos relevantes ou resultados dos testes.

## 6. Regras para alterações

Antes de editar:

- Verifique se o arquivo já existe.
- Preserve convenções e padrões já adotados.
- Identifique possíveis impactos sobre funcionalidades existentes.
- Prefira mudanças pequenas e localizadas.
- Não substitua implementações funcionais sem necessidade.

Não:

- Reescreva o projeto inteiro para resolver um problema localizado.
- Remova testes existentes para fazer a suíte passar.
- Adicione dependências sem justificar a necessidade.
- Altere configurações do ambiente host sem autorização.
- Altere o servidor Ubuntu durante a fase de desenvolvimento local.
- Declare uma funcionalidade concluída sem verificar os critérios de aceitação.

## 7. Docker e ambiente

O desenvolvimento ocorre no Windows, usando containers Linux.

- Execute comandos Python no container quando depender do Python 3.13 do projeto.
- Não exija instalação de Python 3.13 no Windows.
- Não altere o Python padrão do Windows.
- Inspecione o Dockerfile, o Compose e os volumes antes de modificá-los.
- Não remova containers, imagens, volumes ou dados sem autorização explícita.
- Não utilize comandos destrutivos de limpeza como solução genérica para problemas.
- Não monte o socket do Docker no container da aplicação sem uma necessidade aprovada.

## 8. Documentação e encerramento

Atualize a documentação pertinente quando uma decisão, arquitetura, comando ou etapa de implementação mudar.

Não registre como fato algo que foi apenas planejado.

Ao encerrar cada etapa, informe:

- Objetivo alcançado.
- Arquivos criados ou alterados.
- Comandos executados.
- Resultado real dos testes.
- Limitações ou pendências.
- Próxima etapa sugerida.

Se uma validação não foi executada, declare isso explicitamente.

## 9. Critério de sucesso

Uma etapa está concluída quando sua funcionalidade atende aos critérios definidos, os testes pertinentes foram executados com resultado conhecido e o desenvolvedor compreende o que foi implementado.

O objetivo não é escrever o máximo de código no menor tempo possível. É construir um DataVision funcional, seguro, testável e compreensível.
