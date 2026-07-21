from process_types import PROCESS_TYPE_BY_KEY, resolve_process_type_key
from process_stage_templates import RETIRED_WORKFLOW_STAGE_KEYS


REQUIREMENT_REQUIRED = "OBRIGATORIO"
REQUIREMENT_RECOMMENDED = "RECOMENDADO"
REQUIREMENT_OPTIONAL = "OPCIONAL"
REQUIREMENT_CONDITIONAL = "CONDICIONAL"

CRITICALITY_LOW = "BAIXA"
CRITICALITY_MEDIUM = "MEDIA"
CRITICALITY_HIGH = "ALTA"
CRITICALITY_CRITICAL = "CRITICA"

ROLE_MANAGER = "GESTOR"
ROLE_FIELD = "CAMPO"
ROLE_OFFICE = "ESCRITORIO"
ROLE_DOCUMENTATION = "DOCUMENTACAO"
ROLE_REGISTRY = "CARTORIO"
ROLE_ENVIRONMENTAL = "AMBIENTAL"
ROLE_LEGAL = "JURIDICO"
ROLE_FINANCE = "FINANCEIRO"
ROLE_CLIENT = "CLIENTE"
ROLE_OTHER = "OUTRO"

CHECKLIST_STATUS_NOT_STARTED = "NAO_INICIADO"
CHECKLIST_STATUS_IN_PROGRESS = "EM_ANDAMENTO"
CHECKLIST_STATUS_DONE = "CONCLUIDO"
CHECKLIST_STATUS_NOT_APPLICABLE = "NAO_APLICAVEL"

REQUIREMENT_LABELS = {
    REQUIREMENT_REQUIRED: "Obrigatorio",
    REQUIREMENT_RECOMMENDED: "Recomendado",
    REQUIREMENT_OPTIONAL: "Opcional",
    REQUIREMENT_CONDITIONAL: "Condicional",
}

CRITICALITY_LABELS = {
    CRITICALITY_LOW: "Baixa",
    CRITICALITY_MEDIUM: "Media",
    CRITICALITY_HIGH: "Alta",
    CRITICALITY_CRITICAL: "Critica",
}

STAGE_LABELS = {
    "ORCAMENTO": "Orcamento",
    "DOCUMENTOS": "Documentos",
    "ANALISE": "Analise / Viabilidade",
    "PREPARACAO": "Preparacao",
    "MEDICAO": "Medicao / Campo",
    "PROCESSAMENTO": "Processamento",
    "ESCRITORIO": "Escritorio",
    "CONFERENCIA": "Conferencia",
    "ASSINATURAS": "Assinaturas / Anuencias",
    "PREFEITURA": "Prefeitura",
    "ORGAO_EXTERNO": "Cartorio",
    "PENDENCIAS": "Exigencias",
    "ENTREGA": "Entrega / Encerramento",
    "FINALIZADO": "Finalizado",
}

STAGE_DEFAULT_ROLE = {
    "ORCAMENTO": ROLE_MANAGER,
    "DOCUMENTOS": ROLE_DOCUMENTATION,
    "ANALISE": ROLE_MANAGER,
    "PREPARACAO": ROLE_MANAGER,
    "MEDICAO": ROLE_FIELD,
    "PROCESSAMENTO": ROLE_OFFICE,
    "ESCRITORIO": ROLE_OFFICE,
    "CONFERENCIA": ROLE_MANAGER,
    "ASSINATURAS": ROLE_DOCUMENTATION,
    "PREFEITURA": ROLE_REGISTRY,
    "ORGAO_EXTERNO": ROLE_REGISTRY,
    "PENDENCIAS": ROLE_MANAGER,
    "ENTREGA": ROLE_MANAGER,
    "FINALIZADO": ROLE_MANAGER,
}


def item(
    title,
    requirement_level=REQUIREMENT_REQUIRED,
    criticality=CRITICALITY_MEDIUM,
    role=None,
    blocks_stage_completion=None,
    blocks_process_completion=False,
    requires_attachment=False,
    allows_observation=True,
    condition_text="",
    help_text="",
    description="",
):
    if blocks_stage_completion is None:
        blocks_stage_completion = requirement_level == REQUIREMENT_REQUIRED
    return {
        "title": title,
        "description": description,
        "requirement_level": requirement_level,
        "criticality": criticality,
        "default_responsible_role": role,
        "blocks_stage_completion": blocks_stage_completion,
        "blocks_process_completion": blocks_process_completion,
        "requires_attachment": requires_attachment,
        "allows_observation": allows_observation,
        "condition_text": condition_text,
        "help_text": help_text,
    }


def rec(title, **kwargs):
    return item(title, requirement_level=REQUIREMENT_RECOMMENDED, blocks_stage_completion=False, **kwargs)


def opt(title, **kwargs):
    return item(title, requirement_level=REQUIREMENT_OPTIONAL, blocks_stage_completion=False, **kwargs)


def cond(title, condition_text="", **kwargs):
    return item(title, requirement_level=REQUIREMENT_CONDITIONAL, condition_text=condition_text, **kwargs)


def prefeitura_item(**kwargs):
    """Item de checklist da etapa Assinaturas que remete ao botao Prefeitura (popup com
    o que aquela prefeitura exige e o link para solicitar online). A prefeitura e tratada
    aqui como uma anuencia/exigencia a resolver junto com as demais assinaturas, e nao
    mais como parte do fluxo de protocolo do orgao externo (que agora e somente cartorio).
    """
    return item(
        "Prefeitura",
        role=ROLE_DOCUMENTATION,
        criticality=CRITICALITY_HIGH,
        help_text="Confira o que a prefeitura do municipio exige no botao Prefeitura, ao lado de Detalhes completos.",
        **kwargs,
    )


def orcamento_padrao():
    return [
        item("Elaborar orcamento", role=ROLE_FINANCE),
        item("Enviar orcamento ao cliente", role=ROLE_MANAGER, criticality=CRITICALITY_HIGH),
    ]


