# Modelos de Processo - GeoGestao

## Fluxo operacional atual

A matriz usa o mesmo fluxo operacional para todos os tipos de servico:

`Orcamento -> Documentos -> Medicao -> Processamento -> Escritorio -> Assinaturas -> Orgao externo -> Finalizado`

- Todas essas etapas sao criadas e ativadas por padrao, independentemente do tipo de processo.
- `ANALISE`, `PREPARACAO`, `CONFERENCIA`, `PREFEITURA` e `ENTREGA` permanecem apenas como chaves historicas e nao geram cliques ou colunas.
- Uma exigencia move o projeto de `ORGAO_EXTERNO` para `PENDENCIAS` (exibida como **Exigencias**).
- Ao concluir todas as exigencias, o projeto retorna para `ORGAO_EXTERNO`.
- Quando nao houver protocolo externo, o botao proprio da etapa permite seguir para `FINALIZADO`.
- Retirar todos os protocolos nao finaliza o projeto automaticamente. O usuario decide quando avancar para `FINALIZADO`.

## Fase 1 - Catalogo de tipos de processo

Esta fase cria a base oficial de tipos de processo/servico usados nos projetos do GeoGestao.

Antes desta fase, o campo de tipo de servico podia receber textos livres como `Geo`, `retif rural`, `Retificacao area` ou `georreferenciamento`. Isso dificulta filtros, relatorios, matriz, checklists futuros e documentos especificos por processo.

A partir desta fase, o projeto deve armazenar uma chave interna padronizada e exibir um nome amigavel para o usuario.

Exemplo:

- Usuario ve: `Retificacao de Area Rural`
- Sistema salva: `RETIFICACAO_AREA_RURAL`

## Por que nao usar texto livre

Texto livre gera nomes duplicados para o mesmo processo e impede o sistema de saber qual fluxo aplicar. O catalogo padroniza a linguagem da empresa e prepara o GeoGestao para as proximas fases:

- modelos de etapas por processo;
- checklists especificos;
- documentos exigidos por tipo de processo;
- relatorios por processo;
- regras de etapa obrigatoria, opcional ou nao aplicavel.

## O que foi criado nesta fase

Foi criado um catalogo oficial com codigo interno, nome exibido, categoria e indicadores operacionais:

- se normalmente usa campo/medicao;
- se normalmente usa cartorio;
- se normalmente usa orgao externo;
- se possui documentos especificos;
- se esta ativo;
- ordem de exibicao.

A matriz continua simples. Ela mostra o tipo de processo de forma amigavel, mas nao mostra checklist dentro da matriz.

## O que ainda nao foi implementado

Esta fase nao implementa:

- `ProcessTemplate`;
- `ProcessStageTemplate`;
- `ChecklistItemTemplate`;
- `RequiredDocumentTemplate`;
- checklists especificos por processo;
- documentos exigidos por processo;
- regra de etapa nao aplicavel;
- bloqueios de avancar etapa;
- geracao automatica de documentos;
- automacoes avancadas.

Esses itens serao tratados em fases futuras.

## Catalogo inicial

| Codigo interno | Nome exibido | Categoria | Usa campo | Usa cartorio | Usa orgao externo | Observacao |
| --- | --- | --- | --- | --- | --- | --- |
| `RETIFICACAO_AREA_RURAL` | Retificacao de Area Rural | Regularizacao cartorial | sim | sim | nao por padrao | Corrige area, perimetro, confrontacoes ou descricao da matricula. |
| `DESMEMBRAMENTO` | Desmembramento | Regularizacao cartorial | opcional/conforme caso | sim | prefeitura/cartorio quando aplicavel | Divide uma matricula ja correta em novas areas. |
| `DESTACAMENTO_ESTREMACAO` | Destacamento / Estremacao | Regularizacao cartorial | sim | sim | nao por padrao | Separa ou individualiza area em condominio ou situacao equivalente. |
| `UNIFICACAO` | Unificacao | Regularizacao cartorial | opcional/conforme caso | sim | nao por padrao | Une matriculas ou areas quando a base documental esta correta. |
| `USUCAPIAO` | Usucapiao | Regularizacao juridica/cartorial | sim | sim | advogado/forum/cartorio conforme modalidade | Regulariza posse por usucapiao. |
| `GEORREFERENCIAMENTO_TECNICO` | Georreferenciamento Tecnico | Tecnico/topografico | sim | opcional/conforme contratacao | SIGEF/INCRA quando aplicavel | Levantamento e georreferenciamento do imovel rural. |
| `CERTIFICACAO_SIGEF` | Certificacao SIGEF | INCRA/SIGEF | opcional/conforme qualidade dos dados | nao por padrao | SIGEF/INCRA | Certificacao do imovel rural no SIGEF. |
| `AVERBACAO_CERTIFICACAO` | Averbacao da Certificacao | Regularizacao cartorial | nao por padrao | sim | cartorio de registro de imoveis | Averba na matricula uma certificacao SIGEF ja emitida. |
| `CAR` | Cadastro Ambiental Rural - CAR | Ambiental | opcional/conforme caso | nao | SICAR/orgao ambiental | Cadastro, analise ou ajuste ambiental do imovel rural. |
| `ATUALIZACAO_CCIR` | Atualizacao de CCIR | INCRA/SNCR | nao por padrao | nao | SNCR/INCRA | Atualizacao ou emissao de CCIR e dados do cadastro rural. |
| `MEDICAO` | Medicao / Levantamento | Tecnico/topografico | sim | nao por padrao | nao por padrao | Medicao, levantamento ou conferencia de area. |
| `REGULARIZACAO_TITULARIDADE` | Regularizacao de Titularidade | Regularizacao documental | opcional/conforme caso | sim | pode envolver cartorio, tabelionato, prefeitura ou advogado | Organiza titularidade, documentacao e situacao cadastral do imovel. |
| `OUTRO` | Outro | Geral | conforme caso | conforme caso | conforme caso | Processo ainda nao padronizado. |

