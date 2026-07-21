-- A etapa Exigencias usa apenas os itens vinculados as notas do orgao externo.
-- Os registros antigos permanecem no banco para preservar o historico.
BEGIN;

UPDATE public.process_checklist_templates
SET active = 0,
    updated_at = CURRENT_TIMESTAMP::text
WHERE stage_key = 'PENDENCIAS'
  AND active = 1;

UPDATE public.project_checklist_items
SET active = 0,
    updated_at = CURRENT_TIMESTAMP::text
WHERE stage_key = 'PENDENCIAS'
  AND active = 1;

COMMIT;