RETIFICACAO_AREA_RURAL = {
    "ORCAMENTO": orcamento_padrao(),
    "DOCUMENTOS": [
        item("Solicitar matricula/transcricao atualizada", criticality=CRITICALITY_HIGH, requires_attachment=True),
        item("Solicitar documentos pessoais do proprietario", requires_attachment=True),
        cond("Solicitar documentos do conjuge, se aplicavel", "Quando estado civil/regime exigir conjuge."),
        cond("Solicitar procuracao, se houver procurador", "Quando quem assina for procurador.", requires_attachment=True),
        cond("Solicitar CCIR, CAR, ITR ou documentos rurais quando aplicavel", "Conforme natureza do imovel rural."),
        item("Conferir se documentos recebidos estao legiveis", criticality=CRITICALITY_HIGH),
        item("Registrar documentos faltantes"),
    ],
    "ANALISE": [
        item("Conferir area, perimetro e confrontacoes da matricula", criticality=CRITICALITY_CRITICAL),
        item("Identificar divergencia entre matricula e realidade", criticality=CRITICALITY_HIGH),
        item("Verificar confrontantes"),
        cond("Verificar necessidade de anuencia", "Quando houver confrontantes/terceiros relevantes."),
        rec("Verificar se ha sobreposicao ou conflito aparente", criticality=CRITICALITY_HIGH),
        item("Confirmar se retificacao e o processo correto", criticality=CRITICALITY_HIGH),
        item("Definir estrategia operacional"),
    ],
    "PREPARACAO": [
        item("Criar/organizar pasta do projeto"),
        item("Separar dados para campo"),
        item("Planejar medicao"),
        item("Definir equipe responsavel"),
        item("Conferir equipamentos necessarios"),
        cond("Agendar campo com cliente, se necessario", "Quando depender de acesso acompanhado."),
    ],
    "MEDICAO": [
        item("Executar levantamento de campo", role=ROLE_FIELD, criticality=CRITICALITY_HIGH),
        item("Coletar pontos/perimetro", role=ROLE_FIELD, criticality=CRITICALITY_HIGH),
        item("Registrar confrontacoes", role=ROLE_FIELD),
        item("Conferir acessos e marcos", role=ROLE_FIELD),
        rec("Registrar observacoes de campo", role=ROLE_FIELD),
        item("Salvar dados brutos na pasta do projeto", role=ROLE_FIELD, requires_attachment=True),
    ],
    "PROCESSAMENTO": [
        item("Descarregar dados de campo"),
        item("Processar pontos", criticality=CRITICALITY_HIGH),
        item("Conferir fechamento/perimetro", criticality=CRITICALITY_HIGH),
        item("Conferir area apurada", criticality=CRITICALITY_HIGH),
        item("Verificar inconsistencias tecnicas"),
        item("Salvar arquivos processados", requires_attachment=True),
    ],
    "ESCRITORIO": [
        item("Elaborar planta", criticality=CRITICALITY_HIGH),
        item("Elaborar memorial descritivo", criticality=CRITICALITY_HIGH),
        item("Preparar requerimento de retificacao"),
        cond("Preparar declaracao Art. 213, se aplicavel", "Quando exigida para o caso/cartorio."),
        cond("Preparar declaracao de responsabilidade, se aplicavel", "Quando exigida para o caso/cartorio."),
        item("Organizar documentos para protocolo"),
    ],
    "CONFERENCIA": [
        item("Conferir dados do proprietario"),
        item("Conferir matricula/certidao", criticality=CRITICALITY_HIGH),
        item("Conferir area antiga e nova", criticality=CRITICALITY_CRITICAL),
        item("Conferir perimetro", criticality=CRITICALITY_CRITICAL),
        item("Conferir confrontantes", criticality=CRITICALITY_HIGH),
        item("Conferir pecas finais"),
        item("Revisar pendencias antes de assinatura"),
    ],
    "ASSINATURAS": [
        prefeitura_item(),
        item("Coletar assinatura do proprietario", role=ROLE_CLIENT),
        cond("Coletar assinatura do conjuge, se aplicavel", "Quando juridicamente necessario.", role=ROLE_CLIENT),
        cond("Coletar assinatura do procurador, se aplicavel", "Quando assina por procuracao.", role=ROLE_CLIENT),
        cond("Coletar anuencia de confrontantes, se aplicavel", "Quando o procedimento exigir anuencia.", role=ROLE_CLIENT),
        cond("Conferir reconhecimento de firma, se necessario", "Conforme exigencia do cartorio.", role=ROLE_DOCUMENTATION),
    ],
    "ORGAO_EXTERNO": [
        item("Protocolar no cartorio", role=ROLE_REGISTRY, criticality=CRITICALITY_HIGH),
        item("Registrar data de protocolo", role=ROLE_REGISTRY),
        item("Registrar numero de protocolo", role=ROLE_REGISTRY),
        item("Acompanhar analise do cartorio", role=ROLE_REGISTRY),
    ],
    "PENDENCIAS": [
        item("Registrar exigencia do cartorio", role=ROLE_REGISTRY, criticality=CRITICALITY_HIGH),
        item("Identificar responsavel pela correcao"),
        item("Corrigir documentacao ou peca tecnica"),
        cond("Recolher nova assinatura, se necessario", "Quando a correcao alterar peca assinada."),
        item("Reprotocolar ou responder exigencia", role=ROLE_REGISTRY),
    ],
    "ENTREGA": [
        item("Confirmar registro/averbacao concluida", criticality=CRITICALITY_HIGH),
        item("Entregar documentos ao cliente"),
        item("Arquivar pasta final"),
        item("Marcar projeto como finalizado"),
    ],
}

