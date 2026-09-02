"""Regras de negocio do modulo de Despesas (Financeiro -> Despesas/Reembolsos).

expense_repository.py cuida do SQL puro; este modulo cuida das regras: soma
de alocacoes, resolucao automatica de cliente a partir do projeto, a
diferenca entre desembolso e reembolso interno, transicoes de status e
migracao dos custos legados. Como person_repository.py/representation_service.py,
recebe `db` explicitamente (sem conexao propria) para poder ser chamado de
dentro de uma rota do app.py, que controla commit/rollback por request.

Nomenclatura deliberada: "desembolsado_por" em vez de "pagador", porque
"pagamento" no GeoGestao ja significa dinheiro que o CLIENTE paga a empresa
(projeto_pagamentos). Aqui e sempre sobre quem adiantou o dinheiro da despesa
-- a empresa ou uma pessoa -- nunca sobre o cliente.
"""

from decimal import Decimal, ROUND_HALF_UP

import psycopg2.errors

import expense_repository as repo

ALLOCATION_TOLERANCE = Decimal("0.01")

DESPESA_STATUSES = ("rascunho", "pendente_classificacao", "classificada", "pronta", "cancelada")


class ExpenseServiceError(RuntimeError):
    """Erro de regra de negocio do modulo de Despesas (mensagem ja pronta para o usuario)."""


# --- Helpers puros (sem banco) -- testaveis sem FakeDb ---------------------

def to_currency(value):
    """Normaliza qualquer numero para Decimal com 2 casas, arredondamento comercial."""
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def validate_allocations_sum(valor_total, alocacoes):
    """Garante que a soma das alocacoes bate com o valor total da despesa.

    Tolerancia de 1 centavo para absorver arredondamento quando o usuario
    preencheu por percentual. Fora disso, rejeita -- nunca permite concluir
    uma despesa com soma diferente do total (regra obrigatoria do pedido).
    """
    if not alocacoes:
        raise ExpenseServiceError("Informe ao menos uma alocacao (projeto) para a despesa.")
    total = to_currency(valor_total)
    soma = sum((to_currency(a["valor"]) for a in alocacoes), Decimal("0.00"))
    if abs(soma - total) > ALLOCATION_TOLERANCE:
        raise ExpenseServiceError(
            f"A soma das alocacoes (R$ {soma}) precisa ser igual ao valor total da despesa (R$ {total})."
        )
    projetos = [a["projeto_id"] for a in alocacoes]
    if len(projetos) != len(set(projetos)):
        raise ExpenseServiceError("O mesmo projeto foi informado mais de uma vez na divisao.")
    for alocacao in alocacoes:
        if to_currency(alocacao["valor"]) <= 0:
            raise ExpenseServiceError("Cada alocacao precisa ter um valor maior que zero.")


def split_by_percentual(valor_total, percentuais_por_projeto):
    """Converte percentuais em valores monetarios que somam exatamente o total.

    Usa o metodo dos maiores restos: arredonda cada fatia para baixo e
    distribui os centavos residuais (1 em 1) para as maiores fracoes
    perdidas, na ordem em que os projetos foram informados. Evita o erro
    classico de "33% + 33% + 34%" nao fechar por causa de arredondamento.
    """
    total_cents = int(to_currency(valor_total) * 100)
    percent_total = sum(Decimal(str(p)) for _, p in percentuais_por_projeto)
    if abs(percent_total - Decimal("100")) > Decimal("0.5"):
        raise ExpenseServiceError(f"Os percentuais somam {percent_total}%, mas precisam somar 100%.")

    raw_shares = []
    for projeto_id, percent in percentuais_por_projeto:
        exact_cents = (Decimal(str(percent)) / Decimal("100")) * total_cents
        floor_cents = int(exact_cents)
        raw_shares.append([projeto_id, floor_cents, exact_cents - floor_cents])

    distributed = sum(share[1] for share in raw_shares)
    leftover = total_cents - distributed
    raw_shares.sort(key=lambda share: share[2], reverse=True)
    for i in range(leftover):
        raw_shares[i % len(raw_shares)][1] += 1

    return {projeto_id: to_currency(Decimal(cents) / 100) for projeto_id, cents, _ in raw_shares}


