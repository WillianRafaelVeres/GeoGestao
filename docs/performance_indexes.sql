-- Indices seguros para acelerar Dashboard, Matriz e acoes frequentes.
-- Rode no SQL Editor do Supabase com um usuario dono/admin do banco.
-- Os comandos usam IF NOT EXISTS e nao apagam nem alteram dados.

CREATE INDEX IF NOT EXISTS idx_projetos_etapa_atual ON projetos (etapa_atual_id);
CREATE INDEX IF NOT EXISTS idx_projetos_cliente ON projetos (cliente_id);
CREATE INDEX IF NOT EXISTS idx_projetos_cartorio ON projetos (cartorio_id);
CREATE INDEX IF NOT EXISTS idx_projetos_responsavel ON projetos (responsavel_geral_id);
CREATE INDEX IF NOT EXISTS idx_projetos_tipo_servico ON projetos (tipo_servico);
CREATE INDEX IF NOT EXISTS idx_projetos_ordem ON projetos (ordem_prioridade, criado_em, id);

CREATE INDEX IF NOT EXISTS idx_projeto_etapas_projeto_modelo ON projeto_etapas (projeto_id, etapa_modelo_id);
CREATE INDEX IF NOT EXISTS idx_projeto_etapas_projeto_visivel ON projeto_etapas (projeto_id, show_in_project);
CREATE INDEX IF NOT EXISTS idx_projeto_etapas_prazo_status ON projeto_etapas (prazo, status);

CREATE INDEX IF NOT EXISTS idx_project_checklist_stage_active_status
    ON project_checklist_items (project_stage_id, active, status, order_index, id);

CREATE INDEX IF NOT EXISTS idx_checklist_itens_etapa_concluido
    ON checklist_itens (projeto_etapa_id, concluido, id);

CREATE INDEX IF NOT EXISTS idx_tarefas_etapa_status_prazo
    ON tarefas (projeto_etapa_id, status, prazo);

CREATE INDEX IF NOT EXISTS idx_pendencias_etapa_status_prazo
    ON pendencias (etapa_id, status, prazo, id);

CREATE INDEX IF NOT EXISTS idx_pendencias_projeto_status
    ON pendencias (projeto_id, status);

CREATE INDEX IF NOT EXISTS idx_eventos_projeto_tipo_criado
    ON eventos_historico (projeto_id, tipo_evento, criado_em DESC);

CREATE INDEX IF NOT EXISTS idx_exigencias_projeto_status_prazo
    ON exigencias_cartorio (projeto_id, status, prazo_resposta);

CREATE INDEX IF NOT EXISTS idx_exigencias_status_prazo
    ON exigencias_cartorio (status, prazo_resposta);