DESMEMBRAMENTO = {
    "ORCAMENTO": orcamento_padrao(),
    "DOCUMENTOS": [
        item("Solicitar matricula atualizada", requires_attachment=True),
        item("Solicitar documentos do proprietario"),
        cond("Solicitar documentos do conjuge/procurador, se aplicavel", "Quando houver conjuge ou procurador."),
        item("Solicitar informacoes da divisao pretendida"),
        item("Conferir documentos recebidos"),
    ],
    "ANALISE": [
        item("Verificar se matricula permite desmembramento", criticality=CRITICALITY_HIGH),
        item("Verificar se ha necessidade de retificacao previa", criticality=CRITICALITY_HIGH),
        cond("Conferir legislacao municipal, se aplicavel", "Quando houver exigencia municipal."),
        item("Avaliar necessidade de prefeitura ou cartorio"),
        item("Definir areas resultantes"),
    ],
    "PREPARACAO": [
        item("Organizar pasta"),
        item("Separar base tecnica existente"),
        item("Definir se havera campo"),
        rec("Preparar croqui/planejamento interno"),
    ],
    "MEDICAO": [
        cond("Executar campo se necessario", "Quando base existente nao for suficiente.", role=ROLE_FIELD),
        cond("Conferir limites internos", "Quando houver divisao fisica a validar.", role=ROLE_FIELD),
        cond("Materializar ou conferir pontos da divisao, se aplicavel", "Quando contratado ou necessario.", role=ROLE_FIELD),
    ],
    "PROCESSAMENTO": [
        cond("Processar dados se houver campo", "Quando a etapa de campo for executada."),
        cond("Conferir areas resultantes", "Quando houver dados tecnicos novos."),
        cond("Conferir perimetros", "Quando houver dados tecnicos novos."),
    ],
    "ESCRITORIO": [
        item("Elaborar planta de desmembramento", criticality=CRITICALITY_HIGH),
        item("Elaborar memoriais das areas resultantes", criticality=CRITICALITY_HIGH),
        item("Preparar requerimento"),
        cond("Preparar documentacao para cartorio/prefeitura, se aplicavel", "Conforme orgao competente."),
    ],
    "CONFERENCIA": [
        item("Conferir areas resultantes"),
        item("Conferir memoriais"),
        item("Conferir matricula"),
        item("Conferir documentos antes de assinatura/protocolo"),
    ],
    "ASSINATURAS": [
        prefeitura_item(),
        item("Coletar assinatura do proprietario", role=ROLE_CLIENT),
        cond("Coletar assinatura do conjuge/procurador, se aplicavel", "Quando juridicamente necessario.", role=ROLE_CLIENT),
        cond("Coletar assinaturas exigidas pelo cartorio ou orgao competente", "Conforme exigencia externa.", role=ROLE_CLIENT),
    ],
    "ORGAO_EXTERNO": [
        item("Protocolar no cartorio", role=ROLE_REGISTRY),
        item("Registrar protocolo", role=ROLE_REGISTRY),
        item("Acompanhar analise", role=ROLE_REGISTRY),
    ],
    "PENDENCIAS": [
        item("Registrar exigencia"),
        item("Corrigir pecas/documentos"),
        item("Reprotocolar ou responder"),
    ],
    "ENTREGA": [
        item("Confirmar conclusao"),
        item("Entregar documentos finais"),
        item("Arquivar pasta"),
    ],
}

DESTACAMENTO_ESTREMACAO = {
    "ORCAMENTO": orcamento_padrao(),
    "DOCUMENTOS": [
        item("Solicitar matricula/transcricao"),
        item("Solicitar documentos dos interessados"),
        cond("Solicitar documentos de representacao, se houver", "Quando houver procurador/representante."),
        cond("Solicitar informacoes dos demais condominos/confrontantes, se aplicavel", "Quando o caso exigir anuencia ou conferencia."),
        item("Conferir documentacao recebida"),
    ],
    "ANALISE": [
        item("Verificar possibilidade de destacamento/estremacao", criticality=CRITICALITY_HIGH),
        cond("Conferir titularidade e fracao ideal, se aplicavel", "Quando houver condominio/fração ideal."),
        item("Verificar necessidade de anuencia"),
        item("Verificar necessidade de advogado/cartorio"),
        item("Definir estrategia do processo"),
    ],
    "MEDICAO": [
        item("Medir area destacada", role=ROLE_FIELD),
        item("Conferir limites e confrontacoes", role=ROLE_FIELD),
        item("Registrar marcos/pontos relevantes", role=ROLE_FIELD),
        item("Salvar dados brutos", role=ROLE_FIELD, requires_attachment=True),
    ],
    "PROCESSAMENTO": [
        item("Processar pontos"),
        item("Conferir area destacada"),
        item("Conferir perimetro"),
        item("Conferir confrontacoes"),
    ],
    "ESCRITORIO": [
        item("Elaborar planta da area destacada"),
        item("Elaborar memorial descritivo"),
        item("Preparar documentos tecnicos"),
        item("Preparar requerimento ou pecas exigidas"),
    ],
    "CONFERENCIA": [
        item("Conferir area, perimetro e confrontacoes"),
        item("Conferir identificacao dos interessados"),
        item("Conferir pecas finais"),
    ],
    "ASSINATURAS": [
        prefeitura_item(),
        item("Coletar assinatura do interessado", role=ROLE_CLIENT),
        item("Coletar anuencias necessarias", role=ROLE_CLIENT),
        cond("Conferir reconhecimento de firma, se aplicavel", "Conforme exigencia externa."),
    ],
    "ORGAO_EXTERNO": [
        item("Protocolar no cartorio ou orgao competente", role=ROLE_REGISTRY),
        item("Registrar protocolo", role=ROLE_REGISTRY),
        item("Acompanhar analise", role=ROLE_REGISTRY),
    ],
    "PENDENCIAS": [
        item("Registrar exigencia"),
        item("Corrigir documentos/pecas"),
        item("Reprotocolar"),
    ],
    "ENTREGA": [
        item("Confirmar conclusao"),
        item("Entregar documentos finais"),
        item("Arquivar pasta"),
    ],
}

