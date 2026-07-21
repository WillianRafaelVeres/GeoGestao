from process_types import PROCESS_TYPE_BY_KEY, resolve_process_type_key


APPLICABILITY_REQUIRED = "OBRIGATORIA"
APPLICABILITY_OPTIONAL = "OPCIONAL"
APPLICABILITY_CONDITIONAL = "CONDICIONAL"
APPLICABILITY_NOT_APPLICABLE = "NAO_APLICAVEL"

APPLICABILITY_VALUES = {
    APPLICABILITY_REQUIRED,
    APPLICABILITY_OPTIONAL,
    APPLICABILITY_CONDITIONAL,
    APPLICABILITY_NOT_APPLICABLE,
}

EXTERNAL_ACTOR_NONE = "NENHUM"
EXTERNAL_ACTOR_REGISTRY = "CARTORIO"
EXTERNAL_ACTOR_SIGEF_INCRA = "SIGEF_INCRA"
EXTERNAL_ACTOR_SICAR = "SICAR"
EXTERNAL_ACTOR_SNCR_INCRA = "SNCR_INCRA"
EXTERNAL_ACTOR_CITY_HALL = "PREFEITURA"
EXTERNAL_ACTOR_LAWYER_COURT = "ADVOGADO_FORUM"
EXTERNAL_ACTOR_MIXED = "MISTO"

RETIRED_WORKFLOW_STAGE_KEYS = frozenset({
    "ANALISE",
    "PREPARACAO",
    "CONFERENCIA",
    "PREFEITURA",
    "ENTREGA",
})

MACRO_STAGES = [
    {
        "key": "ORCAMENTO",
        "name": "Orcamento",
        "description": "Fase de orcamento, proposta e aceite do servico.",
        "order": 1,
        "default_responsible_role": "comercial",
        "default_deadline_days": 3,
    },
    {
        "key": "DOCUMENTOS",
        "name": "Documentos",
        "description": "Coleta e conferencia inicial dos documentos necessarios.",
        "order": 2,
        "default_responsible_role": "documentacao",
        "default_deadline_days": 4,
    },
    {
        "key": "ANALISE",
        "name": "Analise / Viabilidade",
        "description": "Analise tecnica, juridica, documental e de viabilidade.",
        "order": 3,
        "default_responsible_role": "gestao_tecnica",
        "default_deadline_days": 3,
    },
    {
        "key": "PREPARACAO",
        "name": "Preparacao",
        "description": "Preparacao do servico, organizacao da pasta, planejamento e dados iniciais.",
        "order": 4,
        "default_responsible_role": "gestao_operacional",
        "default_deadline_days": 3,
    },
    {
        "key": "MEDICAO",
        "name": "Medicao / Campo",
        "description": "Trabalho de campo, levantamento, vistoria ou coleta de dados.",
        "order": 5,
        "default_responsible_role": "campo",
        "default_deadline_days": 2,
    },
    {
        "key": "PROCESSAMENTO",
        "name": "Processamento",
        "description": "Processamento tecnico dos dados levantados ou recebidos.",
        "order": 6,
        "default_responsible_role": "processamento",
        "default_deadline_days": 6,
    },
    {
        "key": "ESCRITORIO",
        "name": "Escritorio",
        "description": "Preparacao das pecas e do checklist de documentacao obrigatoria do cartorio.",
        "order": 7,
        "default_responsible_role": "escritorio",
        "default_deadline_days": 6,
    },
    {
        "key": "CONFERENCIA",
        "name": "Conferencia",
        "description": "Revisao tecnica e conferencia antes de assinatura, protocolo ou entrega.",
        "order": 8,
        "default_responsible_role": "conferencia",
        "default_deadline_days": 2,
    },
    {
        "key": "ASSINATURAS",
        "name": "Assinaturas / Anuencias",
        "description": "Coleta de assinaturas, anuencias, reconhecimento, procuracoes ou documentos assinados.",
        "order": 9,
        "default_responsible_role": "documentacao",
        "default_deadline_days": 4,
    },
    {
        "key": "PREFEITURA",
        "name": "Prefeitura",
        "description": "Protocolo, exigencias, deferimento e retirada junto a prefeitura.",
        "order": 10,
        "default_responsible_role": "acompanhamento_externo",
        "default_deadline_days": 10,
    },
    {
        "key": "ORGAO_EXTERNO",
        "name": "Orgao externo",
        "description": "Protocolo, verificacao, deferimento e retirada junto a prefeitura, cartorio, SIGEF, INCRA, SICAR ou outro orgao externo.",
        "order": 11,
        "default_responsible_role": "acompanhamento_externo",
        "default_deadline_days": 10,
    },
    {
        "key": "PENDENCIAS",
        "name": "Exigencias",
        "description": "Tratamento das exigencias recebidas de orgaos externos.",
        "order": 12,
        "default_responsible_role": "responsavel_do_caso",
        "default_deadline_days": 5,
    },
    {
        "key": "ENTREGA",
        "name": "Entrega / Encerramento",
        "description": "Entrega final ao cliente, arquivamento e encerramento operacional.",
        "order": 13,
        "default_responsible_role": "gestao_operacional",
        "default_deadline_days": 2,
    },
    {
        "key": "FINALIZADO",
        "name": "Finalizado",
        "description": "Projeto finalizado.",
        "order": 14,
        "default_responsible_role": "sistema",
        "default_deadline_days": 1,
    },
]

