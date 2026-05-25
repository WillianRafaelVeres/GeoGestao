import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation


TIPOS_CLIENTE = {
    "PESSOA_FISICA": "Pessoa fisica",
    "PESSOA_JURIDICA": "Pessoa juridica",
}

QUEM_ASSINA = {
    "PROPRIETARIO": "Proprietario",
    "PROCURADOR": "Procurador / representante",
}

SEXOS = {
    "MASCULINO": "Masculino",
    "FEMININO": "Feminino",
}

ESTADOS_CIVIS = {
    "SOLTEIRO": "Solteiro",
    "CASADO": "Casado",
    "DIVORCIADO": "Divorciado",
    "VIUVO": "Viuvo",
    "SEPARADO_JUDICIALMENTE": "Separado judicialmente",
    "UNIAO_ESTAVEL": "Uniao estavel",
}

REGIMES_CASAMENTO = {
    "COMUNHAO_PARCIAL": "Comunhao parcial de bens",
    "COMUNHAO_UNIVERSAL": "Comunhao universal de bens",
    "SEPARACAO_TOTAL": "Separacao total de bens",
    "PARTICIPACAO_FINAL_AQUESTOS": "Participacao final nos aquestos",
}

TIPOS_CERTIDAO = {
    "MATRICULA": "Matricula",
    "TRANSCRICAO": "Transcricao",
}

STATUS_CADASTRO = {
    "RASCUNHO": "Rascunho",
    "COMPLETO": "Completo",
    "INCOMPLETO": "Incompleto",
    "COM_PENDENCIAS": "Com pendencias",
}

UFS = [
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS",
    "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC",
    "SP", "SE", "TO",
]

# Estrutura inicial para validacao cidade/UF. A lista oficial do IBGE deve
# popular este mapa futuramente sem mudar a API usada pelo formulario.
CIDADES_REFERENCIA_POR_UF = {
    "PR": {"Rio Negro", "Curitiba", "Campo Largo", "Lapa", "Sao Mateus do Sul"},
    "SC": {"Mafra", "Joinville", "Florianopolis", "Canoinhas", "Porto Uniao"},
    "SP": {"Sao Paulo", "Campinas", "Santos", "Sorocaba", "Jundiai"},
    "RS": {"Porto Alegre", "Caxias do Sul", "Pelotas", "Santa Maria"},
    "MG": {"Belo Horizonte", "Uberlandia", "Juiz de Fora", "Contagem"},
}

CONJUGE_REQUIRED_REGIMES = {
    "COMUNHAO_PARCIAL",
    "COMUNHAO_UNIVERSAL",
    "PARTICIPACAO_FINAL_AQUESTOS",
}

TEMPLATE_PLACEHOLDERS = {
    "Template_RR_Geral": [
        "CARTORIO", "TEXTO_PROPRIETARIO", "TEXTO_1", "TEXTO_3", "TEXTO_5",
        "DATA", "TIITULO_ASSINATURA", "PROPRIETARIO_1", "LINHA_ASSINATURA",
        "PROPRIETARIO_2",
    ],
    "Template_RR_RioNegro": [
        "TEXTO_PROPRIETARIO", "TEXTO_1", "TEXTO_2", "COD_CERTIFICACAO",
        "TEXTO_AREA", "TEXTO_PERIMETRO", "TEXTO_MEMORIAL", "TEXTO_3",
        "TEXTO_4", "DATA", "PROPRIETARIO_1", "LINHA_ASSINATURA",
        "PROPRIETARIO_2",
    ],
    "Template_DEC_ART_213": [
        "TEXTO_PROPRIETARIO", "CERTIDAO", "NCERTIDAO", "CARTORIO", "TEXTO_1",
        "DATA", "TIITULO_ASSINATURA", "PROPRIETARIO_1", "LINHA_ASSINATURA",
        "PROPRIETARIO_2",
    ],
    "Template_DEC_ART_213_RN": [
        "TEXTO_PROPRIETARIO", "CERTIDAO", "NCERTIDAO", "CARTORIO", "TEXTO_1",
        "TEXTO_2", "TEXTO_3", "TEXTO_4", "TEXTO_5", "DATA",
        "TIITULO_ASSINATURA", "PROPRIETARIO_1", "LINHA_ASSINATURA",
        "PROPRIETARIO_2",
    ],
    "Template_DEC_RESP_PROP": [
        "TEXTO_PROPRIETARIO", "TEXTO_1", "CERTIDAO", "NCERTIDAO", "CARTORIO",
        "TEXTO_2", "TEXTO_3", "TEXTO_4", "DATA", "PROPRIETARIO_1",
        "LINHA_ASSINATURA", "PROPRIETARIO_2",
    ],
    "Template_RAC": [
        "CARTORIO", "TEXTO_PROPRIETARIO", "CERTIDAO", "NCERTIDAO",
        "COD_CERTIFICACAO", "DATA", "PROPRIETARIO_1", "LINHA_ASSINATURA",
        "PROPRIETARIO_2",
    ],
    "Template_Memorial": [
        "PROPRIETARIO", "CPF", "CERTIDAO", "MATRICULA", "CNS_CARTORIO",
        "CIDADE", "SNCR", "COD_CERTIFICACAO", "TEXTO_AREA", "TEXTO_PERIMETRO",
        "TEXTO_MEMORIAL", "DATA", "NOME_ASSINATURA", "PROPRIETARIO_1",
        "LINHA_ASSINATURA", "PROPRIETARIO_2",
    ],
}