UNIFICACAO = {
    "ORCAMENTO": orcamento_padrao(),
    "DOCUMENTOS": [
        item("Solicitar matriculas atualizadas", criticality=CRITICALITY_HIGH),
        item("Solicitar documentos do proprietario"),
        cond("Solicitar documentos do conjuge/procurador, se aplicavel", "Quando houver conjuge ou procurador."),
        item("Conferir documentacao recebida"),
    ],
    "ANALISE": [
        item("Verificar se matriculas podem ser unificadas", criticality=CRITICALITY_HIGH),
        item("Verificar se ha necessidade de retificacao previa", criticality=CRITICALITY_HIGH),
        item("Conferir titularidade"),
        item("Conferir continuidade/confrontacao entre areas"),
    ],
    "PREPARACAO": [
        item("Organizar pasta"),
        item("Separar base tecnica existente"),
        item("Definir necessidade de campo"),
    ],
    "MEDICAO": [
        cond("Executar campo se necessario", "Quando a base documental/tecnica nao for suficiente.", role=ROLE_FIELD),
        cond("Conferir perimetro resultante", "Quando houver campo ou base tecnica a validar.", role=ROLE_FIELD),
    ],
    "PROCESSAMENTO": [
        cond("Processar dados se houver campo", "Quando houver dados novos."),
        cond("Conferir area resultante", "Quando houver dados novos."),
        cond("Conferir perimetro resultante", "Quando houver dados novos."),
    ],
    "ESCRITORIO": [
        item("Elaborar planta de unificacao"),
        item("Elaborar memorial da area resultante"),
        item("Preparar requerimento"),
        item("Organizar documentos para protocolo"),
    ],
    "CONFERENCIA": [
        item("Conferir matriculas"),
        item("Conferir area resultante"),
        item("Conferir memorial/planta"),
        item("Conferir documentos"),
    ],
    "ASSINATURAS": [
        prefeitura_item(),
        item("Coletar assinatura do proprietario", role=ROLE_CLIENT),
        cond("Coletar assinatura do conjuge/procurador, se aplicavel", "Quando juridicamente necessario.", role=ROLE_CLIENT),
    ],
    "ORGAO_EXTERNO": [
        item("Protocolar no cartorio", role=ROLE_REGISTRY),
        item("Registrar protocolo", role=ROLE_REGISTRY),
        item("Acompanhar analise", role=ROLE_REGISTRY),
    ],
    "PENDENCIAS": [
        item("Registrar exigencia"),
        item("Corrigir pecas/documentos"),
        item("Reprotocolar"),
    ],
    "ENTREGA": [
        item("Confirmar conclusao"),
        item("Entregar documentos finais"),
        item("Arquivar pasta"),
    ],
}

USUCAPIAO = {
    "ORCAMENTO": orcamento_padrao(),
    "DOCUMENTOS": [
        item("Solicitar documentos pessoais"),
        item("Solicitar documentos do imovel"),
        item("Solicitar comprovantes de posse", criticality=CRITICALITY_HIGH),
        cond("Solicitar documentos de confrontantes, se aplicavel", "Quando necessario ao procedimento."),
        cond("Solicitar documentos para advogado/cartorio, se aplicavel", "Conforme modalidade."),
    ],
    "ANALISE": [
        item("Avaliar documentacao de posse", criticality=CRITICALITY_HIGH),
        item("Conferir imovel e confrontacoes"),
        item("Verificar necessidade de advogado", role=ROLE_LEGAL),
        item("Verificar modalidade cartorial ou judicial", role=ROLE_LEGAL),
        item("Identificar riscos e pendencias", criticality=CRITICALITY_HIGH),
    ],
    "MEDICAO": [
        item("Medir imovel", role=ROLE_FIELD),
        item("Conferir confrontacoes", role=ROLE_FIELD),
        cond("Registrar ocupacao/uso, se necessario", "Quando ajudar a caracterizar posse.", role=ROLE_FIELD),
        item("Salvar dados brutos", role=ROLE_FIELD),
    ],
    "PROCESSAMENTO": [
        item("Processar levantamento"),
        item("Conferir area e perimetro"),
        item("Conferir confrontacoes"),
    ],
    "ESCRITORIO": [
        item("Elaborar planta"),
        item("Elaborar memorial"),
        item("Preparar pecas tecnicas para usucapiao"),
        item("Organizar documentos para advogado/cartorio"),
    ],
    "CONFERENCIA": [
        item("Conferir pecas tecnicas"),
        item("Conferir documentos"),
        item("Conferir assinaturas necessarias"),
        item("Conferir confrontantes"),
    ],
    "ASSINATURAS": [
        prefeitura_item(),
        item("Coletar assinatura do interessado", role=ROLE_CLIENT),
        cond("Coletar anuencias, se aplicavel", "Quando solicitado pelo advogado/cartorio.", role=ROLE_CLIENT),
        cond("Coletar assinaturas exigidas pelo advogado/cartorio", "Conforme modalidade.", role=ROLE_CLIENT),
    ],
    "ORGAO_EXTERNO": [
        item("Encaminhar ao advogado, forum ou cartorio", role=ROLE_LEGAL),
        item("Registrar protocolo ou andamento", role=ROLE_LEGAL),
        item("Acompanhar retorno", role=ROLE_LEGAL),
    ],
    "PENDENCIAS": [
        item("Registrar exigencia"),
        item("Corrigir documentos ou pecas"),
        item("Encaminhar resposta"),
    ],
    "ENTREGA": [
        item("Entregar arquivos/documentos finais da parte tecnica"),
        item("Arquivar pasta"),
        item("Marcar projeto como finalizado ou encerrado pela parte tecnica"),
    ],
}

