import os
import csv
import io
import sqlite3
import unicodedata
from datetime import date, datetime, timedelta
from functools import wraps
from urllib.parse import quote

from flask import Flask, Response, flash, g, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "geo.db")
SECRET_KEY = os.environ.get("GEOGESTAO_SECRET_KEY", "dev-change-this-secret-key")

STATUS_META = {
    "nao iniciado": {"label": "Nao iniciado", "color": "secondary", "tone": "muted"},
    "em andamento": {"label": "Em andamento", "color": "primary", "tone": "blue"},
    "concluido": {"label": "Concluido", "color": "success", "tone": "green"},
    "atencao": {"label": "Atencao", "color": "warning", "tone": "amber"},
    "atrasado": {"label": "Atrasado", "color": "danger", "tone": "red"},
    "aguardando externo": {"label": "Aguardando externo", "color": "purple", "tone": "purple"},
    "retrabalho": {"label": "Retrabalho", "color": "purple", "tone": "purple"},
    "cancelado": {"label": "Cancelado", "color": "dark", "tone": "dark"},
}

ROLE_LABELS = {
    "admin": "Administrador",
    "coordenador": "Coordenador",
    "tecnico": "Tecnico",
    "consulta": "Consulta",
}

PRIORITY_WEIGHT = {"Alta": 0, "Media": 1, "Baixa": 2, "": 3, None: 3}

DEFAULT_STAGES = [
    {
        "nome": "Orcamento",
        "ordem": 1,
        "cor": "secondary",
        "checklist": ["Proposta enviada", "Aceite registrado", "Sinal ou contrato conferido"],
    },
    {
        "nome": "Documentos",
        "ordem": 2,
        "cor": "info",
        "checklist": ["Matricula recebida", "Documentos pessoais", "Documentos do imovel", "Pendencias documentais revisadas"],
    },
    {
        "nome": "Analise",
        "ordem": 3,
        "cor": "primary",
        "checklist": ["Matricula analisada", "Confrontantes conferidos", "Procedimento definido"],
    },
    {
        "nome": "Medicao",
        "ordem": 4,
        "cor": "warning",
        "checklist": ["Campo agendado", "Equipe definida", "Levantamento executado", "Fotos/croqui anexados"],
    },
    {
        "nome": "Processamento",
        "ordem": 5,
        "cor": "primary",
        "checklist": ["Dados baixados", "Processamento concluido", "Coordenadas conferidas", "Arquivos exportados"],
    },
    {
        "nome": "Escritorio",
        "ordem": 6,
        "cor": "dark",
        "checklist": ["Planta iniciada", "Memorial iniciado", "Documentacao revisada", "Conferencia interna"],
    },
    {
        "nome": "Planta",
        "ordem": 7,
        "cor": "primary",
        "checklist": ["Planta PDF", "Planta DWG/DXF", "Camadas conferidas", "Arquivo final validado"],
    },
    {
        "nome": "Documentacao",
        "ordem": 8,
        "cor": "info",
        "checklist": ["Memorial descritivo", "ART/RRT", "Requerimento", "Anexos conferidos"],
    },
    {
        "nome": "Assinaturas",
        "ordem": 9,
        "cor": "warning",
        "checklist": ["Cliente notificado", "Assinaturas coletadas", "Reconhecimentos conferidos"],
    },
    {
        "nome": "Cartorio",
        "ordem": 10,
        "cor": "danger",
        "checklist": ["Protocolo registrado", "Exigencias acompanhadas", "Resposta preparada", "Deferimento conferido"],
    },
    {
        "nome": "Pendencia",
        "ordem": 11,
        "cor": "warning",
        "checklist": ["Pendencia classificada", "Responsavel definido", "Prazo acompanhado", "Resolucao conferida"],
    },
    {
        "nome": "Finalizado",
        "ordem": 12,
        "cor": "success",
        "checklist": ["Entrega ao cliente", "Saldo recebido", "Pasta final organizada", "Backup realizado"],
    },
]

STAGE_ALIASES = {
    "campo": "medicao",
    "medicao": "medicao",
    "finalizacao": "finalizado",
    "finalizado": "finalizado",
}

FUTURE_AUTOMATIONS = [
    "Criar lembrete quando o projeto entrar em Cartorio.",
    "Criar pendencia com prazo quando houver exigencia de cartorio.",
    "Notificar responsavel faltando 5 dias para o prazo.",
    "Notificar responsavel e gestor quando vencer.",
    "Sugerir proxima etapa ao concluir uma etapa.",
    "Marcar como atencao quando o projeto ficar parado por X dias.",
    "Enviar alertas futuros pela WhatsApp Business API.",
]

BACKLOG_FUTURO = [
    "Visao Kanban secundaria por etapa.",
    "Visao Calendario para prazos.",
    "Visao Timeline/Gantt para projetos maiores.",
    "Dashboard de gargalos e tempo medio por etapa.",
    "Registro de tempo em status por etapa.",
    "Campos customizados por tipo de servico.",
    "Modelos de projeto por servico.",
    "Checklist documental por tipo de servico.",
    "Automacao de criacao de estrutura de pastas.",
    "Integracao futura com WhatsApp Business API.",
    "Relatorios PDF para o gestor.",
    "Historico completo de movimentacoes.",
    "Controle de produtividade por responsavel.",
    "Registro de exigencias de cartorio.",
    "Anexos/documentos por projeto.",
    "Permissoes por perfil.",
    "Exportacao para Excel.",
    "Importacao de projetos via planilha.",
    "Campos obrigatorios configuraveis.",
    "Painel de projetos parados.",
]

app = Flask(__name__)
app.config.from_mapping(SECRET_KEY=SECRET_KEY, DATABASE=DATABASE)


def connect_db():
    db = sqlite3.connect(app.config["DATABASE"])
    db.row_factory = sqlite3.Row
    return db


def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = connect_db()
    return db


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()


def query_db(query, args=(), one=False):
    cur = get_db().execute(query, args)
    rows = cur.fetchall()
    cur.close()
    return (rows[0] if rows else None) if one else rows


def execute_db(query, args=()):
    db = get_db()
    cur = db.execute(query, args)
    db.commit()
    last_id = cur.lastrowid
    cur.close()
    return last_id


def table_columns(db, table_name):
    return {row["name"] for row in db.execute(f"PRAGMA table_info({table_name})").fetchall()}


def add_column_if_missing(db, table_name, column_name, definition):
    if column_name not in table_columns(db, table_name):
        db.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")


def first_row(db, query, args=()):
    return db.execute(query, args).fetchone()


def scalar(db, query, args=()):
    row = first_row(db, query, args)
    if row is None:
        return 0
    return row[0]


