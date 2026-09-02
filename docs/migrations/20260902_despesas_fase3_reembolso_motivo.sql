-- Fase 3 do modulo de Despesas (Financeiro -> Reembolsos).
-- Migracao aditiva: so acrescenta uma coluna. Nenhum dado existente e
-- alterado. Espelha despesas.motivo_cancelamento -- o cancelamento de um
-- reembolso (registrado por engano) tambem guarda o motivo, no mesmo padrao
-- de auditoria ja usado para despesas.
ALTER TABLE public.despesa_reembolsos
    ADD COLUMN IF NOT EXISTS motivo_cancelamento TEXT;