def is_reembolsavel(despesa):
    """Uma despesa so gera obrigacao de reembolso interno quando uma PESSOA a desembolsou."""
    return despesa["desembolsado_por_tipo"] == "PESSOA" and bool(despesa.get("desembolsado_por_id"))


def compute_despesa_status(has_alocacoes, has_desembolso):
    """Maquina de estados simples (item 13 do pedido).

    rascunho/pendente_classificacao sao usados pelo fluxo de importacao (fora
    do escopo desta fase); a criacao manual sempre parte de dados completos,
    entao so alterna entre 'classificada' (falta projeto/divisao/desembolso)
    e 'pronta' (tudo definido).
    """
    if has_alocacoes and has_desembolso:
        return "pronta"
    return "classificada"


# --- Desembolsantes ---------------------------------------------------

def resolve_desembolsante(db, *, tipo, desembolsante_id=None, nome_novo=None, usuario_id=None, criado_em=None, criado_por=None):
    """Resolve o `desembolsado_por_id` a gravar na despesa.

    tipo='EMPRESA' -> sempre None (empresa nunca vira linha em desembolsantes).
    tipo='PESSOA' -> usa desembolsante_id existente, ou cria um novo a partir
    de nome_novo (alta rapida direto no formulario, sem tela cadastral
    separada obrigatoria).
    """
    if tipo not in ("EMPRESA", "PESSOA"):
        raise ExpenseServiceError("Tipo de desembolso invalido.")
    if tipo == "EMPRESA":
        return None
    if desembolsante_id:
        desembolsante = repo.get_desembolsante(db, desembolsante_id)
        if not desembolsante or not desembolsante["ativo"]:
            raise ExpenseServiceError("Pessoa selecionada para o desembolso nao encontrada ou inativa.")
        return desembolsante_id
    nome = (nome_novo or "").strip()
    if not nome:
        raise ExpenseServiceError("Informe quem realizou o desembolso.")
    return repo.insert_desembolsante(db, nome, usuario_id=usuario_id, criado_em=criado_em, criado_por=criado_por)


# --- Despesas ---------------------------------------------------------

def create_despesa(
    db,
    *,
    descricao,
    valor_total,
    desembolsado_por_tipo,
    criado_em,
    categoria=None,
    data_despesa=None,
    observacoes=None,
    desembolsante_id=None,
    desembolsante_nome_novo=None,
    alocacoes=None,
    registro_uid=None,
    lote_id=None,
    origem="MANUAL",
    criado_por=None,
):
    """Cria uma despesa e, se `alocacoes` for informado, ja divide entre projetos.

    `alocacoes` e uma lista de dicts {"projeto_id": int, "valor": number} (ou
    "cliente_id" explicito, raro -- por padrao o cliente e sempre resolvido a
    partir do projeto, nunca escolhido manualmente). A soma precisa bater com
    `valor_total` -- ver validate_allocations_sum.
    """
    descricao = (descricao or "").strip()
    if not descricao:
        raise ExpenseServiceError("Informe a descricao da despesa.")
    valor_total = to_currency(valor_total)
    if valor_total <= 0:
        raise ExpenseServiceError("O valor da despesa precisa ser maior que zero.")

    if registro_uid:
        existing = repo.find_despesa_by_registro_uid(db, registro_uid)
        if existing:
            return existing

    # Valida ANTES de qualquer escrita (inclusive antes de resolver/criar o
    # desembolsante): como o request so commita no fim (after_request) e um
    # erro de validacao vira redirect (302, nao >=400), uma escrita feita
    # antes do raise seria salva mesmo com a despesa nao sendo criada.
    if alocacoes:
        validate_allocations_sum(valor_total, alocacoes)

    desembolsado_por_id = resolve_desembolsante(
        db,
        tipo=desembolsado_por_tipo,
        desembolsante_id=desembolsante_id,
        nome_novo=desembolsante_nome_novo,
        criado_em=criado_em,
        criado_por=criado_por,
    )

    status = compute_despesa_status(bool(alocacoes), desembolsado_por_tipo == "EMPRESA" or bool(desembolsado_por_id))

    try:
        despesa_id = repo.insert_despesa(
            db,
            descricao=descricao,
            valor_total=valor_total,
            desembolsado_por_tipo=desembolsado_por_tipo,
            criado_em=criado_em,
            categoria=categoria,
            data_despesa=data_despesa,
            observacoes=observacoes,
            status=status,
            desembolsado_por_id=desembolsado_por_id,
            lote_id=lote_id,
            origem=origem,
            registro_uid=registro_uid,
            criado_por=criado_por,
        )
    except psycopg2.errors.UniqueViolation:
        db.rollback()
        existing = repo.find_despesa_by_registro_uid(db, registro_uid)
        if existing:
            return existing
        raise ExpenseServiceError("Esta despesa ja havia sido salva; o envio repetido foi ignorado.") from None

    if alocacoes:
        _insert_alocacoes(db, despesa_id, alocacoes, criado_em)

    repo.insert_evento(
        db, despesa_id, "despesa_criada",
        f"Despesa registrada: {descricao} - R$ {valor_total}.",
        criado_em, usuario_id=criado_por,
    )
    return repo.get_despesa(db, despesa_id)