def init_db():
    os.makedirs(BASE_DIR, exist_ok=True)
    db = connect_db()
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            senha_hash TEXT NOT NULL,
            perfil_acesso TEXT NOT NULL,
            ativo INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            cpf_cnpj TEXT,
            telefone TEXT,
            email TEXT,
            endereco TEXT,
            observacoes TEXT
        );

        CREATE TABLE IF NOT EXISTS cartorios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            cidade TEXT,
            uf TEXT,
            contato TEXT,
            observacoes TEXT
        );

        CREATE TABLE IF NOT EXISTS etapas_modelo (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            ordem INTEGER NOT NULL,
            cor_padrao TEXT NOT NULL,
            ativa INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS projetos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT NOT NULL,
            nome TEXT NOT NULL,
            proprietario TEXT,
            cliente_id INTEGER,
            cidade TEXT,
            uf TEXT,
            cartorio_id INTEGER,
            tipo_servico TEXT,
            prioridade TEXT,
            status TEXT,
            etapa_atual_id INTEGER,
            prazo_critico TEXT,
            responsavel_geral_id INTEGER,
            caminho_pasta TEXT,
            observacoes TEXT,
            criado_em TEXT,
            atualizado_em TEXT,
            FOREIGN KEY(cliente_id) REFERENCES clientes(id),
            FOREIGN KEY(cartorio_id) REFERENCES cartorios(id),
            FOREIGN KEY(responsavel_geral_id) REFERENCES usuarios(id)
        );

        CREATE TABLE IF NOT EXISTS projeto_etapas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            projeto_id INTEGER NOT NULL,
            etapa_modelo_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            responsavel_id INTEGER,
            data_inicio TEXT,
            data_fim TEXT,
            prazo TEXT,
            progresso INTEGER DEFAULT 0,
            observacoes TEXT,
            FOREIGN KEY(projeto_id) REFERENCES projetos(id),
            FOREIGN KEY(etapa_modelo_id) REFERENCES etapas_modelo(id),
            FOREIGN KEY(responsavel_id) REFERENCES usuarios(id)
        );

        CREATE TABLE IF NOT EXISTS tarefas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            projeto_id INTEGER NOT NULL,
            projeto_etapa_id INTEGER,
            titulo TEXT NOT NULL,
            descricao TEXT,
            responsavel_id INTEGER,
            prioridade TEXT,
            status TEXT,
            prazo TEXT,
            criado_em TEXT,
            FOREIGN KEY(projeto_id) REFERENCES projetos(id),
            FOREIGN KEY(projeto_etapa_id) REFERENCES projeto_etapas(id),
            FOREIGN KEY(responsavel_id) REFERENCES usuarios(id)
        );

        CREATE TABLE IF NOT EXISTS checklist_itens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            projeto_etapa_id INTEGER,
            titulo TEXT NOT NULL,
            concluido INTEGER DEFAULT 0,
            concluido_por INTEGER,
            concluido_em TEXT,
            FOREIGN KEY(projeto_etapa_id) REFERENCES projeto_etapas(id),
            FOREIGN KEY(concluido_por) REFERENCES usuarios(id)
        );

        CREATE TABLE IF NOT EXISTS eventos_historico (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            projeto_id INTEGER,
            usuario_id INTEGER,
            tipo_evento TEXT,
            descricao TEXT,
            criado_em TEXT,
            FOREIGN KEY(projeto_id) REFERENCES projetos(id),
            FOREIGN KEY(usuario_id) REFERENCES usuarios(id)
        );

        CREATE TABLE IF NOT EXISTS exigencias_cartorio (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            projeto_id INTEGER NOT NULL,
            cartorio_id INTEGER,
            data_recebimento TEXT,
            prazo_resposta TEXT,
            descricao TEXT NOT NULL,
            status TEXT NOT NULL,
            responsavel_id INTEGER,
            criado_em TEXT,
            atualizado_em TEXT,
            FOREIGN KEY(projeto_id) REFERENCES projetos(id),
            FOREIGN KEY(cartorio_id) REFERENCES cartorios(id),
            FOREIGN KEY(responsavel_id) REFERENCES usuarios(id)
        );

        CREATE TABLE IF NOT EXISTS apontamentos_tempo (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            projeto_id INTEGER NOT NULL,
            etapa_id INTEGER,
            tarefa_id INTEGER,
            usuario_id INTEGER,
            inicio TEXT,
            fim TEXT,
            duracao_minutos INTEGER NOT NULL,
            tipo_tempo TEXT,
            observacoes TEXT,
            criado_em TEXT,
            FOREIGN KEY(projeto_id) REFERENCES projetos(id),
            FOREIGN KEY(etapa_id) REFERENCES projeto_etapas(id),
            FOREIGN KEY(tarefa_id) REFERENCES tarefas(id),
            FOREIGN KEY(usuario_id) REFERENCES usuarios(id)
        );

        CREATE TABLE IF NOT EXISTS notificacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER,
            projeto_id INTEGER,
            tipo TEXT,
            mensagem TEXT,
            canal TEXT,
            status TEXT,
            enviado_em TEXT,
            criado_em TEXT,
            FOREIGN KEY(usuario_id) REFERENCES usuarios(id),
            FOREIGN KEY(projeto_id) REFERENCES projetos(id)
        );

        CREATE TABLE IF NOT EXISTS pendencias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            projeto_id INTEGER NOT NULL,
            etapa_id INTEGER,
            descricao TEXT NOT NULL,
            origem TEXT,
            responsavel_id INTEGER,
            prazo TEXT,
            status TEXT NOT NULL DEFAULT 'aberta',
            data_abertura TEXT,
            data_resolucao TEXT,
            criado_em TEXT,
            atualizado_em TEXT,
            FOREIGN KEY(projeto_id) REFERENCES projetos(id),
            FOREIGN KEY(etapa_id) REFERENCES projeto_etapas(id),
            FOREIGN KEY(responsavel_id) REFERENCES usuarios(id)
        );

        CREATE TABLE IF NOT EXISTS movimentacoes_etapa (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            projeto_id INTEGER NOT NULL,
            etapa_anterior_id INTEGER,
            etapa_nova_id INTEGER,
            etapa_anterior TEXT,
            etapa_nova TEXT,
            motivo TEXT,
            observacao TEXT,
            responsavel_id INTEGER,
            usuario_id INTEGER,
            criado_em TEXT,
            FOREIGN KEY(projeto_id) REFERENCES projetos(id),
            FOREIGN KEY(etapa_anterior_id) REFERENCES projeto_etapas(id),
            FOREIGN KEY(etapa_nova_id) REFERENCES projeto_etapas(id),
            FOREIGN KEY(responsavel_id) REFERENCES usuarios(id),
            FOREIGN KEY(usuario_id) REFERENCES usuarios(id)
        );
        """
    )

    add_column_if_missing(db, "usuarios", "cargo", "TEXT")
    add_column_if_missing(db, "projetos", "proprietario", "TEXT")
    add_column_if_missing(db, "projetos", "etapa_atual_id", "INTEGER")
    add_column_if_missing(db, "projetos", "observacoes", "TEXT")
    add_column_if_missing(db, "projetos", "atualizado_em", "TEXT")
    add_column_if_missing(db, "projetos", "valor", "REAL")
    add_column_if_missing(db, "projeto_etapas", "subetapa_ativa", "TEXT")
    add_column_if_missing(db, "projeto_etapas", "atraso_origem", "TEXT")
    add_column_if_missing(db, "tarefas", "data_inicio", "TEXT")
    add_column_if_missing(db, "tarefas", "concluido_em", "TEXT")
    add_column_if_missing(db, "tarefas", "comentarios", "TEXT")
    seed_initial_data(db)
    normalize_stage_models(db)
    ensure_project_structure(db)
    db.commit()
    db.close()


def seed_initial_data(db):
    now = datetime.now().isoformat(timespec="seconds")
    if scalar(db, "SELECT COUNT(*) FROM usuarios") == 0:
        users = [
            ("Administrador", "admin@geogestao.local", "admin123", "admin", "Gestor"),
            ("Marcos", "marcos@geogestao.local", "coord123", "coordenador", "Coordenador"),
            ("Rafael", "rafael@geogestao.local", "tecnico123", "tecnico", "Campo"),
            ("Ana", "ana@geogestao.local", "tecnico123", "tecnico", "Documentacao"),
            ("Joao", "joao@geogestao.local", "tecnico123", "tecnico", "Topografia"),
            ("Pedro", "pedro@geogestao.local", "tecnico123", "tecnico", "Desenho"),
        ]
        db.executemany(
            "INSERT INTO usuarios (nome, email, senha_hash, perfil_acesso, cargo) VALUES (?, ?, ?, ?, ?)",
            [(name, email, generate_password_hash(password), role, cargo) for name, email, password, role, cargo in users],
        )

    if scalar(db, "SELECT COUNT(*) FROM clientes") == 0:
        db.executemany(
            "INSERT INTO clientes (nome, cpf_cnpj, telefone, email, endereco, observacoes) VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("Fazenda Boa Vista", "12.345.678/0001-90", "(11) 99999-0001", "contato@boavista.com", "Estrada Rural, km 12", ""),
                ("Sitio Sao Jose", "23.456.789/0001-80", "(11) 99999-0002", "contato@sitiosaojose.com", "Rua do Campo, 305", ""),
                ("Lote Urbano Centro", "34.567.890/0001-70", "(11) 99999-0003", "contato@loteurbano.com", "Avenida Central, 45", ""),
            ],
        )

    if scalar(db, "SELECT COUNT(*) FROM cartorios") == 0:
        db.executemany(
            "INSERT INTO cartorios (nome, cidade, uf, contato, observacoes) VALUES (?, ?, ?, ?, ?)",
            [
                ("Cartorio Central", "Sao Paulo", "SP", "central@cartorio.com", ""),
                ("Cartorio Norte", "Campinas", "SP", "norte@cartorio.com", ""),
                ("Prefeitura Municipal", "Jundiai", "SP", "obras@jundiai.sp.gov.br", "Orgao externo"),
            ],
        )

    if scalar(db, "SELECT COUNT(*) FROM etapas_modelo") == 0:
        db.executemany(
            "INSERT INTO etapas_modelo (nome, ordem, cor_padrao, ativa) VALUES (?, ?, ?, 1)",
            [(stage["nome"], stage["ordem"], stage["cor"]) for stage in DEFAULT_STAGES],
        )
    else:
        for stage in DEFAULT_STAGES:
            exists = first_row(db, "SELECT id FROM etapas_modelo WHERE lower(nome) = lower(?)", [stage["nome"]])
            if not exists:
                db.execute(
                    "INSERT INTO etapas_modelo (nome, ordem, cor_padrao, ativa) VALUES (?, ?, ?, 1)",
                    (stage["nome"], stage["ordem"], stage["cor"]),
                )

    if scalar(db, "SELECT COUNT(*) FROM projetos") == 0:
        users = {row["nome"]: row["id"] for row in db.execute("SELECT id, nome FROM usuarios").fetchall()}
        clients = {row["nome"]: row["id"] for row in db.execute("SELECT id, nome FROM clientes").fetchall()}
        registries = {row["nome"]: row["id"] for row in db.execute("SELECT id, nome FROM cartorios").fetchall()}
        projects = [
            ("GG-001", "Fazenda Boa Vista", "Fazenda Boa Vista", "Campinas", "SP", "Cartorio Norte", "Regularizacao Rural", "Alta", "Em andamento", 9, "Rafael", r"C:\Projetos\BoaVista"),
            ("GG-002", "Sitio Sao Jose", "Sitio Sao Jose", "Jundiai", "SP", "Prefeitura Municipal", "Parcelamento", "Media", "Atencao", -2, "Ana", r"C:\Projetos\SaoJose"),
            ("GG-003", "Lote Urbano Centro", "Lote Urbano Centro", "Sao Paulo", "SP", "Cartorio Central", "Desmembramento", "Alta", "Aguardando externo", 6, "Marcos", r"C:\Projetos\LoteCentro"),
        ]
        for codigo, nome, cliente, cidade, uf, cartorio, tipo, prioridade, status, days, responsavel, pasta in projects:
            project_id = db.execute(
                """
                INSERT INTO projetos
                    (codigo, nome, proprietario, cliente_id, cidade, uf, cartorio_id, tipo_servico, prioridade, status, prazo_critico, responsavel_geral_id, caminho_pasta, criado_em, atualizado_em)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    codigo,
                    nome,
                    cliente,
                    clients.get(cliente),
                    cidade,
                    uf,
                    registries.get(cartorio),
                    tipo,
                    prioridade,
                    status,
                    (date.today() + timedelta(days=days)).isoformat(),
                    users.get(responsavel),
                    pasta,
                    now,
                    now,
                ),
            ).lastrowid
            create_stage_rows(db, project_id, users.get(responsavel), (date.today() + timedelta(days=days)).isoformat())
            db.execute(
                "INSERT INTO eventos_historico (projeto_id, usuario_id, tipo_evento, descricao, criado_em) VALUES (?, ?, ?, ?, ?)",
                (project_id, users.get("Administrador"), "projeto_criado", "Projeto de demonstracao criado.", now),
            )


def default_checklist_for_stage(stage_name):
    normalized = (stage_name or "").lower()
    for stage in DEFAULT_STAGES:
        if stage["nome"].lower() == normalized:
            return stage["checklist"]
    return ["Planejar etapa", "Executar etapa", "Conferir entrega"]


def normalize_text(value):
    value = unicodedata.normalize("NFKD", value or "")
    value = value.encode("ascii", "ignore").decode("ascii").lower()
    return "".join(ch for ch in value if ch.isalnum())


def stage_key(value):
    key = normalize_text(value)
    return STAGE_ALIASES.get(key, key)


def normalize_stage_models(db):
    canonical = {stage_key(stage["nome"]): stage for stage in DEFAULT_STAGES}
    rows = db.execute("SELECT * FROM etapas_modelo ORDER BY id").fetchall()
    used_ids = set()
    for key, stage in canonical.items():
        matches = [row for row in rows if stage_key(row["nome"]) == key]
        if matches:
            keep = matches[0]
            used_ids.add(keep["id"])
            db.execute(
                "UPDATE etapas_modelo SET nome = ?, ordem = ?, cor_padrao = ?, ativa = 1 WHERE id = ?",
                (stage["nome"], stage["ordem"], stage["cor"], keep["id"]),
            )
            for duplicate in matches[1:]:
                db.execute("UPDATE etapas_modelo SET ativa = 0 WHERE id = ?", (duplicate["id"],))
        else:
            db.execute(
                "INSERT INTO etapas_modelo (nome, ordem, cor_padrao, ativa) VALUES (?, ?, ?, 1)",
                (stage["nome"], stage["ordem"], stage["cor"]),
            )

    for row in rows:
        if stage_key(row["nome"]) not in canonical and row["id"] not in used_ids:
            db.execute("UPDATE etapas_modelo SET ativa = 0 WHERE id = ?", (row["id"],))


