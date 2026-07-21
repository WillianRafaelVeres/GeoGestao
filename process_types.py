import unicodedata


PROCESS_TYPES = [
    {
        "key": "RETIFICACAO_AREA_RURAL",
        "nome": "Retificacao",
        "descricao": "Processo usado para corrigir area, perimetro, confrontacoes ou descricao da matricula.",
        "categoria": "Regularizacao cartorial",
        "usa_campo": "sim",
        "usa_cartorio": "sim",
        "usa_orgao_externo": "nao por padrao",
        "possui_documentos_especificos": True,
        "ativo": True,
        "ordem": 1,
    },
    {
        "key": "DESMEMBRAMENTO",
        "nome": "Desmembramento",
        "descricao": "Processo usado para dividir uma matricula ja correta em novas areas.",
        "categoria": "Regularizacao cartorial",
        "usa_campo": "opcional/conforme caso",
        "usa_cartorio": "sim",
        "usa_orgao_externo": "prefeitura/cartorio quando aplicavel",
        "possui_documentos_especificos": True,
        "ativo": True,
        "ordem": 2,
    },
    {
        "key": "DESTACAMENTO_ESTREMACAO",
        "nome": "Destacamento / Estremacao",
        "descricao": "Processo usado para separar ou individualizar area em condominio ou situacao equivalente.",
        "categoria": "Regularizacao cartorial",
        "usa_campo": "sim",
        "usa_cartorio": "sim",
        "usa_orgao_externo": "nao por padrao",
        "possui_documentos_especificos": True,
        "ativo": True,
        "ordem": 3,
    },
    {
        "key": "UNIFICACAO",
        "nome": "Unificacao",
        "descricao": "Processo usado para unir matriculas ou areas, quando a base documental esta correta.",
        "categoria": "Regularizacao cartorial",
        "usa_campo": "opcional/conforme caso",
        "usa_cartorio": "sim",
        "usa_orgao_externo": "nao por padrao",
        "possui_documentos_especificos": True,
        "ativo": True,
        "ordem": 4,
    },
    {
        "key": "USUCAPIAO",
        "nome": "Usucapiao",
        "descricao": "Processo usado para regularizar posse por usucapiao, com atuacao documental e juridica.",
        "categoria": "Regularizacao juridica/cartorial",
        "usa_campo": "sim",
        "usa_cartorio": "sim",
        "usa_orgao_externo": "advogado/forum/cartorio conforme modalidade",
        "possui_documentos_especificos": True,
        "ativo": True,
        "ordem": 5,
    },
    {
        "key": "GEORREFERENCIAMENTO_TECNICO",
        "nome": "Georreferenciamento Tecnico",
        "descricao": "Processo tecnico de levantamento e georreferenciamento do imovel rural.",
        "categoria": "Tecnico/topografico",
        "usa_campo": "sim",
        "usa_cartorio": "opcional/conforme contratacao",
        "usa_orgao_externo": "SIGEF/INCRA quando aplicavel",
        "possui_documentos_especificos": True,
        "ativo": True,
        "ordem": 6,
    },
    {
        "key": "CERTIFICACAO_SIGEF",
        "nome": "Certificacao SIGEF",
        "descricao": "Processo voltado a certificacao do imovel rural no SIGEF.",
        "categoria": "INCRA/SIGEF",
        "usa_campo": "opcional/conforme qualidade dos dados",
        "usa_cartorio": "nao por padrao",
        "usa_orgao_externo": "SIGEF/INCRA",
        "possui_documentos_especificos": True,
        "ativo": True,
        "ordem": 7,
    },
    {
        "key": "AVERBACAO_CERTIFICACAO",
        "nome": "Averbacao da Certificacao",
        "descricao": "Processo para averbar na matricula do imovel uma certificacao SIGEF ja emitida.",
        "categoria": "Regularizacao cartorial",
        "usa_campo": "nao por padrao",
        "usa_cartorio": "sim",
        "usa_orgao_externo": "cartorio de registro de imoveis",
        "possui_documentos_especificos": True,
        "ativo": True,
        "ordem": 8,
    },
    {
        "key": "CAR",
        "nome": "Cadastro Ambiental Rural - CAR",
        "descricao": "Processo de cadastro, analise ou ajuste ambiental do imovel rural.",
        "categoria": "Ambiental",
        "usa_campo": "opcional/conforme caso",
        "usa_cartorio": "nao",
        "usa_orgao_externo": "SICAR/orgao ambiental",
        "possui_documentos_especificos": True,
        "ativo": True,
        "ordem": 8,
    },
    {
        "key": "ATUALIZACAO_CCIR",
        "nome": "Atualizacao de CCIR",
        "descricao": "Processo de atualizacao ou emissao de CCIR e dados relacionados ao cadastro rural.",
        "categoria": "INCRA/SNCR",
        "usa_campo": "nao por padrao",
        "usa_cartorio": "nao",
        "usa_orgao_externo": "SNCR/INCRA",
        "possui_documentos_especificos": True,
        "ativo": True,
        "ordem": 9,
    },
    {
        "key": "MEDICAO",
        "nome": "Medicao / Levantamento",
        "descricao": "Servico tecnico de medicao, levantamento ou conferencia de area.",
        "categoria": "Tecnico/topografico",
        "usa_campo": "sim",
        "usa_cartorio": "nao por padrao",
        "usa_orgao_externo": "nao por padrao",
        "possui_documentos_especificos": True,
        "ativo": True,
        "ordem": 10,
    },
    {
        "key": "REGULARIZACAO_TITULARIDADE",
        "nome": "Regularizacao de Titularidade",
        "descricao": "Processo usado para organizar titularidade, documentacao e situacao cadastral do imovel.",
        "categoria": "Regularizacao documental",
        "usa_campo": "opcional/conforme caso",
        "usa_cartorio": "sim",
        "usa_orgao_externo": "pode envolver cartorio, tabelionato, prefeitura ou advogado",
        "possui_documentos_especificos": True,
        "ativo": True,
        "ordem": 11,
    },
    {
        "key": "OUTRO",
        "nome": "Outro",
        "descricao": "Processo nao padronizado ainda.",
        "categoria": "Geral",
        "usa_campo": "conforme caso",
        "usa_cartorio": "conforme caso",
        "usa_orgao_externo": "conforme caso",
        "possui_documentos_especificos": False,
        "ativo": True,
        "ordem": 99,
    },
]