## Compatibilidade com projetos antigos

Projetos antigos podem ter textos livres em `tipo_servico`. A migracao inicial tenta mapear esses textos para uma chave oficial.

Exemplos:

- `Regularizacao Rural` -> `RETIFICACAO_AREA_RURAL`
- `Retificacao` -> `RETIFICACAO_AREA_RURAL`
- `Desmembramento` -> `DESMEMBRAMENTO`
- `Geo` -> `GEORREFERENCIAMENTO_TECNICO`
- `Georreferenciamento` -> `GEORREFERENCIAMENTO_TECNICO`
- `CAR` -> `CAR`
- `SIGEF` -> `CERTIFICACAO_SIGEF`
- `Averbacao da Certificacao` -> `AVERBACAO_CERTIFICACAO`
- `CCIR` -> `ATUALIZACAO_CCIR`
- `Medicao` -> `MEDICAO`

Quando o texto antigo nao e reconhecido, o sistema usa `OUTRO` e preserva o texto legado em campo separado para consulta tecnica.

## Como sera usado nas proximas fases

Na Fase 2, cada tipo de processo podera apontar para um modelo de etapas e checklist. A criacao do projeto deve continuar simples:

1. Usuario cria projeto.
2. Usuario escolhe o tipo de processo do catalogo.
3. Sistema salva a chave oficial.
4. Em fase futura, o sistema carregara o checklist especifico daquele processo.
5. A matriz continuara mostrando apenas projeto, cliente, processo, cartorio/orgao, etapa atual, responsavel e pendencias.

O detalhe do checklist ficara dentro do projeto, nao na matriz.

## Fase 2 - Modelos de etapas por processo

A Fase 2 cria a estrutura que permite ao GeoGestao entender que cada tipo de processo tem um fluxo diferente.

O sistema continua com uma matriz simples. A matriz nao deve virar checklist e nao deve criar colunas diferentes para cada processo. A inteligencia fica dentro do projeto, em uma camada de modelo que diz quais etapas fazem sentido para aquele tipo de processo.

Exemplos praticos:

- Retificacao de Area Rural normalmente passa por campo, pecas tecnicas, assinaturas e cartorio.
- CAR nao usa cartorio por padrao; usa SICAR ou orgao ambiental.
- Certificacao SIGEF usa SIGEF/INCRA como orgao externo.
- Atualizacao de CCIR nao usa medicao/campo por padrao.
- Medicao / Levantamento nao usa cartorio por padrao.

### O que e um modelo de etapa

Um modelo de etapa e uma configuracao por tipo de processo. Ele informa:

- qual etapa macro existe naquele processo;
- a ordem operacional da etapa;
- se a etapa e obrigatoria, opcional, condicional ou nao aplicavel;
- se envolve responsavel interno;
- se envolve orgao externo;
- prazo padrao em dias, quando fizer sentido;
- se bloqueia finalizacao;
- se deve aparecer na matriz;
- se deve aparecer dentro do projeto.

