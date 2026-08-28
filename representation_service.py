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
    "SOCIO_ADMINISTRADOR": "Socio-administrador",
    "ADMINISTRADOR": "Administrador",
    "DIRETOR": "Diretor",
    "SINDICO": "Sindico",
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
    "ESPOLIO": "Espolio",
    "OUTRO": "Outro",
}


class RepresentationServiceError(RuntimeError):
    """Erro de negocio devolvido pelas RPCs de representacoes (mensagem ja tratada)."""


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
