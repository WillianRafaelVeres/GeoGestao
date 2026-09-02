"""Camada de acesso a dados do modulo de Despesas (Financeiro -> Despesas).

Segue a mesma convencao de person_repository.py/representation_service.py:
este modulo nao guarda estado nem abre conexao propria. Toda funcao recebe
`db` (o wrapper de conexao ja aberto pelo request, com `.execute(sql, args)`
retornando um cursor `RealDictCursor`) e faz SQL simples diretamente --
diferente dos dois modulos citados, aqui NAO existem RPCs `SECURITY DEFINER`
publicadas para despesas, entao o acesso e via `INSERT`/`SELECT`/`UPDATE`
comuns, no mesmo estilo ja usado em app.py para projeto_custos/projeto_pagamentos.

Datas e horarios continuam como TEXT (ISO), no mesmo padrao do resto do
banco; quem chama este modulo (expense_service.py, ou os testes) e quem
decide o valor de "agora" -- este modulo nunca calcula timestamp sozinho.
"""

import psycopg2.extras


def _fetchone(db, sql, params=()):
    cur = db.execute(sql, params)
    try:
        return cur.fetchone()
    finally:
        cur.close()


def _fetchall(db, sql, params=()):
    cur = db.execute(sql, params)
    try:
        return cur.fetchall()
    finally:
        cur.close()


def _insert_returning_id(db, sql, params=()):
    row = _fetchone(db, sql, params)
    return row["id"] if row else None


# --- Desembolsantes ---------------------------------------------------

def insert_desembolsante(db, nome, usuario_id=None, documento=None, criado_em=None, criado_por=None):
    return _insert_returning_id(
        db,
        """
        INSERT INTO desembolsantes (nome, usuario_id, documento, criado_em, criado_por)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
        """,
        (nome, usuario_id, documento, criado_em, criado_por),
    )


def get_desembolsante(db, desembolsante_id):
    return _fetchone(db, "SELECT * FROM desembolsantes WHERE id = %s", (desembolsante_id,))


def list_desembolsantes(db, apenas_ativos=True):
    if apenas_ativos:
        return _fetchall(db, "SELECT * FROM desembolsantes WHERE ativo = TRUE ORDER BY nome")
    return _fetchall(db, "SELECT * FROM desembolsantes ORDER BY nome")


def find_desembolsante_by_usuario(db, usuario_id):
    return _fetchone(db, "SELECT * FROM desembolsantes WHERE usuario_id = %s AND ativo = TRUE", (usuario_id,))


# --- Despesas ------------------------------------------------------------