Nesta fase, os modelos foram criados como fundacao. A criacao real das etapas do projeto ainda nao foi alterada profundamente, porque a matriz atual depende de uma grade fixa de etapas para manter as colunas alinhadas. A aplicacao dos modelos na criacao de novos projetos deve ser feita em uma fase seguinte, com cuidado.

### Aplicabilidade das etapas

| Aplicabilidade | Significado |
| --- | --- |
| `OBRIGATORIA` | A etapa faz parte normal do processo e deve aparecer no projeto. Normalmente bloqueia finalizacao enquanto nao for concluida. |
| `OPCIONAL` | A etapa pode ser ativada manualmente se for necessaria. Nao deve ser tratada como atraso enquanto nao estiver ativa. |
| `CONDICIONAL` | A etapa depende do caso concreto, de exigencia, contratacao ou decisao operacional. |
| `NAO_APLICAVEL` | A etapa nao faz parte daquele processo por padrao e nao deve contar como atraso, pendencia ou etapa nao iniciada. |

### Modelos iniciais por processo

| Tipo de processo | Usa campo? | Usa orgao externo? | Etapas obrigatorias principais | Etapas condicionais | Etapas nao aplicaveis por padrao | Onde normalmente termina |
| --- | --- | --- | --- | --- | --- | --- |
| Retificacao de Area Rural | Sim | Cartorio | Orcamento, Documentos, Analise, Preparacao, Medicao, Processamento, Escritorio, Conferencia, Assinaturas, Orgao externo, Entrega, Finalizado | Pendencias | Nenhuma etapa macro principal | Cartorio, entrega e finalizacao |
| Desmembramento | Condicional | Cartorio/prefeitura conforme caso | Orcamento, Documentos, Analise, Preparacao, Escritorio, Conferencia, Orgao externo, Entrega, Finalizado | Medicao, Processamento, Assinaturas, Pendencias | Nenhuma etapa macro principal | Cartorio ou prefeitura, entrega e finalizacao |
| Destacamento / Estremacao | Sim | Cartorio | Orcamento, Documentos, Analise, Preparacao, Medicao, Processamento, Escritorio, Conferencia, Assinaturas, Orgao externo, Entrega, Finalizado | Pendencias | Nenhuma etapa macro principal | Cartorio, entrega e finalizacao |
| Unificacao | Condicional | Cartorio | Orcamento, Documentos, Analise, Preparacao, Escritorio, Conferencia, Orgao externo, Entrega, Finalizado | Medicao, Processamento, Assinaturas, Pendencias | Nenhuma etapa macro principal | Cartorio, entrega e finalizacao |
| Usucapiao | Sim | Cartorio/advogado/forum | Orcamento, Documentos, Analise, Preparacao, Medicao, Processamento, Escritorio, Conferencia, Assinaturas, Orgao externo, Entrega, Finalizado | Pendencias | Nenhuma etapa macro principal | Orgao externo juridico/cartorial, entrega e finalizacao |
| Georreferenciamento Tecnico | Sim | Condicional SIGEF/INCRA | Orcamento, Documentos, Analise, Preparacao, Medicao, Processamento, Escritorio, Conferencia, Entrega, Finalizado | Assinaturas, Orgao externo, Pendencias | Nenhuma etapa macro principal | Entrega tecnica ou SIGEF/INCRA se contratado |
| Certificacao SIGEF | Condicional | SIGEF/INCRA | Orcamento, Documentos, Analise, Preparacao, Processamento, Escritorio, Conferencia, Orgao externo, Entrega, Finalizado | Medicao, Assinaturas, Pendencias | Nenhuma etapa macro principal | SIGEF/INCRA, entrega e finalizacao |
| CAR | Condicional | SICAR/orgao ambiental | Orcamento, Documentos, Analise, Preparacao, Escritorio, Conferencia, Orgao externo, Entrega, Finalizado | Medicao, Processamento, Assinaturas, Pendencias | Cartorio por padrao | SICAR/orgao ambiental, entrega e finalizacao |
| Atualizacao de CCIR | Nao por padrao | SNCR/INCRA | Orcamento, Documentos, Analise, Preparacao, Escritorio, Conferencia, Orgao externo, Entrega, Finalizado | Processamento, Assinaturas, Pendencias | Medicao / Campo | SNCR/INCRA, entrega e finalizacao |
| Medicao / Levantamento | Sim | Nao por padrao | Orcamento, Preparacao, Medicao, Processamento, Conferencia, Entrega, Finalizado | Documentos, Analise, Escritorio, Pendencias | Assinaturas, Orgao externo | Entrega tecnica |
| Regularizacao de Titularidade | Condicional | Cartorio/tabelionato/prefeitura/advogado | Orcamento, Documentos, Analise, Preparacao, Escritorio, Conferencia, Assinaturas, Orgao externo, Entrega, Finalizado | Medicao, Processamento, Pendencias | Nenhuma etapa macro principal | Orgao externo/documental, entrega e finalizacao |
| Outro | Conforme caso | Conforme caso | Orcamento, Preparacao, Entrega, Finalizado | Documentos, Analise, Medicao, Processamento, Escritorio, Conferencia, Assinaturas, Orgao externo, Pendencias | Nenhuma etapa fixa | Entrega e finalizacao |