def _insert_alocacoes(db, despesa_id, alocacoes, criado_em):
    for alocacao in alocacoes:
        cliente_id = alocacao.get("cliente_id")
        if cliente_id is None:
            cliente_id = repo.resolve_projeto_cliente(db, alocacao["projeto_id"])
        repo.insert_alocacao(
            db, despesa_id, alocacao["projeto_id"], cliente_id,
            to_currency(alocacao["valor"]), criado_em,
            percentual=alocacao.get("percentual"),
        )


def set_alocacoes(db, despesa_id, valor_total, alocacoes, criado_em, criado_por=None):
    """Substitui a divisao completa de uma despesa (mesmo padrao de sync_project_owners:
    apaga tudo e reinsere a lista atual, nunca incremental)."""
    validate_allocations_sum(valor_total, alocacoes)
    repo.delete_alocacoes(db, despesa_id)
    _insert_alocacoes(db, despesa_id, alocacoes, criado_em)
    despesa = repo.get_despesa(db, despesa_id)
    novo_status = compute_despesa_status(True, is_reembolsavel(despesa) or despesa["desembolsado_por_tipo"] == "EMPRESA")
    repo.update_despesa_status(db, despesa_id, novo_status, criado_em, criado_por)
    repo.insert_evento(
        db, despesa_id, "despesa_alocacao_atualizada",
        f"Divisao entre projetos atualizada ({len(alocacoes)} projeto(s)).",
        criado_em, usuario_id=criado_por,
    )


def import_documento(
    db, *, lote_id, descricao, caminho_dropbox, nome_arquivo, criado_em,
    nome_original=None, file_hash=None, tamanho=None, data_despesa=None, criado_por=None,
):
    """Transforma UM arquivo importado em lote num rascunho de despesa (item 9 do
    pedido). Nasce em 'pendente_classificacao': sem valor, sem projeto, sem
    desembolsante definido -- nada disso e decidido automaticamente (item 11).
    O usuario classifica depois com classificar_despesa().
    """
    despesa_id = repo.insert_despesa(
        db,
        descricao=descricao,
        valor_total=None,
        desembolsado_por_tipo="EMPRESA",
        criado_em=criado_em,
        data_despesa=data_despesa,
        status="pendente_classificacao",
        lote_id=lote_id,
        origem="IMPORTACAO",
        criado_por=criado_por,
    )
    repo.insert_anexo(
        db, despesa_id, caminho_dropbox, nome_arquivo, criado_em,
        nome_original=nome_original, file_hash=file_hash, tamanho=tamanho,
        principal=True, criado_por=criado_por,
    )
    repo.insert_evento(
        db, despesa_id, "despesa_importada",
        f"Documento importado: {nome_original or nome_arquivo}.",
        criado_em, usuario_id=criado_por,
    )
    return repo.get_despesa(db, despesa_id)


