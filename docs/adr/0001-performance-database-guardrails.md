# ADR 0001 - Guardrails de performance e banco

Status: aceito  
Data: 2026-07-01

## Contexto

O GeoGestao usa dados reais no Supabase e ja possui fluxos sensiveis de clientes,
projetos, responsabilidades, prazos e historico. O sistema apresentou lentidao em
navegacao e criacao de projetos, mas otimizar sem medir poderia causar perda de
dado, excesso de indices ou refatoracoes arriscadas.

## Decisao

Adotar guardrails permanentes:

- medir antes e depois de mudancas de performance;
- proibir comandos destrutivos sem autorizacao explicita;
- preferir melhorias aditivas e pequenas;
- documentar baseline, arquitetura e regras de banco;
- manter cache com TTL e invalidacao;
- usar indices somente quando houver consulta real justificando.

## Consequencias

Positivas:

- Menor risco de quebrar o sistema durante otimizacoes.
- Comparacao objetiva entre commits.
- Base mais clara para futuras melhorias.

Negativas:

- Algumas melhorias grandes ficam para fases posteriores.
- Toda mudanca de performance passa a exigir medicao e registro minimo.