### Estrutura tecnica criada

A estrutura de Fase 2 usa:

- catalogo central de etapas macro;
- modelos por tipo de processo;
- aplicabilidade por etapa;
- actor externo padrao quando existir;
- prazos padrao iniciais;
- flags para aparecer na matriz ou dentro do projeto;
- seed em banco na tabela `process_stage_templates`.

Helpers preparados:

- `get_stage_template_for_process(processTypeKey)`;
- `get_applicable_stages_for_process(processTypeKey)`.

Esses helpers permitem que a Fase 3 use o tipo de processo para criar as etapas corretas do projeto, sem depender de texto livre.

### Relatorios futuros

Quando os modelos passarem a controlar as etapas reais dos projetos:

- etapas `NAO_APLICAVEL` nao devem entrar como atrasadas;
- etapas `OPCIONAL` so devem entrar nos relatorios se forem ativadas;
- etapas `CONDICIONAL` devem depender da regra do caso concreto;
- relatorios por etapa devem considerar apenas etapas aplicaveis ao projeto.

### O que ainda fica para depois

A Fase 2 ainda nao cria:

- checklists detalhados por processo;
- documentos exigidos por processo;
- itens automaticos de checklist;
- bloqueios avancados de avancar etapa;
- geracao de documentos;
- telas administrativas para editar modelos;
- automacoes avancadas.

A proxima fase deve aplicar os modelos na criacao/edicao do projeto e preparar a aba Etapas para mostrar, com clareza, quais etapas sao obrigatorias, condicionais, opcionais ou nao aplicaveis.

## Fase 3 - Checklists especificos por processo

A Fase 3 cria a camada de checklist operacional por tipo de processo e por etapa.

O objetivo e tirar o checklist do modo generico. Antes, as etapas tinham itens padrao iguais para qualquer projeto. Agora, Retificacao, CAR, CCIR, Medicao, SIGEF, Usucapiao e os demais processos podem ter listas diferentes dentro das mesmas etapas macro.

A matriz continua limpa. Ela nao mostra itens de checklist. O checklist aparece dentro do projeto, agrupado por etapa.

### Checklist template

Checklist template e o modelo padrao de itens para um tipo de processo.

Exemplo:

- `RETIFICACAO_AREA_RURAL` + `DOCUMENTOS` inclui solicitar matricula, documentos pessoais, conjuge quando aplicavel, procuracao quando houver e documentos rurais quando fizer sentido.
- `CAR` + `ESCRITORIO` inclui preencher/ajustar SICAR, delimitar APP, Reserva Legal e uso do solo.
- `ATUALIZACAO_CCIR` + `ESCRITORIO` inclui atualizar SNCR/INCRA, conferir dados, emitir taxa/guia quando aplicavel e emitir CCIR quando possivel.
- `AVERBACAO_CERTIFICACAO` parte de uma certificacao SIGEF ja emitida e segue por analise documental, requerimento, conferencia, assinaturas e protocolo no cartorio.
- `MEDICAO` nao possui checklist de cartorio por padrao.

### Checklist real do projeto

Checklist real e a copia do template dentro do projeto.

O item real guarda:

- projeto;
- etapa;
- template de origem;
- titulo;
- status;
- obrigatoriedade;
- criticidade;
- responsavel, quando existir;
- data de conclusao;
- observacao;
- anexo futuro, quando aplicavel.

Isso permite que o template seja padrao, mas o projeto possa ser ajustado manualmente sem alterar o modelo global.

### Obrigatoriedade do item

| Nivel | Como usar |
| --- | --- |
| `OBRIGATORIO` | Item normal do processo. Pode bloquear conclusao da etapa quando marcado para bloquear. |
| `RECOMENDADO` | Item importante, mas nao bloqueia. Serve como orientacao operacional. |
| `OPCIONAL` | Item que pode ser usado conforme decisao do gestor. |
| `CONDICIONAL` | Item que so se aplica quando uma condicao do caso concreto existir. |

