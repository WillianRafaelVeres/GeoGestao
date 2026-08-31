# ADR 0005 - Experiencia unica de assinatura e representacao

Status: aceito

Data: 2026-08-31

## Contexto

O modal de cliente apresentava duas interfaces para a mesma tarefa: o
gerenciador legado de procuradores e a camada central de representacoes. Isso
obrigava o usuario a conhecer detalhes de implementacao e aumentava o risco
de interpretar a ausencia de campos legados como uma ordem de exclusao.

## Decisao

Para a interface normal, a tarefa passa a ser apresentada em uma unica secao
chamada **Assinatura e representacao**. Ela mantem `clientes.quem_assina`, mas
usa linguagem de negocio e exibe os cards alimentados pela arquitetura central
(`pessoas_cadastro` + `representacoes`). O papel continua pertencendo a cada
relacao, e nao a pessoa.

O backend prepara os rotulos de papel, modo de atuacao, status e validade para
que o template apenas apresente o significado devolvido pela camada de
dominio. A vigencia continua sendo a informacao calculada pela RPC quando
disponivel.

Quando o modal precisa montar texto de qualificacao, a representacao central
ativa e vigente principal e projetada em memoria para o campo historico
`procurador`. Essa adaptacao preserva o contrato de `documental.py` sem
duplicar pessoa nem gravar procurador legado.

## Compatibilidade

As tabelas, colunas, RPCs e funcoes legadas continuam existindo. A funcao
`initRepresentativeManagers()` permanece como fallback. O contexto
documental historico e o campo `quem_assina` nao foram removidos.

## Marker V2

O formulario normal envia `representation_ui_version=2`. Nesse modo, o save
do cadastro nao sincroniza procuradores pelo payload legado ausente. Isso
impede que uma edicao simples de telefone, endereco ou outro dado cadastral
remova procuradores ou quebre vinculos de representacoes.

Sem o marcador, o fluxo legado preserva seu comportamento anterior. Quando a
camada central fica indisponivel, o formulario usa marcador vazio e mostra o
gerenciador legado explicitamente como **Modo de compatibilidade**.

## Fallback

Chave de aplicacao ausente ou falha da RPC exibe um aviso discreto e mantem o
cadastro do cliente editavel. A indisponibilidade nao derruba PF, PJ,
conjuge, endereco ou salvamento cadastral.

## Banco

Nenhuma migration foi criada nesta etapa. Nao houve alteracao de schema, RLS,
grants, SECURITY DEFINER ou dados reais.
