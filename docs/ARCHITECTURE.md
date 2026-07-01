# Arquitetura - GeoGestao

Resumo tecnico do estado atual do sistema para orientar manutencao segura.

## Visao geral

O GeoGestao e uma aplicacao Flask com renderizacao server-side em Jinja e banco
PostgreSQL no Supabase.

Fluxo principal:

```text
Navegador
  -> Flask/Gunicorn
  -> psycopg2 pool
  -> Supabase Postgres
  -> templates Jinja + static CSS/JS
```

## Componentes

- `app.py`: rotas Flask, regras de negocio, acesso ao banco, caches de runtime e
  inicializacao/migracao do schema.
- `templates/`: paginas Jinja renderizadas pelo servidor.
- `static/style.css`: estilos visuais.
- `static/app.js`: interacoes leves da interface.
- `process_types.py`: tipos de processo.
- `process_stage_templates.py`: modelos de etapas por processo.
- `process_checklist_templates.py`: modelos de checklist por processo/etapa.
- `documental.py`: regras de cadastro documental de clientes.
- `report_helpers.py`: calculos de relatorios.
- `scripts/measure_routes.py`: benchmark local das rotas principais.

## Dados centrais

- `usuarios`: login, perfil, cargo e status ativo.
- `clientes` e tabelas auxiliares: proprietarios, pessoas fisicas/juridicas,
  procuradores, enderecos, imoveis e conjuges.
- `projetos`: cabecalho do projeto, cliente, processo, prioridade, pasta,
  responsavel geral e etapa atual.
- `projeto_etapas`: etapas macro do projeto, status, prazo, responsavel e
  progresso historico/operacional.
- `project_checklist_items`: checklist operacional por projeto e etapa.
- `pendencias`, `tarefas`, `exigencias_cartorio`: trabalho pendente e prazos.
- `eventos_historico`, `movimentacoes_etapa`, `project_stage_history`: trilha de
  atividade e movimentacao.

## Rotas mais importantes

- `/`: dashboard operacional.
- `/projects`: matriz de projetos.
- `/project/create`: criacao de projeto.
- `/project/<id>`: detalhe completo do projeto.
- `/my-missions`: fila pessoal por responsavel.
- `/clients`: base de clientes.
- `/cartorios` e `/cartorio`: cartorios/orgaos e acompanhamento externo.
- `/users`: aprovacao e manutencao de usuarios.
- `/reports`: relatorios operacionais.

## Padroes de acesso ao banco

- `connect_db()` cria conexoes via pool.
- `get_db()` reaproveita a conexao durante o request.
- `query_db()` e `execute_db()` sao os helpers principais.
- `_execute_cursor()` mede tempo de cada query.
- `refresh_due_statuses()` atualiza atrasos com TTL para evitar escrita a cada
  clique.
- Lookups comuns usam cache curto via `get_cached_lookup()`.
- Relatorios usam cache curto via `get_reports_context_cached()`.

## Pontos de atencao

- O arquivo `app.py` concentra muitas responsabilidades; mudancas grandes devem
  ser fatiadas.
- Algumas rotas `GET` ainda fazem manutencao preguicosa quando encontram dado
  legado ou incompleto. Antes de chamar isso de bug, verificar se e reparo
  intencional.
- A matriz precisa continuar leve: dados de detalhe devem ser carregados em lote
  ou somente no clique.
- A tela de clientes ainda e um ponto provavel de otimizacao quando a base
  crescer, pois junta muitos dados documentais.
- Sem uma estrategia formal de migrations, toda alteracao de schema precisa de
  SQL claro, backup/rollback planejado e validacao em ambiente seguro.

## Decisoes operacionais atuais

- O app usa horario de Santa Catarina/Sao Paulo via `America/Sao_Paulo`.
- O deploy gratuito recomendado continua sendo Render + Supabase Pooler, com
  poucos workers e threads moderadas.
- Performance deve ser acompanhada por `Server-Timing`, `GEOGESTAO_PERF_LOG` e
  `scripts/measure_routes.py`.