MACRO_STAGE_BY_KEY = {stage["key"]: stage for stage in MACRO_STAGES}


def stage(applicability, notes="", external_actor_type=EXTERNAL_ACTOR_NONE, **overrides):
    if applicability not in APPLICABILITY_VALUES:
        raise ValueError(f"Aplicabilidade invalida: {applicability}")
    data = {
        "applicability": applicability,
        "notes": notes,
        "external_actor_type": external_actor_type,
    }
    data.update(overrides)
    return data


def req(notes="", external_actor_type=EXTERNAL_ACTOR_NONE, **overrides):
    return stage(APPLICABILITY_REQUIRED, notes, external_actor_type, **overrides)


def cond(notes="", external_actor_type=EXTERNAL_ACTOR_NONE, **overrides):
    return stage(APPLICABILITY_CONDITIONAL, notes, external_actor_type, **overrides)


def opt(notes="", external_actor_type=EXTERNAL_ACTOR_NONE, **overrides):
    return stage(APPLICABILITY_OPTIONAL, notes, external_actor_type, **overrides)


def na(notes="", external_actor_type=EXTERNAL_ACTOR_NONE, **overrides):
    return stage(APPLICABILITY_NOT_APPLICABLE, notes, external_actor_type, **overrides)


PROCESS_STAGE_OVERRIDES = {
    "RETIFICACAO_AREA_RURAL": {
        "ORCAMENTO": req(),
        "DOCUMENTOS": req(),
        "ANALISE": req(),
        "PREPARACAO": req(),
        "MEDICAO": req(),
        "PROCESSAMENTO": req(),
        "ESCRITORIO": req(),
        "CONFERENCIA": req(),
        "ASSINATURAS": req(),
        "PREFEITURA": req("Se nao houver tramite na prefeitura, marcar como nao aplicavel.", EXTERNAL_ACTOR_CITY_HALL, can_skip=True),
        "ORGAO_EXTERNO": req("Normalmente cartorio.", EXTERNAL_ACTOR_REGISTRY),
        "PENDENCIAS": cond("Aparece se houver exigencia, documento faltante ou correcao.", EXTERNAL_ACTOR_REGISTRY),
        "ENTREGA": req(),
        "FINALIZADO": req(),
    },
    "DESMEMBRAMENTO": {
        "ORCAMENTO": req(),
        "DOCUMENTOS": req(),
        "ANALISE": req(),
        "PREPARACAO": req(),
        "MEDICAO": cond("Campo pode nao ser necessario se a matricula ja estiver correta e os dados forem confiaveis."),
        "PROCESSAMENTO": cond(),
        "ESCRITORIO": req(),
        "CONFERENCIA": req(),
        "ASSINATURAS": cond("Depende do caso, cartorio, prefeitura ou exigencia."),
        "PREFEITURA": req("Aprovacao municipal quando exigida; se nao se aplicar, marcar como nao aplicavel.", EXTERNAL_ACTOR_CITY_HALL, can_skip=True),
        "ORGAO_EXTERNO": req("Normalmente cartorio e, em alguns casos, prefeitura.", EXTERNAL_ACTOR_MIXED),
        "PENDENCIAS": cond(),
        "ENTREGA": req(),
        "FINALIZADO": req(),
    },
    "DESTACAMENTO_ESTREMACAO": {
        "ORCAMENTO": req(),
        "DOCUMENTOS": req(),
        "ANALISE": req(),
        "PREPARACAO": req(),
        "MEDICAO": req(),
        "PROCESSAMENTO": req(),
        "ESCRITORIO": req(),
        "CONFERENCIA": req(),
        "ASSINATURAS": req(),
        "PREFEITURA": req("Se nao houver tramite na prefeitura, marcar como nao aplicavel.", EXTERNAL_ACTOR_CITY_HALL, can_skip=True),
        "ORGAO_EXTERNO": req("Normalmente cartorio.", EXTERNAL_ACTOR_REGISTRY),
        "PENDENCIAS": cond(),
        "ENTREGA": req(),
        "FINALIZADO": req(),
    },
    "UNIFICACAO": {
        "ORCAMENTO": req(),
        "DOCUMENTOS": req(),
        "ANALISE": req(),
        "PREPARACAO": req(),
        "MEDICAO": cond("Pode nao ser necessario se a base ja estiver correta."),
        "PROCESSAMENTO": cond(),
        "ESCRITORIO": req(),
        "CONFERENCIA": req(),
        "ASSINATURAS": cond(),
        "PREFEITURA": req("Aprovacao municipal quando exigida; se nao se aplicar, marcar como nao aplicavel.", EXTERNAL_ACTOR_CITY_HALL, can_skip=True),
        "ORGAO_EXTERNO": req("Normalmente cartorio.", EXTERNAL_ACTOR_REGISTRY),
        "PENDENCIAS": cond(),
        "ENTREGA": req(),
        "FINALIZADO": req(),
    },
    "USUCAPIAO": {
        "ORCAMENTO": req(),
        "DOCUMENTOS": req(),
        "ANALISE": req(),
        "PREPARACAO": req(),
        "MEDICAO": req(),
        "PROCESSAMENTO": req(),
        "ESCRITORIO": req(),
        "CONFERENCIA": req(),
        "ASSINATURAS": req(),
        "PREFEITURA": req("Se houver tramite municipal, controlar aqui; se nao houver, marcar como nao aplicavel.", EXTERNAL_ACTOR_CITY_HALL, can_skip=True),
        "ORGAO_EXTERNO": req("Pode envolver cartorio, advogado, forum, tabelionato ou confrontantes.", EXTERNAL_ACTOR_LAWYER_COURT),
        "PENDENCIAS": cond(),
        "ENTREGA": req(),
        "FINALIZADO": req(),
    },
    "GEORREFERENCIAMENTO_TECNICO": {
        "ORCAMENTO": req(),
        "DOCUMENTOS": req(),
        "ANALISE": req(),
        "PREPARACAO": req(),
        "MEDICAO": req(),
        "PROCESSAMENTO": req(),
        "ESCRITORIO": req(),
        "CONFERENCIA": req(),
        "ASSINATURAS": cond(),
        "PREFEITURA": na("Nao usa prefeitura por padrao."),
        "ORGAO_EXTERNO": cond("SIGEF/INCRA apenas se a contratacao incluir certificacao.", EXTERNAL_ACTOR_SIGEF_INCRA),
        "PENDENCIAS": cond(),
        "ENTREGA": req(),
        "FINALIZADO": req(),
    },
    "CERTIFICACAO_SIGEF": {
        "ORCAMENTO": req(),
        "DOCUMENTOS": req(),
        "ANALISE": req(),
        "PREPARACAO": req(),
        "MEDICAO": cond("Depende da qualidade dos dados existentes."),
        "PROCESSAMENTO": req(),
        "ESCRITORIO": req(),
        "CONFERENCIA": req(),
        "ASSINATURAS": cond(),
        "PREFEITURA": na("Nao usa prefeitura por padrao."),
        "ORGAO_EXTERNO": req("SIGEF/INCRA.", EXTERNAL_ACTOR_SIGEF_INCRA),
        "PENDENCIAS": cond("Sobreposicao, erro tecnico, exigencia SIGEF ou ajuste.", EXTERNAL_ACTOR_SIGEF_INCRA),
        "ENTREGA": req(),
        "FINALIZADO": req(),
    },
    "AVERBACAO_CERTIFICACAO": {
        "ORCAMENTO": req(),
        "DOCUMENTOS": req(),
        "ANALISE": req(),
        "PREPARACAO": req(),
        "MEDICAO": na("A certificacao ja deve estar emitida; nao usa campo por padrao."),
        "PROCESSAMENTO": na("Nao exige novo processamento tecnico por padrao."),
        "ESCRITORIO": req("Preparacao do requerimento e dos documentos para averbacao."),
        "CONFERENCIA": req(),
        "ASSINATURAS": req("Coleta das assinaturas exigidas pelo cartorio."),
        "PREFEITURA": na("Nao usa prefeitura por padrao."),
        "ORGAO_EXTERNO": req("Protocolo no cartorio de registro de imoveis.", EXTERNAL_ACTOR_REGISTRY),
        "PENDENCIAS": cond("Exigencias ou correcoes solicitadas pelo cartorio.", EXTERNAL_ACTOR_REGISTRY),
        "ENTREGA": req(),
        "FINALIZADO": req(),
    },
    "CAR": {
        "ORCAMENTO": req(),
        "DOCUMENTOS": req(),
        "ANALISE": req(),
        "PREPARACAO": req(),
        "MEDICAO": cond("So se precisar levantar perimetro, APP, reserva ou dados nao confiaveis."),
        "PROCESSAMENTO": cond(),
        "ESCRITORIO": req("Elaboracao ou ajuste das informacoes ambientais."),
        "CONFERENCIA": req(),
        "ASSINATURAS": cond(),
        "PREFEITURA": cond("Somente quando houver protocolo ambiental ou municipal na prefeitura.", EXTERNAL_ACTOR_CITY_HALL, can_skip=True),
        "ORGAO_EXTERNO": req("SICAR/orgao ambiental. Nao usa cartorio por padrao.", EXTERNAL_ACTOR_SICAR),
        "PENDENCIAS": cond(),
        "ENTREGA": req(),
        "FINALIZADO": req(),
    },
    "ATUALIZACAO_CCIR": {
        "ORCAMENTO": req(),
        "DOCUMENTOS": req(),
        "ANALISE": req(),
        "PREPARACAO": req(),
        "MEDICAO": na("Nao usa medicao/campo por padrao."),
        "PROCESSAMENTO": cond(),
        "ESCRITORIO": req(),
        "CONFERENCIA": req(),
        "ASSINATURAS": cond(),
        "PREFEITURA": na("Nao usa prefeitura por padrao."),
        "ORGAO_EXTERNO": req("SNCR/INCRA.", EXTERNAL_ACTOR_SNCR_INCRA),
        "PENDENCIAS": cond(),
        "ENTREGA": req(),
        "FINALIZADO": req(),
    },
    "MEDICAO": {
        "ORCAMENTO": req(),
        "DOCUMENTOS": cond(),
        "ANALISE": cond(),
        "PREPARACAO": req(),
        "MEDICAO": req(),
        "PROCESSAMENTO": req(),
        "ESCRITORIO": cond("Depende se havera planta, relatorio, memorial simples ou apenas entrega de dados."),
        "CONFERENCIA": req(),
        "ASSINATURAS": na("Nao aplicavel por padrao em medicao simples."),
        "PREFEITURA": na("Nao usa prefeitura por padrao em medicao simples."),
        "ORGAO_EXTERNO": na("Nao usa cartorio ou orgao externo por padrao."),
        "PENDENCIAS": cond(),
        "ENTREGA": req(),
        "FINALIZADO": req(),
    },
    "REGULARIZACAO_TITULARIDADE": {
        "ORCAMENTO": req(),
        "DOCUMENTOS": req(),
        "ANALISE": req(),
        "PREPARACAO": req(),
        "MEDICAO": cond(),
        "PROCESSAMENTO": cond(),
        "ESCRITORIO": req(),
        "CONFERENCIA": req(),
        "ASSINATURAS": req(),
        "PREFEITURA": req("Se houver tramite municipal, controlar aqui; se nao houver, marcar como nao aplicavel.", EXTERNAL_ACTOR_CITY_HALL, can_skip=True),
        "ORGAO_EXTERNO": req("Pode envolver cartorio, tabelionato, prefeitura, advogado ou outro orgao.", EXTERNAL_ACTOR_MIXED),
        "PENDENCIAS": cond(),
        "ENTREGA": req(),
        "FINALIZADO": req(),
    },
    "OUTRO": {
        "ORCAMENTO": req(),
        "DOCUMENTOS": cond(),
        "ANALISE": cond(),
        "PREPARACAO": req(),
        "MEDICAO": cond(),
        "PROCESSAMENTO": cond(),
        "ESCRITORIO": cond(),
        "CONFERENCIA": cond(),
        "ASSINATURAS": cond(),
        "PREFEITURA": cond("Use quando houver protocolo ou exigencia municipal.", EXTERNAL_ACTOR_CITY_HALL, can_skip=True),
        "ORGAO_EXTERNO": cond(),
        "PENDENCIAS": cond(),
        "ENTREGA": req(),
        "FINALIZADO": req(),
    },
}


