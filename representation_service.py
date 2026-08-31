"""Camada de dominio para representacoes (public.representacoes e tabelas ligadas).

Segue a mesma convencao de `person_repository.py`: recebe `db` (conexao ja
aberta pelo request) e `chave_app`, e delega toda leitura/escrita as RPCs
`public.obter_contexto_assinatura_v1`, `public.salvar_representacao_assinatura_v1`
e `public.desativar_representacao_assinatura_v1`.

Nenhuma funcao aqui apaga e recria em massa: `salvar_representacao_assinatura_v1`
substitui apenas os representantes/representados da UNICA representacao
identificada por `representacao_id` (uma operacao do tipo "PUT" sobre aquele
registro especifico) -- as demais representacoes do cliente/pessoa
permanecem intocadas. Desativar usa soft-delete (`ativo = false`), nunca
DELETE.
"""

import datetime as dt

import psycopg2
import psycopg2.extras

# Papeis que uma pessoa pode exercer dentro de UMA representacao especifica.
# O papel pertence a relacao (representacao_representantes.papel), nunca a
# pessoa em si -- a mesma pessoa pode ter papeis diferentes em representacoes
# diferentes.
PAPEIS_REPRESENTACAO = {
    "PROCURADOR": "Procurador",
    "REPRESENTANTE_LEGAL": "Representante legal",
    "INVENTARIANTE": "Inventariante",
    "SOCIO_ADMINISTRADOR": "Sócio-administrador",
    "ADMINISTRADOR": "Administrador",
    "DIRETOR": "Diretor",
    "SINDICO": "Síndico",
    "ADMINISTRADOR_JUDICIAL": "Administrador judicial",
    "CURADOR": "Curador",
    "TUTOR": "Tutor",
    "REPRESENTANTE": "Representante",
    "OUTRO": "Outro",
}

MODOS_ATUACAO = {
    "INDIVIDUAL": "Pode assinar sozinho",
    "CONJUNTA": "Deve assinar em conjunto",
    "QUALQUER_UM": "Qualquer um dos representantes pode assinar",
}

NATUREZAS_SUGERIDAS = [
    "PROCURACAO",
    "INVENTARIO",
    "REPRESENTACAO",
    "CONTRATO_SOCIAL",
    "OUTRO",
]

CONDICOES_JURIDICAS = {
    "NORMAL": "Normal",
    "ESPOLIO": "Espólio",
    "OUTRO": "Outro",
}


def legacy_representatives_sync_allowed(form):
    """Indica se o POST ainda usa a tela legada de procuradores.

    A interface V2 gerencia representações pelas RPCs próprias e não envia
    `rep_*`. A ausência desses campos, portanto, não pode ser interpretada
    como remoção quando o marcador V2 está presente. Sem o marcador,
    preservamos o contrato histórico do formulário.
    """
    return str(form.get("representation_ui_version") or "").strip() != "2"


class RepresentationServiceError(RuntimeError):
    """Erro de negocio devolvido pelas RPCs de representacoes (mensagem ja tratada)."""


def papel_label(papel):
    """Converte o codigo do papel em texto apropriado para a interface."""
    codigo = str(papel or "").strip().upper()
    return PAPEIS_REPRESENTACAO.get(codigo, codigo.replace("_", " ").title() or "Representante")


def _date_value(value):
    if not value:
        return None
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    try:
        return dt.date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def validade_label(representacao, today=None):
    """Formata a validade para o card sem substituir a vigencia da RPC."""
    inicio = _date_value(representacao.get("validade_inicio"))
    fim = _date_value(representacao.get("validade_fim"))
    if not inicio and not fim:
        return "Sem prazo informado"
    hoje = today or dt.date.today()
    if fim and fim < hoje:
        return f"Fora de validade desde {fim.strftime('%d/%m/%Y')}"
    if fim:
        return f"Válida até {fim.strftime('%d/%m/%Y')}"
    return f"Válida desde {inicio.strftime('%d/%m/%Y')}"


