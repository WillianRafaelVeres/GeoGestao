# AGENTS.md - GeoGestao

Estas regras valem para qualquer agente ou pessoa alterando este repositorio.

## Prioridade

1. Proteger dados reais.
2. Manter login, permissoes, projetos, clientes e matriz funcionando.
3. Medir antes de otimizar.
4. Fazer mudancas pequenas, reversiveis e testadas.

## Banco de dados e Supabase

- Nunca rode `DROP`, `TRUNCATE`, `DELETE` amplo, `UPDATE` amplo ou reset de schema sem uma instrucao explicita do dono do projeto.
- Nunca use `python app.py --init-db` em producao sem confirmar ambiente, backup e necessidade.
- Prefira migracoes SQL aditivas: `CREATE INDEX CONCURRENTLY`, `ADD COLUMN` com default seguro, constraints validadas em etapas.
- Nao remova indices so porque o Advisor marcou como "unused"; confirme volume, historico de uso e plano de execucao.
- Use o Pooler do Supabase quando a aplicacao estiver hospedada em servico com limite de conexoes ou rede instavel.
- Segredos do `.env` nunca devem aparecer em commit, log, print ou documentacao.

## Performance

- Antes de alterar performance, rode:
  ```bash
  python scripts/measure_routes.py --runs 3
  ```
- Depois de alterar, rode o mesmo comando e compare.
- Nao crie cache sem TTL e sem invalidacao clara.
- Evite N+1: prefira queries agregadas, `JOIN`, `WITH` e carregamento em lote.
- Evite `SELECT *` em telas pesadas quando a tela usa poucas colunas.
- Paginacao ou limite e obrigatorio para listas que possam crescer muito.
- Toda nova rota que conversa com banco deve considerar: numero de queries, indices, payload e permissao.

## Verificacoes minimas

Antes de commit:

```bash
python -m py_compile app.py
python scripts/measure_routes.py --runs 2
git diff --check
```

Se a mudanca tocar templates ou fluxo de usuario, abrir manualmente pelo menos:

- `/`
- `/projects`
- `/project/create`
- `/my-missions`
- `/clients`
- `/reports`

## Estilo de mudanca

- Preserve o padrao atual do Flask/Jinja/PostgreSQL.
- Evite refatoracao grande junto com correcao urgente.
- Documente decisoes permanentes em `docs/` e, quando houver trade-off arquitetural, em `docs/adr/`.
- Commits devem ter escopo claro e mensagem objetiva.