def insert_despesa(
    db,
    descricao,
    valor_total,
    desembolsado_por_tipo,
    criado_em,
    categoria=None,
    data_despesa=None,
    observacoes=None,
    status="rascunho",
    desembolsado_por_id=None,
    lote_id=None,
    origem="MANUAL",
    registro_uid=None,
    criado_por=None,
    migrado_de_custo_id=None,
):
    return _insert_returning_id(
        db,
        """
        INSERT INTO despesas (
            descricao, categoria, valor_total, data_despesa, observacoes, status,
            desembolsado_por_tipo, desembolsado_por_id, lote_id, origem, registro_uid,
            criado_em, criado_por, migrado_de_custo_id
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            descricao, categoria, valor_total, data_despesa, observacoes, status,
            desembolsado_por_tipo, desembolsado_por_id, lote_id, origem, registro_uid,
            criado_em, criado_por, migrado_de_custo_id,
        ),
    )


def get_despesa(db, despesa_id):
    return _fetchone(db, "SELECT * FROM despesas WHERE id = %s", (despesa_id,))


def find_despesa_by_registro_uid(db, registro_uid):
    if not registro_uid:
        return None
    return _fetchone(db, "SELECT * FROM despesas WHERE registro_uid = %s", (registro_uid,))


def find_despesa_by_migrado_de_custo(db, custo_id):
    return _fetchone(db, "SELECT * FROM despesas WHERE migrado_de_custo_id = %s", (custo_id,))


def update_despesa_status(db, despesa_id, status, atualizado_em, atualizado_por=None):
    db.execute(
        "UPDATE despesas SET status = %s, atualizado_em = %s, atualizado_por = %s WHERE id = %s",
        (status, atualizado_em, atualizado_por, despesa_id),
    ).close()


def cancel_despesa(db, despesa_id, motivo, cancelado_em, cancelado_por=None):
    db.execute(
        """
        UPDATE despesas
        SET status = 'cancelada', motivo_cancelamento = %s, cancelado_em = %s, cancelado_por = %s
        WHERE id = %s
        """,
        (motivo, cancelado_em, cancelado_por, despesa_id),
    ).close()


def list_despesas(db, status=None, desembolsado_por_id=None, projeto_id=None, cliente_id=None, limit=200):
    """Listagem com filtros simples, usada pela futura tela Despesas.

    Usa EXISTS (nao JOIN) quando filtra por projeto/cliente para nao duplicar
    a despesa por alocacao na listagem principal.
    """
    clauses = []
    params = []
    if status:
        clauses.append("d.status = %s")
        params.append(status)
    if desembolsado_por_id:
        clauses.append("d.desembolsado_por_id = %s")
        params.append(desembolsado_por_id)
    if projeto_id:
        clauses.append("EXISTS (SELECT 1 FROM despesa_alocacoes a WHERE a.despesa_id = d.id AND a.projeto_id = %s)")
        params.append(projeto_id)
    if cliente_id:
        clauses.append("EXISTS (SELECT 1 FROM despesa_alocacoes a WHERE a.despesa_id = d.id AND a.cliente_id = %s)")
        params.append(cliente_id)
    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit)
    return _fetchall(
        db,
        f"""
        SELECT d.*
        FROM despesas d
        {where_sql}
        ORDER BY COALESCE(d.data_despesa, '') DESC, d.id DESC
        LIMIT %s
        """,
        params,
    )


# --- Alocacoes -------------------------------------------------------------

def resolve_projeto_cliente(db, projeto_id):
    """Cliente 'dono' do projeto no momento da chamada: proprietario principal
    em projeto_proprietarios, com fallback para o cliente_id legado do projeto."""
    row = _fetchone(
        db,
        """
        SELECT COALESCE(pp.cliente_id, p.cliente_id) AS cliente_id
        FROM projetos p
        LEFT JOIN LATERAL (
            SELECT cliente_id FROM projeto_proprietarios
            WHERE projeto_id = p.id
            ORDER BY principal DESC, cliente_id
            LIMIT 1
        ) pp ON TRUE
        WHERE p.id = %s
        """,
        (projeto_id,),
    )
    return row["cliente_id"] if row else None


def insert_alocacao(db, despesa_id, projeto_id, cliente_id, valor, criado_em, percentual=None):
    return _insert_returning_id(
        db,
        """
        INSERT INTO despesa_alocacoes (despesa_id, projeto_id, cliente_id, valor, percentual, criado_em)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (despesa_id, projeto_id, cliente_id, valor, percentual, criado_em),
    )


def list_alocacoes(db, despesa_id):
    return _fetchall(
        db,
        """
        SELECT a.*, p.nome AS projeto_nome, p.codigo AS projeto_codigo, c.nome_exibicao, c.nome AS cliente_nome_legado
        FROM despesa_alocacoes a
        JOIN projetos p ON p.id = a.projeto_id
        LEFT JOIN clientes c ON c.id = a.cliente_id
        WHERE a.despesa_id = %s
        ORDER BY a.id
        """,
        (despesa_id,),
    )


def delete_alocacoes(db, despesa_id):
    db.execute("DELETE FROM despesa_alocacoes WHERE despesa_id = %s", (despesa_id,)).close()


# --- Anexos ------------------------------------------------------------