def classificar_despesa(
    db, despesa_id, *, descricao, valor_total, categoria, data_despesa, observacoes,
    desembolsado_por_tipo, alocacoes, atualizado_em,
    desembolsante_id=None, desembolsante_nome_novo=None, atualizado_por=None,
):
    """Completa um rascunho (importado ou manual incompleto) com os dados que a
    IA/importacao nunca decide sozinha: valor confirmado, quem desembolsou e a
    divisao entre projetos. Ao final a despesa fica 'pronta' (via set_alocacoes)."""
    despesa = repo.get_despesa(db, despesa_id)
    if not despesa:
        raise ExpenseServiceError("Despesa nao encontrada.")
    if despesa["status"] == "cancelada":
        raise ExpenseServiceError("Esta despesa esta cancelada e nao pode ser classificada.")

    descricao = (descricao or "").strip()
    if not descricao:
        raise ExpenseServiceError("Informe a descricao da despesa.")
    valor_total = to_currency(valor_total)
    if valor_total <= 0:
        raise ExpenseServiceError("O valor da despesa precisa ser maior que zero.")
    # Valida a soma ANTES de escrever qualquer coisa: como o request inteiro so
    # commita no fim (after_request), um raise depois de um UPDATE parcial
    # ainda seria salvo (o redirect de erro nao e status >=400). Ver
    # set_alocacoes, que faz a mesma validacao de novo antes de aplicar.
    validate_allocations_sum(valor_total, alocacoes)

    desembolsado_por_id = resolve_desembolsante(
        db, tipo=desembolsado_por_tipo, desembolsante_id=desembolsante_id,
        nome_novo=desembolsante_nome_novo, criado_em=atualizado_em, criado_por=atualizado_por,
    )
    repo.update_despesa_classificacao(
        db, despesa_id,
        descricao=descricao, categoria=categoria, valor_total=valor_total,
        data_despesa=data_despesa, observacoes=observacoes,
        desembolsado_por_tipo=desembolsado_por_tipo, desembolsado_por_id=desembolsado_por_id,
        atualizado_em=atualizado_em, atualizado_por=atualizado_por,
    )
    set_alocacoes(db, despesa_id, valor_total, alocacoes, atualizado_em, criado_por=atualizado_por)
    repo.insert_evento(
        db, despesa_id, "despesa_classificada",
        f"Despesa classificada: {descricao} - R$ {valor_total}.",
        atualizado_em, usuario_id=atualizado_por,
    )
    return repo.get_despesa(db, despesa_id)


def cancelar_despesa(db, despesa_id, motivo, cancelado_em, cancelado_por=None):
    despesa = repo.get_despesa(db, despesa_id)
    if not despesa:
        raise ExpenseServiceError("Despesa nao encontrada.")
    if despesa["status"] == "cancelada":
        raise ExpenseServiceError("Esta despesa ja esta cancelada.")
    reembolsado = repo.sum_reembolsado_por_despesa(db, despesa_id)
    if reembolsado > 0.005:
        raise ExpenseServiceError(
            "Esta despesa ja tem reembolso registrado; cancele/estorne o reembolso antes de cancelar a despesa."
        )
    repo.cancel_despesa(db, despesa_id, motivo, cancelado_em, cancelado_por)
    repo.insert_evento(
        db, despesa_id, "despesa_cancelada",
        f"Despesa cancelada: {despesa['descricao']} - R$ {despesa['valor_total']}."
        + (f" Motivo: {motivo}." if motivo else ""),
        cancelado_em, usuario_id=cancelado_por,
    )


# --- Reembolsos ---------------------------------------------------------

def get_saldo_desembolsante(db, desembolsante_id):
    despesas_pendentes = repo.list_despesas_pendentes_por_desembolsante(db, desembolsante_id)
    total_pendente = sum((to_currency(d["saldo_pendente"]) for d in despesas_pendentes), Decimal("0.00"))
    return {
        "despesas_pendentes": despesas_pendentes,
        "quantidade": len(despesas_pendentes),
        "total_pendente": total_pendente,
    }