def representacao_view(representacao, today=None):
    """Adiciona significado de apresentacao ao payload retornado pela RPC."""
    view = dict(representacao or {})
    representantes = [dict(item) for item in (view.get("representantes") or [])]
    for representante in representantes:
        representante["papel_label"] = papel_label(representante.get("papel"))
    view["representantes"] = representantes
    view["representantes_label"] = " e ".join(
        item.get("nome") or "Sem nome" for item in representantes
    )
    view["papel_label"] = ", ".join(item["papel_label"] for item in representantes) or "Representante"
    view["atuacao_label"] = MODOS_ATUACAO.get(
        view.get("modo_atuacao"), view.get("modo_atuacao") or ""
    )
    view["status_label"] = (
        "Inativa" if not view.get("ativo")
        else ("Vigente" if view.get("vigente") else "Fora de validade")
    )
    view["validade_label"] = validade_label(view, today=today)
    return view


def select_document_representante(representacoes):
    """Projeta a representacao central principal para o contrato documental legado."""
    vigentes = [
        item for item in (representacoes or [])
        if item.get("ativo") and item.get("vigente") and item.get("representantes")
    ]
    ativas = [
        item for item in (representacoes or [])
        if item.get("ativo") and item.get("representantes")
    ]
    representacao = (vigentes or ativas or [None])[0]
    if not representacao:
        return None
    representantes = sorted(
        representacao.get("representantes") or [],
        key=lambda item: (not bool(item.get("principal")), item.get("ordem") or 0),
    )
    pessoa = representantes[0]
    perfil = dict(pessoa.get("qualificacao_central") or {})
    perfil["nome_completo"] = pessoa.get("nome") or perfil.get("nome_completo") or ""
    perfil["cpf"] = pessoa.get("cpf_cnpj") or perfil.get("cpf") or ""
    perfil["tipo_representacao"] = pessoa.get("papel") or "PROCURADOR"
    return perfil


def _clean_pg_message(exc):
    diag = getattr(exc, "diag", None)
    message = (getattr(diag, "message_primary", None) or "").strip()
    return message or str(exc).strip()


def _fetch_single_column(cur):
    row = cur.fetchone()
    if row is None:
        return None
    if isinstance(row, dict):
        return next(iter(row.values()))
    return row[0]


def _run_read_rpc(db, sql, params):
    try:
        cur = db.execute(sql, params)
        try:
            return _fetch_single_column(cur)
        finally:
            cur.close()
    except psycopg2.Error as exc:
        db.rollback()
        raise RepresentationServiceError(_clean_pg_message(exc)) from exc


def _run_write_rpc(db, sql, params):
    try:
        cur = db.execute(sql, params)
        try:
            result = _fetch_single_column(cur)
        finally:
            cur.close()
        # Mesma ressalva de person_repository._run_write_rpc: a escrita
        # acontece dentro da funcao SECURITY DEFINER, entao precisa de commit
        # explicito para nao ser perdida no fechamento da conexao.
        db.commit(force=True)
        return result
    except psycopg2.Error as exc:
        db.rollback()
        raise RepresentationServiceError(_clean_pg_message(exc)) from exc


def get_contexto_assinatura(db, chave_app, cliente_id):
    """Contexto documental completo de um cliente: titular, conjuge e
    representacoes ativas/vigentes (obter_contexto_assinatura_v1)."""
    return _run_read_rpc(
        db,
        "SELECT public.obter_contexto_assinatura_v1(%s, %s)",
        (str(cliente_id), chave_app),
    )


def save_representacao(db, chave_app, dados):
    """Cria ou atualiza uma representacao (salvar_representacao_assinatura_v1).

    `dados` esperado: representacao_id (opcional; presente = edicao),
    natureza, modo_atuacao (INDIVIDUAL/CONJUNTA/QUALQUER_UM), principal,
    ativo, documento_base, referencia_documento, escopo_poderes,
    validade_inicio, validade_fim, observacoes,
    representantes: [{pessoa_id, papel, principal, ordem}, ...],
    representados: [{cliente_id: ...} | {pessoa_id: ...}, ...].
    """
    return _run_write_rpc(
        db,
        "SELECT public.salvar_representacao_assinatura_v1(%s, %s)",
        (psycopg2.extras.Json(dados), chave_app),
    )


def deactivate_representacao(db, chave_app, representacao_id):
    """Desativa (soft-delete) uma representacao; ela some da lista ativa mas
    continua no historico (desativar_representacao_assinatura_v1)."""
    return _run_write_rpc(
        db,
        "SELECT public.desativar_representacao_assinatura_v1(%s, %s)",
        (representacao_id, chave_app),
    )
