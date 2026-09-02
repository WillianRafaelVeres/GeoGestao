-- Fase 1 do modulo de Despesas (Financeiro -> Despesas/Reembolsos).
-- Migracao aditiva: cria tabelas novas apenas. NAO altera, apaga nem
-- invalida nenhuma linha existente em projeto_custos/projeto_pagamentos
-- (essas tabelas e as rotas /financeiro atuais continuam funcionando
-- exatamente como hoje). Ver docs/CADASTRO_CLIENTES_DOCUMENTOS.md e
-- expense_service.py para o desenho completo.
--
-- Ordem de execucao: unica migracao, idempotente (pode rodar de novo sem
-- duplicar dados, inclusive a migracao de projeto_custos no final).

-- Pessoas que podem realizar um desembolso (nao precisam ser usuario do
-- sistema). "Empresa" NAO e uma linha aqui -- e representada por
-- despesas.desembolsado_por_tipo = 'EMPRESA' com desembolsado_por_id NULL.
CREATE TABLE IF NOT EXISTS public.desembolsantes (
    id SERIAL PRIMARY KEY,
    nome TEXT NOT NULL,
    usuario_id INTEGER REFERENCES public.usuarios(id) ON DELETE SET NULL,
    documento TEXT,
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    criado_em TEXT,
    criado_por INTEGER REFERENCES public.usuarios(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_desembolsantes_ativo ON public.desembolsantes (ativo, nome);

-- Cabecalho de um lote de importacao de comprovantes (ex.: varios arquivos
-- baixados de um grupo de WhatsApp, enviados de uma vez). Cada documento do
-- lote vira uma linha em despesas (com lote_id preenchido) -- nao existe uma
-- tabela "despesa_lotes_itens" separada espelhando despesas.
CREATE TABLE IF NOT EXISTS public.despesa_lotes (
    id SERIAL PRIMARY KEY,
    titulo TEXT,
    status TEXT NOT NULL DEFAULT 'em_andamento' CHECK (status IN ('em_andamento', 'concluido')),
    total_documentos INTEGER NOT NULL DEFAULT 0,
    criado_em TEXT,
    criado_por INTEGER REFERENCES public.usuarios(id) ON DELETE SET NULL
);

-- Entidade central: a despesa existe independente de projeto/divisao.
CREATE TABLE IF NOT EXISTS public.despesas (
    id SERIAL PRIMARY KEY,
    descricao TEXT NOT NULL,
    categoria TEXT,
    valor_total NUMERIC(12, 2) NOT NULL CHECK (valor_total > 0),
    data_despesa TEXT,
    observacoes TEXT,
    status TEXT NOT NULL DEFAULT 'rascunho'
        CHECK (status IN ('rascunho', 'pendente_classificacao', 'classificada', 'pronta', 'cancelada')),
    desembolsado_por_tipo TEXT NOT NULL DEFAULT 'EMPRESA'
        CHECK (desembolsado_por_tipo IN ('EMPRESA', 'PESSOA')),
    desembolsado_por_id INTEGER REFERENCES public.desembolsantes(id) ON DELETE RESTRICT,
    lote_id INTEGER REFERENCES public.despesa_lotes(id) ON DELETE SET NULL,
    origem TEXT NOT NULL DEFAULT 'MANUAL' CHECK (origem IN ('MANUAL', 'IMPORTACAO', 'MIGRACAO')),
    migrado_de_custo_id INTEGER,
    registro_uid TEXT,
    criado_em TEXT NOT NULL,
    criado_por INTEGER REFERENCES public.usuarios(id) ON DELETE SET NULL,
    atualizado_em TEXT,
    atualizado_por INTEGER REFERENCES public.usuarios(id) ON DELETE SET NULL,
    cancelado_em TEXT,
    cancelado_por INTEGER REFERENCES public.usuarios(id) ON DELETE SET NULL,
    motivo_cancelamento TEXT,
    CONSTRAINT despesas_desembolso_pessoa_check CHECK (
        (desembolsado_por_tipo = 'PESSOA' AND desembolsado_por_id IS NOT NULL)
        OR (desembolsado_por_tipo = 'EMPRESA' AND desembolsado_por_id IS NULL)
    )
);
CREATE INDEX IF NOT EXISTS idx_despesas_status_data ON public.despesas (status, data_despesa DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_despesas_desembolsante ON public.despesas (desembolsado_por_id) WHERE desembolsado_por_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_despesas_lote ON public.despesas (lote_id) WHERE lote_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_despesas_registro_uid ON public.despesas (registro_uid) WHERE registro_uid IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_despesas_migrado_de_custo ON public.despesas (migrado_de_custo_id) WHERE migrado_de_custo_id IS NOT NULL;

-- Divisao da despesa entre projetos. cliente_id e um "retrato" resolvido
-- automaticamente do proprietario principal do projeto no momento em que a
-- alocacao e salva (nunca escolhido manualmente no formulario). A soma das
-- alocacoes de uma despesa deve ser igual a despesas.valor_total; isso e
-- validado na camada de servico (expense_service.py) dentro da mesma
-- transacao, porque Postgres nao valida agregados entre linhas via CHECK.
CREATE TABLE IF NOT EXISTS public.despesa_alocacoes (
    id SERIAL PRIMARY KEY,
    despesa_id INTEGER NOT NULL REFERENCES public.despesas(id) ON DELETE CASCADE,
    projeto_id INTEGER NOT NULL REFERENCES public.projetos(id) ON DELETE RESTRICT,
    cliente_id INTEGER REFERENCES public.clientes(id) ON DELETE SET NULL,
    valor NUMERIC(12, 2) NOT NULL CHECK (valor > 0),
    percentual NUMERIC(6, 3),
    criado_em TEXT,
    atualizado_em TEXT,
    UNIQUE (despesa_id, projeto_id)
);
CREATE INDEX IF NOT EXISTS idx_despesa_alocacoes_projeto ON public.despesa_alocacoes (projeto_id);
CREATE INDEX IF NOT EXISTS idx_despesa_alocacoes_cliente ON public.despesa_alocacoes (cliente_id) WHERE cliente_id IS NOT NULL;

-- Documentos da despesa (nota fiscal, comprovante PIX, recibo, documento de
-- cartorio...). "principal" marca o arquivo fonte-unica quando a despesa e
-- dividida entre varios projetos (o arquivo fica em um lugar so, nunca
-- duplicado por projeto). Guardado no Dropbox em Novo/_despesas/<ano>/<mes>;
-- anexos migrados de projeto_custos continuam apontando para o arquivo
-- antigo, dentro da pasta do projeto original (nada e movido).
CREATE TABLE IF NOT EXISTS public.despesa_anexos (
    id SERIAL PRIMARY KEY,
    despesa_id INTEGER NOT NULL REFERENCES public.despesas(id) ON DELETE CASCADE,
    caminho_dropbox TEXT NOT NULL,
    nome_arquivo TEXT NOT NULL,
    nome_original TEXT,
    tipo TEXT,
    hash TEXT,
    tamanho BIGINT,
    principal BOOLEAN NOT NULL DEFAULT FALSE,
    criado_em TEXT,
    criado_por INTEGER REFERENCES public.usuarios(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_despesa_anexos_despesa ON public.despesa_anexos (despesa_id);
CREATE INDEX IF NOT EXISTS idx_despesa_anexos_hash ON public.despesa_anexos (hash) WHERE hash IS NOT NULL;

-- Reembolso interno: a empresa reembolsando um desembolsante do tipo PESSOA.
-- Nunca se confunde com pagamento/recebimento de cliente (projeto_pagamentos).
CREATE TABLE IF NOT EXISTS public.despesa_reembolsos (
    id SERIAL PRIMARY KEY,
    desembolsante_id INTEGER NOT NULL REFERENCES public.desembolsantes(id) ON DELETE RESTRICT,
    valor NUMERIC(12, 2) NOT NULL CHECK (valor > 0),
    data_reembolso TEXT NOT NULL,
    forma_reembolso TEXT,
    observacoes TEXT,
    anexo_path TEXT,
    anexo_nome TEXT,
    status TEXT NOT NULL DEFAULT 'confirmado' CHECK (status IN ('confirmado', 'cancelado')),
    registro_uid TEXT,
    criado_em TEXT NOT NULL,
    criado_por INTEGER REFERENCES public.usuarios(id) ON DELETE SET NULL,
    cancelado_em TEXT,
    cancelado_por INTEGER REFERENCES public.usuarios(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_despesa_reembolsos_desembolsante ON public.despesa_reembolsos (desembolsante_id, status);
CREATE UNIQUE INDEX IF NOT EXISTS idx_despesa_reembolsos_registro_uid ON public.despesa_reembolsos (registro_uid) WHERE registro_uid IS NOT NULL;

-- Quais despesas (ou parte delas) um reembolso quita. A primeira interface
-- so oferece reembolso integral (valor = despesas.valor_total), mas o banco
-- ja permite reembolso parcial: varias linhas podem quitar a mesma despesa
-- aos poucos, desde que a soma nunca ultrapasse valor_total (validado em
-- expense_service.py).
CREATE TABLE IF NOT EXISTS public.despesa_reembolso_alocacoes (
    id SERIAL PRIMARY KEY,
    reembolso_id INTEGER NOT NULL REFERENCES public.despesa_reembolsos(id) ON DELETE CASCADE,
    despesa_id INTEGER NOT NULL REFERENCES public.despesas(id) ON DELETE RESTRICT,
    valor NUMERIC(12, 2) NOT NULL CHECK (valor > 0),
    UNIQUE (reembolso_id, despesa_id)
);
CREATE INDEX IF NOT EXISTS idx_despesa_reembolso_alocacoes_despesa ON public.despesa_reembolso_alocacoes (despesa_id);

-- Rascunho de leitura por IA de um comprovante, no mesmo formato de
-- exigencia_analises_ia (status rascunho/aplicado, draft_json e um JSON com
-- os campos sugeridos, nunca gravado como fato definitivo sem confirmacao).
CREATE TABLE IF NOT EXISTS public.despesa_documento_analises_ia (
    id SERIAL PRIMARY KEY,
    despesa_id INTEGER NOT NULL UNIQUE REFERENCES public.despesas(id) ON DELETE CASCADE,
    anexo_id INTEGER REFERENCES public.despesa_anexos(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'rascunho' CHECK (status IN ('rascunho', 'aplicado')),
    provider TEXT NOT NULL DEFAULT 'groq',
    model TEXT,
    source_hash TEXT NOT NULL,
    source_method TEXT,
    draft_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    usage_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    warning_message TEXT,
    prompt_version TEXT,
    criado_por INTEGER REFERENCES public.usuarios(id) ON DELETE SET NULL,
    criado_em TEXT,
    atualizado_em TEXT,
    aplicado_em TEXT
);

-- Auditoria dedicada (mesmo padrao texto-livre de eventos_historico, mas por
-- despesa_id -- eventos_historico exige projeto_id e uma despesa pode nao
-- ter nenhum projeto ainda quando e criada).
CREATE TABLE IF NOT EXISTS public.despesa_eventos (
    id SERIAL PRIMARY KEY,
    despesa_id INTEGER NOT NULL REFERENCES public.despesas(id) ON DELETE CASCADE,
    usuario_id INTEGER REFERENCES public.usuarios(id) ON DELETE SET NULL,
    tipo_evento TEXT NOT NULL,
    descricao TEXT,
    criado_em TEXT
);
CREATE INDEX IF NOT EXISTS idx_despesa_eventos_despesa ON public.despesa_eventos (despesa_id, criado_em DESC);

-- Migracao dos custos existentes: cada projeto_custos vira 1 despesa (100%
-- desembolsada pela empresa, ja que o modelo antigo nao distinguia isso) com
-- 1 alocacao de 100% para o mesmo projeto e o mesmo comprovante (se houver),
-- sem mover nenhum arquivo no Dropbox. Idempotente via migrado_de_custo_id:
-- rodar de novo pula os custos ja migrados. projeto_custos NAO e alterada
-- nem apagada.
BEGIN;

INSERT INTO public.despesas (
    descricao, categoria, valor_total, data_despesa, observacoes, status,
    desembolsado_por_tipo, origem, migrado_de_custo_id, registro_uid,
    criado_em, criado_por
)
SELECT
    pc.descricao,
    pc.categoria,
    pc.valor,
    pc.data_custo,
    pc.observacoes,
    CASE WHEN lower(COALESCE(pc.status, '')) = 'cancelado' THEN 'cancelada' ELSE 'pronta' END,
    'EMPRESA',
    'MIGRACAO',
    pc.id,
    pc.registro_uid,
    COALESCE(NULLIF(pc.criado_em, ''), to_char(now() AT TIME ZONE 'America/Sao_Paulo', 'YYYY-MM-DD"T"HH24:MI:SS')),
    pc.usuario_id
FROM public.projeto_custos pc
JOIN public.projetos p ON p.id = pc.projeto_id
WHERE pc.valor > 0
  AND NOT EXISTS (SELECT 1 FROM public.despesas d WHERE d.migrado_de_custo_id = pc.id);

INSERT INTO public.despesa_alocacoes (despesa_id, projeto_id, cliente_id, valor, criado_em)
SELECT
    d.id,
    pc.projeto_id,
    COALESCE(pp.cliente_id, p.cliente_id),
    d.valor_total,
    d.criado_em
FROM public.despesas d
JOIN public.projeto_custos pc ON pc.id = d.migrado_de_custo_id
JOIN public.projetos p ON p.id = pc.projeto_id
LEFT JOIN LATERAL (
    SELECT cliente_id FROM public.projeto_proprietarios
    WHERE projeto_id = pc.projeto_id
    ORDER BY principal DESC, cliente_id
    LIMIT 1
) pp ON TRUE
WHERE d.origem = 'MIGRACAO'
  AND NOT EXISTS (SELECT 1 FROM public.despesa_alocacoes da WHERE da.despesa_id = d.id);

INSERT INTO public.despesa_anexos (despesa_id, caminho_dropbox, nome_arquivo, principal, criado_em, criado_por)
SELECT d.id, pc.anexo_path, COALESCE(NULLIF(pc.anexo_nome, ''), pc.anexo_path), TRUE, d.criado_em, pc.usuario_id
FROM public.despesas d
JOIN public.projeto_custos pc ON pc.id = d.migrado_de_custo_id
WHERE d.origem = 'MIGRACAO'
  AND pc.anexo_path IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM public.despesa_anexos da WHERE da.despesa_id = d.id);

COMMIT;