### Criticidade

| Criticidade | Uso |
| --- | --- |
| `BAIXA` | Conferencia simples. |
| `MEDIA` | Item operacional normal. |
| `ALTA` | Item com impacto relevante em prazo, retrabalho ou qualidade. |
| `CRITICA` | Item que pode comprometer a etapa ou o processo se ficar errado. |

### Regra inicial de bloqueio

A Fase 3 cria uma regra inicial leve:

- item obrigatorio que bloqueia etapa deve estar concluido para a etapa ser considerada sem bloqueio;
- item recomendado nao bloqueia;
- item opcional nao bloqueia;
- item condicional so deve bloquear quando for aplicavel ao caso;
- item critico deve ficar visualmente destacado.

Nesta fase, o sistema orienta mais do que trava. Bloqueios rigidos devem ser refinados depois, quando a equipe validar os modelos.

### Estrutura tecnica criada

A Fase 3 usa:

- `process_checklist_templates`: tabela de templates por processo e etapa;
- `project_checklist_items`: tabela dos itens reais de cada projeto;
- arquivo central `process_checklist_templates.py`;
- helper `get_checklist_template_for_process(processTypeKey)`;
- helper `get_checklist_template_for_process_stage(processTypeKey, stageKey)`;
- helper `create_project_checklist_from_template(projectId, processTypeKey)`;
- helper `get_checklist_progress(projectChecklistItems)`;
- helper `get_stage_checklist_progress(projectId, stageKey)`.

Quando um projeto novo e criado, o sistema gera o checklist operacional conforme o tipo de processo selecionado.

Projetos antigos recebem checklist automaticamente se ainda nao tiverem itens reais em `project_checklist_items`.

### Exemplos de diferenca por processo

Retificacao de Area Rural:

- documentos;
- analise de matricula;
- medicao;
- processamento;
- planta/memorial;
- declaracoes quando aplicavel;
- assinaturas;
- protocolo no cartorio;
- exigencias;
- entrega.

CAR:

- dados do proprietario;
- situacao do CAR;
- perimetro;
- APP;
- Reserva Legal;
- uso do solo;
- SICAR;
- recibo/demonstrativo;
- entrega.

CCIR:

- CPF/CNPJ;
- matricula ou dados do imovel;
- CCIR anterior, se houver;
- conferencia SNCR/INCRA;
- atualizacao cadastral;
- taxa/guia quando aplicavel;
- emissao do CCIR;
- entrega.

Medicao / Levantamento:

- planejamento de campo;
- equipamento;
- equipe;
- levantamento;
- dados brutos;
- processamento;
- entrega tecnica.

Medicao nao exige cartorio por padrao.

### O que ainda fica para depois

A Fase 3 nao implementa:

- documentos exigidos como entidade separada;
- upload/anexo obrigatorio avancado;
- geracao automatica de DOCX/PDF;
- tomada de decisao assistida;
- bloqueios rigidos;
- automacoes por WhatsApp;
- relatorios avancados baseados em checklist;
- tela administrativa para editar modelos.

A proxima fase deve separar documentos exigidos dos itens operacionais de checklist. Checklist e "fazer algo"; documento exigido e "ter um arquivo/dado/documento valido".

## Fase 4 - Aplicacao dos modelos aos projetos

A Fase 4 faz o GeoGestao usar, na pratica, o catalogo de tipos de processo, os modelos de etapas e os checklists especificos.

Quando um novo projeto e criado, o tipo de processo escolhido deixa de ser apenas uma informacao descritiva. Ele passa a definir a estrutura inicial do projeto.

### Como o projeto nasce

Ao salvar um novo projeto:

1. O sistema identifica a chave do processo, por exemplo `RETIFICACAO_AREA_RURAL`, `CAR`, `MEDICAO` ou `ATUALIZACAO_CCIR`.
2. O sistema carrega o modelo de etapas daquele processo em `process_stage_templates`.
3. O sistema cria as etapas reais em `projeto_etapas`.
4. O sistema carrega o checklist template daquele processo em `process_checklist_templates`.
5. O sistema cria os itens reais em `project_checklist_items`.
6. O sistema define a etapa inicial como a primeira etapa obrigatoria do fluxo.
7. O sistema registra historico inicial e evento de aplicacao do modelo.

Com isso, Retificacao, CAR, CCIR e Medicao deixam de nascer com o mesmo fluxo generico.

### Etapa template e etapa real

O template de etapa e o modelo padrao por tipo de processo.