def insert_anexo(
    db, despesa_id, caminho_dropbox, nome_arquivo, criado_em,
    nome_original=None, tipo=None, file_hash=None, tamanho=None, principal=False, criado_por=None,
):
    return _insert_returning_id(
        db,
        """
        INSERT INTO despesa_anexos
            (despesa_id, caminho_dropbox, nome_arquivo, nome_original, tipo, hash, tamanho, principal, criado_em, criado_por)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (despesa_id, caminho_dropbox, nome_arquivo, nome_original, tipo, file_hash, tamanho, principal, criado_em, criado_por),
    )


def list_anexos(db, despesa_id):
    return _fetchall(db, "SELECT * FROM despesa_anexos WHERE despesa_id = %s ORDER BY principal DESC, id", (despesa_id,))


def find_anexo_by_hash(db, file_hash, exclude_despesa_id=None):
    """Comprovante com o mesmo hash SHA-256 ja lancado em QUALQUER despesa (nao so a atual).

    Hash identico e o caso rigoroso do item 20 do pedido: mesmo conteudo de
    arquivo, quase certamente o mesmo comprovante sendo importado de novo.
    """
    if not file_hash:
        return None
    if exclude_despesa_id:
        return _fetchone(
            db,
            """
            SELECT da.*, d.descricao AS despesa_descricao, d.status AS despesa_status
            FROM despesa_anexos da
            JOIN despesas d ON d.id = da.despesa_id
            WHERE da.hash = %s AND da.despesa_id != %s
            ORDER BY da.id DESC
            LIMIT 1
            """,
            (file_hash, exclude_despesa_id),
        )
    return _fetchone(
        db,
        """
        SELECT da.*, d.descricao AS despesa_descricao, d.status AS despesa_status
        FROM despesa_anexos da
        JOIN despesas d ON d.id = da.despesa_id
        WHERE da.hash = %s
        ORDER BY da.id DESC
        LIMIT 1
        """,
        (file_hash,),
    )


# --- Reembolsos ------------------------------------------------------------

def insert_reembolso(
    db, desembolsante_id, valor, data_reembolso, criado_em,
    forma_reembolso=None, observacoes=None, anexo_path=None, anexo_nome=None,
    registro_uid=None, criado_por=None,
):
    return _insert_returning_id(
        db,
        """
        INSERT INTO despesa_reembolsos
            (desembolsante_id, valor, data_reembolso, forma_reembolso, observacoes,
             anexo_path, anexo_nome, registro_uid, criado_em, criado_por)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (desembolsante_id, valor, data_reembolso, forma_reembolso, observacoes,
         anexo_path, anexo_nome, registro_uid, criado_em, criado_por),
    )


def find_reembolso_by_registro_uid(db, registro_uid):
    if not registro_uid:
        return None
    return _fetchone(db, "SELECT * FROM despesa_reembolsos WHERE registro_uid = %s", (registro_uid,))


def insert_reembolso_alocacao(db, reembolso_id, despesa_id, valor):
    return _insert_returning_id(
        db,
        """
        INSERT INTO despesa_reembolso_alocacoes (reembolso_id, despesa_id, valor)
        VALUES (%s, %s, %s)
        RETURNING id
        """,
        (reembolso_id, despesa_id, valor),
    )


def sum_reembolsado_por_despesa(db, despesa_id):
    row = _fetchone(
        db,
        """
        SELECT COALESCE(SUM(ra.valor), 0) AS total
        FROM despesa_reembolso_alocacoes ra
        JOIN despesa_reembolsos r ON r.id = ra.reembolso_id
        WHERE ra.despesa_id = %s AND r.status = 'confirmado'
        """,
        (despesa_id,),
    )
    return float(row["total"]) if row else 0.0


def list_despesas_pendentes_por_desembolsante(db, desembolsante_id):
    """Despesas prontas, desembolsadas por essa pessoa, com saldo de reembolso > 0."""
    return _fetchall(
        db,
        """
        SELECT
            d.*,
            COALESCE(ra.total_reembolsado, 0) AS total_reembolsado,
            d.valor_total - COALESCE(ra.total_reembolsado, 0) AS saldo_pendente
        FROM despesas d
        LEFT JOIN LATERAL (
            SELECT SUM(ra.valor) AS total_reembolsado
            FROM despesa_reembolso_alocacoes ra
            JOIN despesa_reembolsos r ON r.id = ra.reembolso_id
            WHERE ra.despesa_id = d.id AND r.status = 'confirmado'
        ) ra ON TRUE
        WHERE d.desembolsado_por_tipo = 'PESSOA'
          AND d.desembolsado_por_id = %s
          AND d.status != 'cancelada'
          AND d.valor_total - COALESCE(ra.total_reembolsado, 0) > 0.005
        ORDER BY COALESCE(d.data_despesa, '') DESC, d.id DESC
        """,
        (desembolsante_id,),
    )