def registrar_reembolso(
    db,
    *,
    desembolsante_id,
    data_reembolso,
    criado_em,
    despesa_ids=None,
    valor=None,
    forma_reembolso=None,
    observacoes=None,
    anexo_path=None,
    anexo_nome=None,
    registro_uid=None,
    criado_por=None,
):
    """Registra o reembolso da empresa a um desembolsante.

    Sem despesa_ids: reembolsa integralmente TODAS as despesas pendentes da
    pessoa (uso mais comum: "Rafael - R$ 840,00 a reembolsar" -> um clique).
    Com despesa_ids: reembolsa integralmente so as despesas escolhidas. Em
    ambos os casos, cada alocacao de reembolso e o saldo pendente cheio da
    despesa (reembolso parcial fica disponivel no banco para uso futuro, mas
    esta funcao so grava reembolso integral por despesa, como pedido).
    """
    if registro_uid:
        existing = repo.find_reembolso_by_registro_uid(db, registro_uid)
        if existing:
            return existing

    desembolsante = repo.get_desembolsante(db, desembolsante_id)
    if not desembolsante:
        raise ExpenseServiceError("Pessoa nao encontrada para reembolso.")

    pendentes = repo.list_despesas_pendentes_por_desembolsante(db, desembolsante_id)
    if despesa_ids:
        pendentes = [d for d in pendentes if d["id"] in set(despesa_ids)]
        faltando = set(despesa_ids) - {d["id"] for d in pendentes}
        if faltando:
            raise ExpenseServiceError("Alguma despesa selecionada ja nao tem mais saldo pendente para reembolso.")
    if not pendentes:
        raise ExpenseServiceError(f"{desembolsante['nome']} nao tem despesas pendentes de reembolso.")

    total_selecionado = sum((to_currency(d["saldo_pendente"]) for d in pendentes), Decimal("0.00"))
    if valor is not None and abs(to_currency(valor) - total_selecionado) > ALLOCATION_TOLERANCE:
        raise ExpenseServiceError(
            f"O valor informado (R$ {to_currency(valor)}) nao bate com o total pendente das despesas selecionadas (R$ {total_selecionado})."
        )

    try:
        reembolso_id = repo.insert_reembolso(
            db, desembolsante_id, total_selecionado, data_reembolso, criado_em,
            forma_reembolso=forma_reembolso, observacoes=observacoes,
            anexo_path=anexo_path, anexo_nome=anexo_nome,
            registro_uid=registro_uid, criado_por=criado_por,
        )
    except psycopg2.errors.UniqueViolation:
        db.rollback()
        existing = repo.find_reembolso_by_registro_uid(db, registro_uid)
        if existing:
            return existing
        raise ExpenseServiceError("Este reembolso ja havia sido salvo; o envio repetido foi ignorado.") from None

    for despesa in pendentes:
        repo.insert_reembolso_alocacao(db, reembolso_id, despesa["id"], to_currency(despesa["saldo_pendente"]))
        repo.insert_evento(
            db, despesa["id"], "reembolso_registrado",
            f"Reembolso de R$ {to_currency(despesa['saldo_pendente'])} registrado para {desembolsante['nome']}.",
            criado_em, usuario_id=criado_por,
        )
    return {"id": reembolso_id, "valor": total_selecionado, "despesas": [d["id"] for d in pendentes]}


def cancelar_reembolso(db, reembolso_id, motivo, cancelado_em, cancelado_por=None):
    """Cancela um reembolso registrado por engano. Soft (nunca DELETE): as despesas
    que ele quitava voltam a aparecer como pendentes automaticamente, porque toda
    consulta de saldo ja filtra por status='confirmado'."""
    reembolso = repo.get_reembolso(db, reembolso_id)
    if not reembolso:
        raise ExpenseServiceError("Reembolso nao encontrado.")
    if reembolso["status"] == "cancelado":
        raise ExpenseServiceError("Este reembolso ja esta cancelado.")
    alocacoes = repo.list_reembolso_alocacoes(db, reembolso_id)
    repo.cancel_reembolso(db, reembolso_id, motivo, cancelado_em, cancelado_por)
    for alocacao in alocacoes:
        repo.insert_evento(
            db, alocacao["despesa_id"], "reembolso_cancelado",
            f"Reembolso de R$ {to_currency(alocacao['valor'])} cancelado."
            + (f" Motivo: {motivo}." if motivo else "") + " A despesa voltou a ficar pendente de reembolso.",
            cancelado_em, usuario_id=cancelado_por,
        )


