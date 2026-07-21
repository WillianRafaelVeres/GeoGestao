-- Metadados das notas de exigencia armazenadas no Dropbox.
-- Migracao aditiva: nao altera nem remove exigencias existentes.
ALTER TABLE public.exigencias_cartorio
    ADD COLUMN IF NOT EXISTS anexo_path TEXT,
    ADD COLUMN IF NOT EXISTS anexo_nome TEXT,
    ADD COLUMN IF NOT EXISTS anexo_nome_original TEXT,
    ADD COLUMN IF NOT EXISTS anexo_hash TEXT,
    ADD COLUMN IF NOT EXISTS anexo_versao INTEGER,
    ADD COLUMN IF NOT EXISTS anexo_tamanho BIGINT,
    ADD COLUMN IF NOT EXISTS anexo_criado_em TEXT,
    ADD COLUMN IF NOT EXISTS anexo_usuario_id INTEGER;

-- O hash SHA-256 impede que o mesmo conteudo seja vinculado duas vezes ao projeto.
CREATE UNIQUE INDEX IF NOT EXISTS idx_exigencias_nota_hash_unique
    ON public.exigencias_cartorio (projeto_id, anexo_hash)
    WHERE COALESCE(tipo_registro, 'exigencia') = 'exigencia'
      AND anexo_hash IS NOT NULL;

-- Mantem a sequencia V1, V2, V3 unica por projeto.
CREATE UNIQUE INDEX IF NOT EXISTS idx_exigencias_nota_versao_unique
    ON public.exigencias_cartorio (projeto_id, anexo_versao)
    WHERE COALESCE(tipo_registro, 'exigencia') = 'exigencia'
      AND anexo_versao IS NOT NULL;