GEORREFERENCIAMENTO_TECNICO = {
    "ORCAMENTO": orcamento_padrao(),
    "DOCUMENTOS": [
        item("Solicitar matricula ou documento do imovel"),
        item("Solicitar CCIR/SNCR, se aplicavel"),
        item("Solicitar dados tecnicos existentes, se houver"),
        item("Conferir documentos recebidos"),
    ],
    "ANALISE": [
        item("Avaliar dados existentes"),
        item("Verificar necessidade de certificacao SIGEF"),
        rec("Verificar indicios de sobreposicao ou conflito tecnico", criticality=CRITICALITY_HIGH),
        item("Definir estrategia tecnica"),
    ],
    "PREPARACAO": [
        item("Organizar pasta"),
        item("Planejar campo"),
        item("Separar equipamentos"),
        item("Definir equipe"),
    ],
    "MEDICAO": [
        item("Executar levantamento georreferenciado", role=ROLE_FIELD),
        item("Levantar perimetro", role=ROLE_FIELD),
        item("Conferir confrontacoes", role=ROLE_FIELD),
        item("Salvar dados brutos", role=ROLE_FIELD, requires_attachment=True),
    ],
    "PROCESSAMENTO": [
        item("Processar dados"),
        item("Conferir fechamento"),
        item("Conferir area e perimetro"),
        item("Gerar arquivos tecnicos"),
    ],
    "ESCRITORIO": [
        item("Preparar planta/memorial, se contratado"),
        item("Organizar arquivos tecnicos"),
        cond("Preparar dados para SIGEF, se aplicavel", "Quando houver certificacao contratada."),
    ],
    "CONFERENCIA": [
        item("Conferir coordenadas"),
        item("Conferir confrontacoes"),
        item("Conferir arquivos finais"),
    ],
    "ASSINATURAS": [
        cond("Coletar assinaturas/anuencias, se aplicavel", "Quando houver documentos assinados."),
    ],
    "ORGAO_EXTERNO": [
        cond("Encaminhar ao SIGEF/INCRA, se contratado", "Somente quando certificacao estiver incluida.", role=ROLE_REGISTRY),
    ],
    "PENDENCIAS": [
        cond("Registrar pendencia tecnica ou externa", "Quando houver retorno tecnico."),
        cond("Corrigir inconsistencias", "Quando necessario."),
    ],
    "ENTREGA": [
        item("Entregar resultado tecnico ao cliente"),
        item("Arquivar arquivos finais"),
        item("Marcar projeto como finalizado"),
    ],
}

CERTIFICACAO_SIGEF = {
    "ORCAMENTO": orcamento_padrao(),
    "DOCUMENTOS": [
        item("Solicitar matricula"),
        item("Solicitar CCIR/SNCR"),
        item("Solicitar documentos do proprietario"),
        cond("Solicitar ART/TRT, se aplicavel", "Quando exigida no caso."),
        cond("Solicitar dados tecnicos existentes, se houver", "Quando cliente possui base anterior."),
    ],
    "ANALISE": [
        item("Verificar se dados existentes sao confiaveis", criticality=CRITICALITY_HIGH),
        item("Verificar necessidade de campo"),
        item("Conferir situacao no SIGEF"),
        item("Verificar indicios de sobreposicao", criticality=CRITICALITY_HIGH),
        item("Definir estrategia de certificacao"),
    ],
    "MEDICAO": [
        cond("Executar campo se necessario", "Quando dados existentes forem insuficientes.", role=ROLE_FIELD),
        cond("Levantar perimetro", "Quando houver campo.", role=ROLE_FIELD),
        cond("Conferir confrontacoes", "Quando houver campo.", role=ROLE_FIELD),
        cond("Salvar dados brutos", "Quando houver campo.", role=ROLE_FIELD, requires_attachment=True),
    ],
    "PROCESSAMENTO": [
        item("Processar dados"),
        item("Preparar planilha/arquivo tecnico", criticality=CRITICALITY_HIGH),
        item("Conferir fechamento"),
        item("Conferir confrontacoes"),
        item("Verificar sobreposicao aparente", criticality=CRITICALITY_HIGH),
    ],
    "ESCRITORIO": [
        item("Preparar dados para SIGEF"),
        cond("Preparar planta/memorial, se aplicavel", "Quando fizer parte da entrega."),
        item("Organizar arquivos tecnicos"),
        rec("Preparar documentos auxiliares"),
    ],
    "CONFERENCIA": [
        item("Conferir planilha/arquivo SIGEF", criticality=CRITICALITY_CRITICAL),
        item("Conferir matricula"),
        item("Conferir dados do proprietario"),
        item("Conferir confrontacoes"),
        item("Conferir consistencia tecnica"),
    ],
    "ORGAO_EXTERNO": [
        item("Submeter no SIGEF/INCRA", role=ROLE_REGISTRY, criticality=CRITICALITY_HIGH),
        item("Registrar protocolo/certificacao", role=ROLE_REGISTRY),
        item("Acompanhar analise", role=ROLE_REGISTRY),
    ],
    "PENDENCIAS": [
        item("Registrar erro ou pendencia SIGEF", role=ROLE_REGISTRY),
        item("Corrigir sobreposicao/inconsistencia"),
        item("Reenviar ao SIGEF", role=ROLE_REGISTRY),
    ],
    "ENTREGA": [
        item("Entregar certificacao/relatorios ao cliente"),
        item("Arquivar arquivos finais"),
        item("Marcar projeto como finalizado"),
    ],
}

