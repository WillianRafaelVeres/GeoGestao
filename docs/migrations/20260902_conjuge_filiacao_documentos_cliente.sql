-- Filiacao do conjuge (nome do pai e da mae), espelhando o que ja existe
-- para o titular (pessoas_fisicas) e para o procurador (procuradores).
-- Migracao aditiva: nao altera nem remove dados existentes.
ALTER TABLE public.conjuges
    ADD COLUMN IF NOT EXISTS nome_pai TEXT,
    ADD COLUMN IF NOT EXISTS nome_mae TEXT;

-- Documentos anexados ao cadastro do cliente (RG, comprovantes etc.).
-- O arquivo em si fica no Dropbox, em Novo/_clientes/<nome do cliente>;
-- aqui so guardamos os metadados para listar e reabrir. Tabela nova: nao
-- afeta nenhum dado existente.
CREATE TABLE IF NOT EXISTS public.cliente_documentos (
    id SERIAL PRIMARY KEY,
    cliente_id INTEGER NOT NULL REFERENCES public.clientes(id) ON DELETE CASCADE,
    titulo TEXT NOT NULL,
    caminho_dropbox TEXT NOT NULL,
    nome_arquivo TEXT NOT NULL,
    nome_original TEXT,
    hash TEXT,
    tamanho BIGINT,
    criado_em TEXT,
    usuario_id INTEGER
);

CREATE INDEX IF NOT EXISTS idx_cliente_documentos_cliente_id
    ON public.cliente_documentos (cliente_id);