DOCUMENT_FIELD_REQUIREMENTS = {
    "Template_RR_Geral": [
        ("cliente.nome_exibicao", "Cliente", "Informe o nome do cliente."),
        ("imovel.cartorio_comarca", "Cartorio", "Informe cartorio/comarca."),
        ("imovel.tipo_certidao", "Tipo de certidao", "Informe matricula ou transcricao."),
        ("imovel.numero_certidao", "Numero da certidao", "Informe matricula/transcricao."),
    ],
    "Template_RR_RioNegro": [
        ("cliente.nome_exibicao", "Cliente", "Informe o nome do cliente."),
        ("imovel.codigo_certificacao_sigef", "Codigo SIGEF", "Informe a certificacao SIGEF."),
        ("imovel.nova_area_m2", "Nova area", "Informe a nova area."),
        ("imovel.perimetro_m", "Perimetro", "Informe o perimetro."),
    ],
    "Template_DEC_ART_213": [
        ("cliente.nome_exibicao", "Cliente", "Informe o nome do cliente."),
        ("imovel.cartorio_comarca", "Cartorio", "Informe cartorio/comarca."),
        ("imovel.numero_certidao", "Numero da certidao", "Informe matricula/transcricao."),
    ],
    "Template_DEC_ART_213_RN": [
        ("cliente.nome_exibicao", "Cliente", "Informe o nome do cliente."),
        ("imovel.numero_certidao", "Numero da certidao", "Informe matricula/transcricao."),
        ("imovel.cidade_imovel", "Cidade", "Informe a cidade do imovel."),
    ],
    "Template_DEC_RESP_PROP": [
        ("cliente.nome_exibicao", "Cliente", "Informe o nome do cliente."),
        ("imovel.numero_certidao", "Numero da certidao", "Informe matricula/transcricao."),
    ],
    "Template_RAC": [
        ("cliente.nome_exibicao", "Cliente", "Informe o nome do cliente."),
        ("imovel.cartorio_comarca", "Cartorio", "Informe cartorio/comarca."),
        ("imovel.codigo_certificacao_sigef", "Codigo SIGEF", "Informe a certificacao SIGEF."),
    ],
    "Template_Memorial": [
        ("cliente.nome_exibicao", "Cliente", "Informe o nome do cliente."),
        ("imovel.numero_certidao", "Matricula", "Informe matricula/transcricao."),
        ("imovel.cns_cartorio", "CNS", "Informe o CNS do cartorio."),
        ("imovel.codigo_sncr", "SNCR", "Informe o codigo SNCR."),
        ("imovel.nova_area_m2", "Area", "Informe a nova area."),
        ("imovel.perimetro_m", "Perimetro", "Informe o perimetro."),
    ],
}

BD_DADOS_FIELDS = [
    "Tipo_Proprietario", "Quem_Assina", "Emp_Nome", "Emp_CNPJ",
    "Emp_Logradouro", "Emp_UF", "Emp_Cidade", "Emp_Bairro", "Emp_CEP",
    "Emp_Numero", "Emp_Compl", "Prop_Sexo", "Prop_Nome", "Prop_EstCivil",
    "Prop_RegimeCas", "Prop_Profissao", "Prop_Nacionalidade", "Prop_UF_Nasc",
    "Prop_Cidade_Nasc", "Prop_RG", "Prop_OrgaoRG", "Prop_CPF",
    "Prop_NomePai", "Prop_NomeMae", "Prop_DataNasc", "Conj_Nome",
    "Conj_CPF", "Conj_Profissao", "Conj_Nacionalidade", "Conj_UF_Nasc",
    "Conj_Cidade_Nasc", "Conj_RG", "Conj_OrgaoRG", "Prop_End_Logradouro",
    "Prop_End_UF", "Prop_End_Cidade", "Prop_End_Bairro", "Prop_End_CEP",
    "Prop_End_Numero", "Prop_End_Compl", "Proc_Sexo", "Proc_Nome",
    "Proc_EstCivil", "Proc_RegimeCas", "Proc_Profissao", "Proc_Nacionalidade",
    "Proc_UF_Nasc", "Proc_Cidade_Nasc", "Proc_RG", "Proc_OrgaoRG",
    "Proc_CPF", "Proc_NomePai", "Proc_NomeMae", "Proc_DataNasc",
    "Proc_Email", "Proc_TextoAdic", "Proc_End_Logradouro", "Proc_End_UF",
    "Proc_End_Cidade", "Proc_End_Bairro", "Proc_End_CEP", "Proc_End_Numero",
    "Proc_End_Compl",
]