AVERBACAO_CERTIFICACAO = {
    "ORCAMENTO": orcamento_padrao(),
    "DOCUMENTOS": [
        item("Solicitar matricula atualizada"),
        item("Solicitar certificado SIGEF", criticality=CRITICALITY_HIGH),
        item("Solicitar planta e memorial certificados", criticality=CRITICALITY_HIGH),
        item("Solicitar documentos dos proprietarios"),
        cond("Solicitar procuracao", "Quando houver procurador ou representante."),
        cond("Solicitar CCIR, ITR ou CAR", "Quando exigido pelo cartorio."),
        item("Conferir documentos recebidos"),
    ],
    "ANALISE": [
        item("Validar certificacao no SIGEF", criticality=CRITICALITY_CRITICAL),
        item("Conferir correspondencia entre certificacao e matricula", criticality=CRITICALITY_HIGH),
        item("Conferir titularidade e qualificacao dos proprietarios", criticality=CRITICALITY_HIGH),
        item("Conferir area, perimetro e codigo da parcela"),
        item("Verificar exigencias do cartorio competente"),
        item("Definir documentos e assinaturas necessarios"),
    ],
    "PREPARACAO": [
        item("Organizar pasta do processo"),
        item("Confirmar cartorio e CNS"),
        item("Separar modelos exigidos pelo cartorio"),
        item("Montar lista final de documentos"),
    ],
    "ESCRITORIO": [
        item("Elaborar requerimento de averbacao", role=ROLE_DOCUMENTATION, criticality=CRITICALITY_HIGH),
        item("Organizar certificado SIGEF, planta e memorial"),
        item("Preparar documentos obrigatorios do cartorio"),
        cond("Preparar declaracoes complementares", "Quando exigidas pelo cartorio."),
        cond("Emitir guia ou custas para protocolo", "Quando aplicavel.", role=ROLE_FINANCE),
    ],
    "CONFERENCIA": [
        item("Conferir requerimento de averbacao", criticality=CRITICALITY_CRITICAL),
        item("Conferir matricula, titularidade e qualificacao"),
        item("Conferir codigo da certificacao SIGEF"),
        item("Conferir planta e memorial certificados"),
        item("Conferir checklist documental do cartorio"),
    ],
    "ASSINATURAS": [
        item("Coletar assinatura dos proprietarios ou representantes", role=ROLE_DOCUMENTATION),
        cond("Reconhecer firma", "Quando exigido pelo cartorio.", role=ROLE_DOCUMENTATION),
        item("Conferir documentos assinados", role=ROLE_DOCUMENTATION),
    ],
    "ORGAO_EXTERNO": [
        item("Protocolar averbacao no cartorio", role=ROLE_REGISTRY, criticality=CRITICALITY_HIGH),
        item("Registrar numero e data do protocolo", role=ROLE_REGISTRY),
        item("Acompanhar qualificacao registral", role=ROLE_REGISTRY),
        item("Retirar matricula com averbacao concluida", role=ROLE_REGISTRY),
    ],
    "PENDENCIAS": [
        item("Registrar exigencia do cartorio", role=ROLE_REGISTRY),
        item("Corrigir documentos ou requerimento"),
        item("Conferir atendimento da exigencia"),
        item("Reprotocolar documentos", role=ROLE_REGISTRY),
    ],
    "ENTREGA": [
        item("Entregar matricula atualizada ao cliente", role=ROLE_CLIENT),
        item("Entregar comprovantes do protocolo"),
        item("Arquivar documentos finais"),
        item("Marcar projeto como finalizado"),
    ],
}

CAR = {
    "ORCAMENTO": orcamento_padrao(),
    "DOCUMENTOS": [
        item("Solicitar dados do proprietario"),
        item("Solicitar matricula ou documento do imovel"),
        cond("Solicitar CCIR/ITR quando aplicavel", "Quando houver dados rurais disponiveis."),
        cond("Solicitar CAR anterior, se existir", "Quando for retificacao ou analise."),
        cond("Solicitar arquivos/mapas anteriores, se existirem", "Quando houver base anterior."),
    ],
    "ANALISE": [
        item("Verificar situacao atual do CAR", role=ROLE_ENVIRONMENTAL),
        item("Verificar perimetro disponivel", role=ROLE_ENVIRONMENTAL),
        item("Avaliar necessidade de campo", role=ROLE_ENVIRONMENTAL),
        item("Verificar APP, Reserva Legal e uso do solo", role=ROLE_ENVIRONMENTAL, criticality=CRITICALITY_HIGH),
        item("Identificar pendencias ambientais", role=ROLE_ENVIRONMENTAL),
    ],
    "PREPARACAO": [
        item("Organizar pasta"),
        item("Separar base cartografica", role=ROLE_ENVIRONMENTAL),
        item("Definir se havera campo"),
        item("Preparar dados para SICAR", role=ROLE_ENVIRONMENTAL),
    ],
    "MEDICAO": [
        cond("Executar campo se necessario", "Somente se precisar levantar perimetro, APP, reserva ou dados nao confiaveis.", role=ROLE_FIELD),
        cond("Conferir perimetro", "Quando houver campo.", role=ROLE_FIELD),
        cond("Conferir areas ambientais", "Quando houver campo.", role=ROLE_FIELD),
        cond("Registrar informacoes relevantes", "Quando houver campo.", role=ROLE_FIELD),
    ],
    "PROCESSAMENTO": [
        cond("Processar dados geograficos, se houver", "Quando houver campo/base espacial.", role=ROLE_ENVIRONMENTAL),
        cond("Ajustar perimetro", "Quando necessario.", role=ROLE_ENVIRONMENTAL),
        cond("Preparar arquivos espaciais, se necessario", "Quando necessario para SICAR.", role=ROLE_ENVIRONMENTAL),
    ],
    "ESCRITORIO": [
        item("Preencher ou ajustar cadastro no SICAR", role=ROLE_ENVIRONMENTAL, criticality=CRITICALITY_HIGH),
        item("Delimitar APP", role=ROLE_ENVIRONMENTAL, criticality=CRITICALITY_HIGH),
        item("Delimitar Reserva Legal", role=ROLE_ENVIRONMENTAL, criticality=CRITICALITY_HIGH),
        item("Revisar uso do solo", role=ROLE_ENVIRONMENTAL),
        cond("Gerar recibo/demonstrativo quando aplicavel", "Quando o sistema permitir emissao.", role=ROLE_ENVIRONMENTAL),
    ],
    "CONFERENCIA": [
        item("Conferir dados do proprietario", role=ROLE_ENVIRONMENTAL),
        item("Conferir dados do imovel", role=ROLE_ENVIRONMENTAL),
        item("Conferir areas ambientais", role=ROLE_ENVIRONMENTAL, criticality=CRITICALITY_HIGH),
        cond("Conferir recibo/demonstrativo", "Quando emitido.", role=ROLE_ENVIRONMENTAL),
        item("Conferir pendencias antes da entrega", role=ROLE_ENVIRONMENTAL),
    ],
    "ASSINATURAS": [
        cond(
            "Prefeitura",
            "Somente quando houver protocolo ambiental ou municipal na prefeitura.",
            role=ROLE_DOCUMENTATION,
            help_text="Confira o que a prefeitura do municipio exige no botao Prefeitura, ao lado de Detalhes completos.",
        ),
    ],
    "ORGAO_EXTERNO": [
        item("Enviar/atualizar cadastro no SICAR", role=ROLE_ENVIRONMENTAL, criticality=CRITICALITY_HIGH),
        item("Registrar protocolo/recibo", role=ROLE_ENVIRONMENTAL),
        cond("Acompanhar situacao, se aplicavel", "Quando houver acompanhamento pos-envio.", role=ROLE_ENVIRONMENTAL),
    ],
    "PENDENCIAS": [
        item("Registrar pendencia SICAR ou ambiental", role=ROLE_ENVIRONMENTAL),
        item("Corrigir informacoes", role=ROLE_ENVIRONMENTAL),
        item("Reenviar ou atualizar cadastro", role=ROLE_ENVIRONMENTAL),
    ],
    "ENTREGA": [
        item("Entregar recibo/demonstrativo ao cliente", role=ROLE_CLIENT),
        item("Arquivar arquivos finais"),
        item("Marcar projeto como finalizado"),
    ],
}