def create_stage_rows(db, project_id, responsavel_id, prazo_critico):
    stages = db.execute("SELECT * FROM etapas_modelo WHERE ativa = 1 ORDER BY ordem").fetchall()
    current_stage_id = None
    for index, stage in enumerate(stages):
        status = "em andamento" if index == 0 else "nao iniciado"
        prazo = prazo_critico or (date.today() + timedelta(days=7 + index * 2)).isoformat()
        stage_id = db.execute(
            """
            INSERT INTO projeto_etapas
                (projeto_id, etapa_modelo_id, status, responsavel_id, prazo, progresso, subetapa_ativa)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (project_id, stage["id"], status, responsavel_id, prazo, 10 if index == 0 else 0, default_checklist_for_stage(stage["nome"])[0]),
        ).lastrowid
        for item in default_checklist_for_stage(stage["nome"]):
            db.execute("INSERT INTO checklist_itens (projeto_etapa_id, titulo) VALUES (?, ?)", (stage_id, item))
        if index == 0:
            current_stage_id = stage_id
    if current_stage_id:
        db.execute("UPDATE projetos SET etapa_atual_id = ?, atualizado_em = ? WHERE id = ?", (current_stage_id, datetime.now().isoformat(timespec="seconds"), project_id))


def infer_current_stage_id_db(db, project_id):
    row = first_row(
        db,
        """
        SELECT pe.id
        FROM projeto_etapas pe
        JOIN etapas_modelo em ON em.id = pe.etapa_modelo_id
        WHERE pe.projeto_id = ?
          AND em.ativa = 1
          AND lower(pe.status) IN ('em andamento', 'atencao', 'atrasado', 'aguardando externo', 'retrabalho')
        ORDER BY
          CASE lower(pe.status)
            WHEN 'atrasado' THEN 0
            WHEN 'retrabalho' THEN 1
            WHEN 'atencao' THEN 2
            WHEN 'em andamento' THEN 3
            WHEN 'aguardando externo' THEN 4
            ELSE 5
          END,
          em.ordem
        LIMIT 1
        """,
        (project_id,),
    )
    if row:
        return row["id"]
    row = first_row(
        db,
        """
        SELECT pe.id
        FROM projeto_etapas pe
        JOIN etapas_modelo em ON em.id = pe.etapa_modelo_id
        WHERE pe.projeto_id = ?
          AND em.ativa = 1
          AND lower(pe.status) NOT IN ('concluido', 'cancelado')
        ORDER BY em.ordem
        LIMIT 1
        """,
        (project_id,),
    )
    if row:
        return row["id"]
    row = first_row(
        db,
        """
        SELECT pe.id
        FROM projeto_etapas pe
        JOIN etapas_modelo em ON em.id = pe.etapa_modelo_id
        WHERE pe.projeto_id = ? AND em.ativa = 1
        ORDER BY em.ordem DESC
        LIMIT 1
        """,
        (project_id,),
    )
    return row["id"] if row else None


def ensure_project_structure(db):
    projects = db.execute("SELECT * FROM projetos").fetchall()
    stages = db.execute("SELECT * FROM etapas_modelo WHERE ativa = 1 ORDER BY ordem").fetchall()
    for project in projects:
        for stage in stages:
            existing_stage = first_row(
                db,
                "SELECT * FROM projeto_etapas WHERE projeto_id = ? AND etapa_modelo_id = ?",
                (project["id"], stage["id"]),
            )
            if existing_stage is None:
                due = project["prazo_critico"] or (date.today() + timedelta(days=stage["ordem"] * 2)).isoformat()
                stage_id = db.execute(
                    """
                    INSERT INTO projeto_etapas
                        (projeto_id, etapa_modelo_id, status, responsavel_id, prazo, progresso, subetapa_ativa)
                    VALUES (?, ?, ?, ?, ?, 0, ?)
                    """,
                    (project["id"], stage["id"], "nao iniciado", project["responsavel_geral_id"], due, default_checklist_for_stage(stage["nome"])[0]),
                ).lastrowid
            else:
                stage_id = existing_stage["id"]
                if "subetapa_ativa" in existing_stage.keys() and not existing_stage["subetapa_ativa"]:
                    db.execute("UPDATE projeto_etapas SET subetapa_ativa = ? WHERE id = ?", (default_checklist_for_stage(stage["nome"])[0], stage_id))

            if scalar(db, "SELECT COUNT(*) FROM checklist_itens WHERE projeto_etapa_id = ?", (stage_id,)) == 0:
                for item in default_checklist_for_stage(stage["nome"]):
                    db.execute("INSERT INTO checklist_itens (projeto_etapa_id, titulo) VALUES (?, ?)", (stage_id, item))

        current_valid = None
        if project["etapa_atual_id"]:
            current_valid = first_row(
                db,
                """
                SELECT pe.id
                FROM projeto_etapas pe
                JOIN etapas_modelo em ON em.id = pe.etapa_modelo_id
                WHERE pe.id = ? AND pe.projeto_id = ? AND em.ativa = 1
                """,
                (project["etapa_atual_id"], project["id"]),
            )
        current_stage_id = project["etapa_atual_id"] if current_valid else infer_current_stage_id_db(db, project["id"])
        if current_stage_id != project["etapa_atual_id"]:
            db.execute("UPDATE projetos SET etapa_atual_id = ?, atualizado_em = COALESCE(atualizado_em, criado_em) WHERE id = ?", (current_stage_id, project["id"]))
        if not project["proprietario"]:
            client = first_row(db, "SELECT nome FROM clientes WHERE id = ?", (project["cliente_id"],))
            db.execute(
                "UPDATE projetos SET proprietario = ?, atualizado_em = COALESCE(atualizado_em, criado_em) WHERE id = ?",
                ((client["nome"] if client else project["nome"]), project["id"]),
            )
        if not project["atualizado_em"]:
            db.execute("UPDATE projetos SET atualizado_em = COALESCE(criado_em, ?) WHERE id = ?", (datetime.now().isoformat(timespec="seconds"), project["id"]))

        if scalar(db, "SELECT COUNT(*) FROM tarefas WHERE projeto_id = ?", (project["id"],)) == 0:
            active_stage = first_row(
                db,
                """
                SELECT pe.*, em.nome AS etapa_nome
                FROM projeto_etapas pe
                JOIN etapas_modelo em ON em.id = pe.etapa_modelo_id
                WHERE pe.projeto_id = ? AND lower(pe.status) != 'concluido' AND em.ativa = 1
                ORDER BY em.ordem
                """,
                (project["id"],),
            )
            if active_stage:
                db.execute(
                    """
                    INSERT INTO tarefas
                        (projeto_id, projeto_etapa_id, titulo, descricao, responsavel_id, prioridade, status, prazo, criado_em)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        project["id"],
                        active_stage["id"],
                        f"Avancar etapa {active_stage['etapa_nome']}",
                        "Tarefa inicial gerada para o prototipo.",
                        active_stage["responsavel_id"] or project["responsavel_geral_id"],
                        project["prioridade"] or "Media",
                        "em andamento",
                        active_stage["prazo"],
                        datetime.now().isoformat(timespec="seconds"),
                    ),
                )

        if scalar(db, "SELECT COUNT(*) FROM eventos_historico WHERE projeto_id = ?", (project["id"],)) == 0:
            db.execute(
                "INSERT INTO eventos_historico (projeto_id, usuario_id, tipo_evento, descricao, criado_em) VALUES (?, NULL, ?, ?, ?)",
                (project["id"], "importacao", "Projeto importado para o prototipo.", datetime.now().isoformat(timespec="seconds")),
            )

    if scalar(db, "SELECT COUNT(*) FROM exigencias_cartorio") == 0:
        project = first_row(db, "SELECT * FROM projetos ORDER BY id DESC LIMIT 1")
        if project:
            db.execute(
                """
                INSERT INTO exigencias_cartorio
                    (projeto_id, cartorio_id, data_recebimento, prazo_resposta, descricao, status, responsavel_id, criado_em, atualizado_em)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project["id"],
                    project["cartorio_id"],
                    date.today().isoformat(),
                    (date.today() + timedelta(days=5)).isoformat(),
                    "Conferir memorial e anexar declaracao complementar.",
                    "em andamento",
                    project["responsavel_geral_id"],
                    datetime.now().isoformat(timespec="seconds"),
                    datetime.now().isoformat(timespec="seconds"),
                ),
            )

    if scalar(db, "SELECT COUNT(*) FROM apontamentos_tempo") == 0:
        stage = first_row(db, "SELECT * FROM projeto_etapas ORDER BY id LIMIT 1")
        if stage:
            db.execute(
                """
                INSERT INTO apontamentos_tempo
                    (projeto_id, etapa_id, usuario_id, duracao_minutos, tipo_tempo, observacoes, criado_em)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (stage["projeto_id"], stage["id"], stage["responsavel_id"], 95, "execucao", "Apontamento de exemplo.", datetime.now().isoformat(timespec="seconds")),
            )


def refresh_due_statuses():
    today = date.today().isoformat()
    execute_db(
        """
        UPDATE projeto_etapas
        SET status = 'atrasado', atraso_origem = COALESCE(atraso_origem, 'interno')
        WHERE prazo IS NOT NULL
          AND prazo != ''
          AND prazo < ?
          AND id IN (SELECT etapa_atual_id FROM projetos WHERE etapa_atual_id IS NOT NULL)
          AND lower(status) NOT IN ('concluido', 'cancelado', 'aguardando externo')
        """,
        (today,),
    )
    execute_db(
        """
        UPDATE tarefas
        SET status = 'atrasado'
        WHERE prazo IS NOT NULL
          AND prazo != ''
          AND prazo < ?
          AND lower(status) NOT IN ('concluido', 'cancelado', 'aguardando externo')
        """,
        (today,),
    )
    execute_db(
        """
        UPDATE exigencias_cartorio
        SET status = 'atrasado', atualizado_em = ?
        WHERE prazo_resposta IS NOT NULL
          AND prazo_resposta != ''
          AND prazo_resposta < ?
          AND lower(status) NOT IN ('concluido', 'cancelado')
        """,
        (datetime.now().isoformat(timespec="seconds"), today),
    )


def record_event(project_id, event_type, description, user_id=None):
    if user_id is None:
        user = getattr(g, "user", None)
        user_id = user["id"] if user else None
    execute_db(
        "INSERT INTO eventos_historico (projeto_id, usuario_id, tipo_evento, descricao, criado_em) VALUES (?, ?, ?, ?, ?)",
        (project_id, user_id, event_type, description, datetime.now().isoformat(timespec="seconds")),
    )


def update_stage_progress(stage_id):
    counts = query_db(
        """
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN concluido = 1 THEN 1 ELSE 0 END) AS done
        FROM checklist_itens
        WHERE projeto_etapa_id = ?
        """,
        (stage_id,),
        one=True,
    )
    total = counts["total"] or 0
    done = counts["done"] or 0
    progress = int((done / total) * 100) if total else 0
    execute_db("UPDATE projeto_etapas SET progresso = ? WHERE id = ?", (progress, stage_id))
    return progress


def load_stage_rows(project_id):
    return query_db(
        """
        SELECT
            pe.*,
            em.nome AS etapa_nome,
            em.ordem AS etapa_ordem,
            u.nome AS responsavel_nome,
            (SELECT COUNT(*) FROM checklist_itens ci WHERE ci.projeto_etapa_id = pe.id) AS checklist_total,
            (SELECT COUNT(*) FROM checklist_itens ci WHERE ci.projeto_etapa_id = pe.id AND ci.concluido = 1) AS checklist_done,
            (SELECT ci.titulo FROM checklist_itens ci WHERE ci.projeto_etapa_id = pe.id AND ci.concluido = 0 ORDER BY ci.id LIMIT 1) AS proximo_checklist,
            (
                SELECT t.titulo
                FROM tarefas t
                WHERE t.projeto_etapa_id = pe.id AND lower(COALESCE(t.status, '')) != 'concluido'
                ORDER BY
                    CASE t.prioridade WHEN 'Alta' THEN 0 WHEN 'Media' THEN 1 WHEN 'Baixa' THEN 2 ELSE 3 END,
                    COALESCE(t.prazo, '9999-12-31')
                LIMIT 1
            ) AS tarefa_ativa
        FROM projeto_etapas pe
        JOIN etapas_modelo em ON em.id = pe.etapa_modelo_id
        LEFT JOIN usuarios u ON u.id = pe.responsavel_id
        WHERE pe.projeto_id = ?
          AND em.ativa = 1
        ORDER BY em.ordem
        """,
        (project_id,),
    )


def can_manage():
    user = getattr(g, "user", None)
    return bool(user and user["perfil_acesso"] in ("admin", "coordenador"))


def can_admin():
    user = getattr(g, "user", None)
    return bool(user and user["perfil_acesso"] == "admin")


def login_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        g.user = query_db("SELECT * FROM usuarios WHERE id = ? AND ativo = 1", [session["user_id"]], one=True)
        if g.user is None:
            session.clear()
            return redirect(url_for("login"))
        return view(**kwargs)

    return wrapped_view


@app.before_request
def load_logged_user():
    g.user = None
    if "user_id" in session:
        db = get_db()
        g.user = db.execute("SELECT * FROM usuarios WHERE id = ? AND ativo = 1", (session["user_id"],)).fetchone()


def format_date(value):
    if not value:
        return "-"
    try:
        return datetime.fromisoformat(value).strftime("%d/%m/%Y")
    except ValueError:
        return value


def format_datetime(value):
    if not value:
        return "-"
    try:
        return datetime.fromisoformat(value).strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return value


def is_overdue(value, status=None):
    if not value or str(status or "").lower() in ("concluido", "cancelado", "aguardando externo"):
        return False
    try:
        return datetime.fromisoformat(value).date() < date.today()
    except ValueError:
        return False


