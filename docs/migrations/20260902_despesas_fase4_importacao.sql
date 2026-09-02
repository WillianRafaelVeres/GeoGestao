-- Fase 4 do modulo de Despesas (Financeiro -> Despesas -> Importar documentos).
-- Migracao aditiva/relaxante: nao apaga nem invalida nenhuma despesa
-- existente (todas ja tem valor_total valido, entao continuam satisfazendo
-- a regra nova sem qualquer alteracao de dado).
--
-- Um documento importado em lote vira uma despesa em status 'rascunho' ou
-- 'pendente_classificacao' ANTES de o usuario confirmar o valor (a IA da
-- Fase 5 tambem vai gravar nesse mesmo estado). valor_total NOT NULL + CHECK
-- > 0 impedia isso. A partir de agora, valor_total so e obrigatorio quando a
-- despesa sai do estado de rascunho/pendente.
ALTER TABLE public.despesas ALTER COLUMN valor_total DROP NOT NULL;

ALTER TABLE public.despesas DROP CONSTRAINT IF EXISTS despesas_valor_total_check;
ALTER TABLE public.despesas ADD CONSTRAINT despesas_valor_total_check
    CHECK (
        status IN ('rascunho', 'pendente_classificacao')
        OR (valor_total IS NOT NULL AND valor_total > 0)
    );
