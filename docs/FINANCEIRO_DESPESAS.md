# Financeiro - Modulo de Despesas

Este documento registra a decisao de produto e arquitetura do redesenho do
Financeiro focado em despesas, comprovantes, divisao de custos entre
projetos e reembolsos internos. Complementa (nao substitui)
`docs/DROPBOX.md` e `docs/CADASTRO_CLIENTES_DOCUMENTOS.md`.

## 1. Por que existe

O Financeiro antigo (`projeto_custos`/`projeto_pagamentos`) trata todo custo
como preso a um unico projeto e nao distingue quem de fato desembolsou o
dinheiro. Isso nao atende casos reais: uma nota de matricula que serve dois
projetos ao mesmo tempo, ou uma despesa pequena que um socio paga do proprio
bolso e precisa ser reembolsado depois -- sem confundir isso com o que o
*cliente* deve pagar.

O novo modulo trata **Despesa** como entidade propria, independente de
projeto, com divisao explicita entre um ou mais projetos e uma distincao
clara entre:

- **desembolso**: quem adiantou o dinheiro no mundo real (a empresa ou uma
  pessoa);
- **reembolso interno**: a empresa devolvendo esse adiantamento a uma
  pessoa;
- **cobranca ao cliente**: valor que a empresa vai cobrar de quem contratou
  o servico -- **isso ainda nao existe** neste modulo (ver secao 8).

## 2. Navegacao

`Financeiro` ganhou abas (`templates/_financeiro_tabs.html`, incluida com
`with context` -- ver nota tecnica na secao 9):

- **Visao geral** (`/financeiro`, rota `financeiro`) -- tela antiga,
  preservada, mais o painel "Despesas" com os indicadores da Fase 6 e os
  5 cards clicaveis da Fase 5/redesenho (Documentos para lancar, Total a
  cobrar, Proprietarios pendentes, Total cobrado, Reembolsos pendentes).
- **Lancamentos** (`/financeiro/lancamentos`, rota `financeiro_lancamentos`)
  -- tela principal de entrada de documentos, ver secao 10.
- **Despesas** (`/financeiro/despesas`, rota `financeiro_despesas`) --
  visao administrativa completa: lancamento manual, importacao em lote,
  classificacao, filtros, cancelamento.
- **Cobrancas** (`/financeiro/cobrancas`, rota `financeiro_cobrancas`) --
  agrupamento por proprietario das despesas prontas ainda nao cobradas, ver
  secao 11.
- **Reembolsos** (`/financeiro/reembolsos`, rota `financeiro_reembolsos`) --
  so aparece para quem tem `can_manage_despesas()`.

## 3. Modelo de dados

Todas as tabelas abaixo sao aditivas -- nenhuma coluna de
`projeto_custos`/`projeto_pagamentos` foi alterada ou removida. Migrations
em `docs/migrations/20260902_despesas_fase*.sql`.

```
despesas
  -> despesa_alocacoes   (divisao por projeto; cliente_id "retrato" do projeto)
  -> despesa_anexos      (comprovantes; "principal" marca a fonte-unica)
  -> despesa_eventos     (auditoria dedicada, texto-livre, por despesa_id)
  -> despesa_documento_analises_ia  (rascunho da leitura por IA, 1:1)

desembolsantes           (pessoas que podem desembolsar; "empresa" nao e uma linha aqui)
  <- despesas.desembolsado_por_id

despesa_lotes             (cabecalho de uma importacao em lote)
  <- despesas.lote_id

despesa_reembolsos
  -> despesa_reembolso_alocacoes  (quais despesas cada reembolso quita)
```

### `despesas`

Campos centrais: `descricao`, `categoria`, `valor_total` (NUMERIC, nullable
enquanto em rascunho -- ver Fase 4), `data_despesa`, `status`,
`desembolsado_por_tipo` (`EMPRESA`/`PESSOA`) + `desembolsado_por_id`,
`lote_id`, `origem` (`MANUAL`/`IMPORTACAO`/`MIGRACAO`),
`migrado_de_custo_id` (rastreabilidade da migracao), `registro_uid` (dedup
de duplo-submit, mesmo padrao do Financeiro antigo).

**"Empresa" nunca vira linha em `desembolsantes`.** Um `CHECK` garante isso:
`desembolsado_por_tipo='PESSOA'` exige `desembolsado_por_id` preenchido;
`'EMPRESA'` exige que seja `NULL`. Ver `expense_service.resolve_desembolsante`.

### Maquina de status

