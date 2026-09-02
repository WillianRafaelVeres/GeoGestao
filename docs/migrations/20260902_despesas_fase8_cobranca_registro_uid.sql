-- Fase 8 do modulo de Despesas (Financeiro -> Cobrancas).
-- Migracao aditiva: so acrescenta uma coluna + indice. Nenhum dado existente
-- e alterado. Mesma protecao de duplo-envio ja usada em despesas/reembolsos
-- (despesas.registro_uid / despesa_reembolsos.registro_uid): o formulario
-- "Marcar como cobrado" gera um UUID por abertura de modal e reenvia o mesmo
-- valor se o usuario clicar duas vezes ou a rede falhar e o navegador tentar
-- de novo -- expense_service.criar_cobranca detecta e devolve a cobranca ja
-- criada em vez de duplicar.
ALTER TABLE public.cobrancas
    ADD COLUMN IF NOT EXISTS registro_uid TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS idx_cobrancas_registro_uid
    ON public.cobrancas (registro_uid) WHERE registro_uid IS NOT NULL;