PROCESS_TYPE_BY_KEY = {item["key"]: item for item in PROCESS_TYPES}


def normalize_process_text(value):
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = text.encode("ascii", "ignore").decode("ascii").lower()
    return "".join(ch for ch in text if ch.isalnum())


PROCESS_TYPE_ALIASES = {
    "retificacao": "RETIFICACAO_AREA_RURAL",
    "retificacaoarea": "RETIFICACAO_AREA_RURAL",
    "retificacaoarearural": "RETIFICACAO_AREA_RURAL",
    "retifrural": "RETIFICACAO_AREA_RURAL",
    "regularizacaorural": "RETIFICACAO_AREA_RURAL",
    "desmembramento": "DESMEMBRAMENTO",
    "desmembramentorural": "DESMEMBRAMENTO",
    "parcelamento": "DESMEMBRAMENTO",
    "destacamento": "DESTACAMENTO_ESTREMACAO",
    "estremacao": "DESTACAMENTO_ESTREMACAO",
    "extincaodecondominio": "DESTACAMENTO_ESTREMACAO",
    "unificacao": "UNIFICACAO",
    "remembramento": "UNIFICACAO",
    "usucapiao": "USUCAPIAO",
    "geo": "GEORREFERENCIAMENTO_TECNICO",
    "georreferenciamento": "GEORREFERENCIAMENTO_TECNICO",
    "georreferenciamentotecnico": "GEORREFERENCIAMENTO_TECNICO",
    "georreferenciamentoimovelrural": "GEORREFERENCIAMENTO_TECNICO",
    "certificacaosigef": "CERTIFICACAO_SIGEF",
    "sigef": "CERTIFICACAO_SIGEF",
    "averbacaodacertificacao": "AVERBACAO_CERTIFICACAO",
    "averbacaocertificacao": "AVERBACAO_CERTIFICACAO",
    "averbacaosigef": "AVERBACAO_CERTIFICACAO",
    "car": "CAR",
    "cadastroambientalrural": "CAR",
    "cadastroambientalruralcar": "CAR",
    "atualizacaoccir": "ATUALIZACAO_CCIR",
    "ccir": "ATUALIZACAO_CCIR",
    "medicao": "MEDICAO",
    "medio": "MEDICAO",
    "levantamento": "MEDICAO",
    "medicaolevantamento": "MEDICAO",
    "regularizacaotitularidade": "REGULARIZACAO_TITULARIDADE",
    "regularizacaodetitularidade": "REGULARIZACAO_TITULARIDADE",
    "inventariodeimovel": "REGULARIZACAO_TITULARIDADE",
    "outro": "OUTRO",
}


def resolve_process_type_key(value):
    if value in PROCESS_TYPE_BY_KEY:
        return value
    normalized = normalize_process_text(value)
    return PROCESS_TYPE_ALIASES.get(normalized, "OUTRO")


def get_process_type(value):
    return PROCESS_TYPE_BY_KEY.get(resolve_process_type_key(value), PROCESS_TYPE_BY_KEY["OUTRO"])


def process_type_name(value):
    return get_process_type(value)["nome"]