def build_stage_template(process_type_key, macro_stage, override):
    applicability = override.get("applicability", APPLICABILITY_NOT_APPLICABLE)
    if macro_stage["key"] in RETIRED_WORKFLOW_STAGE_KEYS:
        override = {
            **override,
            "applicability": APPLICABILITY_NOT_APPLICABLE,
            "show_in_matrix": False,
            "show_in_project": False,
            "active": True,
            "notes": "Etapa retirada do fluxo operacional simplificado.",
        }
        applicability = APPLICABILITY_NOT_APPLICABLE
    can_skip = override.get("can_skip")
    if can_skip is None:
        can_skip = applicability != APPLICABILITY_REQUIRED
    blocks_completion = override.get("blocks_completion")
    if blocks_completion is None:
        blocks_completion = applicability == APPLICABILITY_REQUIRED
    show_in_matrix = override.get("show_in_matrix")
    if show_in_matrix is None:
        show_in_matrix = applicability != APPLICABILITY_NOT_APPLICABLE
    show_in_project = override.get("show_in_project")
    if show_in_project is None:
        show_in_project = applicability != APPLICABILITY_NOT_APPLICABLE

    return {
        "process_type_key": process_type_key,
        "stage_key": macro_stage["key"],
        "stage_name": override.get("stage_name", macro_stage["name"]),
        "stage_order": override.get("stage_order", macro_stage["order"]),
        "applicability": applicability,
        "description": override.get("description", macro_stage["description"]),
        "default_responsible_role": override.get("default_responsible_role", macro_stage["default_responsible_role"]),
        "default_deadline_days": override.get("default_deadline_days", macro_stage["default_deadline_days"]),
        "can_skip": can_skip,
        "blocks_completion": blocks_completion,
        "show_in_matrix": show_in_matrix,
        "show_in_project": show_in_project,
        "external_actor_type": override.get("external_actor_type", EXTERNAL_ACTOR_NONE),
        "notes": override.get("notes", ""),
        "active": override.get("active", True),
    }