def file_url(path):
    if not path:
        return "#"
    normalized = path.replace("\\", "/")
    if normalized.startswith("//"):
        return "file:" + quote(normalized)
    return "file:///" + quote(normalized)


def minutes_to_hours(minutes):
    minutes = int(minutes or 0)
    hours, mins = divmod(minutes, 60)
    return f"{hours}h{mins:02d}"


def format_currency(value):
    if value is None:
        return "-"
    try:
        v = float(value)
        return f"R$ {v:_.2f}".replace(".", ",").replace("_", ".")
    except (ValueError, TypeError):
        return "-"


@app.context_processor
def utility_processor():
    return {
        "status_meta": STATUS_META,
        "status_options": list(STATUS_META.keys()),
        "role_labels": ROLE_LABELS,
        "format_date": format_date,
        "format_datetime": format_datetime,
        "is_overdue": is_overdue,
        "file_url": file_url,
        "minutes_to_hours": minutes_to_hours,
        "format_currency": format_currency,
        "can_manage": can_manage,
        "can_admin": can_admin,
        "today_iso": date.today().isoformat(),
    }


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        senha = request.form["senha"]
        usuario = query_db("SELECT * FROM usuarios WHERE lower(email) = ? AND ativo = 1", [email], one=True)
        if usuario and check_password_hash(usuario["senha_hash"], senha):
            session.clear()
            session["user_id"] = usuario["id"]
            return redirect(url_for("dashboard"))
        flash("E-mail ou senha invalidos.", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def dashboard():
    refresh_due_statuses()
    today = date.today()
    in_7 = (today + timedelta(days=7)).isoformat()
    today_iso = today.isoformat()

    total_projects = query_db("SELECT COUNT(*) AS count FROM projetos", one=True)["count"]
    active_projects = query_db(
        "SELECT COUNT(*) AS count FROM projetos WHERE lower(COALESCE(status, '')) NOT IN ('concluido', 'cancelado')",
        one=True,
    )["count"]
    overdue = query_db(
        "SELECT COUNT(*) AS count FROM projeto_etapas WHERE lower(status) = 'atrasado' AND id IN (SELECT etapa_atual_id FROM projetos WHERE etapa_atual_id IS NOT NULL)",
        one=True,
    )["count"]
    waiting_external = query_db(
        "SELECT COUNT(*) AS count FROM projeto_etapas WHERE lower(status) = 'aguardando externo' AND id IN (SELECT etapa_atual_id FROM projetos WHERE etapa_atual_id IS NOT NULL)",
        one=True,
    )["count"]
    due_soon_count = query_db(
        """
        SELECT COUNT(*) AS count
        FROM projeto_etapas
        WHERE prazo BETWEEN ? AND ?
          AND id IN (SELECT etapa_atual_id FROM projetos WHERE etapa_atual_id IS NOT NULL)
          AND lower(status) NOT IN ('concluido', 'cancelado')
        """,
        (today_iso, in_7),
        one=True,
    )["count"]
    projects_recent = query_db(
        """
        SELECT p.*, c.nome AS cliente_nome, u.nome AS responsavel_nome
        FROM projetos p
        LEFT JOIN clientes c ON c.id = p.cliente_id
        LEFT JOIN usuarios u ON u.id = p.responsavel_geral_id
        ORDER BY p.criado_em DESC, p.id DESC
        LIMIT 6
        """
    )
    critical_alerts = query_db(
        """
        SELECT p.id AS projeto_id, p.nome AS projeto_nome, em.nome AS etapa_nome, pe.status, pe.prazo, u.nome AS responsavel_nome
        FROM projeto_etapas pe
        JOIN projetos p ON p.id = pe.projeto_id
        JOIN etapas_modelo em ON em.id = pe.etapa_modelo_id
        LEFT JOIN usuarios u ON u.id = pe.responsavel_id
        WHERE em.ativa = 1
          AND pe.id IN (SELECT etapa_atual_id FROM projetos WHERE etapa_atual_id IS NOT NULL)
          AND (
              lower(pe.status) = 'atrasado'
              OR (pe.prazo BETWEEN ? AND ? AND lower(pe.status) NOT IN ('concluido', 'cancelado'))
          )
        ORDER BY pe.prazo
        LIMIT 10
        """,
        (today_iso, in_7),
    )
    bottlenecks = query_db(
        """
        SELECT em.nome AS etapa_nome, COUNT(pe.id) AS total
        FROM projeto_etapas pe
        JOIN etapas_modelo em ON em.id = pe.etapa_modelo_id
        WHERE lower(pe.status) NOT IN ('concluido', 'cancelado')
          AND em.ativa = 1
          AND pe.id IN (SELECT etapa_atual_id FROM projetos WHERE etapa_atual_id IS NOT NULL)
        GROUP BY em.id, em.nome
        ORDER BY total DESC, em.ordem
        LIMIT 8
        """
    )
    total_bottlenecks = max([row["total"] for row in bottlenecks] or [1])
    exigencias = query_db(
        """
        SELECT e.*, p.nome AS projeto_nome, c.nome AS cartorio_nome, u.nome AS responsavel_nome
        FROM exigencias_cartorio e
        JOIN projetos p ON p.id = e.projeto_id
        LEFT JOIN cartorios c ON c.id = e.cartorio_id
        LEFT JOIN usuarios u ON u.id = e.responsavel_id
        WHERE lower(e.status) NOT IN ('concluido', 'cancelado')
        ORDER BY e.prazo_resposta
        LIMIT 6
        """
    )
    return render_template(
        "dashboard.html",
        total_projects=total_projects,
        active_projects=active_projects,
        overdue=overdue,
        waiting_external=waiting_external,
        due_soon_count=due_soon_count,
        projects_recent=projects_recent,
        critical_alerts=critical_alerts,
        bottlenecks=bottlenecks,
        total_bottlenecks=total_bottlenecks,
        exigencias=exigencias,
    )


@app.route("/projects")
@login_required
def projects():
    refresh_due_statuses()
    filters = request.args.to_dict()
    sql_filters = []
    params = []
    q = filters.get("q", "").strip()
    if q:
        sql_filters.append("(p.nome LIKE ? OR p.codigo LIKE ? OR p.proprietario LIKE ? OR c.nome LIKE ? OR ct.nome LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%"])
    if filters.get("cidade"):
        sql_filters.append("p.cidade LIKE ?")
        params.append(f"%{filters['cidade']}%")
    if filters.get("cliente_id"):
        sql_filters.append("p.cliente_id = ?")
        params.append(filters["cliente_id"])
    if filters.get("cartorio_id"):
        sql_filters.append("p.cartorio_id = ?")
        params.append(filters["cartorio_id"])
    if filters.get("responsavel_id"):
        sql_filters.append(
            """
            (
                p.responsavel_geral_id = ?
                OR EXISTS (
                    SELECT 1 FROM projeto_etapas pe2
                    WHERE pe2.id = p.etapa_atual_id AND pe2.responsavel_id = ?
                )
            )
            """
        )
        params.extend([filters["responsavel_id"], filters["responsavel_id"]])
    if filters.get("status"):
        sql_filters.append(
            "(lower(p.status) = ? OR EXISTS (SELECT 1 FROM projeto_etapas pe3 WHERE pe3.projeto_id = p.id AND lower(pe3.status) = ?))"
        )
        params.extend([filters["status"], filters["status"]])
    if filters.get("prioridade"):
        sql_filters.append("p.prioridade = ?")
        params.append(filters["prioridade"])
    if filters.get("tipo_servico"):
        sql_filters.append("p.tipo_servico LIKE ?")
        params.append(f"%{filters['tipo_servico']}%")
    if filters.get("etapa_id"):
        sql_filters.append(
            """
            EXISTS (
                SELECT 1
                FROM projeto_etapas pe4
                WHERE pe4.projeto_id = p.id
                  AND pe4.etapa_modelo_id = ?
                  AND pe4.id = p.etapa_atual_id
                  AND lower(pe4.status) NOT IN ('concluido', 'cancelado')
            )
            """
        )
        params.append(filters["etapa_id"])
    if filters.get("pendencia") == "aberta":
        sql_filters.append("EXISTS (SELECT 1 FROM pendencias pd WHERE pd.projeto_id = p.id AND lower(pd.status) NOT IN ('resolvida', 'cancelada'))")
    if filters.get("atrasados") == "1":
        sql_filters.append(
            """
            (
                EXISTS (SELECT 1 FROM projeto_etapas pe7 WHERE pe7.id = p.etapa_atual_id AND pe7.prazo < ? AND lower(pe7.status) NOT IN ('concluido', 'cancelado', 'aguardando externo'))
                OR EXISTS (SELECT 1 FROM pendencias pd2 WHERE pd2.projeto_id = p.id AND pd2.prazo < ? AND lower(pd2.status) NOT IN ('resolvida', 'cancelada'))
            )
            """
        )
        params.extend([date.today().isoformat(), date.today().isoformat()])
    if filters.get("sem_responsavel") == "1":
        sql_filters.append(
            """
            (
                p.responsavel_geral_id IS NULL
                OR EXISTS (SELECT 1 FROM projeto_etapas pe8 WHERE pe8.id = p.etapa_atual_id AND pe8.responsavel_id IS NULL)
            )
            """
        )
    prazo_filter = filters.get("prazo")
    if prazo_filter == "vencido":
        sql_filters.append(
            "EXISTS (SELECT 1 FROM projeto_etapas pe5 WHERE pe5.id = p.etapa_atual_id AND pe5.prazo < ? AND lower(pe5.status) NOT IN ('concluido', 'cancelado', 'aguardando externo'))"
        )
        params.append(date.today().isoformat())
    elif prazo_filter == "7dias":
        sql_filters.append(
            "EXISTS (SELECT 1 FROM projeto_etapas pe6 WHERE pe6.id = p.etapa_atual_id AND pe6.prazo BETWEEN ? AND ? AND lower(pe6.status) NOT IN ('concluido', 'cancelado'))"
        )
        params.extend([date.today().isoformat(), (date.today() + timedelta(days=7)).isoformat()])
    elif prazo_filter == "sem_prazo":
        sql_filters.append("(p.prazo_critico IS NULL OR p.prazo_critico = '')")

    where_clause = "WHERE " + " AND ".join(sql_filters) if sql_filters else ""
    projetos = query_db(
        f"""
        SELECT DISTINCT
            p.*,
            c.nome AS cliente_nome,
            ct.nome AS cartorio_nome,
            u.nome AS responsavel_nome
        FROM projetos p
        LEFT JOIN clientes c ON c.id = p.cliente_id
        LEFT JOIN cartorios ct ON ct.id = p.cartorio_id
        LEFT JOIN usuarios u ON u.id = p.responsavel_geral_id
        {where_clause}
        ORDER BY
            CASE p.prioridade WHEN 'Alta' THEN 0 WHEN 'Media' THEN 1 WHEN 'Baixa' THEN 2 ELSE 3 END,
            COALESCE(p.prazo_critico, '9999-12-31'),
            p.nome
        """,
        params,
    )
    matrix = [(project, load_stage_rows(project["id"])) for project in projetos]
    stage_ids = [stage["id"] for _, project_stages in matrix for stage in project_stages]
    matrix_checklists = {}
    pending_by_stage = {}
    pending_by_project = {}
    if stage_ids:
        placeholders = ",".join("?" for _ in stage_ids)
        for item in query_db(
            f"SELECT * FROM checklist_itens WHERE projeto_etapa_id IN ({placeholders}) ORDER BY projeto_etapa_id, id",
            stage_ids,
        ):
            matrix_checklists.setdefault(item["projeto_etapa_id"], []).append(item)
        for pending in query_db(
            f"""
            SELECT pd.*, u.nome AS responsavel_nome
            FROM pendencias pd
            LEFT JOIN usuarios u ON u.id = pd.responsavel_id
            WHERE pd.etapa_id IN ({placeholders})
              AND lower(pd.status) NOT IN ('resolvida', 'cancelada')
            ORDER BY COALESCE(pd.prazo, '9999-12-31'), pd.id
            """,
            stage_ids,
        ):
            pending_by_stage.setdefault(pending["etapa_id"], []).append(pending)
            pending_by_project.setdefault(pending["projeto_id"], []).append(pending)
    project_ids = [project["id"] for project, _ in matrix]
    movements_by_project = {}
    if project_ids:
        project_placeholders = ",".join("?" for _ in project_ids)
        for movement in query_db(
            f"""
            SELECT m.*, u.nome AS usuario_nome
            FROM movimentacoes_etapa m
            LEFT JOIN usuarios u ON u.id = m.usuario_id
            WHERE m.projeto_id IN ({project_placeholders})
            ORDER BY m.criado_em DESC
            """,
            project_ids,
        ):
            movements_by_project.setdefault(movement["projeto_id"], []).append(movement)
    summary = {
        "ativos": len([project for project, _ in matrix if str(project["status"] or "").lower() not in ("concluido", "cancelado")]),
        "sete_dias": query_db(
            """
            SELECT COUNT(*) AS total
            FROM projeto_etapas pe
            JOIN etapas_modelo em ON em.id = pe.etapa_modelo_id
            WHERE em.ativa = 1
              AND pe.id IN (SELECT etapa_atual_id FROM projetos WHERE etapa_atual_id IS NOT NULL)
              AND pe.prazo BETWEEN ? AND ?
              AND lower(pe.status) NOT IN ('concluido', 'cancelado')
            """,
            (date.today().isoformat(), (date.today() + timedelta(days=7)).isoformat()),
            one=True,
        )["total"],
        "atrasados": query_db(
            "SELECT COUNT(*) AS total FROM projeto_etapas WHERE lower(status) = 'atrasado' AND id IN (SELECT etapa_atual_id FROM projetos WHERE etapa_atual_id IS NOT NULL)",
            one=True,
        )["total"],
        "cartorio": query_db(
            """
            SELECT COUNT(*) AS total
            FROM projetos p
            JOIN projeto_etapas pe ON pe.id = p.etapa_atual_id
            JOIN etapas_modelo em ON em.id = pe.etapa_modelo_id
            WHERE lower(em.nome) = 'cartorio'
            """,
            one=True,
        )["total"],
        "pendencias": query_db(
            "SELECT COUNT(*) AS total FROM pendencias WHERE lower(status) NOT IN ('resolvida', 'cancelada')",
            one=True,
        )["total"],
    }
    return render_template(
        "projects.html",
        projects=matrix,
        matrix_checklists=matrix_checklists,
        pending_by_stage=pending_by_stage,
        pending_by_project=pending_by_project,
        movements_by_project=movements_by_project,
        summary=summary,
        etapas=query_db("SELECT * FROM etapas_modelo WHERE ativa = 1 ORDER BY ordem"),
        usuarios=query_db("SELECT * FROM usuarios WHERE ativo = 1 ORDER BY nome"),
        clientes=query_db("SELECT * FROM clientes ORDER BY nome"),
        cartorios=query_db("SELECT * FROM cartorios ORDER BY nome"),
        filters=filters,
    )


