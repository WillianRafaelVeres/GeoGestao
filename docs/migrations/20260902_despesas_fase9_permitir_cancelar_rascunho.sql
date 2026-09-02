-- Fase 9 do modulo de Despesas (Financeiro -> Lancamentos).
-- Migracao aditiva/relaxante: nao apaga nem invalida nenhuma despesa
-- existente (toda despesa que ja estava 'pronta'/'classificada' continua
-- satisfazendo a regra nova sem qualquer alteracao de dado).
--
-- Bug real: a constraint despesas_valor_total_check (fase4) so permitia
-- valor_total nulo enquanto status estivesse em rascunho/pendente_classificacao.
-- Cancelar um documento AINDA nao classificado (exatamente o botao "Cancelar
-- documento"/lixeira de Financeiro -> Lancamentos, e tambem o "Cancelar" de
-- Financeiro -> Despesas quando usado num rascunho importado) muda o status
-- para 'cancelada' sem preencher valor_total -- e a constraint rejeitava essa
-- transicao com um erro 500 nao tratado (nao e um ExpenseServiceError, entao
-- financeiro_lancamentos_cancelar/financeiro_despesas_cancelar nao pegavam).
-- Uma despesa cancelada nunca precisa de valor_total valido: ela ja saiu do
-- controle de custos.
ALTER TABLE public.despesas DROP CONSTRAINT IF EXISTS despesas_valor_total_check;
ALTER TABLE public.despesas ADD CONSTRAINT despesas_valor_total_check
    CHECK (
        status IN ('rascunho', 'pendente_classificacao', 'cancelada')
        OR (valor_total IS NOT NULL AND valor_total > 0)
    );
