# ADR 0002 - Observabilidade por request

Status: aceito  
Data: 2026-07-01

## Contexto

As queixas de lentidao podem vir de rede, renderizacao, banco, cold start do
servidor ou excesso de queries. Sem uma medicao por request, a investigacao fica
dependente de sensacao visual ou logs manuais.

## Decisao

Adicionar instrumentacao leve em todas as respostas HTTP:

- `X-Request-ID` para correlacionar diagnostico.
- `Server-Timing` com tempo total, tempo de banco e quantidade de queries.
- Logs detalhados opcionais quando `GEOGESTAO_PERF_LOG=1`.

## Consequencias

Positivas:

- Diagnostico mais rapido de rotas lentas.
- Nao exige ferramenta externa para a primeira analise.
- Baixo risco funcional, pois nao altera regra de negocio.

Negativas:

- Existe pequeno custo de medir tempo por request.
- A medida local nao substitui monitoramento real em producao quando o uso
  crescer.
