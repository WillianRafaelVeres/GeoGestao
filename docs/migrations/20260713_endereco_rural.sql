-- Suporte a endereco rural nos cadastros documentais.
-- Mudanca aditiva e segura: os cadastros existentes permanecem urbanos por padrao.

ALTER TABLE pessoas_juridicas
    ADD COLUMN IF NOT EXISTS tipo_endereco TEXT DEFAULT 'URBANO';

ALTER TABLE enderecos_proprietario
    ADD COLUMN IF NOT EXISTS tipo_endereco TEXT DEFAULT 'URBANO';

ALTER TABLE procuradores
    ADD COLUMN IF NOT EXISTS tipo_endereco TEXT DEFAULT 'URBANO';
