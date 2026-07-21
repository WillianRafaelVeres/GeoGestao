-- Rascunhos de checklist extraidos de notas de exigencia com revisao humana.
-- A migracao e aditiva e nao altera exigencias ou itens existentes.
CREATE TABLE IF NOT EXISTS public.exigencia_analises_ia (
    id SERIAL PRIMARY KEY,
    projeto_id INTEGER NOT NULL REFERENCES public.projetos(id) ON DELETE CASCADE,
    exigencia_id INTEGER NOT NULL UNIQUE REFERENCES public.exigencias_cartorio(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'rascunho'
        CHECK (status IN ('rascunho', 'aplicado')),
    provider TEXT NOT NULL DEFAULT 'groq',
    model TEXT,
    source_hash TEXT NOT NULL,
    source_method TEXT,
    draft_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    usage_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    warning_message TEXT,
    prompt_version TEXT,
    criado_por INTEGER REFERENCES public.usuarios(id) ON DELETE SET NULL,
    criado_em TEXT,
    atualizado_em TEXT,
    aplicado_em TEXT
);

ALTER TABLE public.exigencia_itens
    ADD COLUMN IF NOT EXISTS codigo TEXT,
    ADD COLUMN IF NOT EXISTS resumo TEXT,
    ADD COLUMN IF NOT EXISTS pagina INTEGER,
    ADD COLUMN IF NOT EXISTS origem TEXT NOT NULL DEFAULT 'manual',
    ADD COLUMN IF NOT EXISTS analise_ia_id INTEGER
        REFERENCES public.exigencia_analises_ia(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_exigencia_analises_ia_projeto_status
    ON public.exigencia_analises_ia (projeto_id, status);

CREATE INDEX IF NOT EXISTS idx_exigencia_analises_ia_criado_por
    ON public.exigencia_analises_ia (criado_por)
    WHERE criado_por IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_exigencia_itens_analise_ia
    ON public.exigencia_itens (analise_ia_id)
    WHERE analise_ia_id IS NOT NULL;

ALTER TABLE public.exigencia_analises_ia ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.exigencia_analises_ia FROM anon, authenticated;
REVOKE ALL ON SEQUENCE public.exigencia_analises_ia_id_seq FROM anon, authenticated;

GRANT SELECT, INSERT, UPDATE, DELETE
    ON TABLE public.exigencia_analises_ia TO geogestao_app;
GRANT USAGE, SELECT
    ON SEQUENCE public.exigencia_analises_ia_id_seq TO geogestao_app;

DROP POLICY IF EXISTS backend_all ON public.exigencia_analises_ia;
CREATE POLICY backend_all
    ON public.exigencia_analises_ia
    FOR ALL
    TO geogestao_app
    USING (true)
    WITH CHECK (true);
