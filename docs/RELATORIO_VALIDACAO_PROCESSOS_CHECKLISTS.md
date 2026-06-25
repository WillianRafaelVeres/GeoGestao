# Relatorio de Validacao - Processos e Checklists do GeoGestao

Fonte analisada: `c:\Users\willi\Downloads\Plano_GeoGestao_Processos_Checklists.docx`.

Observacao: o arquivo nao estava em `docs/`, mas foi possivel ler o DOCX informado na pasta Downloads. A analise abaixo tambem considera o codigo atual do sistema Flask/Jinja/PostgreSQL.

## 1. Resumo executivo

A logica proposta e viavel e faz sentido para o GeoGestao.

O ponto principal e que a matriz deve continuar simples, com etapas macro gerais, enquanto o detalhe de cada projeto deve carregar checklists, documentos e regras especificas conforme o tipo de processo.

O sistema atual ja tem uma boa base para isso:

- projetos;
- tipo de servico;
- etapas macro;
- checklist por etapa;
- tarefas;
- pendencias;
- historico de movimentacao;
- relatorios por etapa.

Mas ainda falta uma camada essencial: modelos de processo.

Hoje o sistema cria praticamente o mesmo fluxo para todos os projetos. Para a logica do plano funcionar bem, o GeoGestao precisa separar:

- etapa macro geral;
- modelo do tipo de processo;
- checklist especifico;
- documento exigido;
- regra de etapa obrigatoria, opcional ou nao aplicavel.

Recomendacao: seguir com a arquitetura proposta, mas implementar por fases, sem transformar a matriz em uma tela pesada.

## 2. Situacao atual do sistema

### Projetos

O projeto atual guarda dados como:

- nome;
- cliente/proprietario;
- cidade e UF;
- cartorio/orgao externo;
- tipo de servico;
- valor;
- pasta;
- status;
- etapa atual.

O campo `tipo_servico` ja existe e aparece na criacao e nos detalhes do projeto. Na matriz, ele aparece como o processo principal. Porem, hoje ele funciona apenas como informacao textual. Ele ainda nao muda automaticamente etapas, checklists, documentos ou regras.

### Etapas

As etapas macro existem em `DEFAULT_STAGES` no codigo e sao persistidas em `etapas_modelo` no banco.

Etapas atuais encontradas:

1. Orcamento
2. Documentos
3. Analise
4. Medicao
5. Processamento
6. Escritorio
7. Planta
8. Documentacao
9. Assinaturas
10. Cartorio
11. Pendencia
12. Finalizado

O sistema normaliza essas etapas e mantém a ordem pelo campo `ordem`, nao por ordem alfabetica.

### Criacao automatica de etapas

Ao criar um projeto, a funcao de criacao de etapas cria todas as etapas ativas para o projeto.

Isso significa que, hoje, todo projeto recebe o mesmo conjunto de etapas macro, independentemente do tipo de servico.

Esse comportamento ajuda a matriz ficar consistente, mas ainda nao atende bem processos que nao passam por campo, cartorio, assinaturas, SIGEF, SICAR ou SNCR.

### Checklist interno

Existe checklist por etapa.

O sistema usa o checklist definido em `DEFAULT_STAGES` para criar itens em `checklist_itens`.

Exemplo:

- Documentos: matricula recebida, documentos pessoais, documentos do imovel etc.
- Medicao: campo agendado, equipe definida, levantamento executado etc.
- Cartorio: protocolo registrado, exigencias acompanhadas etc.

Esse checklist e generico por etapa. Ainda nao existe checklist especifico por tipo de processo.

### Tarefas

O sistema possui tarefas vinculadas a projeto e, opcionalmente, a uma etapa.

Elas possuem:

- titulo;
- descricao;
- responsavel;
- prioridade;
- status;
- prazo.

Hoje as tarefas nao sao geradas com base no tipo de processo. Elas podem ser criadas manualmente ou por algumas acoes do sistema.

### Documentos

A aba "Documentos" nos detalhes do projeto mostra, na pratica, os itens de checklist por etapa.

Ainda nao existe uma entidade clara de documento exigido por tipo de processo, como:

- matricula;
- CND;
- TRT;
- planta;
- memorial;
- requerimento;
- declaracao;
- recibo CAR;
- planilha SIGEF;
- comprovante SNCR/CCIR.

