# Baseline de Performance - GeoGestao

Data: 2026-07-01  
Ambiente medido: aplicacao local usando `DATABASE_URL` do Supabase configurado no
`.env`  
Ferramenta: `python scripts/measure_routes.py --runs 3`  
Observacao: benchmark de diagnostico, nao teste de carga.

## Resultado atual

| Rota | Status | Mediana total ms | Mediana DB ms | Mediana queries | Bytes |
| --- | ---: | ---: | ---: | ---: | ---: |
| `/` | 200 | 571.2 | 291.1 | 6 | 13725 |
| `/projects` | 200 | 680.2 | 537.4 | 8 | 134576 |
| `/project/create` | 200 | 159.8 | 66.3 | 1 | 24404 |
| `/project/1` | 200 | 523.9 | 358.0 | 16 | 35025 |
| `/my-missions` | 200 | 172.1 | 90.5 | 4 | 6464 |
| `/clients` | 200 | 621.7 | 535.3 | 16 | 132722 |
| `/cartorios` | 200 | 128.0 | 53.9 | 2 | 4644 |
| `/users` | 200 | 148.2 | 52.2 | 2 | 6633 |
| `/cartorio` | 200 | 138.7 | 62.4 | 2 | 3907 |
| `/reports` | 200 | 115.5 | 35.2 | 1 | 22618 |

## Leitura rapida

- A matriz esta em nivel aceitavel de queries para a base atual: 8 consultas na
  mediana com cache de runtime aquecido.
- O detalhe do projeto ainda e a rota mais cara entre as rotas comuns: 16
  consultas e maior tempo de banco.
- A tela de clientes tambem merece acompanhamento: 16 consultas e HTML grande.
- Criacao de projeto em `GET` esta leve: 1 consulta na mediana com cache
  aquecido.
- Cartorios, usuarios e cartorio operacional estao leves.

## Estado do banco durante auditoria

Consulta de seguranca e inventario feita sem apagar ou zerar dados:

| Tabela | Registros |
| --- | ---: |
| `usuarios` | 2 |
| `clientes` | 2 |
| `projetos` | 4 |
| `projeto_etapas` | 52 |
| `project_checklist_items` | 280 |
| `pendencias` | 1 |
| `exigencias_cartorio` | 1 |

Tambem foi conferido:

- `pg_stat_statements` habilitado.
- Supabase Advisor de seguranca sem alertas no momento da auditoria.
- Supabase Advisor de performance apontando apenas avisos informativos de
  indices sem uso recente; nenhum indice foi removido por esse motivo.

## Melhorias ja presentes no codigo

- Pool de conexoes psycopg2.
- `statement_timeout` configuravel por ambiente.
- Cache curto para lookups de usuarios, cartorios, tipos de processo, clientes
  para autocomplete e relatorios.
- Atualizacao de atrasos com TTL para evitar escrita em todo request.
- Carregamento em lote das linhas de etapas da matriz.
- Criacao de projeto em transacao unica.
- Ordenacao de novos projetos para o fim da prioridade manual.
- Indices de apoio registrados em `docs/performance_indexes.sql`.

## Instrumentacao adicionada

Toda resposta HTTP recebe:

- `X-Request-ID`: identificador curto para correlacionar diagnostico.
- `Server-Timing`: tempo total da aplicacao, tempo de banco e numero de queries.

Exemplo:

```text
Server-Timing: app;dur=376.1, db;dur=265.6;desc="10 queries"
```

## Proximas oportunidades seguras

- Reduzir a rota `/project/<id>` juntando consultas de detalhe que sempre andam
  juntas, com cuidado para nao perder dados de historico/checklist.
- Otimizar `/clients` quando a base crescer, possivelmente separando listagem
  leve de detalhes documentais.
- Criar paginacao/limites explicitos para listas que hoje renderizam todos os
  registros.
- Avaliar planos de execucao de queries lentas quando houver volume real.
- Evoluir migrations formais para schema e indices.

## Como atualizar este baseline

1. Garantir que a mudanca esta aplicada.
2. Rodar:
   ```bash
   python scripts/measure_routes.py --runs 3
   ```
3. Substituir ou adicionar uma nova tabela com data, ambiente e commit.
4. Registrar tambem se houve mudanca no volume de dados, pois isso altera a
   comparacao.