def only_digits(value):
    return re.sub(r"\D+", "", value or "")


def row_to_dict(row):
    if row is None:
        return {}
    if isinstance(row, dict):
        return row
    return {key: row[key] for key in row.keys()}


def validate_cpf(value):
    cpf = only_digits(value)
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    for size in (9, 10):
        total = sum(int(cpf[i]) * ((size + 1) - i) for i in range(size))
        digit = (total * 10) % 11
        if digit == 10:
            digit = 0
        if digit != int(cpf[size]):
            return False
    return True


def validate_cnpj(value):
    cnpj = only_digits(value)
    if len(cnpj) != 14 or cnpj == cnpj[0] * 14:
        return False
    weights = ([5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2], [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    for index, weight in enumerate(weights):
        total = sum(int(cnpj[i]) * weight[i] for i in range(len(weight)))
        digit = 11 - (total % 11)
        if digit >= 10:
            digit = 0
        if digit != int(cnpj[12 + index]):
            return False
    return True


def validate_email(value):
    if not value:
        return True
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", value))


def validate_date(value):
    if not value:
        return True
    try:
        datetime.fromisoformat(value)
        return True
    except ValueError:
        return False


def parse_decimal_br(value):
    if value in (None, ""):
        return None
    text = str(value).strip().replace("R$", "").replace(" ", "")
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    try:
        return str(Decimal(text))
    except InvalidOperation:
        return None


def validate_uuid_like(value):
    if not value:
        return True
    return bool(re.match(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$", value))


def format_cpf(value):
    cpf = only_digits(value)
    if len(cpf) != 11:
        return value or ""
    return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"


def format_cnpj(value):
    cnpj = only_digits(value)
    if len(cnpj) != 14:
        return value or ""
    return f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"


def format_cep(value):
    cep = only_digits(value)
    if len(cep) != 8:
        return value or ""
    return f"{cep[:5]}-{cep[5:]}"


def format_phone(value):
    digits = only_digits(value)
    if len(digits) == 11:
        return f"({digits[:2]}) {digits[2:7]}-{digits[7:]}"
    if len(digits) == 10:
        return f"({digits[:2]}) {digits[2:6]}-{digits[6:]}"
    return value or ""


def validate_cep(value):
    if not value:
        return True
    return len(only_digits(value)) == 8


def normalize_city(value):
    text = (value or "").strip()
    return " ".join(part.capitalize() for part in text.split())


def validate_cidade_uf(cidade, uf):
    if not cidade or not uf:
        return True
    cidades = CIDADES_REFERENCIA_POR_UF.get(uf)
    if not cidades:
        return True
    return normalize_city(cidade) in cidades


def get_cliente_pendencias(cliente_context):
    cliente = cliente_context.get("cliente") or {}
    pf = cliente_context.get("pessoa_fisica") or {}
    pj = cliente_context.get("pessoa_juridica") or {}
    conjuge = cliente_context.get("conjuge") or {}
    endereco = cliente_context.get("endereco") or {}
    procurador = cliente_context.get("procurador") or {}

    obrigatorias = []
    recomendadas = []
    obrigatorias_por_secao = {}
    recomendadas_por_secao = {}
    complete_sections = set()
    pending_sections = set()
    section_ids = {
        "Dados principais": "dados-principais",
        "Pessoa fisica": "pessoa-fisica",
        "Nascimento e filiacao": "nascimento-filiacao",
        "Contato": "contato",
        "Pessoa juridica": "pessoa-juridica",
        "Endereco da empresa": "pessoa-juridica",
        "Endereco do proprietario": "endereco-pf",
        "Conjuge": "conjuge",
        "Procurador/representante": "procurador",
    }

    def has_value(value):
        return value not in (None, "")

    def push(collection, grouped, section, label, field=None, severity="obrigatorio", message=None):
        item = {
            "id": f"{severity}-{field or label}".lower().replace("_", "-").replace(" ", "-"),
            "secao": section,
            "secao_id": section_ids.get(section, section.lower().replace(" ", "-")),
            "section": section_ids.get(section, section.lower().replace(" ", "-")),
            "label": label,
            "campo": field or label,
            "field": field or label,
            "severity": severity,
            "message": message or f"Informe {label.lower()}.",
        }
        collection.append(item)
        grouped.setdefault(section, []).append(item)
        pending_sections.add(section)

    def require(section, label, value, field=None):
        if has_value(value):
            return True
        push(obrigatorias, obrigatorias_por_secao, section, label, field)
        return False

    def recommend(section, label, value, field=None):
        if has_value(value):
            return True
        push(
            recomendadas,
            recomendadas_por_secao,
            section,
            label,
            field,
            severity="recomendado",
            message=f"Recomendado para cadastros e documentos futuros: {label.lower()}.",
        )
        return False

    tipo_cliente = cliente.get("tipo_cliente") or "PESSOA_FISICA"
    quem_assina = "PROCURADOR" if tipo_cliente == "PESSOA_JURIDICA" else (cliente.get("quem_assina") or "PROPRIETARIO")

    require("Dados principais", "Tipo de cliente", tipo_cliente, "tipo_cliente")
    require("Dados principais", "Quem assina", quem_assina, "quem_assina")

    if tipo_cliente == "PESSOA_JURIDICA":
        pj_ok = all([
            require("Pessoa juridica", "Razao social", pj.get("razao_social"), "pj_razao_social"),
            require("Pessoa juridica", "CNPJ", pj.get("cnpj"), "pj_cnpj"),
        ])
        if pj.get("cnpj") and not validate_cnpj(pj.get("cnpj")):
            push(obrigatorias, obrigatorias_por_secao, "Pessoa juridica", "CNPJ invalido", "pj_cnpj", message="Informe um CNPJ valido.")
            pj_ok = False
        for label, value, field in [
            ("CEP", pj.get("cep"), "pj_cep"),
            ("UF", pj.get("uf"), "pj_uf"),
            ("Cidade", pj.get("cidade"), "pj_cidade"),
            ("Bairro", pj.get("bairro"), "pj_bairro"),
            ("Logradouro", pj.get("logradouro"), "pj_logradouro"),
            ("Numero", pj.get("numero"), "pj_numero"),
        ]:
            pj_ok = require("Endereco da empresa", label, value, field) and pj_ok
        if pj.get("cep") and not validate_cep(pj.get("cep")):
            push(obrigatorias, obrigatorias_por_secao, "Endereco da empresa", "CEP invalido", "pj_cep", message="Informe o CEP com 8 digitos.")
            pj_ok = False
        if pj.get("email") and not validate_email(pj.get("email")):
            push(obrigatorias, obrigatorias_por_secao, "Pessoa juridica", "E-mail invalido", "pj_email", message="Informe um e-mail valido.")
            pj_ok = False
        recommend("Pessoa juridica", "E-mail da empresa", pj.get("email"), "pj_email")
        recommend("Pessoa juridica", "Telefone da empresa", pj.get("telefone"), "pj_telefone")
        if pj_ok:
            complete_sections.update({"Pessoa juridica", "Endereco da empresa"})
    else:
        pf_ok = all([
            require("Pessoa fisica", "Nome completo", pf.get("nome_completo"), "pf_nome_completo"),
            require("Pessoa fisica", "CPF", pf.get("cpf"), "pf_cpf"),
            require("Pessoa fisica", "Sexo", pf.get("sexo"), "pf_sexo"),
            require("Pessoa fisica", "Estado civil", pf.get("estado_civil"), "pf_estado_civil"),
        ])
        if pf.get("cpf") and not validate_cpf(pf.get("cpf")):
            push(obrigatorias, obrigatorias_por_secao, "Pessoa fisica", "CPF invalido", "pf_cpf", message="Informe um CPF valido.")
            pf_ok = False
        if pf.get("estado_civil") in ("CASADO", "UNIAO_ESTAVEL"):
            pf_ok = require("Pessoa fisica", "Regime de casamento", pf.get("regime_casamento"), "pf_regime_casamento") and pf_ok
        if pf.get("email") and not validate_email(pf.get("email")):
            push(obrigatorias, obrigatorias_por_secao, "Contato", "E-mail invalido", "pf_email", message="Informe um e-mail valido.")
            pf_ok = False
        for label, value, field in [
            ("RG", pf.get("rg"), "pf_rg"),
            ("Orgao expedidor do RG", pf.get("orgao_expedidor_rg"), "pf_orgao_expedidor_rg"),
            ("Nacionalidade", pf.get("nacionalidade"), "pf_nacionalidade"),
            ("Profissao/ocupacao", pf.get("profissao_ocupacao"), "pf_profissao_ocupacao"),
        ]:
            recommend("Pessoa fisica", label, value, field)
        for label, value, field in [
            ("Data de nascimento", pf.get("data_nascimento"), "pf_data_nascimento"),
            ("UF de nascimento", pf.get("uf_nascimento"), "pf_uf_nascimento"),
            ("Cidade de nascimento", pf.get("cidade_nascimento"), "pf_cidade_nascimento"),
            ("Nome do pai", pf.get("nome_pai"), "pf_nome_pai"),
            ("Nome da mae", pf.get("nome_mae"), "pf_nome_mae"),
        ]:
            recommend("Nascimento e filiacao", label, value, field)
        for label, value, field in [
            ("E-mail", pf.get("email"), "pf_email"),
            ("Telefone", pf.get("telefone"), "pf_telefone"),
        ]:
            recommend("Contato", label, value, field)
        if pf_ok:
            complete_sections.add("Pessoa fisica")

        end_ok = True
        for label, value, field in [
            ("CEP", endereco.get("cep"), "pf_end_cep"),
            ("UF", endereco.get("uf"), "pf_end_uf"),
            ("Cidade", endereco.get("cidade"), "pf_end_cidade"),
            ("Bairro", endereco.get("bairro"), "pf_end_bairro"),
            ("Logradouro", endereco.get("logradouro"), "pf_end_logradouro"),
            ("Numero", endereco.get("numero"), "pf_end_numero"),
        ]:
            end_ok = require("Endereco do proprietario", label, value, field) and end_ok
        if endereco.get("cep") and not validate_cep(endereco.get("cep")):
            push(obrigatorias, obrigatorias_por_secao, "Endereco do proprietario", "CEP invalido", "pf_end_cep", message="Informe o CEP com 8 digitos.")
            end_ok = False
        if end_ok:
            complete_sections.add("Endereco do proprietario")

        spouse_required = requires_conjuge(
            pf.get("estado_civil"),
            pf.get("regime_casamento"),
            bool(pf.get("incluir_conjuge")),
        )
        if spouse_required:
            conj_ok = all([
                require("Conjuge", "Nome completo do conjuge", conjuge.get("nome_completo"), "conj_nome_completo"),
                require("Conjuge", "CPF do conjuge", conjuge.get("cpf"), "conj_cpf"),
            ])
            if conjuge.get("cpf") and not validate_cpf(conjuge.get("cpf")):
                push(obrigatorias, obrigatorias_por_secao, "Conjuge", "CPF do conjuge invalido", "conj_cpf", message="Informe um CPF valido.")
                conj_ok = False
            for label, value, field in [
                ("RG do conjuge", conjuge.get("rg"), "conj_rg"),
                ("Orgao expedidor do RG", conjuge.get("orgao_expedidor_rg"), "conj_orgao_expedidor_rg"),
                ("Nacionalidade", conjuge.get("nacionalidade"), "conj_nacionalidade"),
                ("Profissao/ocupacao", conjuge.get("profissao_ocupacao"), "conj_profissao_ocupacao"),
                ("E-mail", conjuge.get("email"), "conj_email"),
                ("Telefone", conjuge.get("telefone"), "conj_telefone"),
            ]:
                recommend("Conjuge", label, value, field)
            if conj_ok:
                complete_sections.add("Conjuge")

    if quem_assina == "PROCURADOR" or tipo_cliente == "PESSOA_JURIDICA":
        proc_ok = all([
            require("Procurador/representante", "Nome completo", procurador.get("nome_completo"), "proc_nome_completo"),
            require("Procurador/representante", "CPF", procurador.get("cpf"), "proc_cpf"),
            require("Procurador/representante", "CEP", procurador.get("cep"), "proc_cep"),
            require("Procurador/representante", "UF", procurador.get("uf"), "proc_uf"),
            require("Procurador/representante", "Cidade", procurador.get("cidade"), "proc_cidade"),
            require("Procurador/representante", "Logradouro", procurador.get("logradouro"), "proc_logradouro"),
            require("Procurador/representante", "Numero", procurador.get("numero"), "proc_numero"),
        ])
        if procurador.get("cpf") and not validate_cpf(procurador.get("cpf")):
            push(obrigatorias, obrigatorias_por_secao, "Procurador/representante", "CPF invalido", "proc_cpf", message="Informe um CPF valido.")
            proc_ok = False
        if procurador.get("email") and not validate_email(procurador.get("email")):
            push(obrigatorias, obrigatorias_por_secao, "Procurador/representante", "E-mail invalido", "proc_email", message="Informe um e-mail valido.")
            proc_ok = False
        if procurador.get("cep") and not validate_cep(procurador.get("cep")):
            push(obrigatorias, obrigatorias_por_secao, "Procurador/representante", "CEP invalido", "proc_cep", message="Informe o CEP com 8 digitos.")
            proc_ok = False
        for label, value, field in [
            ("RG", procurador.get("rg"), "proc_rg"),
            ("Orgao expedidor do RG", procurador.get("orgao_expedidor_rg"), "proc_orgao_expedidor_rg"),
            ("Nacionalidade", procurador.get("nacionalidade"), "proc_nacionalidade"),
            ("Profissao/ocupacao", procurador.get("profissao_ocupacao"), "proc_profissao_ocupacao"),
            ("Sexo", procurador.get("sexo"), "proc_sexo"),
            ("Estado civil", procurador.get("estado_civil"), "proc_estado_civil"),
            ("E-mail", procurador.get("email"), "proc_email"),
            ("Telefone", procurador.get("telefone"), "proc_telefone"),
            ("Texto adicional/habilitacao", procurador.get("texto_adicional"), "proc_texto_adicional"),
        ]:
            recommend("Procurador/representante", label, value, field)
        if proc_ok:
            complete_sections.add("Procurador/representante")

    sections = {"Dados principais", "Pessoa fisica" if tipo_cliente != "PESSOA_JURIDICA" else "Pessoa juridica"}
    if tipo_cliente != "PESSOA_JURIDICA":
        sections.add("Endereco do proprietario")
        if requires_conjuge(pf.get("estado_civil"), pf.get("regime_casamento"), bool(pf.get("incluir_conjuge"))):
            sections.add("Conjuge")
    else:
        sections.add("Endereco da empresa")
        sections.add("Procurador/representante")
    if quem_assina == "PROCURADOR":
        sections.add("Procurador/representante")

    filled_core = 0
    for value in [
        cliente.get("nome_exibicao"),
        pf.get("nome_completo"),
        pf.get("cpf"),
        pj.get("razao_social"),
        pj.get("cnpj"),
        procurador.get("nome_completo"),
    ]:
        if has_value(value):
            filled_core += 1

    total_required = len(obrigatorias) + max(len(sections), 1)
    percentual = int(max(0, min(100, ((total_required - len(obrigatorias)) / total_required) * 100)))

    if filled_core <= 1 and len(obrigatorias) >= 4:
        status = "RASCUNHO"
    elif obrigatorias:
        status = "INCOMPLETO"
    elif recomendadas:
        status = "COM_PENDENCIAS"
    else:
        status = "COMPLETO"

    return {
        "pendenciasObrigatorias": obrigatorias,
        "pendenciasRecomendadas": recomendadas,
        "obrigatorias_por_secao": obrigatorias_por_secao,
        "recomendadas_por_secao": recomendadas_por_secao,
        "statusCadastro": status,
        "status_label": STATUS_CADASTRO.get(status, status),
        "percentualCompletude": percentual,
        "secoes_completas": sorted(complete_sections),
        "secoes_pendentes": sorted(pending_sections),
    }


def requires_conjuge(estado_civil, regime_casamento, incluir_conjuge=False):
    if incluir_conjuge:
        return True
    if estado_civil not in ("CASADO", "UNIAO_ESTAVEL"):
        return False
    return regime_casamento in CONJUGE_REQUIRED_REGIMES


def build_flexoes_genero(sexo):
    if sexo == "FEMININO":
        return {
            "brasileiro": "brasileira",
            "casado": "casada",
            "portador": "portadora",
            "inscrito": "inscrita",
            "proprietario": "proprietaria",
            "filho_de": "filha de",
            "residente_domiciliado": "residente e domiciliada",
        }
    return {
        "brasileiro": "brasileiro",
        "casado": "casado",
        "portador": "portador",
        "inscrito": "inscrito",
        "proprietario": "proprietario",
        "filho_de": "filho de",
        "residente_domiciliado": "residente e domiciliado",
    }


def get_path(data, path):
    current = data
    for part in path.split("."):
        if current is None:
            return None
        if isinstance(current, dict):
            current = current.get(part)
        else:
            current = getattr(current, part, None)
    return current


def get_missing_fields_for_document(tipo_documento, cliente_context):
    missing = []
    for path, label, message in DOCUMENT_FIELD_REQUIREMENTS.get(tipo_documento, []):
        value = get_path(cliente_context, path)
        if value in (None, ""):
            missing.append({"campo": path, "label": label, "mensagem": message})
    return missing


def can_generate_document(tipo_documento, cliente_context):
    return not get_missing_fields_for_document(tipo_documento, cliente_context)


def get_document_readiness(cliente_context):
    return {
        document: {
            "can_generate": can_generate_document(document, cliente_context),
            "missing": get_missing_fields_for_document(document, cliente_context),
            "placeholders": TEMPLATE_PLACEHOLDERS.get(document, []),
        }
        for document in TEMPLATE_PLACEHOLDERS
    }


def get_cadastro_completeness(cliente_context):
    cliente = cliente_context.get("cliente") or {}
    pf = cliente_context.get("pessoa_fisica") or {}
    pj = cliente_context.get("pessoa_juridica") or {}
    conjuge = cliente_context.get("conjuge") or {}
    endereco = cliente_context.get("endereco") or {}
    procurador = cliente_context.get("procurador") or {}
    imoveis = cliente_context.get("imoveis") or []

    missing = []
    complete_sections = []
    pending_sections = []

    def require(section, label, value):
        if value not in (None, ""):
            return True
        missing.append({"secao": section, "label": label})
        return False

    if require("dados_gerais", "Nome de exibicao", cliente.get("nome_exibicao")):
        complete_sections.append("Dados gerais")
    else:
        pending_sections.append("Dados gerais")

    if cliente.get("tipo_cliente") == "PESSOA_JURIDICA":
        ok = all([
            require("pessoa_juridica", "Razao social", pj.get("razao_social")),
            require("pessoa_juridica", "CNPJ", pj.get("cnpj")),
            require("pessoa_juridica", "Logradouro", pj.get("logradouro")),
            require("pessoa_juridica", "Cidade", pj.get("cidade")),
            require("pessoa_juridica", "UF", pj.get("uf")),
        ])
        (complete_sections if ok else pending_sections).append("Pessoa juridica")
    else:
        ok = all([
            require("pessoa_fisica", "Nome completo", pf.get("nome_completo")),
            require("pessoa_fisica", "CPF", pf.get("cpf")),
            require("pessoa_fisica", "Sexo", pf.get("sexo")),
            require("pessoa_fisica", "Estado civil", pf.get("estado_civil")),
        ])
        if pf.get("estado_civil") in ("CASADO", "UNIAO_ESTAVEL"):
            ok = require("pessoa_fisica", "Regime de casamento", pf.get("regime_casamento")) and ok
        (complete_sections if ok else pending_sections).append("Pessoa fisica")

        end_ok = all([
            require("endereco", "Logradouro", endereco.get("logradouro")),
            require("endereco", "Cidade", endereco.get("cidade")),
            require("endereco", "UF", endereco.get("uf")),
        ])
        (complete_sections if end_ok else pending_sections).append("Endereco PF")

        if requires_conjuge(pf.get("estado_civil"), pf.get("regime_casamento"), bool(pf.get("incluir_conjuge"))):
            conj_ok = all([
                require("conjuge", "Nome do conjuge", conjuge.get("nome_completo")),
                require("conjuge", "CPF do conjuge", conjuge.get("cpf")),
            ])
            (complete_sections if conj_ok else pending_sections).append("Conjuge")

    if cliente.get("quem_assina") == "PROCURADOR" or cliente.get("tipo_cliente") == "PESSOA_JURIDICA":
        proc_ok = all([
            require("procurador", "Nome do procurador", procurador.get("nome_completo")),
            require("procurador", "CPF do procurador", procurador.get("cpf")),
            require("procurador", "Logradouro do procurador", procurador.get("logradouro")),
            require("procurador", "Cidade do procurador", procurador.get("cidade")),
            require("procurador", "UF do procurador", procurador.get("uf")),
        ])
        (complete_sections if proc_ok else pending_sections).append("Procurador")

    if imoveis:
        complete_sections.append("Imoveis vinculados")
    else:
        pending_sections.append("Imoveis vinculados")
        missing.append({"secao": "imoveis", "label": "Imovel vinculado"})

    total_checks = max(len(complete_sections) + len(pending_sections), 1)
    percent = int((len(complete_sections) / total_checks) * 100)
    readiness = get_document_readiness(cliente_context)
    return {
        "percentual": percent,
        "secoes_completas": complete_sections,
        "secoes_pendentes": pending_sections,
        "campos_faltantes": missing,
        "documentos_liberados": [doc for doc, info in readiness.items() if info["can_generate"]],
        "documentos_bloqueados": [doc for doc, info in readiness.items() if not info["can_generate"]],
        "readiness": readiness,
    }


def build_texto_proprietario(cliente_context, imovel=None):
    cliente = cliente_context.get("cliente") or {}
    pf = cliente_context.get("pessoa_fisica") or {}
    pj = cliente_context.get("pessoa_juridica") or {}
    if cliente.get("tipo_cliente") == "PESSOA_JURIDICA":
        return f"{pj.get('razao_social') or cliente.get('nome_exibicao') or ''}, inscrita no CNPJ sob n. {format_cnpj(pj.get('cnpj'))}"
    flex = build_flexoes_genero(pf.get("sexo"))
    return (
        f"{pf.get('nome_completo') or cliente.get('nome_exibicao') or ''}, "
        f"{pf.get('nacionalidade') or flex['brasileiro']}, "
        f"{(pf.get('estado_civil') or '').lower().replace('_', ' ')}, "
        f"{pf.get('profissao_ocupacao') or ''}, "
        f"{flex['portador']} do RG {pf.get('rg') or ''}, "
        f"{flex['inscrito']} no CPF sob n. {format_cpf(pf.get('cpf'))}"
    ).strip()


def build_texto_conjuge(cliente_context):
    conjuge = cliente_context.get("conjuge") or {}
    if not conjuge.get("nome_completo"):
        return ""
    return f"{conjuge.get('nome_completo')}, CPF {format_cpf(conjuge.get('cpf'))}"


def build_texto_procurador(cliente_context):
    procurador = cliente_context.get("procurador") or {}
    if not procurador.get("nome_completo"):
        return ""
    return (
        f"{procurador.get('nome_completo')}, CPF {format_cpf(procurador.get('cpf'))}, "
        f"{procurador.get('texto_adicional') or ''}"
    ).strip()


def build_assinaturas(cliente_context):
    cliente = cliente_context.get("cliente") or {}
    procurador = cliente_context.get("procurador") or {}
    pf = cliente_context.get("pessoa_fisica") or {}
    nome = procurador.get("nome_completo") if cliente.get("quem_assina") == "PROCURADOR" else pf.get("nome_completo") or cliente.get("nome_exibicao")
    return {
        "PROPRIETARIO_1": nome or "",
        "PROPRIETARIO_2": build_texto_conjuge(cliente_context),
        "LINHA_ASSINATURA": "________________________________________",
        "TIITULO_ASSINATURA": "Proprietario" if cliente.get("quem_assina") == "PROPRIETARIO" else "Procurador / representante",
        "NOME_ASSINATURA": nome or "",
    }


def build_documento_context(cliente_context, imovel=None, vertices=None):
    imovel = imovel or (cliente_context.get("imoveis") or [{}])[0] or {}
    assinatura = build_assinaturas(cliente_context)
    certidao = imovel.get("tipo_certidao") or ""
    numero = imovel.get("numero_certidao") or ""
    area = imovel.get("nova_area_m2") or ""
    perimetro = imovel.get("perimetro_m") or ""
    memorial = ""
    for vertex in vertices or []:
        memorial += (
            f"{vertex.get('codigo_vertice') or ''} a {vertex.get('codigo_vertice_destino') or ''}, "
            f"azimute {vertex.get('azimute') or ''}, distancia {vertex.get('distancia_m') or ''}m, "
            f"confrontando com {vertex.get('confrontacao') or ''}. "
        )
    context = {
        "TEXTO_PROPRIETARIO": build_texto_proprietario(cliente_context, imovel),
        "CERTIDAO": certidao,
        "NCERTIDAO": numero,
        "CARTORIO": imovel.get("cartorio_comarca") or "",
        "DATA": date.today().strftime("%d/%m/%Y"),
        "TEXTO_1": "",
        "TEXTO_2": "",
        "TEXTO_3": "",
        "TEXTO_4": "",
        "TEXTO_5": "",
        "COD_CERTIFICACAO": imovel.get("codigo_certificacao_sigef") or "",
        "TEXTO_AREA": str(area),
        "TEXTO_PERIMETRO": str(perimetro),
        "TEXTO_MEMORIAL": memorial.strip(),
        "PROPRIETARIO": cliente_context.get("cliente", {}).get("nome_exibicao") or "",
        "CPF": format_cpf((cliente_context.get("pessoa_fisica") or {}).get("cpf")),
        "MATRICULA": numero if certidao == "MATRICULA" else "",
        "CNS_CARTORIO": imovel.get("cns_cartorio") or "",
        "CIDADE": imovel.get("cidade_imovel") or "",
        "SNCR": imovel.get("codigo_sncr") or "",
    }
    context.update(assinatura)
    return context