def build_process_stage_templates():
    templates = {}
    for process_type_key in PROCESS_TYPE_BY_KEY:
        process_overrides = PROCESS_STAGE_OVERRIDES.get(process_type_key, PROCESS_STAGE_OVERRIDES["OUTRO"])
        rows = []
        for macro_stage in MACRO_STAGES:
            override = process_overrides.get(macro_stage["key"], na("Nao se aplica por padrao."))
            rows.append(build_stage_template(process_type_key, macro_stage, override))
        templates[process_type_key] = rows
    return templates


PROCESS_STAGE_TEMPLATES = build_process_stage_templates()


def get_stage_template_for_process(process_type_key):
    key = resolve_process_type_key(process_type_key)
    return list(PROCESS_STAGE_TEMPLATES.get(key, PROCESS_STAGE_TEMPLATES["OUTRO"]))


def get_applicable_stages_for_process(process_type_key, include_optional=False, include_conditional=True):
    allowed = {APPLICABILITY_REQUIRED}
    if include_optional:
        allowed.add(APPLICABILITY_OPTIONAL)
    if include_conditional:
        allowed.add(APPLICABILITY_CONDITIONAL)
    return [stage_template for stage_template in get_stage_template_for_process(process_type_key) if stage_template["applicability"] in allowed]