A etapa real e a copia aplicada a um projeto especifico.

Exemplo:

- Template: `CAR` + `ORGAO_EXTERNO` = SICAR/orgao ambiental.
- Projeto real: etapa "Orgao externo" criada no projeto de CAR, com status, prazo, responsavel e historico proprios.

### Checklist template e checklist real

O checklist template e a lista padrao do processo.

O checklist real fica vinculado ao projeto e a etapa real.

Isso permite que o modelo continue padrao, mas o projeto possa ter status, observacoes e marcacoes proprias.

### Aplicabilidade na criacao

| Aplicabilidade | Tratamento inicial |
| --- | --- |
| `OBRIGATORIA` | A etapa e criada como parte ativa do fluxo. A primeira obrigatoria inicia em andamento. |
| `CONDICIONAL` | A etapa e criada como disponivel, mas nao conta como atraso enquanto nao for ativada. |
| `OPCIONAL` | A etapa fica disponivel para uso, sem bloquear o fluxo por padrao. |
| `NAO_APLICAVEL` | A etapa nao e criada como etapa ativa e nao entra como pendencia ou atraso. |

Etapas condicionais e opcionais ajudam a manter flexibilidade sem poluir a matriz ou os relatorios.

### Projetos antigos

Projetos antigos continuam funcionando.

Se um projeto foi criado antes da aplicacao dos modelos, a tela de detalhes mostra um aviso com a acao "Aplicar modelo de processo".

Essa acao:

- cria apenas etapas e checklist faltantes;
- nao duplica itens ja existentes;
- nao apaga historico;
- preserva dados antigos;
- organiza o projeto para o novo padrao.

Se o projeto ja possui fluxo por modelo, a acao apenas confere itens faltantes sem duplicar.

### Edicao do tipo de processo

Alterar o tipo de processo de um projeto com andamento e uma operacao sensivel.

Nesta fase, o sistema nao apaga automaticamente etapas ou checklist antigos quando o tipo e alterado. Ele avisa que o fluxo precisa ser revisado.

A migracao automatica completa, com confirmacao visual e comparacao entre modelos, deve ficar para uma fase futura.

### Matriz continua simples

A matriz nao mostra checklist.

Ela continua mostrando apenas:

- projeto;
- cliente/proprietario;
- tipo de processo;
- cartorio ou orgao externo;
- etapa atual;
- responsavel;
- status;
- prazo;
- pendencias.

Internamente, a matriz continua alinhada por colunas macro gerais. Quando uma etapa nova do modelo mapeia para uma coluna antiga, o sistema escolhe a etapa real mais relevante para exibir naquela coluna.

Exemplo:

- `ORGAO_EXTERNO` aparece na coluna operacional de cartorio/orgao;
- `FINALIZADO` e a ultima coluna e depende de avanco manual;
- etapas nao aplicaveis nao aparecem como atraso.

### Aba Etapas

A aba Etapas passa a ser o lugar principal para entender o fluxo interno do projeto.

Cada etapa mostra:

- nome da etapa;
- aplicabilidade: obrigatoria, opcional ou condicional;
- status;
- responsavel;
- prazo;
- progresso do checklist;
- quantidade de itens obrigatorios pendentes.

Ao abrir uma etapa, o usuario ve o checklist daquela etapa e pode marcar itens como concluidos ou nao aplicaveis.

### Conclusao de etapa

Ao concluir uma etapa, o sistema verifica o checklist da etapa.

Regra inicial:

- item obrigatorio que bloqueia etapa precisa estar concluido ou marcado como nao aplicavel;
- item recomendado nao bloqueia;
- item opcional nao bloqueia;
- item condicional so deve bloquear quando estiver ativo/aplicavel ao caso.

Se houver bloqueio, a etapa nao e concluida e o sistema mostra quais itens precisam ser resolvidos.

Quando a etapa e concluida com sucesso:

1. a data de conclusao e registrada;
2. o historico da etapa e atualizado;
3. o sistema encontra a proxima etapa aplicavel;
4. etapas nao aplicaveis, opcionais inativas e condicionais inativas sao puladas;
5. o projeto avanca para a proxima etapa ativa.

### Pendencias

Pendencias continuam vinculadas ao projeto e podem ser vinculadas a etapa.

Pendencias criadas dentro do contexto de uma etapa ficam visiveis na propria etapa e na aba Pendencias.

### Documentos

Documentos exigidos por processo ainda nao foram separados como entidade propria.

Nesta fase, itens documentais continuam no checklist operacional.

