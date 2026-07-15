# ADR 0003 - Transacoes por request e cache de runtime

Status: aceito

Data: 2026-07-15

## Contexto

O PostgreSQL esta remoto e uma viagem de rede custa muito mais que a execucao
das consultas na base atual. Rotas com varias consultas pequenas, commits
intermediarios e rollback de leitura acumulavam latencia perceptivel mesmo com
planos SQL rapidos.

## Decisao

- Escritas feitas durante um request Flask compartilham uma transacao e recebem
  um unico commit fisico no `after_request` quando a resposta e bem-sucedida.
- Respostas com erro fazem rollback; chamadas legadas a `commit()` apenas marcam
  a escrita como pendente ate o fim do request.
- Endpoints GET explicitamente auditados como somente leitura usam autocommit
  para nao abrir uma transacao que exigiria rollback ao devolver a conexao.
- Resultados operacionais de leitura podem usar cache curto em memoria, sempre
  com TTL, limite de entradas, invalidacao apos escrita, carga unica por chave e
  contador de geracao contra recolocacao de snapshots antigos.
- Cada consumidor recebe uma copia do valor cacheado para impedir mutacao entre
  requests.
- A interface pode ser otimista, mas o servidor e o banco continuam sendo a
  fonte da verdade; falhas revertem o estado local ou exibem aviso claro.

## Consequencias

Positivas:

- Menos viagens ao Supabase em leitura e escrita.
- Acoes com varios passos tornam-se atomicas.
- Acessos simultaneos nao disparam consultas identicas em cascata.
- Navegacao repetida e imediata sem esconder falhas de persistencia.

Cuidados permanentes:

- Uma rota adicionada a `READ_ONLY_DB_ENDPOINTS` deve permanecer estritamente de
  leitura; se passar a escrever, deve sair da lista.
- Toda escrita que altera opcoes estaveis deve invalidar suas chaves especificas.
- O cache e local ao processo. Se a aplicacao ganhar varios workers/processos,
  sera necessario aceitar o TTL curto ou adotar invalidacao compartilhada.
- Operacoes financeiras, permissoes e transicoes de etapa nao devem virar fila
  eventual no navegador.