```
rascunho / pendente_classificacao   (documento importado, sem valor nem projeto ainda)
        |  usuario confirma valor, categoria, quem desembolsou e divide entre projetos
        v
classificada                        (valor confirmado, mas sem divisao completa -- raro:
                                      as rotas de criacao/classificacao ja exigem alocacao
                                      no mesmo passo, esse estado existe no modelo para uso
                                      futuro/defensivo)
        v
pronta                               (valor + divisao + desembolsante definidos)

cancelada                            (soft, a qualquer momento; nunca DELETE)
```

`valor_total` so e `NOT NULL`/`> 0` fora dos status de rascunho/pendente/**cancelada**
(migrations `20260902_despesas_fase4_importacao.sql` e
`..._fase9_permitir_cancelar_rascunho.sql` -- a fase4 tinha deixado de fora o
proprio `cancelada`, entao cancelar um documento importado que ainda nao
tinha `valor_total` -- o caso normal de descartar algo na fila de Lancamentos
-- violava a constraint e derrubava a rota com 500). Cancelamento bloqueia se
ja houver reembolso confirmado sobre a despesa (precisa cancelar o reembolso
primeiro).

### `despesa_alocacoes` -- cliente vem do projeto, nunca escolhido a mao

`cliente_id` e resolvido automaticamente (`expense_repository.resolve_projeto_cliente`)
a partir do proprietario principal do projeto (`projeto_proprietarios`, com
fallback para o `cliente_id` legado) no momento em que a alocacao e salva. A
soma das alocacoes precisa bater com `valor_total` (tolerancia de 1 centavo);
isso e validado em `expense_service.validate_allocations_sum` **antes** de
qualquer escrita no banco -- importante porque uma falha de validacao vira
`redirect` (302), nao um status HTTP de erro, e o `after_request` do app so
faz rollback em respostas >= 400. Ver o comentario correspondente em
`create_despesa`/`classificar_despesa`.

### Anexos -- uma unica pasta compartilhada

Diferente do Financeiro antigo (anexo dentro da pasta do projeto), o
comprovante de uma despesa fica em `Novo/_despesas/<ano>/<mes>` no Dropbox
(`dropbox_despesa_destination`), porque uma despesa pode ter mais de um
projeto e nao ha pasta de projeto "certa" para guardar o arquivo. Anexos
migrados de `projeto_custos` continuam apontando para o arquivo antigo,
dentro da pasta do projeto original -- nada foi movido.

O comprovante do reembolso em si (ex.: print do PIX) fica em
`Novo/_despesas/_reembolsos/<ano>/<mes>`, separado do comprovante da(s)
despesa(s) quitada(s).

Duplicidade por hash SHA-256 e checada (`expense_service.check_duplicate_anexo`):
na importacao em lote, hash identico e ignorado automaticamente (nao vira
rascunho duplicado); no lancamento manual/classificacao, so gera um aviso --
a despesa e salva do mesmo jeito e o usuario decide.

## 4. Reembolso interno

`desembolsado_por_tipo='EMPRESA'` nunca gera reembolso. `'PESSOA'` gera um
saldo pendente = `valor_total` menos o que ja foi reembolsado
(`despesa_reembolso_alocacoes` com `despesa_reembolsos.status='confirmado'`).

`expense_service.registrar_reembolso` quita integralmente as despesas
selecionadas (ou todas as pendentes da pessoa, se nenhuma for informada
explicitamente) numa unica operacao. O banco ja suporta reembolso parcial
(varias linhas de `despesa_reembolso_alocacoes` podem quitar a mesma despesa
aos poucos), mas a interface atual so oferece o caso integral.
`cancelar_reembolso` e soft e reabre a pendencia automaticamente, porque toda
consulta de saldo ja filtra por `status='confirmado'`.

## 5. Importacao em lote

`Financeiro -> Despesas -> Importar documentos`: varios arquivos de uma vez
(o caso de uso e baixar do WhatsApp e subir aqui -- **nao ha integracao com
WhatsApp**, o usuario baixa e importa manualmente). Cada arquivo vira uma
linha em `despesas` com `lote_id` preenchido -- nao existe uma tabela
`despesa_lote_itens` separada espelhando despesas, de proposito.
`despesa_lotes.total_documentos` e o progresso (`classificados`/`pendentes`)
e calculado ao vivo via `expense_repository.get_lote_progresso`/`list_lotes`.

## 6. Leitura de comprovantes por IA

Reaproveita 100% da infraestrutura ja usada nas notas de exigencia de
cartorio (`_groq_post`, `_extract_ai_source`, PyMuPDF para PDF/imagem,
fallback quando a IA falha ou nao esta configurada) -- ver
`app.py` a partir de `DESPESA_AI_PROMPT_VERSION`. So o prompt, o schema
estruturado e a normalizacao dos campos sao proprios de despesa (a
exigencia extrai uma **lista** de itens de checklist; despesa extrai um
**objeto** com os campos do comprovante: valor, data, estabelecimento, cnpj,
descricao, categoria sugerida, numero de documento).

Regras de seguranca (item 11 do pedido original, preservadas):

- A IA **nunca** decide projeto, cliente, quem desembolsou, divisao entre
  projetos ou qualquer movimentacao financeira -- so sugere campos do
  proprio comprovante (`_normalize_despesa_ai_fields` descarta qualquer
  valor que nao valide: numero invalido, data invalida, categoria
  desconhecida, CNPJ com tamanho errado viram `null`).
- O resultado e sempre um rascunho (`despesa_documento_analises_ia`,
  `status='rascunho'`) usado so para **pre-preencher o formulario de
  classificacao** -- nunca grava a despesa sozinho. So vira `'aplicado'`
  quando o usuario efetivamente confirma a classificacao.
- IA so roda quando o usuario clica em "Sugerir com IA", nunca durante o
  carregamento de pagina.

## 7. Permissoes

Novo, mais conservador que o `/financeiro` antigo de proposito (que hoje
nao verifica perfil nenhum -- isso foi preservado sem alteracao):

```python
can_view_despesas()       # qualquer usuario logado
can_manage_despesas()     # admin ou coordenador -- criar, classificar, cancelar, ver Reembolsos
can_register_reembolso()  # so admin -- registrar/cancelar reembolso
```

Registradas no `context_processor` global (`utility_processor`) para uso
direto em templates.

## 8. O que fica para depois

Nao implementado ainda, de proposito:

- **Recebimentos** e conciliacao avancada (o quarto status visual,
  "Resolvido", esta reservado para isso -- ver secao 11).
- Relatorio/PDF de cobranca.
- Historico de reembolsos com acao de cancelar na interface (a rota existe
  e e testada -- `financeiro_reembolsos_cancelar` -- so nao tem botao na
  tela ainda).
- Cobranca de uma despesa cujas alocacoes apontem para clientes diferentes
  (ver secao 11 -- fica de fora da Fase 1 do fluxo de cobrancas, tratada
  manualmente por enquanto).

**Cobrancas foi implementado** (ver secao 11) -- esta secao descrevia isso
como pendente antes do redesenho "caixa de entrada de documentos".

## 9. Notas tecnicas

- `expense_repository.py`/`expense_service.py` seguem o mesmo padrao de
  `person_repository.py`/`representation_service.py`: recebem `db`
  explicitamente, sem conexao propria, chamados a partir de rotas finas em
  `app.py`. Nenhum Blueprint foi introduzido (o app nao tinha nenhum antes).
- **Import de macro com `with context`**: `_financeiro_tabs.html` chama
  `can_manage_despesas()` (valor do context processor). Um macro importado
  via `{% from ... import ... %}` sem `with context` nao enxerga esses
  valores -- isso quebrou silenciosamente na primeira versao da aba
  Reembolsos e foi corrigido adicionando `with context` nas tres
  importacoes (`financeiro.html`, `despesas.html`, `reembolsos.html`).
- Todas as migrations desta feature (`docs/migrations/20260902_despesas_*.sql`)
  sao aditivas ou relaxam uma restricao sem afetar dado existente; cada uma
  foi conferida com uma consulta direta no banco antes e depois de aplicar.
- Os 46 custos de `projeto_custos` existentes antes desta feature foram
  migrados 1:1 para `despesas` (100% desembolsado pela empresa, 1 alocacao
  de 100% para o mesmo projeto, mesmo comprovante sem mover arquivo). A
  migracao e idempotente via `migrado_de_custo_id`; `expense_service.migrate_custo`/
  `migrate_pending_custos` permitem rodar o mesmo backfill de novo para
  custos lancados depois pela tela antiga (que continua existindo e **nao**
  espelha automaticamente em `despesas`).

## 10. Lancamentos -- caixa de entrada de documentos

`/financeiro/lancamentos` e a tela principal para o caso de uso real da
empresa: funcionario volta do cartorio com varios comprovantes pequenos
(matricula, reconhecimento de firma, certidao, taxa) e precisa lancar todos
rapido. Nao e uma tela nova de dados -- e uma camada de UX sobre a mesma
`despesas`/`despesa_alocacoes`/importacao em lote/IA ja descritas acima.

- **Fila**: `expense_repository.list_fila_lancamento` lista despesas em
  `rascunho`/`pendente_classificacao` (a mesma importacao em lote da secao 5
  alimenta essa fila -- o dropzone da tela posta pro mesmo
  `financeiro_despesas_importar`, so com `destino=lancamentos` redirecionando
  de volta pra ca em vez de para Despesas).
- **Proprietario -> projeto**: o formulario pede o cliente primeiro
  (`fetch_cliente_autocomplete_options`, o mesmo autocomplete generico de
  cliente ja usado em outras telas via `initProjectClientAutocompletes`) e so
  entao mostra os projetos dele (`GET /api/clientes/<id>/projetos`, que usa
  `expense_repository.list_projetos_do_cliente` -- indexado por cliente, nao
  carrega todos os projetos). Buscar qualquer projeto diretamente continua
  possivel: a mesma caixa de busca mistura os projetos do proprietario
  (primeiro) com o restante (`window.despesaProjetosOptions`, o preload ja
  usado em Despesas).
- **Alocacao automatica de 100%**: `expense_service.classificar_despesa_rapida`
  chama `classificar_despesa` (a mesma funcao de sempre) montando sozinha
  `alocacoes=[{"projeto_id": ..., "valor": valor_total}]`. Dividir entre
  varios projetos continua so na tela completa de Despesas.
- **IA automatica**: ao abrir um documento, o JS chama o MESMO endpoint
  `api_despesa_ai_analysis` de Despesas (GET pra ver se ja tem rascunho,
  senao POST pra analisar) -- nao existe uma segunda leitura por IA nem um
  segundo prompt. Falha da IA nunca bloqueia: o endpoint sempre devolve um
  `analysis` aplicavel (mesmo que com campos vazios), e o formulario continua
  editavel manualmente.
- **"Salvar e proximo" sem reload**: `POST /financeiro/lancamentos/<id>/salvar-proximo`
  chama `classificar_despesa_rapida` e devolve o proximo item da fila em
  JSON. A rota distingue o pedido via header `X-Requested-With: XMLHttpRequest`
  (mandado pelo `fetch` do JS): sem esse header, cai no comportamento
  classico do resto do modulo -- `flash` + redirect de volta pra
  `/financeiro/lancamentos` -- caso o JS falhe em anexar o listener de
  submit (fallback seguro, item 15 do pedido original).

## 11. Cobrancas -- formalizar a divida do proprietario

`/financeiro/cobrancas` fecha o ciclo que a secao 8 (versao anterior deste
documento) descrevia como pendente: transformar despesas `pronta` (valor +
divisao + desembolsante definidos) em uma cobranca formal ao cliente.

- **Elegibilidade**: so entra despesa com status `pronta`, nao cancelada,
  cujas alocacoes apontem para um UNICO cliente (`HAVING COUNT(*) =
  COUNT(a.cliente_id) AND COUNT(DISTINCT a.cliente_id) = 1` em
  `list_despesas_a_cobrar_por_cliente`/`list_despesas_a_cobrar_do_cliente`) e
  que ainda nao esteja numa cobranca ativa. Uma despesa dividida entre
  clientes diferentes fica de fora por enquanto (ver secao 8).
- **Modelo**: `cobrancas` (cabecalho: cliente, valor total, data, status
  `ativa`/`cancelada`, auditoria) e `cobranca_itens` (quais despesas, com um
  `status` proprio `ativo`/`cancelado` que espelha o status da cobranca-pai
  no momento -- existe so para viabilizar o indice unico parcial
  `idx_cobranca_itens_despesa_ativa` (`WHERE status = 'ativo'`), ja que
  Postgres nao aceita subquery entre tabelas num predicado de indice.
  Migrations `docs/migrations/20260902_despesas_fase7_cobrancas.sql`
  (tabelas) e `..._fase8_cobranca_registro_uid.sql` (dedup de duplo-envio,
  mesmo padrao de `despesas.registro_uid`).
- **Criar**: `expense_service.criar_cobranca` reconfere elegibilidade e
  ausencia de cobranca ativa ANTES de escrever (mesmo motivo de sempre: um
  erro de validacao vira redirect 302, que o `after_request` nao reverte).
  `registro_uid` torna reenvio idempotente.
- **Cancelar**: `cancelar_cobranca` e soft -- `cancel_cobranca_and_itens`
  atualiza `cobrancas.status` E `cobranca_itens.status` na mesma chamada. As
  despesas reaparecem em "a cobrar" automaticamente (nenhuma consulta
  precisa saber que houve um cancelamento; ela so filtra por
  `status = 'ativo'`/`'ativa'`).
- **Camadas de apresentacao** (item 11 do pedido original, so visual --
  nenhum status novo de `despesas` foi criado): "Para lancar" =
  `rascunho`/`pendente_classificacao`; "A cobrar" = `pronta` sem cobranca
  ativa; "Cobrado" = tem `cobranca_itens` ativo; "Resolvido" fica reservado
  para quando houver recebimento/baixa (secao 8).