# --- Anexos / duplicidade -----------------------------------------------

def check_duplicate_anexo(db, file_hash, despesa_id=None):
    """Item 20 do pedido: hash identico e o caso rigoroso -- devolve o
    comprovante encontrado para a UI alertar ('Possivel comprovante ja
    lancado'); a decisao final e sempre do usuario, nunca bloqueio automatico."""
    return repo.find_anexo_by_hash(db, file_hash, exclude_despesa_id=despesa_id)


# --- Migracao de projeto_custos ------------------------------------------

def migrate_custo(db, custo, criado_em):
    """Migra um unico projeto_custos para despesas + despesa_alocacoes (+ anexo).

    Idempotente: se ja existe uma despesa com migrado_de_custo_id = custo['id'],
    nao faz nada e devolve essa despesa. Espelha exatamente a migracao em lote
    feita por docs/migrations/20260902_despesas_fase1.sql, disponivel aqui em
    Python para poder ser reexecutada (ex.: novos custos lancados na tela
    antiga) e para ser testada sem depender de uma migracao SQL live.
    """
    if not custo.get("valor") or float(custo["valor"]) <= 0:
        raise ExpenseServiceError("Custo sem valor valido nao pode ser migrado.")

    existing = repo.find_despesa_by_migrado_de_custo(db, custo["id"])
    if existing:
        return existing

    status = "cancelada" if str(custo.get("status") or "").lower() == "cancelado" else "pronta"
    despesa_id = repo.insert_despesa(
        db,
        descricao=custo["descricao"],
        valor_total=to_currency(custo["valor"]),
        desembolsado_por_tipo="EMPRESA",
        criado_em=custo.get("criado_em") or criado_em,
        categoria=custo.get("categoria"),
        data_despesa=custo.get("data_custo"),
        observacoes=custo.get("observacoes"),
        status=status,
        origem="MIGRACAO",
        criado_por=custo.get("usuario_id"),
        migrado_de_custo_id=custo["id"],
    )

    cliente_id = repo.resolve_projeto_cliente(db, custo["projeto_id"])
    repo.insert_alocacao(db, despesa_id, custo["projeto_id"], cliente_id, to_currency(custo["valor"]), criado_em)

    if custo.get("anexo_path"):
        repo.insert_anexo(
            db, despesa_id, custo["anexo_path"], custo.get("anexo_nome") or custo["anexo_path"],
            criado_em, principal=True, criado_por=custo.get("usuario_id"),
        )

    repo.insert_evento(
        db, despesa_id, "despesa_migrada",
        f"Migrado do custo legado #{custo['id']} ({custo['descricao']}).",
        criado_em,
    )
    return repo.get_despesa(db, despesa_id)


def migrate_pending_custos(db, custos, criado_em):
    """Migra uma lista de projeto_custos ainda nao migrados. Retorna quantos migrou."""
    migrated = 0
    for custo in custos:
        if repo.find_despesa_by_migrado_de_custo(db, custo["id"]):
            continue
        migrate_custo(db, custo, criado_em)
        migrated += 1
    return migrated


# --- Lancamento rapido (Financeiro -> Lancamentos) -------------------------

def classificar_despesa_rapida(
    db, despesa_id, *, descricao, valor_total, categoria, data_despesa, observacoes,
    desembolsado_por_tipo, projeto_id, atualizado_em,
    desembolsante_id=None, desembolsante_nome_novo=None, atualizado_por=None,
):
    """Mesma regra de classificar_despesa, mas para o fluxo simplificado de
    Lancamentos: em vez de uma lista de alocacoes, recebe UM projeto e monta
    sozinha a alocacao de 100% do valor para ele (item 4 do redesenho -- o
    usuario nao preenche "divisao entre projetos" quando a despesa inteira e
    de um projeto so). Divisao entre varios projetos continua disponivel na
    tela completa de Despesas via classificar_despesa/set_alocacoes."""
    if not projeto_id:
        raise ExpenseServiceError("Selecione o projeto do lancamento.")
    return classificar_despesa(
        db, despesa_id,
        descricao=descricao, valor_total=valor_total, categoria=categoria,
        data_despesa=data_despesa, observacoes=observacoes,
        desembolsado_por_tipo=desembolsado_por_tipo,
        alocacoes=[{"projeto_id": projeto_id, "valor": valor_total}],
        atualizado_em=atualizado_em,
        desembolsante_id=desembolsante_id, desembolsante_nome_novo=desembolsante_nome_novo,
        atualizado_por=atualizado_por,
    )


