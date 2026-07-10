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