A fase futura deve criar uma camada propria para documentos exigidos, anexos, validade, obrigatoriedade e prontidao documental.

### Relatorios

Os relatorios nao foram refeitos nesta fase.

A nova estrutura ja prepara os relatorios para:

- ignorar etapas `NAO_APLICAVEL`;
- nao tratar etapas opcionais inativas como atraso;
- medir tempo com base nas etapas reais do projeto;
- futuramente cruzar checklist pendente com gargalos.

### O que fica para a Fase 5

A Fase 5 deve cuidar de:

- refinar relatorios usando as etapas reais por processo;
- separar documentos exigidos do checklist operacional;
- melhorar ativacao manual de etapas opcionais e condicionais;
- criar revisao segura ao trocar tipo de processo em projeto com andamento;
- preparar indicadores de gargalo por processo;
- melhorar pendencias por etapa e origem.

Ainda nao fazem parte desta fase:

- geracao de documentos DOCX/PDF;
- upload obrigatorio avancado;
- tomada de decisao assistida;
- automacoes WhatsApp;
- painel administrativo para editar templates;
- permissoes complexas por etapa.

---

## Fase 5 — Relatorios considerando modelos de processo

### Por que os relatorios precisam considerar etapas aplicaveis

Antes desta fase, os relatorios calculavam gargalos, atrasos e pendencias sem saber se a etapa era parte do processo do projeto.

Exemplo do problema anterior:
- Um projeto de CAR sendo contado como "atrasado em Cartorio" — mas Cartorio nao e etapa do CAR.
- CCIR aparecendo como pendente em Medicao — quando Medicao e opcional ou nao aplicavel ao CCIR.
- Projetos de Georreferenciamento Tecnico aparecendo como problema em Assinaturas quando o responsavel pelo cartorio e o SIGEF/INCRA.

Esses erros de contagem geravam inseguranca nos gestores: nao era possivel confiar nos numeros.

### Por que etapa NAO_APLICAVEL nunca e contada como atraso

O catalogo de etapas por processo (Fase 2) define que cada etapa pode ter applicability:
- `OBRIGATORIA` — faz parte do fluxo e deve ser executada;
- `OPCIONAL` — pode ser ativada manualmente se necessario;
- `CONDICIONAL` — depende de condicao do caso concreto;
- `NAO_APLICAVEL` — nao faz parte do processo.

Uma etapa NAO_APLICAVEL para aquele processo jamais deve ser contada como:
- atrasada;
- pendente;
- nao iniciada com problema;
- gargalo;
- falha do responsavel.

O relatorio v2 usa a tabela `projeto_etapas.applicability` para filtrar apenas etapas aplicaveis antes de calcular qualquer metrica.

### Como o checklist obrigatorio entra nos relatorios

Apos a Fase 4, os projetos possuem checklist real a partir dos templates por processo. Um item de checklist marcado como:
- `requirement_level = OBRIGATORIO` — e pendente quando o status nao e CONCLUIDO nem NAO_APLICAVEL;
- `blocks_stage_completion = 1` — bloqueia avanco da etapa enquanto pendente;
- `blocks_process_completion = 1` — bloqueia finalizacao do projeto enquanto pendente.

Os relatorios de Fase 5 exibem:
- Pendencias de checklist obrigatorio por etapa;
- Pendencias de checklist por tipo de processo;
- Contagem de itens criticos pendentes por responsavel;
- Lista completa de itens obrigatorios pendentes com filtros de criticidade e bloqueio.

### Como o gargalo por etapa e calculado

Gargalo por etapa e calculado somente sobre projetos cujo processo inclui aquela etapa como aplicavel.

Criterios de status:
- **Gargalo**: tempo medio >= 10 dias, OU mais de 10 projetos ativos, OU projeto parado ha 10+ dias;
- **Atencao**: tempo medio >= 5 dias, OU mais de 5 projetos ativos, OU projeto parado ha 5+ dias;
- **Normal**: abaixo desses limiares;
- **Sem dados**: nenhum projeto passou ou esta nessa etapa.

Os limiares estao em `report_helpers.THRESHOLDS` e podem ser ajustados sem tocar nos calculos.

### Como o gargalo por processo e calculado

Cada tipo de processo e analisado separadamente. O relatorio mostra:
- Tempo medio total do processo (do inicio ate encerramento ou hoje);
- Etapa onde o processo mais demora (a mais lenta em media);
- Checklist obrigatorio pendente no conjunto de projetos do tipo;
- Projetos parados dentro do tipo.