Portanto, a aba Documentos ainda nao esta preparada para controlar documentos especificos por processo de forma completa.

### Pendencias

As pendencias existem e estao bem encaminhadas.

Elas podem ser vinculadas a:

- projeto;
- etapa;
- origem;
- responsavel;
- prazo;
- status.

Isso e suficiente para evoluir para pendencias especificas por processo, como exigencia de cartorio, sobreposicao SIGEF, documento faltante, pendencia SICAR ou pendencia do cliente.

### Historico

O sistema registra movimentacoes de etapa em `movimentacoes_etapa`.

Tambem existe uma estrutura de historico de etapa em `project_stage_history`, usada pelos relatorios para medir dias em etapa.

Isso e uma boa base para relatorios operacionais, mas ainda precisa ser integrado com os futuros modelos de processo para saber quais etapas eram obrigatorias, opcionais ou nao aplicaveis em cada projeto.

### Relatorios

Os relatorios foram evoluidos para uma leitura operacional em dias.

Hoje ja existe base para:

- status por etapa;
- gargalos;
- responsaveis;
- cidades;
- cartorios;
- projetos parados.

Porem, como todos os projetos ainda recebem o mesmo conjunto generico de etapas, os relatorios ainda nao distinguem bem se uma etapa esta realmente atrasada ou simplesmente nao se aplica ao processo.

## 3. O que o plano propoe

O plano propoe manter a matriz simples e transferir a complexidade para dentro do projeto.

A logica desejada e:

- etapas macro gerais para manter a visao operacional limpa;
- tipo de processo escolhido na criacao do projeto;
- modelo de processo aplicado automaticamente;
- checklist especifico por tipo de processo;
- documentos exigidos conforme processo;
- etapas obrigatorias, opcionais e nao aplicaveis;
- etapas externas diferentes conforme o caso: cartorio, SIGEF, SICAR, SNCR, prefeitura, tabelionato, advogado ou forum;
- finalizacao diferente conforme o processo.

Processos citados no plano:

- Tomada de Decisao;
- Retificacao de Area Rural;
- Desmembramento;
- Destacamento / Estremacao / Extincao de Condominio;
- Usucapiao;
- Georreferenciamento Tecnico;
- Unificacao;
- Medicao;
- Regularizacao de Titularidade;
- Cadastro Ambiental Rural - CAR;
- Certificacao SIGEF;
- Atualizacao de CCIR.

O Manual 00, de Tomada de Decisao, nao e exatamente um processo produtivo final. Ele deve virar uma ajuda na escolha do tipo de processo.

## 4. A ideia vai funcionar?

Sim, a ideia funciona, mas o sistema precisa de ajustes estruturais.

O que ja favorece a implementacao:

- a matriz ja trabalha com etapas macro;
- cada projeto ja tem tipo de servico;
- o sistema ja cria etapas do projeto;
- ja existe checklist por etapa;
- ja existe vinculo de tarefa com etapa;
- ja existe pendencia por etapa;
- ja existe historico de movimentacao;
- ja existem relatorios por etapa.

O que impede a ideia de funcionar corretamente hoje:

- o tipo de servico ainda nao aplica um modelo;
- todos os projetos recebem as mesmas etapas;
- o checklist ainda e generico;
- nao existe conceito de etapa opcional ou nao aplicavel;
- nao existe documento exigido por processo;
- nao existe regra de bloqueio por item obrigatorio critico;
- nao existe finalizacao diferente conforme o tipo de processo.

Conclusao: a base atual suporta evolucao, mas ainda nao deve receber os checklists do plano diretamente no modelo atual. Antes, e necessario criar a camada de modelos de processo.

## 5. Principais lacunas encontradas

1. Nao existe modelo de processo.

O sistema tem `tipo_servico`, mas ele nao controla comportamento.

2. Checklist esta fixo por etapa macro.

Hoje o checklist vem de `DEFAULT_STAGES`, nao de Retificacao, CAR, SIGEF, CCIR etc.

3. Todos os projetos recebem todas as etapas.

Isso gera problema para processos que terminam cedo ou que nao passam por campo, cartorio ou assinaturas.

4. Nao existe etapa nao aplicavel.

O sistema conhece status como em andamento, concluido, atrasado, atencao e outros, mas nao tem um conceito claro de "nao se aplica" por processo.

