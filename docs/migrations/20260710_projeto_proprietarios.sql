CREATE TABLE IF NOT EXISTS public.projeto_proprietarios (
    projeto_id INTEGER NOT NULL REFERENCES public.projetos(id) ON DELETE CASCADE,
    cliente_id INTEGER NOT NULL REFERENCES public.clientes(id) ON DELETE RESTRICT,
    principal INTEGER NOT NULL DEFAULT 0 CHECK (principal IN (0, 1)),
    ordem INTEGER NOT NULL DEFAULT 0,
    criado_em TEXT,
    PRIMARY KEY (projeto_id, cliente_id)
);

ALTER TABLE public.projeto_proprietarios ENABLE ROW LEVEL SECURITY;

CREATE INDEX IF NOT EXISTS idx_projeto_proprietarios_cliente
    ON public.projeto_proprietarios (cliente_id, projeto_id);

CREATE UNIQUE INDEX IF NOT EXISTS idx_projeto_proprietarios_principal
    ON public.projeto_proprietarios (projeto_id)
    WHERE principal = 1;

INSERT INTO public.projeto_proprietarios (projeto_id, cliente_id, principal, ordem, criado_em)
SELECT id, cliente_id, 1, 0, criado_em
FROM public.projetos
WHERE cliente_id IS NOT NULL
ON CONFLICT (projeto_id, cliente_id)
DO UPDATE SET principal = 1, ordem = 0;
