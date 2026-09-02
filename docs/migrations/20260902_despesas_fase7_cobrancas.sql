-- Fase 7 do modulo de Despesas (Financeiro -> Cobrancas).
-- Migracao aditiva: cria tabelas novas apenas. Nao altera nem apaga nenhuma
-- linha existente em despesas/despesa_alocacoes/despesa_anexos/despesa_reembolsos
-- ou em projeto_custos/projeto_pagamentos. Ver docs/FINANCEIRO_DESPESAS.md
-- secao 8 ("o que fica para depois") e expense_service.py.
--
-- Cobranca ao cliente: formaliza que um conjunto de despesas "prontas" (valor +
-- divisao + desembolsante definidos) foi cobrado do proprietario/cliente.
-- Cancelamento e soft (nunca DELETE): as despesas da cobranca cancelada voltam
-- a aparecer como "a cobrar" automaticamente, porque toda consulta de
-- pendencia ja filtra por cobrancas.status = 'ativa'.

CREATE TABLE IF NOT EXISTS public.cobrancas (
    id SERIAL PRIMARY KEY,
    cliente_id INTEGER NOT NULL REFERENCES public.clientes(id) ON DELETE RESTRICT,
    valor_total NUMERIC(12, 2) NOT NULL CHECK (valor_total > 0),
    data_cobranca TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ativa' CHECK (status IN ('ativa', 'cancelada')),
    observacoes TEXT,
    criado_em TEXT NOT NULL,
    criado_por INTEGER REFERENCES public.usuarios(id) ON DELETE SET NULL,
    cancelado_em TEXT,
    cancelado_por INTEGER REFERENCES public.usuarios(id) ON DELETE SET NULL,
    motivo_cancelamento TEXT
);
CREATE INDEX IF NOT EXISTS idx_cobrancas_cliente ON public.cobrancas (cliente_id, status);

-- Quais despesas uma cobranca inclui. "status" aqui e um espelho do status da
-- cobranca-pai no momento (mantido por expense_service.py dentro da mesma
-- transacao que cancela a cobranca) -- existe SO para permitir o indice unico
-- parcial abaixo: Postgres nao aceita subquery/JOIN em predicado de indice,
-- entao a checagem "esta despesa ja esta em outra cobranca ativa" nao dava
-- para expressar olhando so para cobrancas.status. A fonte da verdade
-- continua sendo cobrancas.status; este campo nunca diverge dela porque so e
-- escrito por criar_cobranca/cancelar_cobranca.
CREATE TABLE IF NOT EXISTS public.cobranca_itens (
    id SERIAL PRIMARY KEY,
    cobranca_id INTEGER NOT NULL REFERENCES public.cobrancas(id) ON DELETE CASCADE,
    despesa_id INTEGER NOT NULL REFERENCES public.despesas(id) ON DELETE RESTRICT,
    valor NUMERIC(12, 2) NOT NULL CHECK (valor > 0),
    status TEXT NOT NULL DEFAULT 'ativo' CHECK (status IN ('ativo', 'cancelado'))
);
CREATE INDEX IF NOT EXISTS idx_cobranca_itens_cobranca ON public.cobranca_itens (cobranca_id);
CREATE INDEX IF NOT EXISTS idx_cobranca_itens_despesa ON public.cobranca_itens (despesa_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_cobranca_itens_despesa_ativa
    ON public.cobranca_itens (despesa_id)
    WHERE status = 'ativo';