5. Nao existe etapa opcional condicional.

Exemplo: Medicao em CAR deveria aparecer apenas se o perimetro estiver ruim ou se o cliente contratou campo.

6. Nao existe documento exigido por processo.

A aba Documentos usa checklist, mas ainda nao separa documentos reais obrigatorios, opcionais, anexos e entregaveis.

7. Nao existe regra de checklist critico para bloquear avanco.

O sistema permite controlar itens, mas ainda nao sabe quais itens impedem protocolo, entrega ou conclusao.

8. Tipo de servico nao altera tarefas.

As tarefas nao sao criadas a partir do modelo do processo.

9. Relatorios ainda nao sabem o que nao se aplica.

Sem essa informacao, uma etapa sem movimentacao pode parecer problema, quando na verdade nao fazia parte daquele processo.

10. A aba Etapas ainda mostra uma estrutura generica.

Ela esta pronta para evoluir, mas ainda nao mostra modelo especifico por processo.

## 6. Arquitetura recomendada

A arquitetura recomendada deve manter o sistema simples, com camadas separadas.

### 1. Etapas macro gerais

Sao as grandes fases que aparecem na matriz.

Elas devem continuar estaveis e poucas. Exemplos:

- Orcamento;
- Documentos;
- Analise / Viabilidade;
- Medicao / Campo;
- Processamento;
- Escritorio / Pecas;
- Conferencia;
- Assinaturas / Anuencias;
- Orgao externo;
- Pendencias / Exigencias;
- Entrega / Encerramento.

### 2. Modelo de processo

Define o caminho padrao de cada tipo de servico.

Exemplo: CAR nao deve usar cartorio por padrao. Certificacao SIGEF termina no SIGEF, nao no cartorio, salvo contratacao adicional.

### 3. Etapas do modelo

Define, para cada processo, quais etapas sao:

- obrigatorias;
- opcionais;
- condicionais;
- nao aplicaveis.

### 4. Checklist por processo

Define os itens internos de cada etapa.

Exemplo:

- Retificacao exige confrontantes, Art. 213, anuencias e protocolo cartorial.
- CAR exige APP, Reserva Legal, uso do solo, recibo/demonstrativo.
- CCIR exige SNCR/DCR, taxa e emissao do certificado.

### 5. Documentos exigidos

Deve separar checklist operacional de documento real.

Checklist e "fazer algo".

Documento exigido e "ter ou entregar um arquivo/informacao".

### 6. Regras de avanco

Define o que bloqueia avanco, protocolo ou entrega.

Nem todo item pendente deve bloquear o projeto. Apenas itens obrigatorios criticos.

### 7. Historico

Guarda quando o projeto entrou e saiu de cada etapa, quem era responsavel e por que mudou.

Isso alimenta relatorios confiaveis.

### 8. Pendencias

Pendencias devem continuar vinculadas ao projeto e etapa, mas com origem mais clara:

- cliente;
- cartorio;
- campo;
- escritorio;
- SIGEF;
- SICAR;
- SNCR;
- prefeitura;
- advogado;
- tabelionato.

### 9. Relatorios

Relatorios devem considerar apenas etapas aplicaveis ao processo.

Isso evita medir "atraso" em etapa que nunca deveria existir naquele tipo de servico.

## 7. Modelo de dados recomendado

Sem implementar agora, o modelo recomendado e:

### ProcessType

Representa o tipo de processo.

Exemplos:

- RETIFICACAO_RURAL;
- DESMEMBRAMENTO;
- CAR;
- SIGEF;
- CCIR;
- MEDICAO;
- USUCAPIAO.

Serve para padronizar nomes e evitar texto livre sem controle.

### ProcessTemplate

Representa o modelo operacional de um processo.

Exemplo: Modelo de Retificacao Rural.

Define:

- nome;
- descricao;
- quando usar;
- onde normalmente termina;
- se depende de campo;
- se depende de orgao externo.

### ProcessStageTemplate

Representa uma etapa dentro de um modelo.

Campos conceituais:

- etapa macro;
- ordem;
- obrigatoriedade;
- condicao;
- responsavel padrao;
- prazo padrao;
- pode ser pulada;
- bloqueia entrega.

### ChecklistItemTemplate

Representa item de checklist padrao do processo.

Campos conceituais:

- texto do item;
- etapa vinculada;
- obrigatorio, recomendado ou opcional;
- condicao de exibicao;
- responsavel padrao;
- permite anexo;
- bloqueia avanco;
- bloqueia protocolo;
- bloqueia entrega.

### RequiredDocumentTemplate

Representa documento exigido por processo.

Exemplos:

- matricula;
- CCIR;
- CAR;
- CND;
- planta;
- memorial;
- TRT;
- requerimento;
- recibo SICAR;
- planilha SIGEF;
- comprovante CCIR.

### ProjectStage

Representa a etapa real de um projeto.

Deve ser criada a partir do modelo, mas permitir ajuste manual.

### ProjectChecklistItem

Representa o item real do checklist daquele projeto.

Deve guardar:

- status;
- responsavel;
- data de conclusao;
- observacao;
- anexo ou caminho de arquivo;
- se foi marcado como nao aplicavel.

### ProjectRequiredDocument

Representa documento real exigido para aquele projeto.

Serve para diferenciar documento pendente de tarefa operacional.

### ProjectStageHistory

Representa historico de entrada e saida de etapas.

Ja existe uma base parecida no sistema. Ela deve continuar e ser usada nos relatorios.

## 8. Como deve funcionar ao criar um projeto

Fluxo recomendado:

1. Usuario cria projeto.

Preenche nome do projeto, cliente/proprietario, cidade, cartorio/orgao se houver, pasta e observacoes.

2. Usuario escolhe o tipo de processo.

Exemplos: Retificacao, CAR, SIGEF, CCIR, Medicao.

3. Sistema carrega o modelo daquele processo.

O modelo define etapas, checklist, documentos e regras.

4. Sistema cria as etapas aplicaveis.

Nem todas as etapas macro precisam virar etapa ativa do projeto.

5. Sistema cria checklist especifico.

O checklist deve ser diferente para Retificacao, CAR, CCIR, SIGEF etc.

6. Sistema marca etapas nao aplicaveis.

Elas podem ficar ocultas nos detalhes ou aparecer como "nao aplicavel", mas nao devem confundir o gestor.

7. Sistema cria documentos exigidos.

Aba Documentos deve mostrar o que falta e o que ja foi entregue.

8. Matriz continua simples.

A matriz mostra apenas a etapa atual e informacoes essenciais.

## 9. Como deve funcionar na matriz

A matriz nao deve exibir checklist detalhado.

Ela deve continuar mostrando:

- projeto;
- cliente/proprietario;
- tipo de processo;
- cartorio/orgao externo quando houver;
- etapa atual;
- responsavel;
- status;
- prazo;
- pendencias.

O checklist fica dentro do projeto.

Motivo: se cada processo colocar seus itens na matriz, a tela vira uma planilha gigante e perde a funcao principal: leitura rapida da empresa.

## 10. Como deve funcionar dentro do projeto

### Aba Resumo

Deve mostrar:

- dados principais;
- tipo de processo;
- etapa atual;
- responsavel;
- prazo;
- pendencias importantes;
- pasta do projeto.

### Aba Etapas

Deve mostrar as etapas aplicaveis daquele processo.

Cada etapa deve indicar:

- obrigatoria;
- opcional;
- nao aplicavel;
- em andamento;
- concluida;
- bloqueada por pendencia.

### Aba Checklist

Pode ser uma aba propria ou ficar dentro de Etapas.

Deve mostrar os itens especificos do processo.

Cada item deve ter:

- status;
- responsavel;
- obrigatoriedade;
- observacao;
- anexo/caminho;
- historico.

### Aba Documentos

Deve mostrar documentos exigidos para aquele processo.

Exemplo:

- Retificacao: planta, memorial, TRT, requerimento, Art. 213, anuencias.
- CAR: recibo, demonstrativo, mapa, pendencias SICAR.
- SIGEF: planilha, comprovantes, certificacao ou relatorio de pendencia.
- CCIR: comprovante, taxa, CCIR emitido.

### Aba Pendencias

Deve continuar existindo, mas com origem mais especifica.

Exemplo:

- pendencia do cliente;
- exigencia de cartorio;
- sobreposicao SIGEF;
- pendencia SICAR;
- documento faltante;
- duvida de campo.

### Aba Historico

Deve registrar:

- mudanca de etapa;
- conclusao de checklist critico;
- criacao e resolucao de pendencia;
- protocolo em orgao externo;
- retorno de exigencia;
- reabertura ou retrabalho.

## 11. Riscos se implementar errado

1. Matriz poluida.

Se os checklists forem parar na matriz, a tela deixa de ser gerencial.

2. Checklist generico demais.

Se todos os processos usarem o mesmo checklist, o sistema nao ajuda de verdade.

3. Usuario se perde.

Se CAR, SIGEF, CCIR, retificacao e medicao parecerem iguais, a equipe vai continuar dependendo de memoria e conversa.

4. Documento errado exigido no processo errado.

Exemplo: exigir documento cartorial em CAR simples, ou tratar Medicao como regularizacao cartorial.

5. Relatorio inconsistente.

Se etapa nao aplicavel for tratada como etapa atrasada ou nao iniciada, o gestor vai tirar conclusoes erradas.

6. Sistema rigido demais.

O processo real tem excecoes. O sistema precisa permitir ativar etapa opcional quando necessario.

7. Bloqueio excessivo.

Nem todo item pendente deve impedir avanco. Apenas item obrigatorio critico.

8. Confusao entre orgaos externos.

Cartorio, SIGEF, SICAR, SNCR, prefeitura, tabelionato e advogado nao devem ser tratados como se fossem todos "cartorio".

## 12. Melhor ordem de implementacao

### Fase 1 - Criar catalogo de tipos de processo

Padronizar os tipos de servico.

Resultado: o sistema deixa de depender apenas de texto livre.

### Fase 2 - Criar modelos de etapa e checklist por processo

Criar a camada de modelos sem mudar a matriz.

Resultado: cada tipo de processo passa a ter seu caminho padrao.

### Fase 3 - Aplicar modelo na criacao de projeto

Ao escolher o tipo de processo, o sistema cria etapas, checklist e documentos aplicaveis.

Resultado: projeto novo ja nasce com a estrutura correta.

### Fase 4 - Ajustar detalhes do projeto

Melhorar abas de Etapas, Checklist, Documentos e Pendencias para mostrar a estrutura especifica do processo.

Resultado: usuario trabalha dentro do projeto sem ver informacao desnecessaria.

### Fase 5 - Ajustar relatorios

Relatorios devem considerar somente etapas aplicaveis.

Resultado: gargalos e tempos ficam confiaveis.

### Fase 6 - Refinar documentos e pendencias

Vincular documentos exigidos, anexos, caminho de pasta e pendencias por processo.

Resultado: o sistema passa a controlar melhor a preparacao para protocolo, entrega ou encerramento.

### Fase 7 - Tomada de decisao assistida

Transformar o Manual 00 em perguntas simples na criacao do projeto.

Resultado: o sistema ajuda a escolher o processo correto.

## 13. O que NAO implementar ainda

Nao recomendo implementar agora:

- geracao automatica de documentos;
- preenchimento de DOCX/PDF;
- automacoes complexas;
- WhatsApp;
- controle financeiro avancado;
- permissoes complexas por etapa;
- relatorios muito avancados antes dos dados de processo estarem corretos;
- telas grandes para configurar tudo de uma vez;
- matriz diferente para cada tipo de processo.

O proximo passo deve ser estrutural: modelos de processo e checklists especificos.

## 14. Conclusao

Recomendo seguir com a arquitetura proposta.

A ideia do plano esta correta: manter a matriz simples e criar inteligencia dentro do projeto conforme o tipo de processo.

O sistema atual ja tem base suficiente para evoluir sem jogar tudo fora, mas ainda esta muito generico. Ele precisa de uma camada de modelos de processo para que Retificacao, Desmembramento, CAR, SIGEF, CCIR, Medicao, Usucapiao e os demais fluxos tenham checklists e documentos proprios.

Decisao recomendada antes de programar:

1. Validar os nomes finais das etapas macro com a equipe.
2. Validar os checklists de cada processo com quem executa a operacao.
3. Criar o catalogo de tipos de processo.
4. Depois implementar modelos de etapa, checklist e documentos.

Resposta pratica para Rafael:

Sim, vai dar certo. Mas nao deve ser implementado colocando todos os checklists na matriz. O caminho correto e criar modelos por tipo de processo, aplicar esses modelos ao projeto e manter a matriz apenas como visao gerencial simples.