def summarize_pendencias_reembolso(db):
    """Uma linha por desembolsante com saldo pendente > 0, para 'Financeiro -> Reembolsos'."""
    return _fetchall(
        db,
        """
        SELECT
            p.id AS desembolsante_id,
            p.nome,
            COUNT(*) AS despesas_pendentes,
            SUM(d.valor_total - COALESCE(ra.total_reembolsado, 0)) AS total_pendente
        FROM despesas d
        JOIN desembolsantes p ON p.id = d.desembolsado_por_id
        LEFT JOIN LATERAL (
            SELECT SUM(ra.valor) AS total_reembolsado
            FROM despesa_reembolso_alocacoes ra
            JOIN despesa_reembolsos r ON r.id = ra.reembolso_id
            WHERE ra.despesa_id = d.id AND r.status = 'confirmado'
        ) ra ON TRUE
        WHERE d.desembolsado_por_tipo = 'PESSOA'
          AND d.status != 'cancelada'
          AND d.valor_total - COALESCE(ra.total_reembolsado, 0) > 0.005
        GROUP BY p.id, p.nome
        ORDER BY total_pendente DESC
        """,
    )


# --- Lotes de importacao ----------------------------------------------

def insert_lote(db, criado_em, titulo=None, criado_por=None):
    return _insert_returning_id(
        db,
        "INSERT INTO despesa_lotes (titulo, criado_em, criado_por) VALUES (%s, %s, %s) RETURNING id",
        (titulo, criado_em, criado_por),
    )


def get_lote_progresso(db, lote_id):
    row = _fetchone(
        db,
        """
        SELECT
            l.id, l.titulo, l.status, l.total_documentos,
            COUNT(d.id) FILTER (WHERE d.status NOT IN ('rascunho', 'pendente_classificacao')) AS classificados,
            COUNT(d.id) FILTER (WHERE d.status IN ('rascunho', 'pendente_classificacao')) AS pendentes
        FROM despesa_lotes l
        LEFT JOIN despesas d ON d.lote_id = l.id
        WHERE l.id = %s
        GROUP BY l.id
        """,
        (lote_id,),
    )
    return row


# --- Auditoria (despesa_eventos) ----------------------------------------

def insert_evento(db, despesa_id, tipo_evento, descricao, criado_em, usuario_id=None):
    db.execute(
        "INSERT INTO despesa_eventos (despesa_id, usuario_id, tipo_evento, descricao, criado_em) VALUES (%s, %s, %s, %s, %s)",
        (despesa_id, usuario_id, tipo_evento, descricao, criado_em),
    ).close()


def list_eventos(db, despesa_id):
    return _fetchall(
        db,
        """
        SELECT e.*, u.nome AS usuario_nome
        FROM despesa_eventos e
        LEFT JOIN usuarios u ON u.id = e.usuario_id
        WHERE e.despesa_id = %s
        ORDER BY e.criado_em DESC, e.id DESC
        """,
        (despesa_id,),
    )


# --- Rascunho de leitura por IA (espelha exigencia_analises_ia) -----------

def upsert_ia_analysis(
    db, despesa_id, source_hash, draft, usage, criado_em,
    anexo_id=None, model=None, source_method=None, warning_message=None,
    prompt_version=None, criado_por=None,
):
    return _insert_returning_id(
        db,
        """
        INSERT INTO despesa_documento_analises_ia (
            despesa_id, anexo_id, status, provider, model, source_hash, source_method,
            draft_json, usage_json, warning_message, prompt_version, criado_por, criado_em, atualizado_em
        )
        VALUES (%s, %s, 'rascunho', 'groq', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (despesa_id) DO UPDATE SET
            anexo_id = EXCLUDED.anexo_id,
            status = 'rascunho',
            model = EXCLUDED.model,
            source_hash = EXCLUDED.source_hash,
            source_method = EXCLUDED.source_method,
            draft_json = EXCLUDED.draft_json,
            usage_json = EXCLUDED.usage_json,
            warning_message = EXCLUDED.warning_message,
            prompt_version = EXCLUDED.prompt_version,
            criado_por = EXCLUDED.criado_por,
            atualizado_em = EXCLUDED.atualizado_em,
            aplicado_em = NULL
        RETURNING id
        """,
        (
            despesa_id, anexo_id, model, source_hash, source_method,
            psycopg2.extras.Json(draft), psycopg2.extras.Json(usage), warning_message,
            prompt_version, criado_por, criado_em, criado_em,
        ),
    )


def get_ia_analysis(db, despesa_id):
    return _fetchone(db, "SELECT * FROM despesa_documento_analises_ia WHERE despesa_id = %s", (despesa_id,))


def mark_ia_analysis_applied(db, despesa_id, aplicado_em):
    db.execute(
        "UPDATE despesa_documento_analises_ia SET status = 'aplicado', aplicado_em = %s WHERE despesa_id = %s",
        (aplicado_em, despesa_id),
    ).close()
