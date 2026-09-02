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
  preservada, mais o painel "Despesas" com os indicadores da Fase 6.
- **Despesas** (`/financeiro/despesas`, rota `financeiro_despesas`) --
  lancamento manual, importacao em lote, classificacao.
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

`valor_total` so e `NOT NULL`/`> 0` fora dos status de rascunho (migration
`20260902_despesas_fase4_importacao.sql`). Cancelamento bloqueia se ja houver
reembolso confirmado sobre a despesa (precisa cancelar o reembolso primeiro).

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

Nao implementado nesta fase, de proposito:

- **Cobrancas**: transformar `despesa_alocacoes` (com `cliente_id` ja
  resolvido) em valor formalmente cobrado ao cliente. O dado ja existe
  (`custos_atribuidos_clientes` na Visao Geral mostra o total elegivel), mas
  a decisao de "isso virou cobranca" e um passo separado e consciente, nao
  automatico.
- **Recebimentos** e conciliacao avancada.
- Relatorio/PDF de cobranca.
- Historico de reembolsos com acao de cancelar na interface (a rota existe
  e e testada -- `financeiro_reembolsos_cancelar` -- so nao tem botao na
  tela ainda).

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
