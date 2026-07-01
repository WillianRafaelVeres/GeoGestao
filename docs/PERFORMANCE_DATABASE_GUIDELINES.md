# Performance e Banco de Dados - Diretrizes do GeoGestao

Este documento transforma o relatorio de performance em regras praticas para o
GeoGestao. A meta e melhorar fluidez sem quebrar seguranca, permissoes ou dados.

## Regra principal

Nao otimizar no escuro.

Antes de mexer em query, cache, indice ou fluxo de tela, medir a situacao atual:

```bash
python scripts/measure_routes.py --runs 3
```

Depois da mudanca, repetir o mesmo comando e registrar o resultado em
`docs/PERFORMANCE_BASELINE.md` quando a diferenca for relevante.

## Ordem de investigacao

1. Tempo total da rota.
2. Tempo gasto no banco.
3. Quantidade de queries.
4. Tamanho do HTML/JSON entregue.
5. Repeticao de dados que poderiam vir em lote.
6. Plano de execucao da query quando uma consulta especifica for lenta.

## Consultas SQL

- Evitar N+1: uma lista de projetos nao deve consultar checklist, pendencias ou
  responsaveis projeto por projeto.
- Preferir agregacoes em lote com `JOIN`, `WITH`, `GROUP BY`, `FILTER` e
  `DISTINCT ON` quando isso reduzir idas ao banco.
- Evitar `SELECT *` nas telas de maior trafego, principalmente matriz, clientes,
  missoes e relatorios. Use somente colunas necessarias quando a tabela crescer.
- Filtrar no SQL, nao em Python, quando o filtro depende de dados do banco.
- Usar `LIMIT`/paginacao em listas que possam crescer.
- Nao ordenar grandes conjuntos por expressoes sem indice antes de validar com
  plano de execucao.

## Indices

Indices devem nascer de uma query real, nao de palpite.

Antes de criar indice, responder:

- Qual rota esta lenta?
- Qual query esta lenta?
- Qual `WHERE`, `JOIN` ou `ORDER BY` sera beneficiado?
- Existe risco de piorar escrita por excesso de indices?

Preferir `CREATE INDEX IF NOT EXISTS` em ambiente pequeno e
`CREATE INDEX CONCURRENTLY` quando houver uso real em producao.

Nao remover indice apenas por alerta de "unused index" se o banco acabou de ser
zerado, migrado ou ainda tem pouco historico de uso.

## Cache

Cache permitido quando:

- o dado muda pouco;
- varias rotas reutilizam o mesmo dado;
- existe TTL curto;
- existe invalidacao apos escrita relacionada.

No app atual, os caches de lookup e relatorios devem continuar pequenos e com
TTL. Ao criar, editar ou excluir projetos/clientes/tipos auxiliares, chamar a
invalidacao de runtime quando a tela depender desses dados.

## Transacoes

- Manter transacoes curtas.
- Nao fazer chamada externa, envio de email ou trabalho pesado dentro de
  transacao aberta.
- Em criacao de projeto, manter insercao do projeto, workflow, etapa inicial,
  prioridade e historico em uma unica transacao.
- Ao falhar, fazer rollback e preservar a mensagem de erro para diagnostico.

## Conexoes

- Usar pool de conexoes no app.
- Em hospedagem gratuita ou com limite baixo, manter poucos workers/processos.
- Preferir a connection string do Supabase Pooler em ambiente hospedado.
- Ajustar `GEOGESTAO_DB_POOL_MAXCONN` com cuidado para nao exceder limites do
  plano do Supabase.

## Frontend e navegacao

- Evitar que troca de aba carregue dados que nao aparecem na primeira tela.
- Em telas pesadas, carregar primeiro o essencial e deixar detalhe para clique.
- Evitar submits duplicados bloqueando botoes durante salvamento.
- Mostrar estado de carregamento curto e claro.
- Quando uma acao gravar dados, ela deve invalidar caches necessarios e nao
  reprocessar listas inteiras sem necessidade.

## Observabilidade

Toda resposta HTTP agora recebe:

- `X-Request-ID`
- `Server-Timing`

O `Server-Timing` informa tempo total da aplicacao, tempo de banco e numero de
queries medidas no request. Para log no servidor, ligar:

```text
GEOGESTAO_PERF_LOG=1
```

Ao investigar lentidao reportada por usuario, pedir rota, horario aproximado e,
se possivel, o `X-Request-ID`.

## Checklist antes de aprovar uma mudanca de performance

- O comportamento funcional continuou igual?
- Login/permissoes continuam intactos?
- Nenhum dado real foi apagado ou sobrescrito em massa?
- O benchmark antes/depois foi comparado?
- A quantidade de queries nao aumentou sem motivo?
- A mudanca tem escopo claro?
- A documentacao ou baseline foi atualizada quando necessario?