ATUALIZACAO_CCIR = {
    "ORCAMENTO": orcamento_padrao(),
    "DOCUMENTOS": [
        item("Solicitar CPF/CNPJ do titular"),
        item("Solicitar matricula ou dados do imovel"),
        cond("Solicitar CCIR anterior, se houver", "Quando cliente possuir documento anterior."),
        cond("Solicitar dados de acesso ou procuracao, se aplicavel", "Quando necessario para acessar sistema externo."),
    ],
    "ANALISE": [
        item("Conferir dados cadastrais existentes", criticality=CRITICALITY_HIGH),
        item("Verificar pendencias no SNCR/INCRA", criticality=CRITICALITY_HIGH),
        item("Identificar dados que precisam ser atualizados"),
    ],
    "PREPARACAO": [
        item("Organizar informacoes para atualizacao"),
        item("Separar documentos necessarios"),
        item("Definir responsavel pelo acesso/sistema"),
    ],
    "ESCRITORIO": [
        item("Atualizar dados no SNCR/INCRA", role=ROLE_DOCUMENTATION, criticality=CRITICALITY_HIGH),
        item("Conferir informacoes inseridas", role=ROLE_DOCUMENTATION),
        cond("Emitir taxa ou guia, se aplicavel", "Quando o sistema externo gerar taxa.", role=ROLE_FINANCE),
        cond("Emitir CCIR quando possivel", "Quando a atualizacao permitir emissao.", role=ROLE_DOCUMENTATION),
    ],
    "CONFERENCIA": [
        item("Conferir dados do CCIR emitido"),
        item("Conferir titularidade"),
        item("Conferir area e municipio"),
        item("Conferir pendencias remanescentes"),
    ],
    "ORGAO_EXTERNO": [
        cond("Registrar envio/atualizacao no sistema externo, quando aplicavel", "SNCR/INCRA.", role=ROLE_DOCUMENTATION),
        cond("Acompanhar pendencia do SNCR/INCRA", "Quando houver pendencia externa.", role=ROLE_DOCUMENTATION),
    ],
    "PENDENCIAS": [
        item("Registrar pendencia do cadastro rural"),
        item("Corrigir dados"),
        cond("Reemitir documento, se necessario", "Quando a correcao exigir nova emissao."),
    ],
    "ENTREGA": [
        item("Entregar CCIR/comprovantes ao cliente"),
        item("Arquivar documentos finais"),
        item("Marcar projeto como finalizado"),
    ],
}

MEDICAO = {
    "ORCAMENTO": orcamento_padrao(),
    "PREPARACAO": [
        item("Criar pasta do projeto"),
        item("Planejar campo"),
        item("Separar equipamento", role=ROLE_FIELD),
        item("Definir equipe", role=ROLE_FIELD),
        item("Agendar com cliente", role=ROLE_CLIENT),
    ],
    "MEDICAO": [
        item("Executar levantamento", role=ROLE_FIELD, criticality=CRITICALITY_HIGH),
        item("Coletar pontos", role=ROLE_FIELD),
        rec("Registrar observacoes", role=ROLE_FIELD),
        item("Conferir cobertura da area", role=ROLE_FIELD),
        item("Salvar dados brutos", role=ROLE_FIELD, requires_attachment=True),
    ],
    "PROCESSAMENTO": [
        item("Descarregar dados"),
        item("Processar pontos"),
        item("Conferir consistencia"),
        item("Gerar arquivos tecnicos"),
    ],
    "ESCRITORIO": [
        cond("Elaborar planta, relatorio ou entrega combinada", "Quando fizer parte da contratacao."),
        item("Organizar arquivos para entrega"),
        item("Preparar material final"),
    ],
    "CONFERENCIA": [
        item("Conferir dados processados"),
        item("Conferir entrega tecnica"),
        item("Conferir arquivos finais"),
    ],
    "ENTREGA": [
        item("Entregar resultado ao cliente"),
        item("Arquivar pasta final"),
        item("Marcar projeto como finalizado"),
    ],
}

