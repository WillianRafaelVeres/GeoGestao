-- Unifica o fluxo operacional de todos os tipos de processo.
-- Migracao idempotente: preserva a etapa atual e nao duplica etapas existentes.
BEGIN;

WITH standard_stage(stage_key, can_skip) AS (
    VALUES
        ('ORCAMENTO', 0),
        ('DOCUMENTOS', 0),
        ('MEDICAO', 0),
        ('PROCESSAMENTO', 0),
        ('ESCRITORIO', 0),
        ('ASSINATURAS', 0),
        ('ORGAO_EXTERNO', 1),
        ('FINALIZADO', 0)
)
UPDATE public.process_stage_templates pst
SET applicability = 'OBRIGATORIA',
    can_skip = standard_stage.can_skip,
    blocks_completion = 1,
    show_in_matrix = 1,
    show_in_project = 1,
    active = 1,
    updated_at = to_char(clock_timestamp() AT TIME ZONE 'America/Sao_Paulo', 'YYYY-MM-DD"T"HH24:MI:SS.MS')
FROM standard_stage
WHERE pst.stage_key = standard_stage.stage_key;

WITH current_orders AS (
    SELECT p.id AS project_id,
           p.etapa_atual_id,
           COALESCE(current_stage.stage_order, current_model.ordem) AS current_order
    FROM public.projetos p
    LEFT JOIN public.projeto_etapas current_stage ON current_stage.id = p.etapa_atual_id
    LEFT JOIN public.etapas_modelo current_model ON current_model.id = current_stage.etapa_modelo_id
)
UPDATE public.projeto_etapas pe
SET process_type_key = pst.process_type_key,
    stage_name = CASE WHEN pst.stage_key = 'ORGAO_EXTERNO' THEN 'Orgao externo' ELSE pst.stage_name END,
    stage_order = pst.stage_order,
    applicability = 'OBRIGATORIA',
    workflow_active = 1,
    can_skip = CASE WHEN pst.stage_key = 'ORGAO_EXTERNO' THEN 1 ELSE 0 END,
    blocks_completion = 1,
    show_in_matrix = 1,
    show_in_project = 1,
    external_actor_type = pst.external_actor_type,
    template_stage_id = pst.id,
    stage_description = CASE
        WHEN pst.stage_key = 'ORGAO_EXTERNO'
            THEN 'Protocolo e retirada em prefeitura, cartorio, SIGEF, INCRA, SICAR ou outro orgao externo.'
        ELSE pst.description
    END,
    model_notes = pst.notes,
    status = CASE
        WHEN lower(COALESCE(pe.status, '')) <> 'nao aplicavel' THEN pe.status
        WHEN pe.id = co.etapa_atual_id THEN 'em andamento'
        WHEN pst.stage_order < co.current_order THEN 'concluido'
        ELSE 'nao iniciado'
    END,
    progresso = CASE
        WHEN lower(COALESCE(pe.status, '')) <> 'nao aplicavel' THEN pe.progresso
        WHEN pe.id = co.etapa_atual_id THEN GREATEST(COALESCE(pe.progresso, 0), 10)
        WHEN pst.stage_order < co.current_order THEN 100
        ELSE 0
    END,
    data_inicio = CASE
        WHEN lower(COALESCE(pe.status, '')) = 'nao aplicavel' AND pe.id = co.etapa_atual_id
            THEN COALESCE(pe.data_inicio, to_char(clock_timestamp() AT TIME ZONE 'America/Sao_Paulo', 'YYYY-MM-DD"T"HH24:MI:SS.MS'))
        ELSE pe.data_inicio
    END,
    data_fim = CASE
        WHEN lower(COALESCE(pe.status, '')) = 'nao aplicavel' THEN NULL
        ELSE pe.data_fim
    END
FROM public.projetos p
JOIN public.process_stage_templates pst ON pst.process_type_key = p.tipo_servico
JOIN current_orders co ON co.project_id = p.id
WHERE pe.projeto_id = p.id
  AND pe.stage_key = pst.stage_key
  AND pst.stage_key IN (
      'ORCAMENTO', 'DOCUMENTOS', 'MEDICAO', 'PROCESSAMENTO',
      'ESCRITORIO', 'ASSINATURAS', 'ORGAO_EXTERNO', 'FINALIZADO'
  );

WITH current_orders AS (
    SELECT p.id AS project_id,
           COALESCE(current_stage.stage_order, current_model.ordem) AS current_order
    FROM public.projetos p
    LEFT JOIN public.projeto_etapas current_stage ON current_stage.id = p.etapa_atual_id
    LEFT JOIN public.etapas_modelo current_model ON current_model.id = current_stage.etapa_modelo_id
),
stage_models(stage_key, model_name, default_substage) AS (
    VALUES
        ('ORCAMENTO', 'Orcamento', 'Proposta enviada'),
        ('DOCUMENTOS', 'Documentos', 'Matricula recebida'),
        ('MEDICAO', 'Medicao', 'Campo agendado'),
        ('PROCESSAMENTO', 'Processamento', 'Dados baixados'),
        ('ESCRITORIO', 'Escritorio', 'Planta iniciada'),
        ('ASSINATURAS', 'Assinaturas', 'Cliente notificado'),
        ('ORGAO_EXTERNO', 'Orgao externo', 'Protocolo registrado'),
        ('FINALIZADO', 'Finalizado', 'Entrega ao cliente')
)
INSERT INTO public.projeto_etapas
    (projeto_id, etapa_modelo_id, process_type_key, stage_key, stage_name, stage_order,
     applicability, status, responsavel_id, data_inicio, data_fim, prazo, progresso,
     subetapa_ativa, workflow_active, can_skip, blocks_completion, show_in_matrix,
     show_in_project, external_actor_type, template_stage_id, stage_description, model_notes)
SELECT
    p.id,
    em.id,
    pst.process_type_key,
    pst.stage_key,
    CASE WHEN pst.stage_key = 'ORGAO_EXTERNO' THEN 'Orgao externo' ELSE pst.stage_name END,
    pst.stage_order,
    'OBRIGATORIA',
    CASE WHEN pst.stage_order < co.current_order THEN 'concluido' ELSE 'nao iniciado' END,
    NULL,
    NULL,
    NULL,
    NULL,
    CASE WHEN pst.stage_order < co.current_order THEN 100 ELSE 0 END,
    sm.default_substage,
    1,
    CASE WHEN pst.stage_key = 'ORGAO_EXTERNO' THEN 1 ELSE 0 END,
    1,
    1,
    1,
    pst.external_actor_type,
    pst.id,
    CASE
        WHEN pst.stage_key = 'ORGAO_EXTERNO'
            THEN 'Protocolo e retirada em prefeitura, cartorio, SIGEF, INCRA, SICAR ou outro orgao externo.'
        ELSE pst.description
    END,
    pst.notes
FROM public.projetos p
JOIN public.process_stage_templates pst ON pst.process_type_key = p.tipo_servico
JOIN stage_models sm ON sm.stage_key = pst.stage_key
JOIN public.etapas_modelo em ON em.nome = sm.model_name AND em.ativa = 1
LEFT JOIN current_orders co ON co.project_id = p.id
WHERE NOT EXISTS (
    SELECT 1
    FROM public.projeto_etapas existing
    WHERE existing.projeto_id = p.id
      AND existing.stage_key = pst.stage_key
);

COMMIT;