# --- Cobrancas (Financeiro -> Cobrancas) -----------------------------------

def criar_cobranca(
    db, *, cliente_id, despesa_ids, data_cobranca, criado_em, observacoes=None, criado_por=None,
):
    """Formaliza a cobranca de um conjunto de despesas 'prontas' de UM cliente
    (item 9/10 do redesenho). Recusa qualquer despesa que nao esteja pronta,
    que nao seja desse cliente ou que ja esteja em outra cobranca ativa --
    tudo verificado ANTES de escrever, no mesmo espirito de
    validate_allocations_sum (uma falha de regra nunca pode deixar escrita
    parcial, porque o redirect de erro nao e status >=400)."""
    if not despesa_ids:
        raise ExpenseServiceError("Selecione ao menos uma despesa para cobrar.")
    despesa_ids = list(dict.fromkeys(despesa_ids))  # remove duplicados, preserva ordem

    elegiveis = {d["id"]: d for d in repo.list_despesas_a_cobrar_do_cliente(db, cliente_id)}
    faltando = [despesa_id for despesa_id in despesa_ids if despesa_id not in elegiveis]
    if faltando:
        raise ExpenseServiceError(
            "Alguma despesa selecionada nao esta mais disponivel para cobranca "
            "(pode ja ter sido cobrada, cancelada ou pertencer a outro cliente)."
        )

    ja_cobradas = repo.find_despesas_com_cobranca_ativa(db, despesa_ids)
    if ja_cobradas:
        raise ExpenseServiceError("Alguma despesa selecionada ja esta em outra cobranca ativa.")

    total = sum((to_currency(elegiveis[despesa_id]["valor_total"]) for despesa_id in despesa_ids), Decimal("0.00"))
    if total <= 0:
        raise ExpenseServiceError("O total da cobranca precisa ser maior que zero.")

    cobranca_id = repo.insert_cobranca(
        db, cliente_id, total, data_cobranca, criado_em,
        observacoes=observacoes, criado_por=criado_por,
    )
    for despesa_id in despesa_ids:
        valor = to_currency(elegiveis[despesa_id]["valor_total"])
        repo.insert_cobranca_item(db, cobranca_id, despesa_id, valor)
        repo.insert_evento(
            db, despesa_id, "despesa_cobrada",
            f"Despesa incluida na cobranca #{cobranca_id} (R$ {valor}).",
            criado_em, usuario_id=criado_por,
        )
    return repo.get_cobranca(db, cobranca_id)


def cancelar_cobranca(db, cobranca_id, motivo, cancelado_em, cancelado_por=None):
    """Cancela uma cobranca por engano. Soft (nunca DELETE): as despesas que ela
    incluia voltam a aparecer como 'a cobrar' automaticamente, porque toda
    consulta de pendencia ja filtra por cobrancas.status='ativa'/itens.status='ativo'."""
    cobranca = repo.get_cobranca(db, cobranca_id)
    if not cobranca:
        raise ExpenseServiceError("Cobranca nao encontrada.")
    if cobranca["status"] == "cancelada":
        raise ExpenseServiceError("Esta cobranca ja esta cancelada.")
    itens = repo.list_cobranca_itens(db, cobranca_id)
    repo.cancel_cobranca_and_itens(db, cobranca_id, motivo, cancelado_em, cancelado_por)
    for item in itens:
        repo.insert_evento(
            db, item["despesa_id"], "despesa_cobranca_cancelada",
            f"Cobranca #{cobranca_id} cancelada."
            + (f" Motivo: {motivo}." if motivo else "") + " A despesa voltou a ficar 'a cobrar'.",
            cancelado_em, usuario_id=cancelado_por,
        )