@app.route("/projects/export")
@login_required
def projects_export():
    rows = query_db(
        """
        SELECT
            p.codigo,
            p.proprietario,
            p.nome AS projeto,
            c.nome AS cliente,
            p.cidade,
            ct.nome AS cartorio,
            em.nome AS etapa_atual,
            u.nome AS responsavel_etapa,
            pe.status AS status_etapa,
            pe.prazo AS prazo_etapa,
            p.prioridade,
            p.status AS status_projeto,
            p.caminho_pasta
        FROM projetos p
        LEFT JOIN clientes c ON c.id = p.cliente_id
        LEFT JOIN cartorios ct ON ct.id = p.cartorio_id
        LEFT JOIN projeto_etapas pe ON pe.id = p.etapa_atual_id
        LEFT JOIN etapas_modelo em ON em.id = pe.etapa_modelo_id
        LEFT JOIN usuarios u ON u.id = pe.responsavel_id
        ORDER BY p.proprietario, p.nome
        """
    )
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow(["Codigo", "Proprietario", "Projeto", "Cliente", "Cidade", "Cartorio", "Etapa atual", "Responsavel", "Status etapa", "Prazo etapa", "Prioridade", "Status projeto", "Pasta"])
    for row in rows:
        writer.writerow([row[key] for key in row.keys()])
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=geogestao_projetos.csv"},
    )