REGULARIZACAO_TITULARIDADE = {
    "ORCAMENTO": orcamento_padrao(),
    "DOCUMENTOS": [
        item("Solicitar matricula/documentos do imovel"),
        item("Solicitar documentos pessoais das partes"),
        item("Solicitar contratos, recibos, escrituras ou documentos antigos", criticality=CRITICALITY_HIGH),
        cond("Solicitar procuracoes, se aplicavel", "Quando houver representante."),
    ],
    "ANALISE": [
        item("Analisar cadeia documental", criticality=CRITICALITY_HIGH),
        item("Identificar lacunas de titularidade", criticality=CRITICALITY_HIGH),
        item("Verificar necessidade de cartorio/tabelionato/advogado", role=ROLE_LEGAL),
        item("Definir caminho operacional"),
    ],
    "ESCRITORIO": [
        item("Organizar documentacao"),
        item("Preparar requerimentos ou documentos internos"),
        item("Preparar encaminhamento ao orgao competente"),
    ],
    "CONFERENCIA": [
        item("Conferir documentos"),
        item("Conferir dados das partes"),
        item("Conferir necessidade de assinatura/reconhecimento"),
    ],
    "ASSINATURAS": [
        prefeitura_item(),
        item("Coletar assinaturas necessarias", role=ROLE_CLIENT),
        cond("Coletar procuracoes ou reconhecimentos, se aplicavel", "Quando exigido pelo procedimento.", role=ROLE_CLIENT),
    ],
    "ORGAO_EXTERNO": [
        item("Protocolar ou encaminhar ao orgao competente", role=ROLE_LEGAL),
        item("Registrar andamento", role=ROLE_LEGAL),
        item("Acompanhar retorno", role=ROLE_LEGAL),
    ],
    "PENDENCIAS": [
        item("Registrar pendencia"),
        item("Corrigir documentos"),
        item("Reencaminhar"),
    ],
    "ENTREGA": [
        item("Entregar documentacao final"),
        item("Arquivar pasta"),
        item("Marcar projeto como finalizado"),
    ],
}

OUTRO = {
    "ORCAMENTO": orcamento_padrao(),
    "PREPARACAO": [
        item("Organizar pasta"),
        item("Definir proximas acoes"),
        item("Definir responsavel"),
    ],
    "ESCRITORIO": [
        item("Executar atividade principal"),
        rec("Registrar observacoes"),
        item("Conferir resultado"),
    ],
    "ORGAO_EXTERNO": [
        item("Protocolar ou encaminhar ao orgao competente", role=ROLE_REGISTRY),
        item("Registrar andamento", role=ROLE_REGISTRY),
        item("Acompanhar retorno", role=ROLE_REGISTRY),
    ],
    "ENTREGA": [
        item("Entregar resultado ao cliente"),
        item("Arquivar informacoes"),
        item("Finalizar projeto"),
    ],
}

PROCESS_CHECKLIST_SOURCE = {
    "RETIFICACAO_AREA_RURAL": RETIFICACAO_AREA_RURAL,
    "DESMEMBRAMENTO": DESMEMBRAMENTO,
    "DESTACAMENTO_ESTREMACAO": DESTACAMENTO_ESTREMACAO,
    "UNIFICACAO": UNIFICACAO,
    "USUCAPIAO": USUCAPIAO,
    "GEORREFERENCIAMENTO_TECNICO": GEORREFERENCIAMENTO_TECNICO,
    "CERTIFICACAO_SIGEF": CERTIFICACAO_SIGEF,
    "AVERBACAO_CERTIFICACAO": AVERBACAO_CERTIFICACAO,
    "CAR": CAR,
    "ATUALIZACAO_CCIR": ATUALIZACAO_CCIR,
    "MEDICAO": MEDICAO,
    "REGULARIZACAO_TITULARIDADE": REGULARIZACAO_TITULARIDADE,
    "OUTRO": OUTRO,
}


def build_process_checklist_templates():
    templates = {}
    for process_type_key in PROCESS_TYPE_BY_KEY:
        source = PROCESS_CHECKLIST_SOURCE.get(process_type_key, OUTRO)
        rows = []
        for stage_key, items in source.items():
            # Exigencias usa exclusivamente os itens recebidos do orgao externo.
            # Os modelos genericos desta etapa permanecem apenas como historico no fonte.
            if stage_key in RETIRED_WORKFLOW_STAGE_KEYS or stage_key == "PENDENCIAS":
                continue
            for index, data in enumerate(items, 1):
                row = dict(data)
                row["process_type_key"] = process_type_key
                row["stage_key"] = stage_key
                row["stage_name"] = STAGE_LABELS.get(stage_key, stage_key)
                row["order_index"] = index
                row["default_responsible_role"] = row["default_responsible_role"] or STAGE_DEFAULT_ROLE.get(stage_key, ROLE_OTHER)
                row["active"] = True
                rows.append(row)
        templates[process_type_key] = rows
    return templates


PROCESS_CHECKLIST_TEMPLATES = build_process_checklist_templates()


def get_checklist_template_for_process(process_type_key):
    key = resolve_process_type_key(process_type_key)
    return list(PROCESS_CHECKLIST_TEMPLATES.get(key, PROCESS_CHECKLIST_TEMPLATES["OUTRO"]))


def get_checklist_template_for_process_stage(process_type_key, stage_key):
    normalized_stage_key = str(stage_key or "").upper()
    return [
        row for row in get_checklist_template_for_process(process_type_key)
        if row["stage_key"] == normalized_stage_key
    ]


def get_checklist_template_grouped_by_stage(process_type_key):
    grouped = {}
    for row in get_checklist_template_for_process(process_type_key):
        grouped.setdefault(row["stage_key"], []).append(row)
    return grouped
