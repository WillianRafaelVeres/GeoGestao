# Otimizacao profunda de performance - 2026-07-10

## Diagnostico

O custo dominante e a latencia acumulada entre Flask e PostgreSQL remoto. Nas
medicoes iniciais, `/projects` gastou 714,6 ms de 819,2 ms no banco e
`/project/15` gastou 1.125,1 ms de 1.228,9 ms no banco.

## Mudancas aplicadas

- Anotacoes usam atualizacao otimista: aparecem imediatamente e sincronizam ao
  fundo, com restauracao do texto em caso de erro.
- `Enter` envia a anotacao; `Shift+Enter` continua inserindo nova linha.
- Validacao do projeto e insercao da anotacao foram unificadas em um SQL.
- Toggles dos dois modelos de checklist agora atualizam item, contadores e
  progresso em uma unica transacao/viagem ao banco.
- Checklists mudam visualmente antes da resposta e revertem em caso de falha.
- Pendencias, anotacoes e protocolos da matriz passaram de tres consultas para
  uma consulta agregada.
- Exigencias, pendencias, historico e timeline do detalhe do projeto passaram de
  quatro consultas para uma consulta agregada.

## Resultado medido

Mesmo ambiente local conectado ao Supabase remoto:

| Rota | Antes | Depois observado | Reducao |
| --- | ---: | ---: | ---: |
| `/projects` | 819,2 ms | 303,7 ms | 62,9% |
| `/project/15` | 1.228,9 ms | 826,3 ms | 32,8% |

Os tempos absolutos variam com rede, cache e atividade do plano do banco. A
quantidade de viagens removida e permanente.

## Limites que exigem infraestrutura ou mudanca de produto

- Flask e Supabase devem ficar na mesma regiao ou na menor distancia disponivel.
  Isso e configuracao de hospedagem, nao uma mudanca segura apenas no codigo.
- Listas ainda precisam de paginacao quando a base crescer. Aplicar agora muda a
  forma de navegacao e deve ser aprovado como decisao de produto.
- Historicos e modais podem ser carregados somente ao abrir. Isso reduz ainda
  mais a primeira carga, mas muda o comportamento offline e a expectativa de
  disponibilidade imediata dos dados.
- Operacoes financeiras, permissoes e transicoes de etapa nao devem usar fila
  local eventual: precisam de confirmacao duravel do servidor.

## Modelo de consistencia adotado

A interface pode ser otimista, mas o banco continua sendo a fonte da verdade.
Nenhuma acao e considerada silenciosamente salva apenas no navegador. Falhas
sao apresentadas e a interface e revertida, evitando perda invisivel de dados.

## Rodada final - 2026-07-15

Esta rodada removeu o custo de rede que ainda permanecia no caminho comum sem
alterar dados, schema ou resultado renderizado das telas.

Mudancas principais:

- dashboard, matriz, detalhe, missoes, clientes, cartorios, usuarios e relatorios
  usam snapshots curtos com TTL, limite de memoria, copia isolada, invalidacao
  explicita e protecao contra cargas simultaneas da mesma chave;
- uma invalidacao ocorrida durante uma consulta impede que o resultado antigo
  volte ao cache quando a consulta terminar;
- GETs auditados como somente leitura usam autocommit, evitando um `ROLLBACK`
  remoto apenas para devolver a conexao ao pool;
- escritas de uma mesma acao fazem um unico commit fisico no fim do request;
- reordenacoes, proprietarios, procuradores, vertices e checklists usam SQL em
  lote em vez de uma viagem ao banco por item;
- delegar responsavel e criar/resolver pendencia passaram a uma unica escrita
  SQL atomica; a resposta e JSON e matriz/modal sao atualizados em paralelo;
- detalhe do projeto e matriz consolidam seus blocos em uma consulta principal;
- checklist, anotacoes e acoes da matriz atualizam a interface sem recarregar a
  pagina, com reversao e aviso visivel em caso de erro;
- o benchmark agora separa cache quente, cache da rota expirado, estado apos
  escrita e processo frio.

Medicao local contra o mesmo Supabase remoto, tres execucoes por rota:

| Rota | Cache quente | Cache da rota expirado | Queries expirado |
| --- | ---: | ---: | ---: |
| `/` | 0,7 ms | 42,5 ms | 1 |
| `/projects` | 2,5 ms | 32,7 ms | 1 |
| `/project/15` | 2,7 ms | 61,9 ms | 1 |
| `/my-missions` | 1,3 ms | 24,1 ms | 1 |
| `/clients` | 1,8 ms | 54,8 ms | 1 |
| `/reports` | 1,0 ms | 63,3 ms | 1 |

O fragmento do modal da matriz, carregado somente ao abrir, ficou em uma
consulta e mediana observada entre 31,8 e 48,9 ms. Os tempos de rede variam;
a reducao de viagens e a parte permanente do ganho.

Validacoes de regressao:

- HTML identico byte a byte ao `HEAD` anterior nas telas sem mudanca visual;
- todas as rotas principais e todos os fragmentos de projeto retornaram 200;
- JavaScript renderizado e Python passaram nas verificacoes de sintaxe;
- transacao 200 faz um commit, erro 500 faz rollback;
- nenhum teste ou migracao destrutiva foi executado no banco real.