@app.route("/project/create", methods=["GET", "POST"])
@login_required
def project_create():
    if not can_manage():
        flash("Permissao negada.", "danger")
        return redirect(url_for("projects"))

    clientes = query_db("SELECT * FROM clientes ORDER BY nome")
    cartorios = query_db("SELECT * FROM cartorios ORDER BY nome")

    if request.method == "POST":
        next_number = query_db("SELECT COUNT(*) + 1 AS total FROM projetos", one=True)["total"]
        codigo = f"GG-{next_number:03d}"
        nome = request.form["nome"].strip()
        if not nome:
            flash("Informe o nome do projeto.", "danger")
            return redirect(url_for("project_create"))

        proprietario = request.form.get("proprietario", "").strip() or nome
        cliente_id = request.form.get("cliente_id") or None

        valor_str = request.form.get("valor", "").strip()
        valor = None
        if valor_str:
            # Remove R$ and spaces
            valor_str = valor_str.replace("R$", "").strip()
            # Brazilian format: 1.000,00 -> convert to 1000.00
            valor_str = valor_str.replace(".", "").replace(",", ".")
            try:
                valor = float(valor_str)
            except ValueError:
                valor = None

        created = datetime.now().isoformat(timespec="seconds")
        project_id = execute_db(
            """
            INSERT INTO projetos
                (codigo, nome, proprietario, cliente_id, cidade, uf, cartorio_id, tipo_servico, valor, caminho_pasta, observacoes, criado_em, atualizado_em)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                codigo,
                nome,
                proprietario,
                cliente_id,
                request.form.get("cidade", "").strip(),
                request.form.get("uf", "").strip().upper(),
                request.form.get("cartorio_id") or None,
                request.form.get("tipo_servico", "").strip(),
                valor,
                request.form.get("caminho_pasta", "").strip(),
                request.form.get("observacoes", "").strip(),
                created,
                created,
            ),
        )
        db = get_db()
        create_stage_rows(db, project_id, None, None)
        db.commit()
        record_event(project_id, "projeto_criado", f"Projeto {codigo} criado.")
        flash("Projeto criado com sucesso.", "success")
        return redirect(url_for("project_detail", project_id=project_id))

    return render_template(
        "project_form.html",
        clientes=clientes,
        cartorios=cartorios,
    )


@app.route("/api/add-cartorio", methods=["POST"])
@login_required
def api_add_cartorio():
    if not can_manage():
        return {"error": "Permissao negada"}, 403

    data = request.get_json() or {}
    nome = (data.get("nome") or "").strip()
    if not nome:
        return {"error": "Nome obrigatorio"}, 400

    try:
        cartorio_id = execute_db("INSERT INTO cartorios (nome) VALUES (?)", (nome,))
        return {"id": cartorio_id, "nome": nome}, 201
    except Exception as e:
        return {"error": str(e)}, 500


@app.route("/api/select-folder", methods=["POST"])
@login_required
def api_select_folder():
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.wm_attributes("-topmost", True)
        folder = filedialog.askdirectory(parent=root, title="Selecionar pasta do projeto")
        root.destroy()
        if folder:
            # Converte para caminho Windows com barras invertidas
            folder = folder.replace("/", "\\")
            return jsonify({"path": folder})
        return jsonify({"path": None})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/add-cliente", methods=["POST"])
@login_required
def api_add_cliente():
    if not can_manage():
        return {"error": "Permissao negada"}, 403

    data = request.get_json() or {}
    nome = (data.get("nome") or "").strip()
    if not nome:
        return {"error": "Nome obrigatorio"}, 400

    try:
        cliente_id = execute_db("INSERT INTO clientes (nome) VALUES (?)", (nome,))
        return {"id": cliente_id, "nome": nome}, 201
    except Exception as e:
        return {"error": str(e)}, 500


@app.route("/project/<int:project_id>")
@login_required
def project_detail(project_id):
    refresh_due_statuses()
    project = query_db(
        """
        SELECT p.*, c.nome AS cliente_nome, ct.nome AS cartorio_nome, u.nome AS responsavel_geral_nome
        FROM projetos p
        LEFT JOIN clientes c ON c.id = p.cliente_id
        LEFT JOIN cartorios ct ON ct.id = p.cartorio_id
        LEFT JOIN usuarios u ON u.id = p.responsavel_geral_id
        WHERE p.id = ?
        """,
        (project_id,),
        one=True,
    )
    if not project:
        flash("Projeto nao encontrado.", "danger")
        return redirect(url_for("projects"))

    etapas = load_stage_rows(project_id)
    tarefas = query_db(
        """
        SELECT t.*, u.nome AS responsavel_nome, em.nome AS etapa_nome
        FROM tarefas t
        LEFT JOIN usuarios u ON u.id = t.responsavel_id
        LEFT JOIN projeto_etapas pe ON pe.id = t.projeto_etapa_id
        LEFT JOIN etapas_modelo em ON em.id = pe.etapa_modelo_id
        WHERE t.projeto_id = ?
        ORDER BY
            CASE t.prioridade WHEN 'Alta' THEN 0 WHEN 'Media' THEN 1 WHEN 'Baixa' THEN 2 ELSE 3 END,
            COALESCE(t.prazo, '9999-12-31')
        """,
        (project_id,),
    )
    checklist = query_db(
        """
        SELECT ci.*, u.nome AS concluido_por_nome
        FROM checklist_itens ci
        LEFT JOIN usuarios u ON u.id = ci.concluido_por
        WHERE ci.projeto_etapa_id IN (SELECT id FROM projeto_etapas WHERE projeto_id = ?)
        ORDER BY ci.projeto_etapa_id, ci.id
        """,
        (project_id,),
    )
    checklist_by_stage = {}
    for item in checklist:
        checklist_by_stage.setdefault(item["projeto_etapa_id"], []).append(item)

    exigencias = query_db(
        """
        SELECT e.*, c.nome AS cartorio_nome, u.nome AS responsavel_nome
        FROM exigencias_cartorio e
        LEFT JOIN cartorios c ON c.id = e.cartorio_id
        LEFT JOIN usuarios u ON u.id = e.responsavel_id
        WHERE e.projeto_id = ?
        ORDER BY COALESCE(e.prazo_resposta, '9999-12-31')
        """,
        (project_id,),
    )
    pendencias = query_db(
        """
        SELECT pd.*, em.nome AS etapa_nome, u.nome AS responsavel_nome
        FROM pendencias pd
        LEFT JOIN projeto_etapas pe ON pe.id = pd.etapa_id
        LEFT JOIN etapas_modelo em ON em.id = pe.etapa_modelo_id
        LEFT JOIN usuarios u ON u.id = pd.responsavel_id
        WHERE pd.projeto_id = ?
        ORDER BY
            CASE WHEN lower(pd.status) IN ('resolvida', 'cancelada') THEN 1 ELSE 0 END,
            COALESCE(pd.prazo, '9999-12-31')
        """,
        (project_id,),
    )
    movimentacoes = query_db(
        """
        SELECT m.*, u.nome AS usuario_nome, r.nome AS responsavel_nome
        FROM movimentacoes_etapa m
        LEFT JOIN usuarios u ON u.id = m.usuario_id
        LEFT JOIN usuarios r ON r.id = m.responsavel_id
        WHERE m.projeto_id = ?
        ORDER BY m.criado_em DESC
        """,
        (project_id,),
    )
    time_entries = query_db(
        """
        SELECT a.*, u.nome AS usuario_nome, em.nome AS etapa_nome, t.titulo AS tarefa_titulo
        FROM apontamentos_tempo a
        LEFT JOIN usuarios u ON u.id = a.usuario_id
        LEFT JOIN projeto_etapas pe ON pe.id = a.etapa_id
        LEFT JOIN etapas_modelo em ON em.id = pe.etapa_modelo_id
        LEFT JOIN tarefas t ON t.id = a.tarefa_id
        WHERE a.projeto_id = ?
        ORDER BY a.criado_em DESC
        """,
        (project_id,),
    )
    total_minutes = query_db(
        "SELECT COALESCE(SUM(duracao_minutos), 0) AS total FROM apontamentos_tempo WHERE projeto_id = ?",
        (project_id,),
        one=True,
    )["total"]
    historico = query_db(
        """
        SELECT e.*, u.nome AS usuario_nome
        FROM eventos_historico e
        LEFT JOIN usuarios u ON u.id = e.usuario_id
        WHERE e.projeto_id = ?
        ORDER BY e.criado_em DESC
        """,
        (project_id,),
    )
    return render_template(
        "project_detail.html",
        project=project,
        etapas=etapas,
        tarefas=tarefas,
        checklist_by_stage=checklist_by_stage,
        exigencias=exigencias,
        pendencias=pendencias,
        movimentacoes=movimentacoes,
        time_entries=time_entries,
        total_minutes=total_minutes,
        historico=historico,
        usuarios=query_db("SELECT * FROM usuarios WHERE ativo = 1 ORDER BY nome"),
        clientes=query_db("SELECT * FROM clientes ORDER BY nome"),
        cartorios=query_db("SELECT * FROM cartorios ORDER BY nome"),
    )


@app.route("/project/<int:project_id>/action", methods=["POST"])
@login_required
def project_action(project_id):
    project = query_db("SELECT * FROM projetos WHERE id = ?", (project_id,), one=True)
    if not project:
        flash("Projeto nao encontrado.", "danger")
        return redirect(url_for("projects"))

    action = request.form.get("action")
    if action == "update_project":
        if not can_manage():
            flash("Permissao negada.", "danger")
            return redirect(url_for("project_detail", project_id=project_id))
        valor_str = request.form.get("valor", "").strip()
        valor = None
        if valor_str:
            # Remove R$ and spaces
            valor_str = valor_str.replace("R$", "").strip()
            # Brazilian format: 1.000,00 -> convert to 1000.00
            valor_str = valor_str.replace(".", "").replace(",", ".")
            try:
                valor = float(valor_str)
            except ValueError:
                valor = None

        execute_db(
            """
            UPDATE projetos
            SET nome = ?, proprietario = ?, cliente_id = ?, cidade = ?, uf = ?, cartorio_id = ?, tipo_servico = ?,
                prioridade = ?, status = ?, prazo_critico = ?, responsavel_geral_id = ?, caminho_pasta = ?,
                observacoes = ?, valor = ?, atualizado_em = ?
            WHERE id = ?
            """,
            (
                request.form.get("nome", "").strip(),
                request.form.get("proprietario", "").strip(),
                request.form.get("cliente_id") or None,
                request.form.get("cidade", "").strip(),
                request.form.get("uf", "").strip().upper(),
                request.form.get("cartorio_id") or None,
                request.form.get("tipo_servico", "").strip(),
                request.form.get("prioridade", "Media"),
                request.form.get("status", "Em andamento"),
                request.form.get("prazo_critico") or None,
                request.form.get("responsavel_geral_id") or None,
                request.form.get("caminho_pasta", "").strip(),
                request.form.get("observacoes", "").strip(),
                valor,
                datetime.now().isoformat(timespec="seconds"),
                project_id,
            ),
        )
        record_event(project_id, "projeto_atualizado", "Dados principais do projeto atualizados.")
        flash("Projeto atualizado.", "success")

    elif action == "update_stage":
        stage_id = request.form.get("etapa_id")
        old_stage = query_db(
            "SELECT pe.*, em.nome AS etapa_nome FROM projeto_etapas pe JOIN etapas_modelo em ON em.id = pe.etapa_modelo_id WHERE pe.id = ?",
            (stage_id,),
            one=True,
        )
        status = request.form.get("status", "nao iniciado")
        progress = int(request.form.get("progresso") or 0)
        data_inicio = old_stage["data_inicio"]
        data_fim = old_stage["data_fim"]
        if status == "em andamento" and not data_inicio:
            data_inicio = datetime.now().isoformat(timespec="seconds")
        if status == "concluido":
            data_fim = datetime.now().isoformat(timespec="seconds")
            progress = 100
        execute_db(
            """
            UPDATE projeto_etapas
            SET status = ?, responsavel_id = ?, prazo = ?, progresso = ?, subetapa_ativa = ?,
                atraso_origem = ?, observacoes = ?, data_inicio = ?, data_fim = ?
            WHERE id = ?
            """,
            (
                status,
                request.form.get("responsavel_id") or None,
                request.form.get("prazo") or None,
                progress,
                request.form.get("subetapa_ativa", "").strip(),
                request.form.get("atraso_origem", "").strip() or None,
                request.form.get("observacoes", "").strip(),
                data_inicio,
                data_fim,
                stage_id,
            ),
        )
        record_event(project_id, "etapa_atualizada", f"Etapa {old_stage['etapa_nome']} atualizada para {STATUS_META.get(status, {}).get('label', status)}.")
        flash("Etapa atualizada.", "success")

    elif action == "move_stage":
        if not can_manage():
            flash("Permissao negada.", "danger")
            return redirect(url_for("project_detail", project_id=project_id))
        new_stage_id = request.form.get("nova_etapa_id")
        new_stage = query_db(
            """
            SELECT pe.*, em.nome AS etapa_nome, em.ordem AS etapa_ordem
            FROM projeto_etapas pe
            JOIN etapas_modelo em ON em.id = pe.etapa_modelo_id
            WHERE pe.id = ? AND pe.projeto_id = ? AND em.ativa = 1
            """,
            (new_stage_id, project_id),
            one=True,
        )
        if not new_stage:
            flash("Etapa de destino invalida.", "danger")
            return redirect(request.form.get("next") or url_for("project_detail", project_id=project_id))

        db = get_db()
        old_stage_id = project["etapa_atual_id"] or infer_current_stage_id_db(db, project_id)
        old_stage = query_db(
            """
            SELECT pe.*, em.nome AS etapa_nome, em.ordem AS etapa_ordem
            FROM projeto_etapas pe
            JOIN etapas_modelo em ON em.id = pe.etapa_modelo_id
            WHERE pe.id = ?
            """,
            (old_stage_id,),
            one=True,
        )

        redirect_url = request.form.get("next") or url_for("project_detail", project_id=project_id)

        if old_stage and old_stage["id"] != new_stage["id"]:
            old_ordem = old_stage["etapa_ordem"]
            new_ordem = new_stage["etapa_ordem"]
            is_advance = new_ordem > old_ordem
            is_return = new_ordem < old_ordem

            if is_advance and new_ordem > old_ordem + 1:
                flash("Nao e permitido pular etapas. Avance apenas para a proxima etapa em sequencia.", "danger")
                return redirect(redirect_url)

            if is_return:
                observacao = request.form.get("observacao", "").strip()
                if not observacao:
                    flash("Justificativa obrigatoria ao retornar uma etapa. Descreva o motivo.", "danger")
                    return redirect(redirect_url)

        motivo_form = request.form.get("motivo", "")
        is_return_move = old_stage and new_stage["etapa_ordem"] < old_stage["etapa_ordem"]
        if not motivo_form:
            motivo = "retorno" if is_return_move else "avanco"
        else:
            motivo = motivo_form
        observacao = request.form.get("observacao", "").strip()
        is_rework = motivo in ("retorno", "exigencia_cartorio", "retrabalho", "pendencia_externa") or is_return_move
        now = datetime.now().isoformat(timespec="seconds")

        if old_stage and old_stage["id"] != new_stage["id"]:
            old_status = "atencao" if is_rework else "concluido"
            execute_db(
                """
                UPDATE projeto_etapas
                SET status = ?, data_fim = ?, progresso = CASE WHEN ? = 'concluido' THEN 100 ELSE progresso END
                WHERE id = ?
                """,
                (old_status, None if is_rework else now, old_status, old_stage["id"]),
            )

        new_status = "retrabalho" if is_rework else "em andamento"
        execute_db(
            """
            UPDATE projeto_etapas
            SET status = ?, responsavel_id = COALESCE(?, responsavel_id), prazo = COALESCE(?, prazo),
                data_inicio = COALESCE(data_inicio, ?), data_fim = NULL, subetapa_ativa = COALESCE(NULLIF(?, ''), subetapa_ativa)
            WHERE id = ?
            """,
            (
                new_status,
                request.form.get("responsavel_id") or None,
                request.form.get("prazo") or None,
                now,
                request.form.get("subetapa_ativa", "").strip(),
                new_stage["id"],
            ),
        )
        execute_db(
            "UPDATE projetos SET etapa_atual_id = ?, status = ?, atualizado_em = ? WHERE id = ?",
            (new_stage["id"], "Atencao" if is_rework else "Em andamento", now, project_id),
        )
        execute_db(
            """
            INSERT INTO movimentacoes_etapa
                (projeto_id, etapa_anterior_id, etapa_nova_id, etapa_anterior, etapa_nova, motivo, observacao, responsavel_id, usuario_id, criado_em)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                old_stage["id"] if old_stage else None,
                new_stage["id"],
                old_stage["etapa_nome"] if old_stage else None,
                new_stage["etapa_nome"],
                motivo,
                observacao,
                request.form.get("responsavel_id") or new_stage["responsavel_id"],
                g.user["id"],
                now,
            ),
        )
        pending_description = request.form.get("pendencia_descricao", "").strip()
        if pending_description:
            execute_db(
                """
                INSERT INTO pendencias
                    (projeto_id, etapa_id, descricao, origem, responsavel_id, prazo, status, data_abertura, criado_em, atualizado_em)
                VALUES (?, ?, ?, ?, ?, ?, 'aberta', ?, ?, ?)
                """,
                (
                    project_id,
                    new_stage["id"],
                    pending_description,
                    "cartorio" if motivo == "exigencia_cartorio" else "interna",
                    request.form.get("responsavel_id") or new_stage["responsavel_id"],
                    request.form.get("prazo") or None,
                    date.today().isoformat(),
                    now,
                    now,
                ),
            )
        record_event(project_id, "movimentacao_etapa", f"Projeto movido de {old_stage['etapa_nome'] if old_stage else '-'} para {new_stage['etapa_nome']} ({motivo}).")
        flash("Etapa atual do projeto atualizada.", "success")

    elif action == "add_task":
        title = request.form.get("titulo", "").strip()
        if title:
            task_id = execute_db(
                """
                INSERT INTO tarefas
                    (projeto_id, projeto_etapa_id, titulo, descricao, responsavel_id, prioridade, status, prazo, criado_em)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    request.form.get("etapa_id") or None,
                    title,
                    request.form.get("descricao", "").strip(),
                    request.form.get("responsavel_id") or None,
                    request.form.get("prioridade", "Media"),
                    request.form.get("status", "nao iniciado"),
                    request.form.get("prazo") or None,
                    datetime.now().isoformat(timespec="seconds"),
                ),
            )
            record_event(project_id, "tarefa_criada", f"Tarefa criada: {title}.")
            flash(f"Tarefa #{task_id} criada.", "success")

    elif action == "add_checklist":
        title = request.form.get("titulo", "").strip()
        stage_id = request.form.get("etapa_id")
        if title and stage_id:
            execute_db("INSERT INTO checklist_itens (projeto_etapa_id, titulo) VALUES (?, ?)", (stage_id, title))
            update_stage_progress(stage_id)
            record_event(project_id, "checklist_adicionado", f"Checklist adicionado: {title}.")
            flash("Item de checklist adicionado.", "success")

    elif action == "toggle_checklist":
        item_id = request.form.get("item_id")
        item = query_db("SELECT * FROM checklist_itens WHERE id = ?", (item_id,), one=True)
        if item:
            new_value = 0 if item["concluido"] else 1
            execute_db(
                "UPDATE checklist_itens SET concluido = ?, concluido_por = ?, concluido_em = ? WHERE id = ?",
                (
                    new_value,
                    g.user["id"] if new_value else None,
                    datetime.now().isoformat(timespec="seconds") if new_value else None,
                    item_id,
                ),
            )
            progress = update_stage_progress(item["projeto_etapa_id"])
            record_event(project_id, "checklist_atualizado", f"Checklist atualizado: {item['titulo']} ({progress}%).")
            flash("Checklist atualizado.", "success")

    elif action == "add_pending":
        description = request.form.get("descricao", "").strip()
        if description:
            now = datetime.now().isoformat(timespec="seconds")
            pending_id = execute_db(
                """
                INSERT INTO pendencias
                    (projeto_id, etapa_id, descricao, origem, responsavel_id, prazo, status, data_abertura, criado_em, atualizado_em)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    request.form.get("etapa_id") or None,
                    description,
                    request.form.get("origem", "interna"),
                    request.form.get("responsavel_id") or None,
                    request.form.get("prazo") or None,
                    request.form.get("status", "aberta"),
                    date.today().isoformat(),
                    now,
                    now,
                ),
            )
            if request.form.get("etapa_id"):
                execute_db("UPDATE projeto_etapas SET status = 'atencao' WHERE id = ? AND lower(status) NOT IN ('concluido', 'cancelado')", (request.form.get("etapa_id"),))
                if str(request.form.get("etapa_id")) == str(project["etapa_atual_id"]):
                    execute_db("UPDATE projetos SET status = 'Atencao', atualizado_em = ? WHERE id = ?", (now, project_id))
            record_event(project_id, "pendencia_criada", f"Pendencia #{pending_id} registrada: {description}.")
            flash("Pendencia registrada.", "success")

    elif action == "resolve_pending":
        pending_id = request.form.get("pendencia_id")
        execute_db(
            "UPDATE pendencias SET status = 'resolvida', data_resolucao = ?, atualizado_em = ? WHERE id = ? AND projeto_id = ?",
            (date.today().isoformat(), datetime.now().isoformat(timespec="seconds"), pending_id, project_id),
        )
        record_event(project_id, "pendencia_resolvida", f"Pendencia #{pending_id} resolvida.")
        flash("Pendencia resolvida.", "success")

    elif action == "add_exigencia":
        description = request.form.get("descricao", "").strip()
        if description:
            exigencia_id = execute_db(
                """
                INSERT INTO exigencias_cartorio
                    (projeto_id, cartorio_id, data_recebimento, prazo_resposta, descricao, status, responsavel_id, criado_em, atualizado_em)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    request.form.get("cartorio_id") or project["cartorio_id"],
                    request.form.get("data_recebimento") or date.today().isoformat(),
                    request.form.get("prazo_resposta") or None,
                    description,
                    request.form.get("status", "em andamento"),
                    request.form.get("responsavel_id") or None,
                    datetime.now().isoformat(timespec="seconds"),
                    datetime.now().isoformat(timespec="seconds"),
                ),
            )
            cartorio_stage = query_db(
                """
                SELECT pe.id
                FROM projeto_etapas pe
                JOIN etapas_modelo em ON em.id = pe.etapa_modelo_id
                WHERE pe.projeto_id = ? AND lower(em.nome) = 'cartorio' AND em.ativa = 1
                LIMIT 1
                """,
                (project_id,),
                one=True,
            )
            if cartorio_stage:
                execute_db("UPDATE projeto_etapas SET status = 'atencao', subetapa_ativa = ? WHERE id = ?", ("Exigencia em correcao", cartorio_stage["id"]))
            execute_db(
                """
                INSERT INTO pendencias
                    (projeto_id, etapa_id, descricao, origem, responsavel_id, prazo, status, data_abertura, criado_em, atualizado_em)
                VALUES (?, ?, ?, 'cartorio', ?, ?, 'aberta', ?, ?, ?)
                """,
                (
                    project_id,
                    cartorio_stage["id"] if cartorio_stage else None,
                    description,
                    request.form.get("responsavel_id") or project["responsavel_geral_id"],
                    request.form.get("prazo_resposta") or None,
                    date.today().isoformat(),
                    datetime.now().isoformat(timespec="seconds"),
                    datetime.now().isoformat(timespec="seconds"),
                ),
            )
            execute_db(
                """
                INSERT INTO tarefas
                    (projeto_id, projeto_etapa_id, titulo, descricao, responsavel_id, prioridade, status, prazo, criado_em)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    cartorio_stage["id"] if cartorio_stage else None,
                    "Responder exigencia de cartorio",
                    description,
                    request.form.get("responsavel_id") or project["responsavel_geral_id"],
                    "Alta",
                    "em andamento",
                    request.form.get("prazo_resposta") or None,
                    datetime.now().isoformat(timespec="seconds"),
                ),
            )
            record_event(project_id, "exigencia_criada", f"Exigencia #{exigencia_id} registrada.")
            flash("Exigencia registrada e tarefa criada.", "success")

    elif action == "update_exigencia":
        exigencia_id = request.form.get("exigencia_id")
        execute_db(
            """
            UPDATE exigencias_cartorio
            SET status = ?, responsavel_id = ?, prazo_resposta = ?, atualizado_em = ?
            WHERE id = ? AND projeto_id = ?
            """,
            (
                request.form.get("status", "em andamento"),
                request.form.get("responsavel_id") or None,
                request.form.get("prazo_resposta") or None,
                datetime.now().isoformat(timespec="seconds"),
                exigencia_id,
                project_id,
            ),
        )
        record_event(project_id, "exigencia_atualizada", f"Exigencia #{exigencia_id} atualizada.")
        flash("Exigencia atualizada.", "success")

    elif action == "add_time":
        minutes = int(request.form.get("duracao_minutos") or 0)
        if minutes > 0:
            execute_db(
                """
                INSERT INTO apontamentos_tempo
                    (projeto_id, etapa_id, tarefa_id, usuario_id, inicio, fim, duracao_minutos, tipo_tempo, observacoes, criado_em)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    request.form.get("etapa_id") or None,
                    request.form.get("tarefa_id") or None,
                    request.form.get("usuario_id") or g.user["id"],
                    request.form.get("inicio") or None,
                    request.form.get("fim") or None,
                    minutes,
                    request.form.get("tipo_tempo", "execucao"),
                    request.form.get("observacoes", "").strip(),
                    datetime.now().isoformat(timespec="seconds"),
                ),
            )
            record_event(project_id, "tempo_registrado", f"Tempo registrado: {minutes_to_hours(minutes)}.")
            flash("Tempo registrado.", "success")

    elif action == "add_comment":
        comment = request.form.get("comentario", "").strip()
        if comment:
            record_event(project_id, "comentario", comment)
            flash("Comentario registrado no historico.", "success")

    next_url = request.form.get("next") or url_for("project_detail", project_id=project_id)
    return redirect(next_url)


@app.route("/api/checklist/add", methods=["POST"])
@login_required
def api_add_checklist_item():
    data = request.get_json() or {}
    titulo = (data.get("titulo") or "").strip()
    stage_id = data.get("stage_id")
    if not titulo or not stage_id:
        return jsonify({"ok": False, "error": "Dados incompletos"}), 400
    stage = query_db("SELECT * FROM projeto_etapas WHERE id = ?", (stage_id,), one=True)
    if not stage:
        return jsonify({"ok": False, "error": "Etapa nao encontrada"}), 404
    item_id = execute_db("INSERT INTO checklist_itens (projeto_etapa_id, titulo) VALUES (?, ?)", (stage_id, titulo))
    progress = update_stage_progress(stage_id)
    done = query_db("SELECT COUNT(*) AS n FROM checklist_itens WHERE projeto_etapa_id = ? AND concluido = 1", (stage_id,), one=True)["n"]
    total = query_db("SELECT COUNT(*) AS n FROM checklist_itens WHERE projeto_etapa_id = ?", (stage_id,), one=True)["n"]
    return jsonify({"ok": True, "id": item_id, "titulo": titulo, "concluido": False, "progress": progress, "done": done, "total": total})


@app.route("/api/checklist/<int:item_id>/toggle", methods=["POST"])
@login_required
def api_toggle_checklist(item_id):
    from flask import jsonify
    item = query_db("SELECT * FROM checklist_itens WHERE id = ?", (item_id,), one=True)
    if not item:
        return jsonify({"ok": False, "error": "Item nao encontrado"}), 404
    new_value = 0 if item["concluido"] else 1
    now = datetime.now().isoformat(timespec="seconds")
    execute_db(
        "UPDATE checklist_itens SET concluido = ?, concluido_por = ?, concluido_em = ? WHERE id = ?",
        (new_value, g.user["id"] if new_value else None, now if new_value else None, item_id),
    )
    progress = update_stage_progress(item["projeto_etapa_id"])
    done = query_db("SELECT COUNT(*) AS n FROM checklist_itens WHERE projeto_etapa_id = ? AND concluido = 1", (item["projeto_etapa_id"],), one=True)["n"]
    total = query_db("SELECT COUNT(*) AS n FROM checklist_itens WHERE projeto_etapa_id = ?", (item["projeto_etapa_id"],), one=True)["n"]
    return jsonify({"ok": True, "concluido": bool(new_value), "progress": progress, "done": done, "total": total})


@app.route("/stage/<int:stage_id>/quick", methods=["POST"])
@login_required
def stage_quick(stage_id):
    stage = query_db(
        "SELECT pe.*, em.nome AS etapa_nome FROM projeto_etapas pe JOIN etapas_modelo em ON em.id = pe.etapa_modelo_id WHERE pe.id = ?",
        (stage_id,),
        one=True,
    )
    if not stage:
        flash("Etapa nao encontrada.", "danger")
        return redirect(url_for("projects"))
    action = request.form.get("quick_action")
    status = stage["status"]
    progress = stage["progresso"] or 0
    data_inicio = stage["data_inicio"]
    data_fim = stage["data_fim"]
    if action == "start":
        status = "em andamento"
        progress = max(progress, 10)
        data_inicio = data_inicio or datetime.now().isoformat(timespec="seconds")
    elif action == "pause":
        status = "atencao"
    elif action == "finish":
        status = "concluido"
        progress = 100
        data_fim = datetime.now().isoformat(timespec="seconds")
    execute_db(
        "UPDATE projeto_etapas SET status = ?, progresso = ?, data_inicio = ?, data_fim = ? WHERE id = ?",
        (status, progress, data_inicio, data_fim, stage_id),
    )
    record_event(stage["projeto_id"], "acao_rapida_etapa", f"Acao rapida em {stage['etapa_nome']}: {STATUS_META.get(status, {}).get('label', status)}.")
    flash("Etapa atualizada.", "success")
    return redirect(request.form.get("next") or url_for("project_detail", project_id=stage["projeto_id"]))


@app.route("/task/<int:task_id>/quick", methods=["POST"])
@login_required
def task_quick(task_id):
    task = query_db("SELECT * FROM tarefas WHERE id = ?", (task_id,), one=True)
    if not task:
        flash("Tarefa nao encontrada.", "danger")
        return redirect(url_for("my_missions"))
    action = request.form.get("quick_action")
    status = task["status"] or "nao iniciado"
    data_inicio = task["data_inicio"]
    concluido_em = task["concluido_em"]
    if action == "start":
        status = "em andamento"
        data_inicio = data_inicio or datetime.now().isoformat(timespec="seconds")
    elif action == "pause":
        status = "atencao"
    elif action == "finish":
        status = "concluido"
        concluido_em = datetime.now().isoformat(timespec="seconds")
    execute_db(
        "UPDATE tarefas SET status = ?, data_inicio = ?, concluido_em = ? WHERE id = ?",
        (status, data_inicio, concluido_em, task_id),
    )
    record_event(task["projeto_id"], "acao_rapida_tarefa", f"Tarefa {task['titulo']} atualizada para {STATUS_META.get(status, {}).get('label', status)}.")
    flash("Tarefa atualizada.", "success")
    return redirect(request.form.get("next") or url_for("my_missions"))


@app.route("/pending/<int:pending_id>/quick", methods=["POST"])
@login_required
def pending_quick(pending_id):
    pending = query_db("SELECT * FROM pendencias WHERE id = ?", (pending_id,), one=True)
    if not pending:
        flash("Pendencia nao encontrada.", "danger")
        return redirect(url_for("my_missions"))
    action = request.form.get("quick_action")
    status = pending["status"]
    resolved_at = pending["data_resolucao"]
    if action == "start":
        status = "em andamento"
    elif action == "finish":
        status = "resolvida"
        resolved_at = date.today().isoformat()
    elif action == "cancel":
        status = "cancelada"
        resolved_at = date.today().isoformat()
    execute_db(
        "UPDATE pendencias SET status = ?, data_resolucao = ?, atualizado_em = ? WHERE id = ?",
        (status, resolved_at, datetime.now().isoformat(timespec="seconds"), pending_id),
    )
    record_event(pending["projeto_id"], "pendencia_atualizada", f"Pendencia #{pending_id} atualizada para {status}.")
    flash("Pendencia atualizada.", "success")
    return redirect(request.form.get("next") or url_for("my_missions"))


@app.route("/my-missions")
@login_required
def my_missions():
    refresh_due_statuses()
    stage_rows = query_db(
        """
        SELECT pe.id, pe.projeto_id, pe.status, pe.prazo, pe.progresso, pe.subetapa_ativa,
               p.nome AS projeto_nome, p.caminho_pasta, em.nome AS etapa_nome, p.prioridade
        FROM projeto_etapas pe
        JOIN projetos p ON p.id = pe.projeto_id
        JOIN etapas_modelo em ON em.id = pe.etapa_modelo_id
        WHERE pe.responsavel_id = ? AND lower(pe.status) NOT IN ('concluido', 'cancelado') AND em.ativa = 1
        """,
        (g.user["id"],),
    )
    task_rows = query_db(
        """
        SELECT t.*, p.nome AS projeto_nome, p.caminho_pasta, em.nome AS etapa_nome
        FROM tarefas t
        JOIN projetos p ON p.id = t.projeto_id
        LEFT JOIN projeto_etapas pe ON pe.id = t.projeto_etapa_id
        LEFT JOIN etapas_modelo em ON em.id = pe.etapa_modelo_id
        WHERE t.responsavel_id = ? AND lower(COALESCE(t.status, '')) NOT IN ('concluido', 'cancelado')
        """,
        (g.user["id"],),
    )
    pending_rows = query_db(
        """
        SELECT pd.*, p.nome AS projeto_nome, p.caminho_pasta, em.nome AS etapa_nome, p.prioridade
        FROM pendencias pd
        JOIN projetos p ON p.id = pd.projeto_id
        LEFT JOIN projeto_etapas pe ON pe.id = pd.etapa_id
        LEFT JOIN etapas_modelo em ON em.id = pe.etapa_modelo_id
        WHERE pd.responsavel_id = ? AND lower(COALESCE(pd.status, '')) NOT IN ('resolvida', 'cancelada')
        """,
        (g.user["id"],),
    )
    missions = []
    for row in stage_rows:
        missions.append(
            {
                "kind": "stage",
                "id": row["id"],
                "project_id": row["projeto_id"],
                "title": row["etapa_nome"],
                "project": row["projeto_nome"],
                "stage": row["subetapa_ativa"] or row["etapa_nome"],
                "status": row["status"],
                "prazo": row["prazo"],
                "priority": row["prioridade"],
                "progress": row["progresso"] or 0,
                "folder": row["caminho_pasta"],
            }
        )
    for row in task_rows:
        missions.append(
            {
                "kind": "task",
                "id": row["id"],
                "project_id": row["projeto_id"],
                "title": row["titulo"],
                "project": row["projeto_nome"],
                "stage": row["etapa_nome"] or "Tarefa avulsa",
                "status": row["status"],
                "prazo": row["prazo"],
                "priority": row["prioridade"],
                "progress": 0,
                "folder": row["caminho_pasta"],
            }
        )
    for row in pending_rows:
        missions.append(
            {
                "kind": "pending",
                "id": row["id"],
                "project_id": row["projeto_id"],
                "title": row["descricao"],
                "project": row["projeto_nome"],
                "stage": row["etapa_nome"] or "Pendencia vinculada ao projeto",
                "status": row["status"],
                "prazo": row["prazo"],
                "priority": row["prioridade"],
                "progress": 0,
                "folder": row["caminho_pasta"],
                "origin": row["origem"],
            }
        )

    def mission_sort_key(mission):
        due = mission["prazo"] or "9999-12-31"
        overdue_rank = 0 if is_overdue(mission["prazo"], mission["status"]) or mission["status"] == "atrasado" else 1
        return (overdue_rank, due, PRIORITY_WEIGHT.get(mission["priority"], 3), mission["project"], mission["title"])

    missions.sort(key=mission_sort_key)
    return render_template("my_missions.html", missions=missions)


@app.route("/clients", methods=["GET", "POST"])
@login_required
def clients():
    if request.method == "POST":
        if not can_manage():
            flash("Permissao negada.", "danger")
            return redirect(url_for("clients"))
        name = request.form.get("nome", "").strip()
        if name:
            execute_db(
                "INSERT INTO clientes (nome, cpf_cnpj, telefone, email, endereco, observacoes) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    name,
                    request.form.get("cpf_cnpj", "").strip(),
                    request.form.get("telefone", "").strip(),
                    request.form.get("email", "").strip(),
                    request.form.get("endereco", "").strip(),
                    request.form.get("observacoes", "").strip(),
                ),
            )
            flash("Cliente cadastrado.", "success")
        return redirect(url_for("clients"))
    rows = query_db(
        """
        SELECT c.*, COUNT(p.id) AS projetos
        FROM clientes c
        LEFT JOIN projetos p ON p.cliente_id = c.id
        GROUP BY c.id
        ORDER BY c.nome
        """
    )
    return render_template("clients.html", clients=rows)


@app.route("/cartorios", methods=["GET", "POST"])
@login_required
def cartorios():
    if request.method == "POST":
        if not can_manage():
            flash("Permissao negada.", "danger")
            return redirect(url_for("cartorios"))
        name = request.form.get("nome", "").strip()
        if name:
            execute_db(
                "INSERT INTO cartorios (nome, cidade, uf, contato, observacoes) VALUES (?, ?, ?, ?, ?)",
                (
                    name,
                    request.form.get("cidade", "").strip(),
                    request.form.get("uf", "").strip().upper(),
                    request.form.get("contato", "").strip(),
                    request.form.get("observacoes", "").strip(),
                ),
            )
            flash("Cartorio/orgao cadastrado.", "success")
        return redirect(url_for("cartorios"))
    rows = query_db(
        """
        SELECT c.*, COUNT(p.id) AS projetos
        FROM cartorios c
        LEFT JOIN projetos p ON p.cartorio_id = c.id
        GROUP BY c.id
        ORDER BY c.nome
        """
    )
    return render_template("cartorios.html", cartorios=rows)


@app.route("/users", methods=["GET", "POST"])
@login_required
def users():
    if not can_admin():
        flash("Somente administrador pode gerenciar usuarios.", "danger")
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        name = request.form.get("nome", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("senha", "").strip() or "tecnico123"
        if name and email:
            try:
                execute_db(
                    "INSERT INTO usuarios (nome, email, senha_hash, perfil_acesso, cargo, ativo) VALUES (?, ?, ?, ?, ?, 1)",
                    (
                        name,
                        email,
                        generate_password_hash(password),
                        request.form.get("perfil_acesso", "tecnico"),
                        request.form.get("cargo", "").strip(),
                    ),
                )
                flash("Usuario cadastrado.", "success")
            except sqlite3.IntegrityError:
                flash("Ja existe usuario com este e-mail.", "danger")
        return redirect(url_for("users"))
    return render_template("users.html", users=query_db("SELECT * FROM usuarios ORDER BY ativo DESC, nome"))


@app.route("/cartorio")
@login_required
def cartorio_board():
    refresh_due_statuses()
    exigencias = query_db(
        """
        SELECT e.*, p.nome AS projeto_nome, p.id AS projeto_id, c.nome AS cartorio_nome, u.nome AS responsavel_nome
        FROM exigencias_cartorio e
        JOIN projetos p ON p.id = e.projeto_id
        LEFT JOIN cartorios c ON c.id = e.cartorio_id
        LEFT JOIN usuarios u ON u.id = e.responsavel_id
        ORDER BY
            CASE WHEN lower(e.status) = 'atrasado' THEN 0 ELSE 1 END,
            COALESCE(e.prazo_resposta, '9999-12-31')
        """
    )
    return render_template("cartorio_board.html", exigencias=exigencias)


@app.route("/reports")
@login_required
def reports():
    refresh_due_statuses()
    stage_status = query_db(
        """
        SELECT em.nome AS etapa_nome, pe.status, COUNT(*) AS total
        FROM projeto_etapas pe
        JOIN etapas_modelo em ON em.id = pe.etapa_modelo_id
        WHERE em.ativa = 1
        GROUP BY em.nome, pe.status
        ORDER BY em.nome, total DESC
        """
    )
    stage_bottlenecks = query_db(
        """
        SELECT em.nome AS etapa_nome, COUNT(*) AS total
        FROM projeto_etapas pe
        JOIN etapas_modelo em ON em.id = pe.etapa_modelo_id
        WHERE lower(pe.status) NOT IN ('concluido', 'cancelado')
          AND em.ativa = 1
          AND pe.id IN (SELECT etapa_atual_id FROM projetos WHERE etapa_atual_id IS NOT NULL)
        GROUP BY em.nome
        ORDER BY total DESC
        """
    )
    time_by_user = query_db(
        """
        SELECT u.nome AS usuario_nome, COALESCE(SUM(a.duracao_minutos), 0) AS minutos
        FROM apontamentos_tempo a
        LEFT JOIN usuarios u ON u.id = a.usuario_id
        GROUP BY u.id, u.nome
        ORDER BY minutos DESC
        """
    )
    time_by_stage = query_db(
        """
        SELECT em.nome AS etapa_nome, COALESCE(SUM(a.duracao_minutos), 0) AS minutos
        FROM apontamentos_tempo a
        LEFT JOIN projeto_etapas pe ON pe.id = a.etapa_id
        LEFT JOIN etapas_modelo em ON em.id = pe.etapa_modelo_id
        GROUP BY em.nome
        ORDER BY minutos DESC
        """
    )
    by_city = query_db("SELECT cidade, COUNT(*) AS total FROM projetos GROUP BY cidade ORDER BY total DESC")
    return render_template(
        "reports.html",
        stage_status=stage_status,
        stage_bottlenecks=stage_bottlenecks,
        time_by_user=time_by_user,
        time_by_stage=time_by_stage,
        by_city=by_city,
    )


init_db()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    debug = os.environ.get("GEOGESTAO_DEBUG", "1") == "1"
    app.run(debug=debug, use_reloader=debug, host="127.0.0.1", port=port)
