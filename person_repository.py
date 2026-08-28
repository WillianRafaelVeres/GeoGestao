"""Camada de acesso ao cadastro central de pessoas (public.pessoas_cadastro).

Este modulo nao guarda estado nem abre conexao propria: recebe `db` (o
wrapper de conexao ja aberto pelo request, com metodos `.execute(sql, args)`,
`.commit(force=True)` e `.rollback()`) e a chave de aplicacao configurada em
`GEOGESTAO_ASSINATURAS_APP_KEY`. Toda leitura/escrita acontece via as RPCs
SECURITY DEFINER `public.*_assinatura_v1` ja publicadas no Supabase -- este
modulo nunca faz DELETE+INSERT direto nas tabelas novas, e nunca duplica a
logica que essas RPCs ja implementam (resolucao de pessoa por CPF/CNPJ,
qualificacao central, etc.).
"""

import unicodedata

import psycopg2
import psycopg2.extras


class PersonRepositoryError(RuntimeError):
    """Erro de negocio devolvido pelas RPCs de pessoas (mensagem ja tratada)."""


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
        raise PersonRepositoryError(_clean_pg_message(exc)) from exc


def _run_write_rpc(db, sql, params):
    try:
        cur = db.execute(sql, params)
        try:
            result = _fetch_single_column(cur)
        finally:
            cur.close()
        # As RPCs sao SECURITY DEFINER chamadas via "SELECT funcao(...)": o
        # heuristico de deteccao de escrita do app (baseado no texto/status do
        # comando) nao enxerga a escrita feita dentro da funcao. Sem commit
        # explicito aqui, o teardown da conexao faria ROLLBACK da chamada.
        db.commit(force=True)
        return result
    except psycopg2.Error as exc:
        db.rollback()
        raise PersonRepositoryError(_clean_pg_message(exc)) from exc


def list_pessoas(db, chave_app):
    """Lista todas as pessoas ativas do cadastro central (listar_pessoas_assinatura_v1)."""
    try:
        cur = db.execute("SELECT * FROM public.listar_pessoas_assinatura_v1(%s)", (chave_app,))
        try:
            rows = cur.fetchall()
        finally:
            cur.close()
    except psycopg2.Error as exc:
        db.rollback()
        raise PersonRepositoryError(_clean_pg_message(exc)) from exc
    return [(next(iter(row.values())) if isinstance(row, dict) else row[0]) for row in rows]


def _normalize_text(value):
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.lower()


def search_pessoas(pessoas, termo, limit=20):
    """Filtra em memoria a lista ja carregada de listar_pessoas_assinatura_v1.

    Funcao pura (sem acesso a banco) para permitir testes rapidos do
    comportamento de busca por nome/CPF/CNPJ sem depender do Supabase.
    """
    termo_normalizado = _normalize_text(termo).strip()
    if not termo_normalizado:
        return pessoas[:limit]
    only_digits_termo = "".join(ch for ch in termo_normalizado if ch.isdigit())
    matches = []
    for pessoa in pessoas:
        haystacks = [
            _normalize_text(pessoa.get("nome_display")),
            _normalize_text(pessoa.get("documento")),
            _normalize_text(pessoa.get("search")),
        ]
        if any(termo_normalizado in haystack for haystack in haystacks):
            matches.append(pessoa)
            continue
        documento_normalizado = pessoa.get("documento_normalizado") or ""
        if only_digits_termo and only_digits_termo in documento_normalizado:
            matches.append(pessoa)
    return matches[:limit]


def get_pessoa(db, chave_app, pessoa_id):
    """Detalhe completo de uma pessoa central (obter_pessoa_assinatura_v1)."""
    return _run_read_rpc(
        db,
        "SELECT public.obter_pessoa_assinatura_v1(%s, %s)",
        (pessoa_id, chave_app),
    )


def save_pessoa(db, chave_app, dados):
    """Cria ou atualiza uma pessoa central (salvar_pessoa_assinatura_v1).

    `dados` deve seguir o formato aceito pela RPC: tipo_pessoa, nome_exibicao,
    documento, pessoa_id (opcional, presente = atualizacao), pessoa_fisica /
    pessoa_juridica / endereco (dicts com os campos de qualificacao).
    """
    return _run_write_rpc(
        db,
        "SELECT public.salvar_pessoa_assinatura_v1(%s, %s)",
        (psycopg2.extras.Json(dados), chave_app),
    )


def create_cliente_for_pessoa(db, chave_app, pessoa_id, dados=None):
    """Cria (ou reaproveita) o cliente/contexto documental de uma pessoa central."""
    return _run_write_rpc(
        db,
        "SELECT public.criar_cliente_para_pessoa_v1(%s, %s, %s)",
        (pessoa_id, psycopg2.extras.Json(dados or {}), chave_app),
    )