Isso permite o gestor entender: "Retificacao de Area Rural demora em media 38 dias, e o gargalo interno e Cartorio. CAR demora 12 dias e o gargalo e Escritorio."

### Como responsaveis sao analisados sem julgamento injusto

O relatorio de responsaveis mostra carga de trabalho e tempo — nao infere competencia.

- **Sobrecarga** = volume alto de projetos ativos (configuravel, default 12);
- **Atencao** = volume moderado (default 5);
- **Normal** = abaixo do limiar.

O relatorio nunca chama alguem de "lento" automaticamente. O gestor vê os dados e toma a decisao de redistribuir, contratar ou revisar processos.

### Como cidades e orgaos externos ajudam na gestao

O relatorio de cidades mostra distribuicao geografica, quantidade de projetos parados por cidade e o tipo de processo mais comum em cada cidade. Isso ajuda a identificar onde a empresa tem maior volume e onde pode ter problemas de capacidade local.

O relatorio de orgaos externos diferencia:
- Cartorio (registro de imoveis);
- SIGEF/INCRA;
- SICAR / orgao ambiental;
- SNCR/INCRA;
- Prefeitura;
- Advogado/Forum;
- Misto.

Isso e importante porque o tempo de espera no SIGEF/INCRA e diferente do tempo no cartorio local. Tratar tudo como "cartorio" escondia essa diferenca.

### O que fica para fases futuras

- Alertas automaticos quando projeto ficar parado acima do limiar;
- Notificacoes por WhatsApp ao responsavel;
- Painel de indicadores em tempo real;
- Exportacao de relatorios para PDF;
- Grafico de Gantt por projeto;
- Dashboard por perfil de acesso (gestor vs tecnico).

---

## Ajuste dos relatorios operacionais

### Visao geral simplificada

Os cards da visao geral foram redesenhados para mostrar o que o gestor realmente precisa:

1. **Projetos ativos** — quantos projetos estao em andamento.
2. **Projetos parados** — quantos estao ha muitos dias na mesma etapa.
3. **Maior gargalo** — etapa com maior acumulo ou tempo elevado.
4. **Em cartorio / orgao externo** — projetos aguardando retorno externo.
5. **Prazos criticos** — projetos com prazo vencido ou etapa em atraso.
6. **Responsavel com maior carga** — pessoa com mais projetos ativos.

Checklist foi removido dos cards principais. Ele e controle interno do projeto, nao metrica de gestao.

### Etapas agora mostram dados reais

A tabela de etapas exibe apenas colunas essenciais:
- Projetos ativos na etapa;
- Projetos concluidos;
- Tempo medio;
- Maior tempo parado;
- Status.

O sistema inclui projetos antigos (legados) via mapeamento de nomes:
"Cartorio" → Orgao externo, "Escritorio" → Escritorio/Pecas tecnicas, etc.
Isso evita que a tabela apareca zerada quando existem projetos ativos.

Etapas sem projetos ativos nem concluidos ficam ocultas para nao poluir a visao.

Quando ha projetos ativos mas ainda sem historico completo, aparece "sem historico suficiente" no tempo medio — nao "sem dados".

### Checklist nao e relatorio principal

O checklist continua existindo dentro de cada projeto (aba Checklist) e serve para:
- orientar a equipe;
- registrar progresso;
- indicar itens pendentes por etapa.

Porem, na tela de Relatorios nao existe mais aba ou contagem de checklist.
Com muitos projetos, o numero de itens de checklist vira ruido e nao ajuda a tomar decisao gerencial.

### Tempo de cartorio / orgao externo

O relatorio de orgaos externos mede somente o periodo em que o projeto ficou na etapa "Orgao externo" ou "Cartorio".
Nao usa o tempo total do projeto.

Isso permite comparar:
- "Projetos no Cartorio X ficam em media 14 dias."
- "Projetos no SIGEF/INCRA ficam em media 9 dias."

Sem confundir com projetos que duraram meses no total.

### Projetos antigos sem historico

Projetos criados antes dos modelos de processo serem aplicados podem nao ter historico de etapas completo.
Eles aparecem como "sem historico suficiente" no tempo medio.
Isso nao e erro — e informacao correta: ainda nao ha historico suficiente para calcular tempo medio.
O gestor pode usar o campo "Maior parado" como referencia enquanto o historico se forma.

### Relatorios servem para decisao gerencial

O objetivo dos relatorios e responder:
- Onde esta travando?
- Quem esta com carga alta?
- Qual cartorio esta segurando mais projetos?
- Quais projetos precisam de acao agora?

Nao e para controlar item por item.
E para controlar a empresa.
