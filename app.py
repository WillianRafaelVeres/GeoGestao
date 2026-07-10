import os
from dotenv import load_dotenv
load_dotenv()
import csv
import gzip
import hashlib
import io
import json
import secrets
import smtplib
import socket
import sys
import threading
import time
from email.message import EmailMessage
import psycopg2
import psycopg2.extensions
import psycopg2.extras
import psycopg2.errors
import psycopg2.pool
import unicodedata
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from functools import wraps
from urllib.parse import quote, urlencode, urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import Flask, Response, flash, g, has_request_context, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from documental import (
    DOCUMENT_FIELD_REQUIREMENTS,
    ESTADOS_CIVIS,
    QUEM_ASSINA,
    REGIMES_CASAMENTO,
    SEXOS,
    STATUS_CADASTRO,
    TIPOS_CLIENTE,
    UFS,
    build_documento_context,
    format_cep,
    format_cnpj,
    format_cpf,
    format_phone,
    get_cadastro_completeness,
    get_cliente_pendencias,
    get_document_readiness,
    only_digits,
    parse_decimal_br,
    requires_conjuge,
    validate_cep,
    validate_cidade_uf,
    validate_cnpj,
    validate_cpf,
    validate_date,
    validate_email,
    validate_uuid_like,
)
from process_types import PROCESS_TYPES, process_type_name, resolve_process_type_key
from report_helpers import (
    calculate_stage_metrics_v2,
    calculate_process_type_metrics,
    calculate_responsible_metrics_v2,
    calculate_city_metrics_v2,
    calculate_external_actor_metrics,
    calculate_stopped_projects_v2,
    calculate_checklist_pending_report,
    build_bottleneck_suggestions_v2,
    build_operational_summary_v2,
    THRESHOLDS as REPORT_THRESHOLDS_V2,
)
from process_stage_templates import (
    APPLICABILITY_CONDITIONAL,
    APPLICABILITY_NOT_APPLICABLE,
    APPLICABILITY_OPTIONAL,
    APPLICABILITY_REQUIRED,
    PROCESS_STAGE_TEMPLATES,
    get_applicable_stages_for_process as get_config_applicable_stages_for_process,
    get_stage_template_for_process as get_config_stage_template_for_process,
)
from process_checklist_templates import (
    CHECKLIST_STATUS_DONE,
    CHECKLIST_STATUS_IN_PROGRESS,
    CHECKLIST_STATUS_NOT_APPLICABLE,
    CHECKLIST_STATUS_NOT_STARTED,
    CRITICALITY_CRITICAL,
    CRITICALITY_LOW,
    CRITICALITY_MEDIUM,
    PROCESS_CHECKLIST_TEMPLATES,
    REQUIREMENT_CONDITIONAL,
    REQUIREMENT_OPTIONAL,
    REQUIREMENT_RECOMMENDED,
    REQUIREMENT_REQUIRED,
    get_checklist_template_for_process as get_config_checklist_template_for_process,
    get_checklist_template_for_process_stage as get_config_checklist_template_for_process_stage,
)


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_URL = os.environ.get("DATABASE_URL", "")
SECRET_KEY = os.environ.get("GEOGESTAO_SECRET_KEY", "dev-change-this-secret-key")
APP_PUBLIC_URL = os.environ.get("GEOGESTAO_PUBLIC_URL", "").strip().rstrip("/")
DROPBOX_APP_KEY = os.environ.get("DROPBOX_APP_KEY", "").strip()
DROPBOX_APP_SECRET = os.environ.get("DROPBOX_APP_SECRET", "").strip()
DROPBOX_REFRESH_TOKEN = os.environ.get("DROPBOX_REFRESH_TOKEN", "").strip()
DROPBOX_PATH_ALIASES_RAW = os.environ.get(
    "DROPBOX_PATH_ALIASES",
    r"Y:\PASTAS=/SC/Pastas;Z:\PASTAS=/SC/Pastas;X:\PASTAS=/SC/Pastas",
).strip()
try:
    APP_TIMEZONE = ZoneInfo(os.environ.get("GEOGESTAO_TIMEZONE", "America/Sao_Paulo"))
except ZoneInfoNotFoundError:
    APP_TIMEZONE = timezone(timedelta(hours=-3), "America/Sao_Paulo")

STATUS_META = {
    "nao iniciado": {"label": "Nao iniciado", "color": "secondary", "tone": "muted"},
    "em andamento": {"label": "Em andamento", "color": "primary", "tone": "blue"},
    "concluido": {"label": "Concluido", "color": "success", "tone": "green"},
    "atencao": {"label": "Atencao", "color": "warning", "tone": "amber"},
    "atrasado": {"label": "Atrasado", "color": "danger", "tone": "red"},
    "aguardando externo": {"label": "Aguardando externo", "color": "purple", "tone": "purple"},
    "pronto para retirada": {"label": "Pronto para retirada", "color": "info", "tone": "blue"},
    "retrabalho": {"label": "Retrabalho", "color": "purple", "tone": "purple"},
    "nao aplicavel": {"label": "Nao aplicavel", "color": "secondary", "tone": "muted"},
    "cancelado": {"label": "Cancelado", "color": "dark", "tone": "dark"},
}

APPLICABILITY_META = {
    APPLICABILITY_REQUIRED: {"label": "Obrigatoria", "color": "primary"},
    APPLICABILITY_OPTIONAL: {"label": "Opcional", "color": "secondary"},
    APPLICABILITY_CONDITIONAL: {"label": "Condicional", "color": "warning"},
    APPLICABILITY_NOT_APPLICABLE: {"label": "Nao aplicavel", "color": "secondary"},
}

ROLE_LABELS = {
    "admin": "Administrador",
    "coordenador": "Coordenador",
    "tecnico": "Tecnico",
    "consulta": "Consulta",
}

REPRESENTATIVE_TYPES = {
    "PROCURADOR": "Procurador",
    "REPRESENTANTE": "Representante",
}

EXTERNAL_ORGAO_OPTIONS = [
    ("CARTORIO", "Cartorio"),
    ("PREFEITURA", "Prefeitura"),
    ("SIGEF", "SIGEF"),
    ("INCRA", "INCRA"),
    ("SICAR", "SICAR"),
    ("SNCR", "SNCR"),
    ("OUTRO", "Outro orgao"),
]
EXTERNAL_ORGAO_LABELS = dict(EXTERNAL_ORGAO_OPTIONS)
EXTERNAL_PROTOCOL_SCOPE = "ORGAO_EXTERNO"

FORMAS_PAGAMENTO = {
    "PIX": "PIX",
    "DINHEIRO": "Dinheiro",
    "TRANSFERENCIA": "Transferencia bancaria",
    "BOLETO": "Boleto",
    "CARTAO_CREDITO": "Cartao de credito",
    "CARTAO_DEBITO": "Cartao de debito",
    "CHEQUE": "Cheque",
    "PERMUTA": "Permuta / servicos",
    "OUTRO": "Outro",
}

CATEGORIAS_CUSTO = {
    "MATRICULA": "Matricula",
    "CERTIDAO": "Certidao",
    "TAXA": "Taxa / emolumento",
    "DESLOCAMENTO": "Deslocamento",
    "IMPRESSAO": "Impressao / copia",
    "OUTRO": "Outro custo",
}

FINANCEIRO_QUASE_PRONTO_PCT = 75

PRIORITY_WEIGHT = {"Alta": 0, "Media": 1, "Baixa": 2, "": 3, None: 3}

REPORT_THRESHOLDS = {
    "attention_days": 5,
    "bottleneck_days": 10,
    "attention_active_count": 5,
    "bottleneck_active_count": 10,
    "stopped_days": 7,
    "responsible_attention_active": 5,
    "responsible_overload_active": 12,
}

REPORT_STAGE_DEFAULT_DAYS = {
    "orcamento": 3,
    "documentos": 4,
    "analise": 3,
    "preparacao": 3,
    "medicao": 2,
    "processamento": 10,
    "escritorio": 9,
    "conferencia": 4,
    "assinaturas": 4,
    "cartorio": 14,
    "orgaoexterno": 14,
    "pendencia": 7,
    "finalizado": 1,
    "arquivado": 1,
}

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
        "checklist": ["Planta iniciada", "Memorial iniciado", "Documentacao obrigatoria revisada", "Conferencia interna", "Planta PDF", "Planta DWG/DXF", "Camadas conferidas", "Arquivo final validado", "Memorial descritivo", "ART/RRT", "Requerimento", "Anexos conferidos"],
    },
    {
        "nome": "Assinaturas",
        "ordem": 9,
        "cor": "warning",
        "checklist": ["Cliente notificado", "Assinaturas coletadas", "Reconhecimentos conferidos"],
    },
    {
        "nome": "Prefeitura",
        "ordem": 10,
        "cor": "info",
        "checklist": ["Protocolo registrado", "Exigencias acompanhadas", "Pronto para retirada", "Retirada concluida"],
    },
    {
        "nome": "Orgao externo",
        "ordem": 11,
        "cor": "danger",
        "checklist": ["Protocolo registrado", "Exigencias acompanhadas", "Pronto para retirada", "Retirada concluida"],
    },
    {
        "nome": "Pendencia",
        "ordem": 12,
        "cor": "warning",
        "checklist": ["Pendencia classificada", "Responsavel definido", "Prazo acompanhado", "Resolucao conferida"],
    },
    {
        "nome": "Finalizado",
        "ordem": 13,
        "cor": "success",
        "checklist": ["Entrega ao cliente", "Saldo recebido", "Pasta final organizada", "Backup realizado"],
    },
]

STAGE_ALIASES = {
    "campo": "medicao",
    "medicao": "medicao",
    "planta": "escritorio",
    "documentacao": "escritorio",
    "finalizacao": "finalizado",
    "finalizado": "finalizado",
    "orgaoexterno": "cartorio",
    "orgao": "cartorio",
}

PROCESS_STAGE_TO_LEGACY_STAGE = {
    "ORCAMENTO": "orcamento",
    "DOCUMENTOS": "documentos",
    "ANALISE": "analise",
    "PREPARACAO": "analise",
    "MEDICAO": "medicao",
    "PROCESSAMENTO": "processamento",
    "ESCRITORIO": "escritorio",
    "CONFERENCIA": "escritorio",
    "ASSINATURAS": "assinaturas",
    "PREFEITURA": "prefeitura",
    "ORGAO_EXTERNO": "cartorio",
    "PENDENCIAS": "pendencia",
    "ENTREGA": "finalizado",
    "FINALIZADO": "finalizado",
}

PROCESS_CHECKLIST_STAGE_ORDER = {
    "ORCAMENTO": 1,
    "DOCUMENTOS": 2,
    "ANALISE": 3,
    "PREPARACAO": 4,
    "MEDICAO": 5,
    "PROCESSAMENTO": 6,
    "ESCRITORIO": 7,
    "CONFERENCIA": 8,
    "ASSINATURAS": 9,
    "PREFEITURA": 10,
    "ORGAO_EXTERNO": 11,
    "PENDENCIAS": 12,
    "ENTREGA": 13,
    "FINALIZADO": 14,
}

PROCESS_CHECKLIST_STAGE_NAMES = {
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
    "ORGAO_EXTERNO": "Orgao externo",
    "PENDENCIAS": "Pendencias / Exigencias",
    "ENTREGA": "Entrega / Encerramento",
    "FINALIZADO": "Finalizado",
}

FUTURE_AUTOMATIONS = [
    "Criar lembrete quando o projeto entrar em Orgao externo.",
    "Criar pendencia com prazo quando houver exigencia de orgao externo.",
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
app.config.from_mapping(SECRET_KEY=SECRET_KEY, DATABASE_URL=DATABASE_URL)

_static_version_cache = {}


def _static_file_version(filename):
    cached = _static_version_cache.get(filename)
    if cached is not None:
        return cached
    try:
        version = str(int(os.stat(os.path.join(app.static_folder, filename)).st_mtime))
    except OSError:
        version = "0"
    if not app.debug:
        _static_version_cache[filename] = version
    return version


@app.url_defaults
def add_static_version(endpoint, values):
    # Anexa ?v=<mtime> a todo url_for('static', ...): o browser pode cachear
    # por um ano e ainda assim buscar a versao nova assim que o arquivo mudar.
    if endpoint == "static" and "filename" in values:
        values.setdefault("v", _static_file_version(values["filename"]))

DB_POOL_MINCONN = int(os.environ.get("GEOGESTAO_DB_POOL_MINCONN", "1"))
DB_POOL_MAXCONN = int(os.environ.get("GEOGESTAO_DB_POOL_MAXCONN", "10"))
DB_STATEMENT_TIMEOUT_MS = int(os.environ.get("GEOGESTAO_DB_STATEMENT_TIMEOUT_MS", "30000"))
DB_IDLE_PING_SECONDS = int(os.environ.get("GEOGESTAO_DB_IDLE_PING_SECONDS", "240"))
USER_CACHE_TTL_SECONDS = int(os.environ.get("GEOGESTAO_USER_CACHE_TTL_SECONDS", "60"))
PERF_LOG_ENABLED = os.environ.get("GEOGESTAO_PERF_LOG", "0") == "1"
REPORTS_CACHE_TTL_SECONDS = int(os.environ.get("GEOGESTAO_REPORTS_CACHE_TTL_SECONDS", "60"))
DUE_STATUS_REFRESH_TTL_SECONDS = int(os.environ.get("GEOGESTAO_DUE_STATUS_REFRESH_TTL_SECONDS", "300"))
LOOKUP_CACHE_TTL_SECONDS = int(os.environ.get("GEOGESTAO_LOOKUP_CACHE_TTL_SECONDS", "120"))
PASSWORD_RESET_TOKEN_MINUTES = int(os.environ.get("GEOGESTAO_PASSWORD_RESET_MINUTES", "30"))
SMTP_HOST = os.environ.get("GEOGESTAO_SMTP_HOST", "").strip()
SMTP_PORT = int(os.environ.get("GEOGESTAO_SMTP_PORT", "587"))
SMTP_USER = os.environ.get("GEOGESTAO_SMTP_USER", "").strip()
SMTP_PASSWORD = os.environ.get("GEOGESTAO_SMTP_PASSWORD", "")
SMTP_FROM = os.environ.get("GEOGESTAO_SMTP_FROM", SMTP_USER or "nao-responder@geogestao.local").strip()
SMTP_USE_TLS = os.environ.get("GEOGESTAO_SMTP_USE_TLS", "1") == "1"

_db_pool = None
_reports_cache = {"expires_at": 0.0, "value": None}
_lookup_cache = {}
_due_statuses_next_refresh = 0.0
_refreshing_due_statuses = False
_due_refresh_lock = threading.Lock()


class PgConn:
    """Wrapper pequeno em cima da conexão psycopg2 usada pelo app."""

    def __init__(self, conn, release_callback=None):
        self._conn = conn
        self._release_callback = release_callback
        self._closed = False

    def execute(self, query, args=()):
        cur = self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        _execute_cursor(cur, query, args if args else ())
        return cur

    def execute_statements(self, script):
        cur = self._conn.cursor()
        try:
            for statement in script.split(";"):
                statement = statement.strip()
                if not statement:
                    continue
                cur.execute(statement)
        finally:
            cur.close()

    def cursor(self, cursor_factory=None):
        if cursor_factory:
            return self._conn.cursor(cursor_factory=cursor_factory)
        return self._conn.cursor()

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        if self._closed:
            return
        self._closed = True
        if not self._conn.closed and self._conn.get_transaction_status() != psycopg2.extensions.TRANSACTION_STATUS_IDLE:
            self._conn.rollback()
        if self._release_callback:
            self._conn.geogestao_last_used = time.monotonic()
            self._release_callback(self._conn)
        else:
            self._conn.close()


def _record_query_time(elapsed):
    if has_request_context():
        g._query_count = getattr(g, "_query_count", 0) + 1
        g._query_time = getattr(g, "_query_time", 0.0) + elapsed


def _execute_cursor(cur, query, args=()):
    start = time.perf_counter()
    try:
        return cur.execute(query, args if args else ())
    finally:
        _record_query_time(time.perf_counter() - start)


class _AppConnection(psycopg2.extensions.connection):
    """Conexão que lembra se já foi configurada, evitando SET/commit a cada checkout."""

    geogestao_configured = False
    geogestao_last_used = 0.0


def _configure_connection(conn):
    with conn.cursor() as cur:
        cur.execute("SET statement_timeout = %s", (DB_STATEMENT_TIMEOUT_MS,))
    conn.commit()
    conn.geogestao_configured = True
    conn.geogestao_last_used = time.monotonic()


def _create_raw_connection(database_url):
    conn = psycopg2.connect(
        database_url,
        connect_timeout=10,
        sslmode="require",
        keepalives=1,
        keepalives_idle=30,
        keepalives_interval=10,
        keepalives_count=3,
        application_name="geogestao",
        connection_factory=_AppConnection,
    )
    _configure_connection(conn)
    return conn


def _get_db_pool(database_url):
    global _db_pool
    if _db_pool is None:
        _db_pool = psycopg2.pool.ThreadedConnectionPool(
            DB_POOL_MINCONN,
            DB_POOL_MAXCONN,
            dsn=database_url,
            connect_timeout=10,
            sslmode="require",
            keepalives=1,
            keepalives_idle=30,
            keepalives_interval=10,
            keepalives_count=3,
            application_name="geogestao",
            connection_factory=_AppConnection,
        )
    return _db_pool


def _checkout_pooled_connection(pool):
    conn = pool.getconn()
    try:
        if conn.closed:
            raise psycopg2.OperationalError("conexao do pool ja estava fechada")
        if not conn.geogestao_configured:
            _configure_connection(conn)
        elif time.monotonic() - conn.geogestao_last_used > DB_IDLE_PING_SECONDS:
            # Conexão ociosa há muito tempo: o pooler pode tê-la derrubado em silêncio.
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
            conn.rollback()
            conn.geogestao_last_used = time.monotonic()
        return conn
    except Exception:
        pool.putconn(conn, close=True)
        raise


def _connect_with_retry(database_url, use_pool=True):
    host = urlparse(database_url).hostname or "host indefinido"
    last_error = None
    for attempt in range(1, 4):
        try:
            if use_pool:
                pool = _get_db_pool(database_url)
                conn = _checkout_pooled_connection(pool)
                return PgConn(conn, release_callback=pool.putconn)
            return PgConn(_create_raw_connection(database_url))
        except psycopg2.pool.PoolError as exc:
            last_error = exc
            if attempt < 3:
                time.sleep(0.1 * attempt)
                continue
            raise
        except psycopg2.OperationalError as exc:
            last_error = exc
            message = str(exc)
            if "could not translate host name" in message:
                raise RuntimeError(
                    f"Nao foi possivel resolver o host do banco Supabase ({host}). "
                    "Confira se a DATABASE_URL no .env foi copiada exatamente do Supabase. "
                    "Se estiver usando a conexao direta db.<projeto>.supabase.co, tente a URL do Pooler "
                    "do Supabase, que funciona melhor em redes sem IPv6."
                ) from exc
            if "password authentication failed" in message or "tenant/user" in message:
                raise
            if attempt < 3:
                time.sleep(attempt)
                continue
            raise
        except socket.gaierror as exc:
            last_error = exc
            if attempt < 3:
                time.sleep(attempt)
                continue
            raise RuntimeError(
                f"Nao foi possivel resolver o host do banco Supabase ({host}). "
                "Confira a DATABASE_URL no .env e sua conexao com a internet."
            ) from exc
    raise last_error


def connect_db(use_pool=True):
    database_url = app.config["DATABASE_URL"]
    if not database_url:
        raise RuntimeError("DATABASE_URL nao foi configurada no arquivo .env.")
    return _connect_with_retry(database_url, use_pool=use_pool)


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


@app.before_request
def start_perf_timer():
    request_id = (request.headers.get("X-Request-ID") or "").strip()
    g.request_id = request_id[:80] if request_id else secrets.token_hex(8)
    g._request_start = time.perf_counter()
    g._query_count = 0
    g._query_time = 0.0


@app.after_request
def log_perf_metrics(response):
    if hasattr(g, "_request_start"):
        elapsed = time.perf_counter() - g._request_start
        db_ms = getattr(g, "_query_time", 0.0) * 1000
        query_count = getattr(g, "_query_count", 0)
        response.headers["X-Request-ID"] = getattr(g, "request_id", "")
        response.headers["Server-Timing"] = f"app;dur={elapsed * 1000:.1f}, db;dur={db_ms:.1f};desc=\"{query_count} queries\""
        if PERF_LOG_ENABLED:
            app.logger.info(
                "perf request_id=%s route=%s method=%s status=%s total_ms=%.1f queries=%s db_ms=%.1f",
                getattr(g, "request_id", ""),
                request.path,
                request.method,
                response.status_code,
                elapsed * 1000,
                query_count,
                db_ms,
            )
    return response


COMPRESSIBLE_MIMETYPES = {
    "text/html",
    "text/css",
    "text/plain",
    "text/csv",
    "application/javascript",
    "application/json",
    "image/svg+xml",
}


@app.after_request
def apply_response_optimizations(response):
    # Estaticos versionados (?v=mtime) podem ser cacheados como imutaveis.
    if request.endpoint == "static" and request.args.get("v"):
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    # Paginas financeiras nunca podem sair de cache/prerender/bfcache:
    # o usuario precisa ver sempre o estado atual dos pagamentos.
    if request.path.startswith("/financeiro"):
        response.headers["Cache-Control"] = "no-store"
    # Compressao gzip: as paginas maiores caem de ~130KB para ~13KB.
    if (
        response.status_code == 200
        and not response.direct_passthrough
        and response.mimetype in COMPRESSIBLE_MIMETYPES
        and not response.headers.get("Content-Encoding")
        and "gzip" in (request.headers.get("Accept-Encoding") or "").lower()
    ):
        payload = response.get_data()
        if len(payload) > 1024:
            compressed = gzip.compress(payload, compresslevel=6)
            if len(compressed) < len(payload):
                response.set_data(compressed)
                response.headers["Content-Encoding"] = "gzip"
                response.vary.add("Accept-Encoding")
    return response


def query_db(query, args=(), one=False):
    cur = get_db().execute(query, args)
    rows = cur.fetchall()
    cur.close()
    return (rows[0] if rows else None) if one else rows


def invalidate_runtime_caches():
    global _reports_cache, _lookup_cache, _due_statuses_next_refresh
    _reports_cache = {"expires_at": 0.0, "value": None}
    _lookup_cache = {}
    if not _refreshing_due_statuses:
        _due_statuses_next_refresh = 0.0


def get_cached_lookup(key, loader, ttl_seconds=None):
    ttl = LOOKUP_CACHE_TTL_SECONDS if ttl_seconds is None else ttl_seconds
    now_monotonic = time.monotonic()
    cached = _lookup_cache.get(key)
    if cached and cached["expires_at"] > now_monotonic:
        return cached["value"]
    value = loader()
    _lookup_cache[key] = {"expires_at": now_monotonic + ttl, "value": value}
    return value


def execute_db(query, args=()):
    db = get_db()
    cur = db.cursor()
    try:
        q = query.strip().rstrip(';')
        is_insert = q.upper().lstrip().startswith('INSERT')
        if is_insert and 'RETURNING' not in q.upper():
            q += ' RETURNING id'
        _execute_cursor(cur, q, args if args else ())
        db.commit()
        invalidate_runtime_caches()
        last_id = None
        if is_insert:
            try:
                row = cur.fetchone()
                last_id = row[0] if row else None
            except Exception:
                pass
        return last_id
    except Exception:
        db.rollback()
        raise
    finally:
        cur.close()


def table_columns(db, table_name):
    cur = db.cursor()
    _execute_cursor(
        cur,
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        """,
        (table_name,),
    )
    rows = cur.fetchall()
    cur.close()
    return {row[0] for row in rows}


def add_column_if_missing(db, table_name, column_name, definition):
    if column_name not in table_columns(db, table_name):
        db.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")


def drop_constraint_if_exists(db, table_name, constraint_name):
    db.execute(f"ALTER TABLE {table_name} DROP CONSTRAINT IF EXISTS {constraint_name}")


def ensure_performance_indexes(db):
    statements = [
        "CREATE INDEX IF NOT EXISTS idx_usuarios_lower_email ON usuarios (lower(email))",
        "CREATE INDEX IF NOT EXISTS idx_projetos_etapa_atual ON projetos (etapa_atual_id)",
        "CREATE INDEX IF NOT EXISTS idx_projetos_cliente_id ON projetos (cliente_id)",
        "CREATE INDEX IF NOT EXISTS idx_projetos_cartorio_id ON projetos (cartorio_id)",
        "CREATE INDEX IF NOT EXISTS idx_projetos_responsavel_geral_id ON projetos (responsavel_geral_id)",
        "CREATE INDEX IF NOT EXISTS idx_projetos_tipo_servico ON projetos (tipo_servico)",
        "CREATE INDEX IF NOT EXISTS idx_projetos_ordem ON projetos (ordem_prioridade, criado_em, id)",
        "CREATE INDEX IF NOT EXISTS idx_projeto_etapas_projeto_modelo ON projeto_etapas (projeto_id, etapa_modelo_id)",
        "CREATE INDEX IF NOT EXISTS idx_projeto_etapas_projeto_visivel ON projeto_etapas (projeto_id, show_in_project)",
        "CREATE INDEX IF NOT EXISTS idx_projeto_etapas_project_stage_key_visible ON projeto_etapas (projeto_id, stage_key, show_in_project)",
        "CREATE INDEX IF NOT EXISTS idx_projeto_etapas_prazo_status ON projeto_etapas (prazo, status)",
        "CREATE INDEX IF NOT EXISTS idx_project_checklist_stage_active_status ON project_checklist_items (project_stage_id, active, status, order_index, id)",
        "CREATE INDEX IF NOT EXISTS idx_project_checklist_project_stage_key ON project_checklist_items (project_id, stage_key, project_stage_id)",
        "CREATE INDEX IF NOT EXISTS idx_checklist_itens_etapa_concluido ON checklist_itens (projeto_etapa_id, concluido, id)",
        "CREATE INDEX IF NOT EXISTS idx_cartorio_checklist_templates_lookup ON cartorio_checklist_templates (process_type_key, cartorio_id, active, order_index, id)",
        "CREATE INDEX IF NOT EXISTS idx_cartorio_checklist_templates_cartorio_id ON cartorio_checklist_templates (cartorio_id)",
        "CREATE INDEX IF NOT EXISTS idx_cartorio_checklist_exclusions_lookup ON cartorio_checklist_exclusions (cartorio_id, process_type_key, template_id)",
        "CREATE INDEX IF NOT EXISTS idx_procuradores_cliente_principal ON procuradores (cliente_id, principal DESC, id)",
        "CREATE INDEX IF NOT EXISTS idx_tarefas_etapa_status_prazo ON tarefas (projeto_etapa_id, status, prazo)",
        "CREATE INDEX IF NOT EXISTS idx_process_stage_templates_process_active ON process_stage_templates (process_type_key, active, stage_order, id)",
        "CREATE INDEX IF NOT EXISTS idx_process_checklist_templates_process_active ON process_checklist_templates (process_type_key, active, stage_key, order_index, id)",
        "CREATE INDEX IF NOT EXISTS idx_pendencias_etapa_status_prazo ON pendencias (etapa_id, status, prazo, id)",
        "CREATE INDEX IF NOT EXISTS idx_pendencias_projeto_status ON pendencias (projeto_id, status)",
        "CREATE INDEX IF NOT EXISTS idx_eventos_projeto_tipo_criado ON eventos_historico (projeto_id, tipo_evento, criado_em DESC)",
        "CREATE INDEX IF NOT EXISTS idx_exigencias_projeto_status_prazo ON exigencias_cartorio (projeto_id, status, prazo_resposta)",
        "CREATE INDEX IF NOT EXISTS idx_exigencias_status_prazo ON exigencias_cartorio (status, prazo_resposta)",
        "CREATE INDEX IF NOT EXISTS idx_exigencias_projeto_orgao_status ON exigencias_cartorio (projeto_id, tipo_orgao, tipo_registro, status)",
        "CREATE INDEX IF NOT EXISTS idx_exigencias_etapa_status ON exigencias_cartorio (etapa_id, status)",
        "CREATE INDEX IF NOT EXISTS idx_senha_reset_tokens_usuario_criado ON senha_reset_tokens (usuario_id, criado_em DESC)",
        "CREATE INDEX IF NOT EXISTS idx_senha_reset_tokens_expires ON senha_reset_tokens (expires_at)",
        "CREATE INDEX IF NOT EXISTS idx_projeto_pagamentos_projeto ON projeto_pagamentos (projeto_id, data_pagamento DESC, id DESC)",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_projeto_pagamentos_registro_uid ON projeto_pagamentos (registro_uid)",
        "CREATE INDEX IF NOT EXISTS idx_projeto_custos_projeto ON projeto_custos (projeto_id, data_custo DESC, id DESC)",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_projeto_custos_registro_uid ON projeto_custos (registro_uid)",
    ]
    cur = db.cursor()
    try:
        for statement in statements:
            try:
                cur.execute(statement)
            except psycopg2.errors.InsufficientPrivilege:
                db.rollback()
                app.logger.warning("Sem permissao para criar indices de performance; pulei esta etapa.")
                return False
    finally:
        cur.close()
    return True


def first_row(db, query, args=()):
    return db.execute(query, args).fetchone()


def scalar(db, query, args=()):
    cur = db.cursor()
    _execute_cursor(cur, query, args if args else ())
    row = cur.fetchone()
    cur.close()
    return row[0] if row else 0


def init_db():
    os.makedirs(BASE_DIR, exist_ok=True)
    db = connect_db(use_pool=False)
    db.execute_statements(
        """
        CREATE TABLE IF NOT EXISTS usuarios (
            id SERIAL PRIMARY KEY,
            nome TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            senha_hash TEXT NOT NULL,
            perfil_acesso TEXT NOT NULL,
            ativo INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS senha_reset_tokens (
            id SERIAL PRIMARY KEY,
            usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
            token_hash TEXT NOT NULL UNIQUE,
            email TEXT,
            expires_at TEXT NOT NULL,
            used_at TEXT,
            request_ip TEXT,
            user_agent TEXT,
            criado_em TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS clientes (
            id SERIAL PRIMARY KEY,
            nome TEXT NOT NULL,
            tipo_cliente TEXT DEFAULT 'PESSOA_FISICA',
            nome_exibicao TEXT,
            quem_assina TEXT DEFAULT 'PROPRIETARIO',
            status_cadastro TEXT DEFAULT 'RASCUNHO',
            tipo_pessoa TEXT DEFAULT 'fisica',
            cpf_cnpj TEXT,
            telefone TEXT,
            email TEXT,
            inscricao_estadual TEXT,
            endereco TEXT,
            estado_civil TEXT,
            regime_casamento TEXT,
            conjuge_nome TEXT,
            conjuge_cpf_cnpj TEXT,
            conjuge_telefone TEXT,
            conjuge_email TEXT,
            tem_procurador INTEGER NOT NULL DEFAULT 0,
            procurador_nome TEXT,
            procurador_cpf_cnpj TEXT,
            procurador_telefone TEXT,
            procurador_email TEXT,
            procurador_endereco TEXT,
            observacoes TEXT,
            criado_em TEXT,
            atualizado_em TEXT
        );

        CREATE TABLE IF NOT EXISTS pessoas_fisicas (
            id SERIAL PRIMARY KEY,
            cliente_id INTEGER NOT NULL UNIQUE,
            sexo TEXT,
            nome_completo TEXT,
            nacionalidade TEXT,
            estado_civil TEXT,
            regime_casamento TEXT,
            incluir_conjuge INTEGER NOT NULL DEFAULT 0,
            profissao_ocupacao TEXT,
            rg TEXT,
            orgao_expedidor_rg TEXT,
            cpf TEXT,
            nome_pai TEXT,
            nome_mae TEXT,
            data_nascimento TEXT,
            uf_nascimento TEXT,
            cidade_nascimento TEXT,
            email TEXT,
            telefone TEXT,
            criado_em TEXT,
            atualizado_em TEXT,
            FOREIGN KEY(cliente_id) REFERENCES clientes(id)
        );

        CREATE TABLE IF NOT EXISTS conjuges (
            id SERIAL PRIMARY KEY,
            pessoa_fisica_id INTEGER NOT NULL UNIQUE,
            sexo TEXT,
            nome_completo TEXT,
            cpf TEXT,
            profissao_ocupacao TEXT,
            nacionalidade TEXT,
            rg TEXT,
            orgao_expedidor_rg TEXT,
            uf_nascimento TEXT,
            cidade_nascimento TEXT,
            data_nascimento TEXT,
            email TEXT,
            telefone TEXT,
            criado_em TEXT,
            atualizado_em TEXT,
            FOREIGN KEY(pessoa_fisica_id) REFERENCES pessoas_fisicas(id)
        );

        CREATE TABLE IF NOT EXISTS pessoas_juridicas (
            id SERIAL PRIMARY KEY,
            cliente_id INTEGER NOT NULL UNIQUE,
            razao_social TEXT,
            nome_fantasia TEXT,
            cnpj TEXT,
            logradouro TEXT,
            uf TEXT,
            cidade TEXT,
            bairro TEXT,
            cep TEXT,
            numero TEXT,
            complemento TEXT,
            email TEXT,
            telefone TEXT,
            criado_em TEXT,
            atualizado_em TEXT,
            FOREIGN KEY(cliente_id) REFERENCES clientes(id)
        );

        CREATE TABLE IF NOT EXISTS enderecos_proprietario (
            id SERIAL PRIMARY KEY,
            pessoa_fisica_id INTEGER NOT NULL UNIQUE,
            logradouro TEXT,
            uf TEXT,
            cidade TEXT,
            bairro TEXT,
            cep TEXT,
            numero TEXT,
            complemento TEXT,
            criado_em TEXT,
            atualizado_em TEXT,
            FOREIGN KEY(pessoa_fisica_id) REFERENCES pessoas_fisicas(id)
        );

        CREATE TABLE IF NOT EXISTS procuradores (
            id SERIAL PRIMARY KEY,
            cliente_id INTEGER NOT NULL,
            tipo_representacao TEXT NOT NULL DEFAULT 'PROCURADOR',
            principal INTEGER NOT NULL DEFAULT 1,
            sexo TEXT,
            nome_completo TEXT,
            estado_civil TEXT,
            regime_casamento TEXT,
            profissao_ocupacao TEXT,
            nacionalidade TEXT,
            rg TEXT,
            orgao_expedidor_rg TEXT,
            cpf TEXT,
            nome_pai TEXT,
            nome_mae TEXT,
            data_nascimento TEXT,
            uf_nascimento TEXT,
            cidade_nascimento TEXT,
            email TEXT,
            telefone TEXT,
            texto_adicional TEXT,
            logradouro TEXT,
            uf TEXT,
            cidade TEXT,
            bairro TEXT,
            cep TEXT,
            numero TEXT,
            complemento TEXT,
            criado_em TEXT,
            atualizado_em TEXT,
            FOREIGN KEY(cliente_id) REFERENCES clientes(id)
        );

        CREATE TABLE IF NOT EXISTS imoveis (
            id SERIAL PRIMARY KEY,
            nome_imovel TEXT,
            nome_terreno TEXT,
            cartorio_comarca TEXT,
            cns_cartorio TEXT,
            tipo_certidao TEXT,
            numero_certidao TEXT,
            estado_imovel TEXT,
            cidade_imovel TEXT,
            localidade_denominacao TEXT,
            valor_imovel_terra_nua DOUBLE PRECISION,
            area_antiga_m2 DOUBLE PRECISION,
            nova_area_m2 DOUBLE PRECISION,
            perimetro_m DOUBLE PRECISION,
            codigo_certificacao_sigef TEXT,
            codigo_sncr TEXT,
            estrada_acesso TEXT,
            ponto_referencia TEXT,
            distancia_ponto_referencia_km DOUBLE PRECISION,
            observacoes TEXT,
            criado_em TEXT,
            atualizado_em TEXT
        );

        CREATE TABLE IF NOT EXISTS clientes_imoveis (
            id SERIAL PRIMARY KEY,
            cliente_id INTEGER NOT NULL,
            imovel_id INTEGER NOT NULL,
            papel TEXT DEFAULT 'PROPRIETARIO',
            percentual_participacao DOUBLE PRECISION,
            principal INTEGER NOT NULL DEFAULT 0,
            criado_em TEXT,
            atualizado_em TEXT,
            FOREIGN KEY(cliente_id) REFERENCES clientes(id),
            FOREIGN KEY(imovel_id) REFERENCES imoveis(id)
        );

        CREATE TABLE IF NOT EXISTS vertices_imovel (
            id SERIAL PRIMARY KEY,
            imovel_id INTEGER NOT NULL,
            ordem INTEGER NOT NULL,
            codigo_vertice TEXT,
            longitude TEXT,
            latitude TEXT,
            altitude_m DOUBLE PRECISION,
            codigo_vertice_destino TEXT,
            azimute TEXT,
            distancia_m DOUBLE PRECISION,
            confrontacao TEXT,
            criado_em TEXT,
            atualizado_em TEXT,
            FOREIGN KEY(imovel_id) REFERENCES imoveis(id)
        );

        CREATE TABLE IF NOT EXISTS document_field_requirements (
            id SERIAL PRIMARY KEY,
            tipo_documento TEXT NOT NULL,
            campo TEXT NOT NULL,
            obrigatorio INTEGER NOT NULL DEFAULT 1,
            origem TEXT,
            label TEXT,
            mensagem_erro TEXT
        );

        CREATE TABLE IF NOT EXISTS cartorios (
            id SERIAL PRIMARY KEY,
            nome TEXT NOT NULL,
            cns TEXT,
            cidade TEXT,
            uf TEXT,
            contato TEXT,
            email TEXT,
            telefone TEXT,
            whatsapp TEXT,
            oficial TEXT,
            observacoes TEXT
        );

        CREATE TABLE IF NOT EXISTS etapas_modelo (
            id SERIAL PRIMARY KEY,
            nome TEXT NOT NULL,
            ordem INTEGER NOT NULL,
            cor_padrao TEXT NOT NULL,
            ativa INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS tipos_processo (
            id SERIAL PRIMARY KEY,
            chave TEXT NOT NULL UNIQUE,
            nome TEXT NOT NULL,
            descricao TEXT,
            categoria TEXT,
            usa_campo TEXT,
            usa_cartorio TEXT,
            usa_orgao_externo TEXT,
            possui_documentos_especificos INTEGER NOT NULL DEFAULT 0,
            ativo INTEGER NOT NULL DEFAULT 1,
            ordem INTEGER NOT NULL DEFAULT 999,
            criado_em TEXT,
            atualizado_em TEXT
        );

        CREATE TABLE IF NOT EXISTS process_stage_templates (
            id SERIAL PRIMARY KEY,
            process_type_key TEXT NOT NULL,
            stage_key TEXT NOT NULL,
            stage_name TEXT NOT NULL,
            stage_order INTEGER NOT NULL,
            applicability TEXT NOT NULL,
            description TEXT,
            default_responsible_role TEXT,
            default_deadline_days INTEGER,
            can_skip INTEGER NOT NULL DEFAULT 0,
            blocks_completion INTEGER NOT NULL DEFAULT 0,
            show_in_matrix INTEGER NOT NULL DEFAULT 1,
            show_in_project INTEGER NOT NULL DEFAULT 1,
            external_actor_type TEXT,
            notes TEXT,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT,
            updated_at TEXT,
            UNIQUE(process_type_key, stage_key),
            FOREIGN KEY(process_type_key) REFERENCES tipos_processo(chave)
        );

        CREATE TABLE IF NOT EXISTS process_checklist_templates (
            id SERIAL PRIMARY KEY,
            process_type_key TEXT NOT NULL,
            stage_key TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            order_index INTEGER NOT NULL DEFAULT 0,
            requirement_level TEXT NOT NULL,
            criticality TEXT NOT NULL,
            default_responsible_role TEXT,
            blocks_stage_completion INTEGER NOT NULL DEFAULT 0,
            blocks_process_completion INTEGER NOT NULL DEFAULT 0,
            requires_attachment INTEGER NOT NULL DEFAULT 0,
            allows_observation INTEGER NOT NULL DEFAULT 1,
            condition_text TEXT,
            help_text TEXT,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT,
            updated_at TEXT,
            UNIQUE(process_type_key, stage_key, title),
            FOREIGN KEY(process_type_key) REFERENCES tipos_processo(chave)
        );

        CREATE TABLE IF NOT EXISTS projetos (
            id SERIAL PRIMARY KEY,
            codigo TEXT NOT NULL,
            nome TEXT NOT NULL,
            proprietario TEXT,
            cliente_id INTEGER,
            cidade TEXT,
            uf TEXT,
            cartorio_id INTEGER,
            tipo_servico TEXT,
            servicos_adicionais TEXT,
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
            id SERIAL PRIMARY KEY,
            projeto_id INTEGER NOT NULL,
            etapa_modelo_id INTEGER NOT NULL,
            process_type_key TEXT,
            stage_key TEXT,
            stage_name TEXT,
            stage_order INTEGER,
            applicability TEXT,
            status TEXT NOT NULL,
            responsavel_id INTEGER,
            data_inicio TEXT,
            data_fim TEXT,
            prazo TEXT,
            progresso INTEGER DEFAULT 0,
            observacoes TEXT,
            workflow_active INTEGER NOT NULL DEFAULT 1,
            can_skip INTEGER NOT NULL DEFAULT 0,
            blocks_completion INTEGER NOT NULL DEFAULT 0,
            show_in_matrix INTEGER NOT NULL DEFAULT 1,
            show_in_project INTEGER NOT NULL DEFAULT 1,
            external_actor_type TEXT,
            template_stage_id INTEGER,
            stage_description TEXT,
            model_notes TEXT,
            FOREIGN KEY(projeto_id) REFERENCES projetos(id),
            FOREIGN KEY(etapa_modelo_id) REFERENCES etapas_modelo(id),
            FOREIGN KEY(responsavel_id) REFERENCES usuarios(id)
        );

        CREATE TABLE IF NOT EXISTS tarefas (
            id SERIAL PRIMARY KEY,
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
            id SERIAL PRIMARY KEY,
            projeto_etapa_id INTEGER,
            titulo TEXT NOT NULL,
            concluido INTEGER DEFAULT 0,
            concluido_por INTEGER,
            concluido_em TEXT,
            FOREIGN KEY(projeto_etapa_id) REFERENCES projeto_etapas(id),
            FOREIGN KEY(concluido_por) REFERENCES usuarios(id)
        );

        CREATE TABLE IF NOT EXISTS project_checklist_items (
            id SERIAL PRIMARY KEY,
            project_id INTEGER NOT NULL,
            project_stage_id INTEGER,
            template_id INTEGER,
            process_type_key TEXT NOT NULL,
            stage_key TEXT NOT NULL,
            stage_name TEXT,
            title TEXT NOT NULL,
            description TEXT,
            status TEXT NOT NULL DEFAULT 'NAO_INICIADO',
            requirement_level TEXT NOT NULL,
            criticality TEXT NOT NULL,
            responsible_id INTEGER,
            responsible_name TEXT,
            due_date TEXT,
            completed_at TEXT,
            completed_by INTEGER,
            observation TEXT,
            attachment_path TEXT,
            blocks_stage_completion INTEGER NOT NULL DEFAULT 0,
            blocks_process_completion INTEGER NOT NULL DEFAULT 0,
            requires_attachment INTEGER NOT NULL DEFAULT 0,
            allows_observation INTEGER NOT NULL DEFAULT 1,
            condition_text TEXT,
            help_text TEXT,
            order_index INTEGER NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT,
            updated_at TEXT,
            UNIQUE(project_id, process_type_key, stage_key, title),
            FOREIGN KEY(project_id) REFERENCES projetos(id),
            FOREIGN KEY(project_stage_id) REFERENCES projeto_etapas(id),
            FOREIGN KEY(template_id) REFERENCES process_checklist_templates(id),
            FOREIGN KEY(responsible_id) REFERENCES usuarios(id),
            FOREIGN KEY(completed_by) REFERENCES usuarios(id)
        );

        CREATE TABLE IF NOT EXISTS cartorio_checklist_templates (
            id SERIAL PRIMARY KEY,
            cartorio_id INTEGER,
            process_type_key TEXT NOT NULL,
            title TEXT NOT NULL,
            modelo_referencia TEXT,
            observacoes TEXT,
            order_index INTEGER NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY(cartorio_id) REFERENCES cartorios(id)
        );

        CREATE TABLE IF NOT EXISTS cartorio_checklist_exclusions (
            id SERIAL PRIMARY KEY,
            cartorio_id INTEGER NOT NULL,
            process_type_key TEXT NOT NULL,
            template_id INTEGER NOT NULL,
            created_at TEXT,
            UNIQUE(cartorio_id, process_type_key, template_id),
            FOREIGN KEY(cartorio_id) REFERENCES cartorios(id),
            FOREIGN KEY(template_id) REFERENCES cartorio_checklist_templates(id)
        );

        CREATE TABLE IF NOT EXISTS eventos_historico (
            id SERIAL PRIMARY KEY,
            projeto_id INTEGER,
            usuario_id INTEGER,
            tipo_evento TEXT,
            descricao TEXT,
            criado_em TEXT,
            FOREIGN KEY(projeto_id) REFERENCES projetos(id),
            FOREIGN KEY(usuario_id) REFERENCES usuarios(id)
        );

        CREATE TABLE IF NOT EXISTS exigencias_cartorio (
            id SERIAL PRIMARY KEY,
            projeto_id INTEGER NOT NULL,
            cartorio_id INTEGER,
            etapa_id INTEGER,
            tipo_orgao TEXT NOT NULL DEFAULT 'CARTORIO',
            tipo_registro TEXT NOT NULL DEFAULT 'exigencia',
            data_protocolo TEXT,
            numero_protocolo TEXT,
            data_recebimento TEXT,
            prazo_resposta TEXT,
            descricao TEXT NOT NULL,
            status TEXT NOT NULL,
            responsavel_id INTEGER,
            data_pronto_retirada TEXT,
            data_retirada TEXT,
            observacoes TEXT,
            criado_em TEXT,
            atualizado_em TEXT,
            FOREIGN KEY(projeto_id) REFERENCES projetos(id),
            FOREIGN KEY(cartorio_id) REFERENCES cartorios(id),
            FOREIGN KEY(etapa_id) REFERENCES projeto_etapas(id),
            FOREIGN KEY(responsavel_id) REFERENCES usuarios(id)
        );

        CREATE TABLE IF NOT EXISTS apontamentos_tempo (
            id SERIAL PRIMARY KEY,
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
            id SERIAL PRIMARY KEY,
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
            id SERIAL PRIMARY KEY,
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
            id SERIAL PRIMARY KEY,
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

        CREATE TABLE IF NOT EXISTS project_stage_history (
            id SERIAL PRIMARY KEY,
            project_id INTEGER NOT NULL,
            stage_id INTEGER,
            stage_key TEXT,
            stage_name TEXT NOT NULL,
            entered_at TEXT NOT NULL,
            exited_at TEXT,
            responsible_id INTEGER,
            responsible_name TEXT,
            reason TEXT,
            created_at TEXT,
            FOREIGN KEY(project_id) REFERENCES projetos(id),
            FOREIGN KEY(stage_id) REFERENCES projeto_etapas(id),
            FOREIGN KEY(responsible_id) REFERENCES usuarios(id)
        );

        CREATE TABLE IF NOT EXISTS projeto_pagamentos (
            id SERIAL PRIMARY KEY,
            projeto_id INTEGER NOT NULL,
            valor DOUBLE PRECISION NOT NULL,
            forma_pagamento TEXT,
            data_pagamento TEXT,
            observacoes TEXT,
            criado_em TEXT NOT NULL,
            usuario_id INTEGER,
            registro_uid TEXT
        );

        CREATE TABLE IF NOT EXISTS projeto_custos (
            id SERIAL PRIMARY KEY,
            projeto_id INTEGER NOT NULL,
            descricao TEXT NOT NULL,
            categoria TEXT,
            valor DOUBLE PRECISION NOT NULL,
            data_custo TEXT,
            observacoes TEXT,
            status TEXT NOT NULL DEFAULT 'a_cobrar',
            criado_em TEXT NOT NULL,
            usuario_id INTEGER,
            registro_uid TEXT
        );
        """
    )

    add_column_if_missing(db, "usuarios", "cargo", "TEXT")
    add_column_if_missing(db, "projetos", "proprietario", "TEXT")
    add_column_if_missing(db, "projetos", "etapa_atual_id", "INTEGER")
    add_column_if_missing(db, "projetos", "observacoes", "TEXT")
    add_column_if_missing(db, "projetos", "atualizado_em", "TEXT")
    add_column_if_missing(db, "projetos", "tipo_servico_legado", "TEXT")
    add_column_if_missing(db, "projetos", "servicos_adicionais", "TEXT")
    add_column_if_missing(db, "clientes", "tipo_pessoa", "TEXT DEFAULT 'fisica'")
    add_column_if_missing(db, "clientes", "tipo_cliente", "TEXT DEFAULT 'PESSOA_FISICA'")
    add_column_if_missing(db, "clientes", "nome_exibicao", "TEXT")
    add_column_if_missing(db, "clientes", "quem_assina", "TEXT DEFAULT 'PROPRIETARIO'")
    add_column_if_missing(db, "clientes", "status_cadastro", "TEXT DEFAULT 'RASCUNHO'")
    add_column_if_missing(db, "clientes", "inscricao_estadual", "TEXT")
    add_column_if_missing(db, "clientes", "estado_civil", "TEXT")
    add_column_if_missing(db, "clientes", "regime_casamento", "TEXT")
    add_column_if_missing(db, "clientes", "conjuge_nome", "TEXT")
    add_column_if_missing(db, "clientes", "conjuge_cpf_cnpj", "TEXT")
    add_column_if_missing(db, "clientes", "conjuge_telefone", "TEXT")
    add_column_if_missing(db, "clientes", "conjuge_email", "TEXT")
    add_column_if_missing(db, "clientes", "tem_procurador", "INTEGER NOT NULL DEFAULT 0")
    add_column_if_missing(db, "clientes", "procurador_nome", "TEXT")
    add_column_if_missing(db, "clientes", "procurador_cpf_cnpj", "TEXT")
    add_column_if_missing(db, "clientes", "procurador_telefone", "TEXT")
    add_column_if_missing(db, "clientes", "procurador_email", "TEXT")
    add_column_if_missing(db, "clientes", "procurador_endereco", "TEXT")
    add_column_if_missing(db, "clientes", "criado_em", "TEXT")
    add_column_if_missing(db, "clientes", "atualizado_em", "TEXT")
    add_column_if_missing(db, "cartorios", "cns", "TEXT")
    add_column_if_missing(db, "cartorios", "email", "TEXT")
    add_column_if_missing(db, "cartorios", "telefone", "TEXT")
    add_column_if_missing(db, "cartorios", "whatsapp", "TEXT")
    add_column_if_missing(db, "cartorios", "oficial", "TEXT")
    add_column_if_missing(db, "cartorio_checklist_templates", "modelo_referencia", "TEXT")
    add_column_if_missing(db, "cartorio_checklist_templates", "observacoes", "TEXT")
    add_column_if_missing(db, "conjuges", "email", "TEXT")
    add_column_if_missing(db, "conjuges", "telefone", "TEXT")
    add_column_if_missing(db, "procuradores", "telefone", "TEXT")
    add_column_if_missing(db, "procuradores", "tipo_representacao", "TEXT NOT NULL DEFAULT 'PROCURADOR'")
    add_column_if_missing(db, "procuradores", "principal", "INTEGER NOT NULL DEFAULT 1")
    drop_constraint_if_exists(db, "procuradores", "procuradores_cliente_id_key")
    add_column_if_missing(db, "projetos", "valor", "DOUBLE PRECISION")
    add_column_if_missing(db, "projetos", "ordem_prioridade", "INTEGER")
    add_column_if_missing(db, "projeto_etapas", "subetapa_ativa", "TEXT")
    add_column_if_missing(db, "projeto_etapas", "atraso_origem", "TEXT")
    add_column_if_missing(db, "projeto_etapas", "process_type_key", "TEXT")
    add_column_if_missing(db, "projeto_etapas", "stage_key", "TEXT")
    add_column_if_missing(db, "projeto_etapas", "stage_name", "TEXT")
    add_column_if_missing(db, "projeto_etapas", "stage_order", "INTEGER")
    add_column_if_missing(db, "projeto_etapas", "applicability", "TEXT")
    add_column_if_missing(db, "projeto_etapas", "workflow_active", "INTEGER NOT NULL DEFAULT 1")
    add_column_if_missing(db, "projeto_etapas", "can_skip", "INTEGER NOT NULL DEFAULT 0")
    add_column_if_missing(db, "projeto_etapas", "blocks_completion", "INTEGER NOT NULL DEFAULT 0")
    add_column_if_missing(db, "projeto_etapas", "show_in_matrix", "INTEGER NOT NULL DEFAULT 1")
    add_column_if_missing(db, "projeto_etapas", "show_in_project", "INTEGER NOT NULL DEFAULT 1")
    add_column_if_missing(db, "projeto_etapas", "external_actor_type", "TEXT")
    add_column_if_missing(db, "projeto_etapas", "template_stage_id", "INTEGER")
    add_column_if_missing(db, "projeto_etapas", "stage_description", "TEXT")
    add_column_if_missing(db, "projeto_etapas", "model_notes", "TEXT")
    add_column_if_missing(db, "tarefas", "data_inicio", "TEXT")
    add_column_if_missing(db, "tarefas", "concluido_em", "TEXT")
    add_column_if_missing(db, "tarefas", "comentarios", "TEXT")
    add_column_if_missing(db, "project_stage_history", "stage_key", "TEXT")
    add_column_if_missing(db, "project_stage_history", "responsible_name", "TEXT")
    add_column_if_missing(db, "project_stage_history", "reason", "TEXT")
    add_column_if_missing(db, "exigencias_cartorio", "etapa_id", "INTEGER")
    add_column_if_missing(db, "exigencias_cartorio", "tipo_orgao", "TEXT NOT NULL DEFAULT 'CARTORIO'")
    add_column_if_missing(db, "exigencias_cartorio", "tipo_registro", "TEXT NOT NULL DEFAULT 'exigencia'")
    add_column_if_missing(db, "exigencias_cartorio", "data_protocolo", "TEXT")
    add_column_if_missing(db, "exigencias_cartorio", "numero_protocolo", "TEXT")
    add_column_if_missing(db, "exigencias_cartorio", "data_pronto_retirada", "TEXT")
    add_column_if_missing(db, "exigencias_cartorio", "data_retirada", "TEXT")
    add_column_if_missing(db, "exigencias_cartorio", "observacoes", "TEXT")
    seed_process_types(db)
    seed_process_stage_templates(db)
    seed_process_checklist_templates(db)
    seed_initial_data(db)
    seed_document_requirements(db)
    normalize_legacy_project_process_types(db)
    migrate_legacy_clients(db)
    normalize_stage_models(db)
    ensure_project_structure(db)
    ensure_project_checklists(db)
    ensure_project_stage_history(db)
    initialize_project_order(db)
    db.commit()
    ensure_performance_indexes(db)
    db.commit()
    db.close()


def seed_document_requirements(db):
    if scalar(db, "SELECT COUNT(*) FROM document_field_requirements") > 0:
        return
    for tipo_documento, requirements in DOCUMENT_FIELD_REQUIREMENTS.items():
        for campo, label, mensagem in requirements:
            origem = campo.split(".")[0]
            db.execute(
                """
                INSERT INTO document_field_requirements
                    (tipo_documento, campo, obrigatorio, origem, label, mensagem_erro)
                VALUES (%s, %s, 1, %s, %s, %s)
                """,
                (tipo_documento, campo, origem, label, mensagem),
            )


def seed_process_types(db):
    now = app_now_iso()
    for item in PROCESS_TYPES:
        existing = first_row(db, "SELECT id FROM tipos_processo WHERE chave = %s", (item["key"],))
        values = (
            item["key"],
            item["nome"],
            item["descricao"],
            item["categoria"],
            item["usa_campo"],
            item["usa_cartorio"],
            item["usa_orgao_externo"],
            1 if item["possui_documentos_especificos"] else 0,
            1 if item["ativo"] else 0,
            item["ordem"],
            now,
        )
        if existing:
            db.execute(
                """
                UPDATE tipos_processo
                SET nome = %s, descricao = %s, categoria = %s, usa_campo = %s, usa_cartorio = %s,
                    usa_orgao_externo = %s, possui_documentos_especificos = %s, ativo = %s, ordem = %s, atualizado_em = %s
                WHERE chave = %s
                """,
                values[1:] + (item["key"],),
            )
        else:
            db.execute(
                """
                INSERT INTO tipos_processo
                    (chave, nome, descricao, categoria, usa_campo, usa_cartorio, usa_orgao_externo,
                     possui_documentos_especificos, ativo, ordem, criado_em, atualizado_em)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                values + (now,),
            )


def seed_process_stage_templates(db):
    now = app_now_iso()
    for process_type_key, stage_templates in PROCESS_STAGE_TEMPLATES.items():
        for template in stage_templates:
            existing = first_row(
                db,
                """
                SELECT id
                FROM process_stage_templates
                WHERE process_type_key = %s AND stage_key = %s
                """,
                (process_type_key, template["stage_key"]),
            )
            values = (
                process_type_key,
                template["stage_key"],
                template["stage_name"],
                template["stage_order"],
                template["applicability"],
                template["description"],
                template["default_responsible_role"],
                template["default_deadline_days"],
                1 if template["can_skip"] else 0,
                1 if template["blocks_completion"] else 0,
                1 if template["show_in_matrix"] else 0,
                1 if template["show_in_project"] else 0,
                template["external_actor_type"],
                template["notes"],
                1 if template["active"] else 0,
                now,
            )
            if existing:
                db.execute(
                    """
                    UPDATE process_stage_templates
                    SET stage_name = %s, stage_order = %s, applicability = %s, description = %s,
                        default_responsible_role = %s, default_deadline_days = %s, can_skip = %s,
                        blocks_completion = %s, show_in_matrix = %s, show_in_project = %s,
                        external_actor_type = %s, notes = %s, active = %s, updated_at = %s
                    WHERE process_type_key = %s AND stage_key = %s
                    """,
                    values[2:] + (process_type_key, template["stage_key"]),
                )
            else:
                db.execute(
                    """
                    INSERT INTO process_stage_templates
                        (process_type_key, stage_key, stage_name, stage_order, applicability, description,
                         default_responsible_role, default_deadline_days, can_skip, blocks_completion,
                         show_in_matrix, show_in_project, external_actor_type, notes, active, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    values + (now,),
                )


def seed_process_checklist_templates(db):
    now = app_now_iso()
    for process_type_key, checklist_templates in PROCESS_CHECKLIST_TEMPLATES.items():
        for template in checklist_templates:
            existing = first_row(
                db,
                """
                SELECT id
                FROM process_checklist_templates
                WHERE process_type_key = %s AND stage_key = %s AND title = %s
                """,
                (process_type_key, template["stage_key"], template["title"]),
            )
            values = (
                process_type_key,
                template["stage_key"],
                template["title"],
                template["description"],
                template["order_index"],
                template["requirement_level"],
                template["criticality"],
                template["default_responsible_role"],
                1 if template["blocks_stage_completion"] else 0,
                1 if template["blocks_process_completion"] else 0,
                1 if template["requires_attachment"] else 0,
                1 if template["allows_observation"] else 0,
                template["condition_text"],
                template["help_text"],
                1 if template["active"] else 0,
                now,
            )
            if existing:
                db.execute(
                    """
                    UPDATE process_checklist_templates
                    SET description = %s, order_index = %s, requirement_level = %s, criticality = %s,
                        default_responsible_role = %s, blocks_stage_completion = %s, blocks_process_completion = %s,
                        requires_attachment = %s, allows_observation = %s, condition_text = %s, help_text = %s,
                        active = %s, updated_at = %s
                    WHERE process_type_key = %s AND stage_key = %s AND title = %s
                    """,
                    values[3:] + (process_type_key, template["stage_key"], template["title"]),
                )
            else:
                db.execute(
                    """
                    INSERT INTO process_checklist_templates
                        (process_type_key, stage_key, title, description, order_index, requirement_level,
                         criticality, default_responsible_role, blocks_stage_completion, blocks_process_completion,
                         requires_attachment, allows_observation, condition_text, help_text, active, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    values + (now,),
                )


def normalize_legacy_project_process_types(db):
    rows = db.execute("SELECT id, tipo_servico, tipo_servico_legado FROM projetos").fetchall()
    for row in rows:
        current = (row["tipo_servico"] or "").strip()
        legacy_text = (row["tipo_servico_legado"] or "").strip()
        if not current:
            db.execute(
                "UPDATE projetos SET tipo_servico = %s, tipo_servico_legado = COALESCE(tipo_servico_legado, %s) WHERE id = %s",
                ("OUTRO", "", row["id"]),
            )
            continue
        if current == "OUTRO" and legacy_text:
            resolved_legacy = resolve_process_type_key(legacy_text)
            if resolved_legacy != "OUTRO":
                db.execute(
                    "UPDATE projetos SET tipo_servico = %s WHERE id = %s",
                    (resolved_legacy, row["id"]),
                )
            continue
        resolved = resolve_process_type_key(current)
        if current == resolved:
            continue
        legacy = legacy_text or current
        db.execute(
            "UPDATE projetos SET tipo_servico = %s, tipo_servico_legado = %s WHERE id = %s",
            (resolved, legacy, row["id"]),
        )


def migrate_legacy_clients(db):
    now = app_now_iso()
    rows = db.execute("SELECT * FROM clientes").fetchall()
    for client in rows:
        tipo_cliente = client["tipo_cliente"] or ("PESSOA_JURIDICA" if client["tipo_pessoa"] == "juridica" else "PESSOA_FISICA")
        quem_assina = "PROCURADOR" if tipo_cliente == "PESSOA_JURIDICA" or client["tem_procurador"] else (client["quem_assina"] or "PROPRIETARIO")
        nome_exibicao = client["nome_exibicao"] or client["nome"]
        db.execute(
            """
            UPDATE clientes
            SET tipo_cliente = %s, nome_exibicao = %s, quem_assina = %s, status_cadastro = COALESCE(status_cadastro, 'RASCUNHO'),
                criado_em = COALESCE(criado_em, %s), atualizado_em = COALESCE(atualizado_em, %s)
            WHERE id = %s
            """,
            (tipo_cliente, nome_exibicao, quem_assina, now, now, client["id"]),
        )

        if tipo_cliente == "PESSOA_JURIDICA":
            if not first_row(db, "SELECT id FROM pessoas_juridicas WHERE cliente_id = %s", (client["id"],)):
                db.execute(
                    """
                    INSERT INTO pessoas_juridicas
                        (cliente_id, razao_social, cnpj, email, telefone, criado_em, atualizado_em)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (client["id"], client["nome"], only_digits(client["cpf_cnpj"]), client["email"], client["telefone"], now, now),
                )
        else:
            pf = first_row(db, "SELECT id FROM pessoas_fisicas WHERE cliente_id = %s", (client["id"],))
            if not pf:
                pf_id = db.execute(
                    """
                    INSERT INTO pessoas_fisicas
                        (cliente_id, nome_completo, estado_civil, regime_casamento, cpf, email, telefone, criado_em, atualizado_em)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        client["id"],
                        client["nome"],
                        legacy_estado_civil(client["estado_civil"]),
                        legacy_regime_casamento(client["regime_casamento"]),
                        only_digits(client["cpf_cnpj"]),
                        client["email"],
                        client["telefone"],
                        now,
                        now,
                    ),
                ).fetchone()["id"]
            else:
                pf_id = pf["id"]
            if client["endereco"] and not first_row(db, "SELECT id FROM enderecos_proprietario WHERE pessoa_fisica_id = %s", (pf_id,)):
                db.execute(
                    """
                    INSERT INTO enderecos_proprietario
                        (pessoa_fisica_id, logradouro, criado_em, atualizado_em)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (pf_id, client["endereco"], now, now),
                )
            if client["conjuge_nome"] and not first_row(db, "SELECT id FROM conjuges WHERE pessoa_fisica_id = %s", (pf_id,)):
                db.execute(
                    """
                    INSERT INTO conjuges
                        (pessoa_fisica_id, nome_completo, cpf, criado_em, atualizado_em)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (pf_id, client["conjuge_nome"], only_digits(client["conjuge_cpf_cnpj"]), now, now),
                )
        if client["procurador_nome"] and not first_row(db, "SELECT id FROM procuradores WHERE cliente_id = %s", (client["id"],)):
            db.execute(
                """
                INSERT INTO procuradores
                    (cliente_id, nome_completo, cpf, email, telefone, logradouro, criado_em, atualizado_em)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    client["id"],
                    client["procurador_nome"],
                    only_digits(client["procurador_cpf_cnpj"]),
                    client["procurador_email"],
                    client["procurador_telefone"],
                    client["procurador_endereco"],
                    now,
                    now,
                ),
            )


def legacy_estado_civil(value):
    mapping = {
        "solteiro": "SOLTEIRO",
        "casado": "CASADO",
        "divorciado": "DIVORCIADO",
        "viuvo": "VIUVO",
        "viúvo": "VIUVO",
        "separado": "SEPARADO_JUDICIALMENTE",
        "uniao_estavel": "UNIAO_ESTAVEL",
    }
    return mapping.get((value or "").lower(), value or None)


def legacy_regime_casamento(value):
    mapping = {
        "comunhao_parcial": "COMUNHAO_PARCIAL",
        "comunhao_parcial_apos_6515": "COMUNHAO_PARCIAL_APOS_6515",
        "comunhao_parcial_apos_lei_6515_77": "COMUNHAO_PARCIAL_APOS_6515",
        "comunhao": "COMUNHAO_BENS",
        "comunhao_bens": "COMUNHAO_BENS",
        "comunhao_de_bens": "COMUNHAO_BENS",
        "comunhao_universal": "COMUNHAO_UNIVERSAL",
        "comunhao_universal_antes_6515": "COMUNHAO_UNIVERSAL_ANTES_6515",
        "comunhao_universal_antes_lei_6515_77": "COMUNHAO_UNIVERSAL_ANTES_6515",
        "comunhao_de_bens_antes_6515": "COMUNHAO_UNIVERSAL_ANTES_6515",
        "comunhao_de_bens_anterior_lei_6515_77": "COMUNHAO_UNIVERSAL_ANTES_6515",
        "separacao_total": "SEPARACAO_TOTAL",
        "separacao_convencional": "SEPARACAO_TOTAL",
        "separacao_obrigatoria": "SEPARACAO_OBRIGATORIA",
        "separacao_legal": "SEPARACAO_OBRIGATORIA",
        "participacao_acertos": "PARTICIPACAO_FINAL_AQUESTOS",
        "participacao_final_aquestos": "PARTICIPACAO_FINAL_AQUESTOS",
        "outro_pacto_antenupcial": "OUTRO_PACTO_ANTENUPCIAL",
    }
    return mapping.get((value or "").lower(), value or None)


def seed_initial_data(db):
    if scalar(db, "SELECT COUNT(*) FROM usuarios") == 0:
        admin_email = os.environ.get("GEOGESTAO_ADMIN_EMAIL", "").strip().lower()
        admin_password = os.environ.get("GEOGESTAO_ADMIN_PASSWORD", "").strip()
        admin_name = os.environ.get("GEOGESTAO_ADMIN_NAME", "Administrador").strip() or "Administrador"
        if admin_email and admin_password:
            db.execute(
                """
                INSERT INTO usuarios (nome, email, senha_hash, perfil_acesso, cargo, ativo)
                VALUES (%s, %s, %s, 'admin', 'Administrador', 1)
                """,
                (admin_name, admin_email, generate_password_hash(admin_password)),
            )

    if scalar(db, "SELECT COUNT(*) FROM etapas_modelo") == 0:
        db.executemany(
            "INSERT INTO etapas_modelo (nome, ordem, cor_padrao, ativa) VALUES (%s, %s, %s, 1)",
            [(stage["nome"], stage["ordem"], stage["cor"]) for stage in DEFAULT_STAGES],
        )
    else:
        for stage in DEFAULT_STAGES:
            exists = first_row(db, "SELECT id FROM etapas_modelo WHERE lower(nome) = lower(%s)", [stage["nome"]])
            if not exists:
                db.execute(
                    "INSERT INTO etapas_modelo (nome, ordem, cor_padrao, ativa) VALUES (%s, %s, %s, 1)",
                    (stage["nome"], stage["ordem"], stage["cor"]),
                )


def initialize_project_order(db):
    """Atribui ordem_prioridade sequencial a projetos que ainda nao tem valor definido."""
    unordered = db.execute(
        """
        SELECT id FROM projetos WHERE ordem_prioridade IS NULL
        ORDER BY
            CASE prioridade WHEN 'Alta' THEN 0 WHEN 'Media' THEN 1 WHEN 'Baixa' THEN 2 ELSE 3 END,
            COALESCE(criado_em, ''), id
        """
    ).fetchall()
    if unordered:
        max_order = db.execute("SELECT COALESCE(MAX(ordem_prioridade), 0) AS max_order FROM projetos").fetchone()["max_order"]
        for i, row in enumerate(unordered, max_order + 1):
            db.execute("UPDATE projetos SET ordem_prioridade = %s WHERE id = %s", (i, row["id"]))


def assign_project_order_to_end(db, project_id):
    max_order = db.execute("SELECT COALESCE(MAX(ordem_prioridade), 0) AS max_order FROM projetos").fetchone()["max_order"]
    db.execute(
        "UPDATE projetos SET ordem_prioridade = COALESCE(ordem_prioridade, %s) WHERE id = %s",
        (max_order + 1, project_id),
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
                "UPDATE etapas_modelo SET nome = %s, ordem = %s, cor_padrao = %s, ativa = 1 WHERE id = %s",
                (stage["nome"], stage["ordem"], stage["cor"], keep["id"]),
            )
            for duplicate in matches[1:]:
                db.execute("UPDATE etapas_modelo SET ativa = 0 WHERE id = %s", (duplicate["id"],))
        else:
            db.execute(
                "INSERT INTO etapas_modelo (nome, ordem, cor_padrao, ativa) VALUES (%s, %s, %s, 1)",
                (stage["nome"], stage["ordem"], stage["cor"]),
            )

    for row in rows:
        if stage_key(row["nome"]) not in canonical and row["id"] not in used_ids:
            db.execute("UPDATE etapas_modelo SET ativa = 0 WHERE id = %s", (row["id"],))


def create_stage_rows(db, project_id, responsavel_id, prazo_critico):
    stages = db.execute("SELECT * FROM etapas_modelo WHERE ativa = 1 ORDER BY ordem").fetchall()
    current_stage_id = None
    for index, stage in enumerate(stages):
        status = "em andamento" if index == 0 else "nao iniciado"
        prazo = prazo_critico or None
        stage_id = db.execute(
            """
            INSERT INTO projeto_etapas
                (projeto_id, etapa_modelo_id, status, responsavel_id, prazo, progresso, subetapa_ativa)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (project_id, stage["id"], status, responsavel_id, prazo, 10 if index == 0 else 0, default_checklist_for_stage(stage["nome"])[0]),
        ).fetchone()["id"]
        for item in default_checklist_for_stage(stage["nome"]):
            db.execute("INSERT INTO checklist_itens (projeto_etapa_id, titulo) VALUES (%s, %s)", (stage_id, item))
        if index == 0:
            current_stage_id = stage_id
    if current_stage_id:
        db.execute("UPDATE projetos SET etapa_atual_id = %s, atualizado_em = %s WHERE id = %s", (current_stage_id, app_now_iso(), project_id))


def get_stage_model_id_for_process_stage(db, template_stage_key):
    legacy_key = PROCESS_STAGE_TO_LEGACY_STAGE.get(template_stage_key, template_stage_key.lower())
    stages = db.execute("SELECT id, nome FROM etapas_modelo WHERE ativa = 1 ORDER BY ordem").fetchall()
    for stage in stages:
        if stage_key(stage["nome"]) == legacy_key:
            return stage["id"]
    return stages[0]["id"] if stages else None


def project_has_workflow_initialized_db(db, project_id):
    return scalar(
        db,
        """
        SELECT COUNT(*)
        FROM projeto_etapas
        WHERE projeto_id = %s
          AND stage_key IS NOT NULL
          AND stage_key != ''
        """,
        (project_id,),
    ) > 0


def find_project_stage_id_for_template_stage(db, project_id, template_stage_key):
    exact_stage = first_row(
        db,
        """
        SELECT id
        FROM projeto_etapas
        WHERE projeto_id = %s
          AND stage_key = %s
          AND COALESCE(show_in_project, 1) = 1
        ORDER BY COALESCE(stage_order, 999), id
        LIMIT 1
        """,
        (project_id, template_stage_key),
    )
    if exact_stage:
        return exact_stage["id"]

    legacy_key = PROCESS_STAGE_TO_LEGACY_STAGE.get(template_stage_key, template_stage_key.lower())
    stages = db.execute(
        """
        SELECT pe.id, COALESCE(pe.stage_name, em.nome) AS etapa_nome, COALESCE(pe.stage_order, em.ordem) AS etapa_ordem
        FROM projeto_etapas pe
        JOIN etapas_modelo em ON em.id = pe.etapa_modelo_id
        WHERE pe.projeto_id = %s
          AND COALESCE(pe.show_in_project, 1) = 1
        ORDER BY COALESCE(pe.stage_order, em.ordem), pe.id
        """,
        (project_id,),
    ).fetchall()
    for stage in stages:
        if stage_key(stage["etapa_nome"]) == legacy_key:
            return stage["id"]
    return stages[0]["id"] if stages else None


def get_cartorio_checklist_rows(db, process_type_key, cartorio_id):
    """Documentacao obrigatoria (etapa Escritorio) configurada em /cartorios/checklist.

    O padrao geral (cartorio_id NULL) vale para todos os cartorios. Um cartorio
    pode ter itens adicionais proprios e excecoes para itens do padrao geral.
    """
    process_key = normalize_project_process_type(process_type_key)
    if cartorio_id:
        return db.execute(
            """
            SELECT cct.*
            FROM cartorio_checklist_templates cct
            WHERE cct.process_type_key = %s
              AND cct.active = 1
              AND (
                  cct.cartorio_id = %s
                  OR (
                      cct.cartorio_id IS NULL
                      AND NOT EXISTS (
                          SELECT 1
                          FROM cartorio_checklist_exclusions cce
                          WHERE cce.cartorio_id = %s
                            AND cce.process_type_key = %s
                            AND cce.template_id = cct.id
                      )
                  )
              )
            ORDER BY CASE WHEN cct.cartorio_id IS NULL THEN 0 ELSE 1 END, cct.order_index, cct.id
            """,
            (process_key, cartorio_id, cartorio_id, process_key),
        ).fetchall()
    return db.execute(
        """
        SELECT * FROM cartorio_checklist_templates
        WHERE process_type_key = %s AND cartorio_id IS NULL AND active = 1
        ORDER BY order_index, id
        """,
        (process_key,),
    ).fetchall()


def create_project_checklist_from_template(db, project_id, process_type_key):
    process_key = normalize_project_process_type(process_type_key)

    templates = db.execute(
        """
        SELECT *
        FROM process_checklist_templates
        WHERE process_type_key = %s AND active = 1
        """,
        (process_key,),
    ).fetchall()
    templates = sorted(
        templates,
        key=lambda row: (PROCESS_CHECKLIST_STAGE_ORDER.get(row["stage_key"], 999), row["order_index"], row["id"]),
    )
    project_row = first_row(db, "SELECT cartorio_id FROM projetos WHERE id = %s", (project_id,))
    custom_office_items = get_cartorio_checklist_rows(
        db, process_key, project_row["cartorio_id"] if project_row else None
    )
    templates = [template for template in templates if template["stage_key"] not in ("ESCRITORIO", "PREFEITURA")]
    now = app_now_iso()
    # O checklist da etapa Escritorio e composto somente pelos documentos do cartorio
    # (definidos em /cartorios/checklist). Itens herdados dos modelos de processo sao
    # aposentados a cada sincronizacao para nao se misturarem a lista de documentos.
    db.execute(
        """
        UPDATE project_checklist_items
        SET active = 0, updated_at = %s
        WHERE project_id = %s AND stage_key = 'ESCRITORIO'
          AND template_id IS NOT NULL AND active = 1
        """,
        (now, project_id),
    )
    stages = db.execute(
        """
        SELECT pe.id, pe.stage_key, COALESCE(pe.stage_name, em.nome) AS etapa_nome, COALESCE(pe.stage_order, em.ordem) AS etapa_ordem
        FROM projeto_etapas pe
        JOIN etapas_modelo em ON em.id = pe.etapa_modelo_id
        WHERE pe.projeto_id = %s
          AND COALESCE(pe.show_in_project, 1) = 1
        ORDER BY COALESCE(pe.stage_order, em.ordem), pe.id
        """,
        (project_id,),
    ).fetchall()
    stage_by_key = {stage["stage_key"]: stage["id"] for stage in stages if stage["stage_key"]}
    stage_by_legacy = {stage_key(stage["etapa_nome"]): stage["id"] for stage in stages}
    first_stage_id = stages[0]["id"] if stages else None
    values = []
    for template in templates:
        project_stage_id = stage_by_key.get(template["stage_key"])
        if not project_stage_id:
            legacy_key = PROCESS_STAGE_TO_LEGACY_STAGE.get(template["stage_key"], template["stage_key"].lower())
            project_stage_id = stage_by_legacy.get(legacy_key) or first_stage_id
        values.append(
            (
                project_id,
                project_stage_id,
                template["id"],
                process_key,
                template["stage_key"],
                PROCESS_CHECKLIST_STAGE_NAMES.get(template["stage_key"], template["stage_key"].replace("_", " ").title()),
                template["title"],
                template["description"],
                CHECKLIST_STATUS_NOT_STARTED,
                template["requirement_level"],
                template["criticality"],
                template["default_responsible_role"],
                None,
                None,
                None,
                None,
                None,
                template["blocks_stage_completion"],
                template["blocks_process_completion"],
                template["requires_attachment"],
                template["allows_observation"],
                template["condition_text"],
                template["help_text"],
                template["order_index"],
                1,
                now,
                now,
            ),
        )
    if custom_office_items:
        office_stage_id = (
            stage_by_key.get("ESCRITORIO")
            or stage_by_legacy.get("escritorio")
            or first_stage_id
        )
        for custom in custom_office_items:
            values.append(
                (
                    project_id,
                    office_stage_id,
                    None,
                    process_key,
                    "ESCRITORIO",
                    PROCESS_CHECKLIST_STAGE_NAMES.get("ESCRITORIO", "Escritorio"),
                    custom["title"],
                    custom["observacoes"],
                    CHECKLIST_STATUS_NOT_STARTED,
                    REQUIREMENT_REQUIRED,
                    CRITICALITY_MEDIUM,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    1,
                    0,
                    0,
                    1,
                    None,
                    custom["modelo_referencia"],
                    custom["order_index"],
                    1,
                    now,
                    now,
                )
            )
    if not values:
        return 0
    cursor = db.cursor()
    psycopg2.extras.execute_values(
        cursor,
        """
        INSERT INTO project_checklist_items
            (project_id, project_stage_id, template_id, process_type_key, stage_key, stage_name, title,
             description, status, requirement_level, criticality, responsible_name, due_date, completed_at,
             completed_by, observation, attachment_path, blocks_stage_completion, blocks_process_completion,
             requires_attachment, allows_observation, condition_text, help_text, order_index, active,
             created_at, updated_at)
        VALUES %s
        ON CONFLICT DO NOTHING
        """,
        values,
    )
    return cursor.rowcount if cursor.rowcount and cursor.rowcount > 0 else 0


def sync_project_checklist_stage_links(db, project_id):
    row = db.execute(
        """
        WITH stage_targets AS (
            SELECT DISTINCT ON (pe.stage_key)
                pe.stage_key,
                pe.id AS stage_id
            FROM projeto_etapas pe
            JOIN etapas_modelo em ON em.id = pe.etapa_modelo_id
            WHERE pe.projeto_id = %s
              AND pe.stage_key IS NOT NULL
              AND pe.stage_key != ''
              AND COALESCE(pe.show_in_project, 1) = 1
            ORDER BY pe.stage_key, COALESCE(pe.stage_order, em.ordem), pe.id
        ),
        updated AS (
            UPDATE project_checklist_items pci
            SET project_stage_id = st.stage_id, updated_at = %s
            FROM stage_targets st
            WHERE pci.project_id = %s
              AND pci.stage_key = st.stage_key
              AND COALESCE(pci.project_stage_id, 0) != st.stage_id
            RETURNING pci.id
        )
        SELECT COUNT(*) AS updated_count FROM updated
        """,
        (project_id, app_now_iso(), project_id),
    ).fetchone()
    return row["updated_count"] if row else 0


def sync_cartorio_checklist_to_projects(db, process_type_key, cartorio_id):
    """Aplica o padrao de documentacao aos projetos ativos afetados (so adiciona itens;
    nada e removido e itens ja marcados nao mudam)."""
    process_key = normalize_project_process_type(process_type_key)
    if cartorio_id:
        projects = db.execute(
            """
            SELECT id FROM projetos
            WHERE tipo_servico = %s AND cartorio_id = %s
              AND lower(COALESCE(status, '')) NOT IN ('concluido', 'cancelado')
            """,
            (process_key, cartorio_id),
        ).fetchall()
    else:
        projects = db.execute(
            """
            SELECT p.id FROM projetos p
            WHERE p.tipo_servico = %s
              AND lower(COALESCE(p.status, '')) NOT IN ('concluido', 'cancelado')
            """,
            (process_key,),
        ).fetchall()
    for row in projects:
        create_project_checklist_from_template(db, row["id"], process_key)
        sync_project_checklist_stage_links(db, row["id"])
    return len(projects)


def initialize_project_workflow(db, project_id, process_type_key, user_id=None, force=False):
    process_key = normalize_project_process_type(process_type_key)
    project = first_row(db, "SELECT * FROM projetos WHERE id = %s", (project_id,))
    if not project:
        return {"created_stages": 0, "updated_stages": 0, "created_checklist": 0, "warnings": ["Projeto nao encontrado."]}

    if project_has_workflow_initialized_db(db, project_id) and not force:
        created_checklist = create_project_checklist_from_template(db, project_id, process_key)
        sync_project_checklist_stage_links(db, project_id)
        return {
            "created_stages": 0,
            "updated_stages": 0,
            "created_checklist": created_checklist,
            "warnings": ["Fluxo do projeto ja estava inicializado."],
        }

    now = app_now_iso()
    if force:
        db.execute(
            """
            UPDATE projeto_etapas
            SET workflow_active = 0, show_in_matrix = 0, show_in_project = 0
            WHERE projeto_id = %s
              AND (stage_key IS NULL OR stage_key = '')
            """,
            (project_id,),
        )

    stage_templates = db.execute(
        """
        SELECT *
        FROM process_stage_templates
        WHERE process_type_key = %s AND active = 1 AND stage_key != 'PREFEITURA'
        ORDER BY stage_order, id
        """,
        (process_key,),
    ).fetchall()
    if not stage_templates:
        return {"created_stages": 0, "updated_stages": 0, "created_checklist": 0, "warnings": ["Tipo de processo sem modelo de etapas."]}

    first_active_stage_id = None
    created_stages = 0
    updated_stages = 0
    active_required_index = 0

    for template in stage_templates:
        applicability = template["applicability"]
        if applicability == APPLICABILITY_NOT_APPLICABLE:
            continue
        template_stage_name = "Orgao externo" if template["stage_key"] == "ORGAO_EXTERNO" else template["stage_name"]
        template_description = (
            "Protocolo e retirada em prefeitura, cartorio, SIGEF, INCRA, SICAR ou outro orgao externo."
            if template["stage_key"] == "ORGAO_EXTERNO"
            else template["description"]
        )

        workflow_active = 1 if applicability == APPLICABILITY_REQUIRED else 0
        if workflow_active:
            active_required_index += 1
        status = "em andamento" if workflow_active and first_active_stage_id is None else "nao iniciado"
        data_inicio = now if status == "em andamento" else None
        prazo = None
        etapa_modelo_id = get_stage_model_id_for_process_stage(db, template["stage_key"])
        if not etapa_modelo_id:
            continue

        existing = first_row(
            db,
            "SELECT * FROM projeto_etapas WHERE projeto_id = %s AND stage_key = %s ORDER BY id LIMIT 1",
            (project_id, template["stage_key"]),
        )
        values = (
            process_key,
            template["stage_key"],
            template_stage_name,
            template["stage_order"],
            applicability,
            1 if workflow_active else 0,
            1 if template["can_skip"] else 0,
            1 if template["blocks_completion"] else 0,
            1 if template["show_in_matrix"] else 0,
            1 if template["show_in_project"] else 0,
            template["external_actor_type"],
            template["id"],
            template_description,
            template["notes"],
        )
        if existing:
            db.execute(
                """
                UPDATE projeto_etapas
                SET process_type_key = %s, stage_key = %s, stage_name = %s, stage_order = %s, applicability = %s,
                    workflow_active = %s, can_skip = %s, blocks_completion = %s, show_in_matrix = %s, show_in_project = %s,
                    external_actor_type = %s, template_stage_id = %s, stage_description = %s, model_notes = %s
                WHERE id = %s
                """,
                values + (existing["id"],),
            )
            stage_id = existing["id"]
            updated_stages += 1
        else:
            stage_id = db.execute(
                """
                INSERT INTO projeto_etapas
                    (projeto_id, etapa_modelo_id, process_type_key, stage_key, stage_name, stage_order, applicability,
                     status, responsavel_id, data_inicio, prazo, progresso, subetapa_ativa, workflow_active,
                     can_skip, blocks_completion, show_in_matrix, show_in_project, external_actor_type,
                     template_stage_id, stage_description, model_notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    project_id,
                    etapa_modelo_id,
                    *values[:5],
                    status,
                    project["responsavel_geral_id"] if workflow_active else None,
                    data_inicio,
                    prazo,
                    10 if status == "em andamento" else 0,
                    default_checklist_for_stage(template_stage_name)[0],
                    *values[5:],
                ),
            ).fetchone()["id"]
            created_stages += 1

        if workflow_active and first_active_stage_id is None:
            first_active_stage_id = stage_id

    if first_active_stage_id:
        db.execute(
            "UPDATE projetos SET etapa_atual_id = %s, tipo_servico = %s, atualizado_em = %s WHERE id = %s",
            (first_active_stage_id, process_key, now, project_id),
        )
        current_stage = first_row(
            db,
            "SELECT * FROM projeto_etapas WHERE id = %s",
            (first_active_stage_id,),
        )
        if current_stage and not first_row(
            db,
            "SELECT id FROM project_stage_history WHERE project_id = %s AND stage_id = %s AND exited_at IS NULL LIMIT 1",
            (project_id, first_active_stage_id),
        ):
            db.execute(
                """
                INSERT INTO project_stage_history
                    (project_id, stage_id, stage_key, stage_name, entered_at, exited_at, responsible_id, responsible_name, reason, created_at)
                VALUES (%s, %s, %s, %s, %s, NULL, %s, %s, %s, %s)
                """,
                (
                    project_id,
                    first_active_stage_id,
                    current_stage["stage_key"] or stage_key(current_stage["stage_name"]),
                    current_stage["stage_name"],
                    now,
                    current_stage["responsavel_id"],
                    None,
                    "criacao_modelo_processo",
                    now,
                ),
            )

    created_checklist = create_project_checklist_from_template(db, project_id, process_key)
    sync_project_checklist_stage_links(db, project_id)
    db.execute(
        """
        INSERT INTO eventos_historico (projeto_id, usuario_id, tipo_evento, descricao, criado_em)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (
            project_id,
            user_id,
            "modelo_processo_aplicado",
            f"Modelo do processo {process_type_name(process_key)} aplicado ao projeto.",
            now,
        ),
    )
    return {
        "created_stages": created_stages,
        "updated_stages": updated_stages,
        "created_checklist": created_checklist,
        "warnings": [],
    }


def ensure_project_checklists(db):
    projects = db.execute("SELECT id, tipo_servico FROM projetos ORDER BY id").fetchall()
    for project in projects:
        create_project_checklist_from_template(db, project["id"], project["tipo_servico"])
        sync_project_checklist_stage_links(db, project["id"])


def get_process_initial_stage_options():
    rows = get_cached_lookup(
        "process_initial_stage_options_rows",
        lambda: query_db(
            """
            SELECT process_type_key, stage_key,
                   CASE WHEN stage_key = 'ORGAO_EXTERNO' THEN 'Orgao externo' ELSE stage_name END AS stage_name,
                   stage_order
            FROM process_stage_templates
            WHERE active = 1
              AND applicability != %s
              AND show_in_project = 1
              AND stage_key != 'PREFEITURA'
            ORDER BY process_type_key, stage_order, id
            """,
            (APPLICABILITY_NOT_APPLICABLE,),
        ),
    )
    options = {}
    for row in rows:
        options.setdefault(row["process_type_key"], []).append(
            {"key": row["stage_key"], "name": row["stage_name"], "order": row["stage_order"]}
        )
    return options


def set_project_initial_stage(db, project_id, stage_key_value):
    stage_key_value = (stage_key_value or "").strip().upper()
    if not stage_key_value:
        return None

    selected = first_row(
        db,
        """
        SELECT pe.*, COALESCE(pe.stage_order, em.ordem) AS effective_order, COALESCE(pe.stage_name, em.nome) AS display_name
        FROM projeto_etapas pe
        JOIN etapas_modelo em ON em.id = pe.etapa_modelo_id
        WHERE pe.projeto_id = %s
          AND pe.stage_key = %s
          AND COALESCE(pe.show_in_project, 1) = 1
          AND COALESCE(pe.applicability, '') != %s
        LIMIT 1
        """,
        (project_id, stage_key_value, APPLICABILITY_NOT_APPLICABLE),
    )
    if not selected:
        return None

    now = app_now_iso()
    stages = db.execute(
        """
        SELECT pe.*, COALESCE(pe.stage_order, em.ordem) AS effective_order
        FROM projeto_etapas pe
        JOIN etapas_modelo em ON em.id = pe.etapa_modelo_id
        WHERE pe.projeto_id = %s
          AND COALESCE(pe.show_in_project, 1) = 1
          AND COALESCE(pe.applicability, '') != %s
        ORDER BY COALESCE(pe.stage_order, em.ordem), pe.id
        """,
        (project_id, APPLICABILITY_NOT_APPLICABLE),
    ).fetchall()
    for stage in stages:
        if stage["id"] == selected["id"]:
            status = "em andamento"
            progresso = max(stage["progresso"] or 0, 10)
            data_inicio = stage["data_inicio"] or now
            data_fim = None
            workflow_active = 1
        elif stage["effective_order"] < selected["effective_order"]:
            status = "concluido"
            progresso = 100
            data_inicio = stage["data_inicio"] or now
            data_fim = stage["data_fim"] or now
            workflow_active = 1
        else:
            status = "nao iniciado"
            progresso = 0
            data_inicio = None
            data_fim = None
            workflow_active = stage["workflow_active"]
        db.execute(
            """
            UPDATE projeto_etapas
            SET status = %s, progresso = %s, data_inicio = %s, data_fim = %s, workflow_active = %s
            WHERE id = %s
            """,
            (status, progresso, data_inicio, data_fim, workflow_active, stage["id"]),
        )

    db.execute(
        "UPDATE project_stage_history SET exited_at = %s, reason = COALESCE(reason, 'ajuste_etapa_inicial') WHERE project_id = %s AND exited_at IS NULL",
        (now, project_id),
    )
    db.execute(
        """
        INSERT INTO project_stage_history
            (project_id, stage_id, stage_key, stage_name, entered_at, exited_at, responsible_id, responsible_name, reason, created_at)
        VALUES (%s, %s, %s, %s, %s, NULL, %s, NULL, %s, %s)
        """,
        (
            project_id,
            selected["id"],
            selected["stage_key"],
            selected["display_name"],
            now,
            selected["responsavel_id"],
            "etapa_inicial_escolhida",
            now,
        ),
    )
    db.execute("UPDATE projetos SET etapa_atual_id = %s, atualizado_em = %s WHERE id = %s", (selected["id"], now, project_id))
    return selected


def infer_current_stage_id_db(db, project_id):
    row = first_row(
        db,
        """
        SELECT pe.id
        FROM projeto_etapas pe
        JOIN etapas_modelo em ON em.id = pe.etapa_modelo_id
        WHERE pe.projeto_id = %s
          AND em.ativa = 1
          AND COALESCE(pe.show_in_project, 1) = 1
          AND COALESCE(pe.workflow_active, 1) = 1
          AND lower(pe.status) != 'nao aplicavel'
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
          COALESCE(pe.stage_order, em.ordem)
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
        WHERE pe.projeto_id = %s
          AND em.ativa = 1
          AND COALESCE(pe.show_in_project, 1) = 1
          AND COALESCE(pe.workflow_active, 1) = 1
          AND lower(pe.status) NOT IN ('concluido', 'cancelado', 'nao aplicavel')
        ORDER BY COALESCE(pe.stage_order, em.ordem)
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
        WHERE pe.projeto_id = %s
          AND em.ativa = 1
          AND COALESCE(pe.show_in_project, 1) = 1
          AND COALESCE(pe.workflow_active, 1) = 1
          AND lower(pe.status) != 'nao aplicavel'
        ORDER BY COALESCE(pe.stage_order, em.ordem) DESC
        LIMIT 1
        """,
        (project_id,),
    )
    return row["id"] if row else None


def ensure_project_structure(db):
    projects = db.execute("SELECT * FROM projetos").fetchall()
    stages = db.execute("SELECT * FROM etapas_modelo WHERE ativa = 1 ORDER BY ordem").fetchall()
    for project in projects:
        workflow_initialized = project_has_workflow_initialized_db(db, project["id"])
        if not workflow_initialized:
            for stage in stages:
                existing_stage = first_row(
                    db,
                    "SELECT * FROM projeto_etapas WHERE projeto_id = %s AND etapa_modelo_id = %s",
                    (project["id"], stage["id"]),
                )
                if existing_stage is None:
                    due = project["prazo_critico"] or None
                    stage_id = db.execute(
                        """
                        INSERT INTO projeto_etapas
                            (projeto_id, etapa_modelo_id, status, responsavel_id, prazo, progresso, subetapa_ativa)
                        VALUES (%s, %s, %s, %s, %s, 0, %s)
                        RETURNING id
                        """,
                        (project["id"], stage["id"], "nao iniciado", project["responsavel_geral_id"], due, default_checklist_for_stage(stage["nome"])[0]),
                    ).fetchone()["id"]
                else:
                    stage_id = existing_stage["id"]
                    if "subetapa_ativa" in existing_stage.keys() and not existing_stage["subetapa_ativa"]:
                        db.execute("UPDATE projeto_etapas SET subetapa_ativa = %s WHERE id = %s", (default_checklist_for_stage(stage["nome"])[0], stage_id))

                if scalar(db, "SELECT COUNT(*) FROM checklist_itens WHERE projeto_etapa_id = %s", (stage_id,)) == 0:
                    for item in default_checklist_for_stage(stage["nome"]):
                        db.execute("INSERT INTO checklist_itens (projeto_etapa_id, titulo) VALUES (%s, %s)", (stage_id, item))

        current_valid = None
        if project["etapa_atual_id"]:
            current_valid = first_row(
                db,
                """
                SELECT pe.id
                FROM projeto_etapas pe
                JOIN etapas_modelo em ON em.id = pe.etapa_modelo_id
                WHERE pe.id = %s AND pe.projeto_id = %s AND em.ativa = 1
                  AND COALESCE(pe.show_in_project, 1) = 1
                  AND lower(pe.status) != 'nao aplicavel'
                """,
                (project["etapa_atual_id"], project["id"]),
            )
        current_stage_id = project["etapa_atual_id"] if current_valid else infer_current_stage_id_db(db, project["id"])
        if current_stage_id != project["etapa_atual_id"]:
            db.execute("UPDATE projetos SET etapa_atual_id = %s, atualizado_em = COALESCE(atualizado_em, criado_em) WHERE id = %s", (current_stage_id, project["id"]))
        if not project["proprietario"]:
            client = first_row(db, "SELECT nome FROM clientes WHERE id = %s", (project["cliente_id"],))
            db.execute(
                "UPDATE projetos SET proprietario = %s, atualizado_em = COALESCE(atualizado_em, criado_em) WHERE id = %s",
                ((client["nome"] if client else project["nome"]), project["id"]),
            )
        if not project["atualizado_em"]:
            db.execute("UPDATE projetos SET atualizado_em = COALESCE(criado_em, %s) WHERE id = %s", (app_now_iso(), project["id"]))

        if scalar(db, "SELECT COUNT(*) FROM tarefas WHERE projeto_id = %s", (project["id"],)) == 0:
            active_stage = first_row(
                db,
                """
                SELECT pe.*, em.nome AS etapa_nome
                FROM projeto_etapas pe
                JOIN etapas_modelo em ON em.id = pe.etapa_modelo_id
                WHERE pe.projeto_id = %s
                  AND lower(pe.status) != 'concluido'
                  AND lower(pe.status) != 'nao aplicavel'
                  AND COALESCE(pe.show_in_project, 1) = 1
                  AND COALESCE(pe.workflow_active, 1) = 1
                  AND em.ativa = 1
                ORDER BY COALESCE(pe.stage_order, em.ordem)
                """,
                (project["id"],),
            )
            if active_stage:
                db.execute(
                    """
                    INSERT INTO tarefas
                        (projeto_id, projeto_etapa_id, titulo, descricao, responsavel_id, prioridade, status, prazo, criado_em)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                        app_now_iso(),
                    ),
                )

        if scalar(db, "SELECT COUNT(*) FROM eventos_historico WHERE projeto_id = %s", (project["id"],)) == 0:
            db.execute(
                "INSERT INTO eventos_historico (projeto_id, usuario_id, tipo_evento, descricao, criado_em) VALUES (%s, NULL, %s, %s, %s)",
                (project["id"], "importacao", "Projeto importado para o prototipo.", app_now_iso()),
            )

    if scalar(db, "SELECT COUNT(*) FROM exigencias_cartorio") == 0:
        project = first_row(db, "SELECT * FROM projetos ORDER BY id DESC LIMIT 1")
        if project:
            db.execute(
                """
                INSERT INTO exigencias_cartorio
                    (projeto_id, cartorio_id, data_recebimento, prazo_resposta, descricao, status, responsavel_id, criado_em, atualizado_em)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    project["id"],
                    project["cartorio_id"],
                    app_today().isoformat(),
                    (app_today() + timedelta(days=5)).isoformat(),
                    "Conferir memorial e anexar declaracao complementar.",
                    "em andamento",
                    project["responsavel_geral_id"],
                    app_now_iso(),
                    app_now_iso(),
                ),
            )

    if scalar(db, "SELECT COUNT(*) FROM apontamentos_tempo") == 0:
        stage = first_row(db, "SELECT * FROM projeto_etapas ORDER BY id LIMIT 1")
        if stage:
            db.execute(
                """
                INSERT INTO apontamentos_tempo
                    (projeto_id, etapa_id, usuario_id, duracao_minutos, tipo_tempo, observacoes, criado_em)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (stage["projeto_id"], stage["id"], stage["responsavel_id"], 95, "execucao", "Apontamento de exemplo.", app_now_iso()),
            )


def parse_report_datetime(value):
    if not value:
        return None
    text = str(value).strip()
    try:
        if len(text) == 10:
            return datetime.fromisoformat(f"{text}T00:00:00")
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def calculate_days_between(start_date, end_date=None):
    start = parse_report_datetime(start_date) if not isinstance(start_date, datetime) else start_date
    end = parse_report_datetime(end_date) if end_date and not isinstance(end_date, datetime) else end_date
    if not start:
        return 0
    end = end or app_now()
    seconds = max((end - start).total_seconds(), 0)
    return seconds / 86400


def format_days(value):
    if value is None:
        return "Sem dados"
    try:
        days = float(value)
    except (TypeError, ValueError):
        return "Sem dados"
    if days <= 0 or days < 0.1:
        return "menos de 1 dia"
    if days < 1:
        return f"{days:.1f}".replace(".", ",") + " dia"
    rounded = round(days, 1)
    if rounded == 1:
        return "1 dia"
    if rounded.is_integer():
        return f"{int(rounded)} dias"
    return f"{rounded:.1f}".replace(".", ",") + " dias"


def ensure_project_stage_history(db):
    projects = db.execute("SELECT * FROM projetos ORDER BY id").fetchall()
    now = app_now()
    for project in projects:
        stages = db.execute(
            """
            SELECT pe.*, COALESCE(pe.stage_name, em.nome) AS etapa_nome, COALESCE(pe.stage_order, em.ordem) AS etapa_ordem, u.nome AS responsavel_nome
            FROM projeto_etapas pe
            JOIN etapas_modelo em ON em.id = pe.etapa_modelo_id
            LEFT JOIN usuarios u ON u.id = pe.responsavel_id
            WHERE pe.projeto_id = %s
              AND em.ativa = 1
              AND COALESCE(pe.show_in_project, 1) = 1
              AND COALESCE(pe.workflow_active, 1) = 1
              AND lower(pe.status) != 'nao aplicavel'
            ORDER BY COALESCE(pe.stage_order, em.ordem)
            """,
            (project["id"],),
        ).fetchall()
        if not stages:
            continue
        current_stage_id = project["etapa_atual_id"] or infer_current_stage_id_db(db, project["id"])
        current_stage = next((stage for stage in stages if stage["id"] == current_stage_id), stages[0])
        current_order = current_stage["etapa_ordem"]
        history_count = scalar(db, "SELECT COUNT(*) FROM project_stage_history WHERE project_id = %s", (project["id"],))

        if history_count == 0:
            past_stages = [stage for stage in stages if stage["etapa_ordem"] <= current_order]
            total_days = sum(REPORT_STAGE_DEFAULT_DAYS.get(stage_key(stage["etapa_nome"]), 3) for stage in past_stages)
            base = parse_report_datetime(project["criado_em"]) or (now - timedelta(days=max(total_days, 1)))
            if (now - base).total_seconds() < max(total_days, 1) * 86400:
                base = now - timedelta(days=max(total_days, 1))
            cursor = base
            for stage in past_stages:
                key = stage["stage_key"] or stage_key(stage["etapa_nome"])
                default_days = REPORT_STAGE_DEFAULT_DAYS.get(key, 3)
                is_current = stage["id"] == current_stage["id"]
                entered = parse_report_datetime(stage["data_inicio"]) or cursor
                if is_current:
                    entered = parse_report_datetime(stage["data_inicio"]) or (now - timedelta(days=default_days))
                    exited = None
                else:
                    exited = parse_report_datetime(stage["data_fim"]) or (entered + timedelta(days=default_days))
                    if exited >= now:
                        exited = now - timedelta(hours=1)
                db.execute(
                    """
                    INSERT INTO project_stage_history
                        (project_id, stage_id, stage_key, stage_name, entered_at, exited_at, responsible_id, responsible_name, reason, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        project["id"],
                        stage["id"],
                        key,
                        stage["etapa_nome"],
                        entered.isoformat(timespec="seconds"),
                        exited.isoformat(timespec="seconds") if exited else None,
                        stage["responsavel_id"] or project["responsavel_geral_id"],
                        stage["responsavel_nome"],
                        "historico_inicial",
                        now.isoformat(timespec="seconds"),
                    ),
                )
                if exited:
                    cursor = exited
        else:
            db.execute(
                """
                UPDATE project_stage_history
                SET exited_at = COALESCE(exited_at, %s)
                WHERE project_id = %s AND exited_at IS NULL AND stage_id != %s
                """,
                (now.isoformat(timespec="seconds"), project["id"], current_stage["id"]),
            )
            open_current = first_row(
                db,
                "SELECT id FROM project_stage_history WHERE project_id = %s AND stage_id = %s AND exited_at IS NULL LIMIT 1",
                (project["id"], current_stage["id"]),
            )
            if not open_current:
                key = current_stage["stage_key"] or stage_key(current_stage["etapa_nome"])
                default_days = REPORT_STAGE_DEFAULT_DAYS.get(key, 3)
                entered = parse_report_datetime(current_stage["data_inicio"]) or parse_report_datetime(project["atualizado_em"]) or (now - timedelta(days=default_days))
                db.execute(
                    """
                    INSERT INTO project_stage_history
                        (project_id, stage_id, stage_key, stage_name, entered_at, exited_at, responsible_id, responsible_name, reason, created_at)
                    VALUES (%s, %s, %s, %s, %s, NULL, %s, %s, %s, %s)
                    """,
                    (
                        project["id"],
                        current_stage["id"],
                        key,
                        current_stage["etapa_nome"],
                        entered.isoformat(timespec="seconds"),
                        current_stage["responsavel_id"] or project["responsavel_geral_id"],
                        current_stage["responsavel_nome"],
                        "etapa_atual",
                        now.isoformat(timespec="seconds"),
                    ),
                )


def record_stage_history_transition(project_id, old_stage, new_stage, moved_at, responsible_id=None, reason=None):
    responsible_name = None
    if responsible_id:
        user = query_db("SELECT nome FROM usuarios WHERE id = %s", (responsible_id,), one=True)
        responsible_name = user["nome"] if user else None
    if old_stage:
        execute_db(
            """
            UPDATE project_stage_history
            SET exited_at = COALESCE(exited_at, %s)
            WHERE project_id = %s AND stage_id = %s AND exited_at IS NULL
            """,
            (moved_at, project_id, old_stage["id"]),
        )
    execute_db(
        """
        UPDATE project_stage_history
        SET exited_at = COALESCE(exited_at, %s)
        WHERE project_id = %s AND stage_id != %s AND exited_at IS NULL
        """,
        (moved_at, project_id, new_stage["id"]),
    )
    open_current = query_db(
        "SELECT id FROM project_stage_history WHERE project_id = %s AND stage_id = %s AND exited_at IS NULL LIMIT 1",
        (project_id, new_stage["id"]),
        one=True,
    )
    if not open_current:
        execute_db(
            """
            INSERT INTO project_stage_history
                (project_id, stage_id, stage_key, stage_name, entered_at, exited_at, responsible_id, responsible_name, reason, created_at)
            VALUES (%s, %s, %s, %s, %s, NULL, %s, %s, %s, %s)
            """,
            (
                project_id,
                new_stage["id"],
                new_stage["stage_key"] if "stage_key" in new_stage.keys() and new_stage["stage_key"] else stage_key(new_stage["etapa_nome"]),
                new_stage["stage_name"] if "stage_name" in new_stage.keys() and new_stage["stage_name"] else new_stage["etapa_nome"],
                moved_at,
                responsible_id,
                responsible_name,
                reason,
                moved_at,
            ),
        )


def get_report_status(avg_days, active_count, max_open_days, completed_count):
    if not completed_count and not active_count:
        return "Sem dados", "muted", 0
    score = 1
    label = "Normal"
    tone = "green"
    if (
        (avg_days or 0) >= REPORT_THRESHOLDS["bottleneck_days"]
        or (max_open_days or 0) >= REPORT_THRESHOLDS["bottleneck_days"]
        or active_count >= REPORT_THRESHOLDS["bottleneck_active_count"]
    ):
        return "Gargalo", "red", 3
    if (
        (avg_days or 0) >= REPORT_THRESHOLDS["attention_days"]
        or (max_open_days or 0) >= REPORT_THRESHOLDS["attention_days"]
        or active_count >= REPORT_THRESHOLDS["attention_active_count"]
    ):
        return "Atencao", "amber", 2
    return label, tone, score


def get_responsible_status(active_count, avg_days, max_open_days):
    if active_count >= REPORT_THRESHOLDS["responsible_overload_active"] or (avg_days or 0) >= REPORT_THRESHOLDS["bottleneck_days"]:
        return "Sobrecarga", "red", 3
    if active_count >= REPORT_THRESHOLDS["responsible_attention_active"] or (max_open_days or 0) >= REPORT_THRESHOLDS["attention_days"]:
        return "Atencao", "amber", 2
    return "Normal", "green", 1


def build_bottleneck_suggestion(metric):
    high_time = (metric.get("avg_days") or 0) >= REPORT_THRESHOLDS["attention_days"] or (metric.get("max_open_days") or 0) >= REPORT_THRESHOLDS["attention_days"]
    high_volume = metric.get("active_count", 0) >= REPORT_THRESHOLDS["attention_active_count"]
    if high_time and high_volume:
        return "Gargalo forte: tempo elevado e acumulo de projetos."
    if high_time:
        return "Etapa com tempo medio elevado ou projeto parado ha muitos dias."
    if high_volume:
        return "Etapa com acumulo de projetos ativos."
    return "Monitorar a etapa nos proximos ciclos."


def get_current_project_open_days(project):
    entered_at = project.get("current_entered_at") or project.get("stage_data_inicio") or project.get("atualizado_em") or project.get("criado_em")
    return calculate_days_between(entered_at)


def calculate_stage_metrics(stages, projects, histories):
    total_projects = len(projects)
    projects_by_id = {project["id"]: project for project in projects}
    histories_by_key = {}
    open_history_by_project_key = {}
    for history in histories:
        raw_key = history["stage_key"]
        key = PROCESS_STAGE_TO_LEGACY_STAGE.get(raw_key, stage_key(history["stage_name"])) if raw_key else stage_key(history["stage_name"])
        histories_by_key.setdefault(key, []).append(history)
        if not history["exited_at"]:
            open_history_by_project_key[(history["project_id"], key)] = history

    metrics = []
    for stage in stages:
        key = stage_key(stage["nome"])
        stage_histories = histories_by_key.get(key, [])
        completed_histories = [history for history in stage_histories if history["exited_at"]]
        active_projects = [
            project for project in projects
            if project["current_stage_key"] == key and str(project["status"] or "").lower() not in ("concluido", "cancelado")
        ]
        completed_project_ids = {history["project_id"] for history in completed_histories}
        concluded_count = len(completed_project_ids)
        not_started = len([
            project for project in projects
            if (project["current_stage_order"] or 0) < stage["ordem"]
            and project["id"] not in {history["project_id"] for history in stage_histories}
        ])
        completed_days = [calculate_days_between(history["entered_at"], history["exited_at"]) for history in completed_histories]
        avg_days = sum(completed_days) / len(completed_days) if completed_days else None
        open_days = []
        for project in active_projects:
            open_history = open_history_by_project_key.get((project["id"], key))
            if open_history:
                open_days.append(calculate_days_between(open_history["entered_at"]))
            else:
                open_days.append(get_current_project_open_days(project))
        max_open_days = max(open_days) if open_days else None
        status, tone, score = get_report_status(avg_days, len(active_projects), max_open_days, concluded_count)
        metric = {
            "stage_id": stage["id"],
            "stage_key": key,
            "stage_name": stage["nome"],
            "order": stage["ordem"],
            "not_started": max(not_started, 0),
            "active_count": len(active_projects),
            "completed_count": concluded_count,
            "avg_days": avg_days,
            "max_open_days": max_open_days,
            "status": status,
            "tone": tone,
            "score": score,
        }
        metrics.append(metric)
    return sorted(metrics, key=lambda item: item["order"])


def calculate_responsible_metrics(projects, histories):
    metrics = {}
    for project in projects:
        if str(project["status"] or "").lower() in ("concluido", "cancelado"):
            continue
        responsible_id = project["current_responsible_id"] or project["responsavel_geral_id"] or "none"
        name = project["current_responsible_name"] or project["responsavel_geral_nome"] or "Sem responsavel"
        item = metrics.setdefault(responsible_id, {"responsible": name, "active_count": 0, "completed_project_ids": set(), "completed_days": [], "open_days": []})
        item["active_count"] += 1
        item["open_days"].append(get_current_project_open_days(project))

    for history in histories:
        if not history["exited_at"]:
            continue
        responsible_id = history["responsible_id"] or "none"
        name = history["responsible_name"] or "Sem responsavel"
        item = metrics.setdefault(responsible_id, {"responsible": name, "active_count": 0, "completed_project_ids": set(), "completed_days": [], "open_days": []})
        item["completed_project_ids"].add(history["project_id"])
        item["completed_days"].append(calculate_days_between(history["entered_at"], history["exited_at"]))

    rows = []
    for item in metrics.values():
        avg_days = None
        if item["completed_days"]:
            avg_days = sum(item["completed_days"]) / len(item["completed_days"])
        elif item["open_days"]:
            avg_days = sum(item["open_days"]) / len(item["open_days"])
        max_open_days = max(item["open_days"]) if item["open_days"] else None
        status, tone, score = get_responsible_status(item["active_count"], avg_days, max_open_days)
        rows.append({
            "responsible": item["responsible"],
            "active_count": item["active_count"],
            "completed_count": len(item["completed_project_ids"]),
            "avg_days": avg_days,
            "max_open_days": max_open_days,
            "status": status,
            "tone": tone,
            "score": score,
        })
    return sorted(rows, key=lambda item: (-item["score"], -item["active_count"], item["responsible"]))


def calculate_city_metrics(projects):
    total = max(len(projects), 1)
    grouped = {}
    for project in projects:
        city = project["cidade"] or "Sem cidade"
        item = grouped.setdefault(city, {"city": city, "total": 0, "active": 0, "finished": 0})
        item["total"] += 1
        status = str(project["status"] or "").lower()
        if status in ("concluido", "cancelado"):
            item["finished"] += 1
        else:
            item["active"] += 1
    rows = []
    for item in grouped.values():
        item["percent"] = item["total"] / total * 100
        rows.append(item)
    return sorted(rows, key=lambda item: (-item["total"], item["city"]))


def calculate_registry_metrics(projects, histories, open_pending_by_project):
    grouped = {}
    cartorio_days = {}
    for history in histories:
        raw_key = history["stage_key"]
        key = PROCESS_STAGE_TO_LEGACY_STAGE.get(raw_key, stage_key(history["stage_name"])) if raw_key else stage_key(history["stage_name"])
        if key == "cartorio" and history["exited_at"]:
            project = next((item for item in projects if item["id"] == history["project_id"]), None)
            registry = project["cartorio_nome"] if project else None
            registry = registry or "Sem cartorio"
            cartorio_days.setdefault(registry, []).append(calculate_days_between(history["entered_at"], history["exited_at"]))

    for project in projects:
        registry = project["cartorio_nome"] or "Sem cartorio"
        item = grouped.setdefault(registry, {"registry": registry, "total": 0, "active": 0, "pending": 0, "avg_cartorio_days": None})
        item["total"] += 1
        if str(project["status"] or "").lower() not in ("concluido", "cancelado"):
            item["active"] += 1
        if open_pending_by_project.get(project["id"], 0):
            item["pending"] += 1

    for registry, item in grouped.items():
        days = cartorio_days.get(registry, [])
        item["avg_cartorio_days"] = sum(days) / len(days) if days else None
    return sorted(grouped.values(), key=lambda item: (-item["total"], item["registry"]))


def calculate_stopped_projects(projects, open_pending_by_project):
    rows = []
    for project in projects:
        if str(project["status"] or "").lower() in ("concluido", "cancelado"):
            continue
        days = get_current_project_open_days(project)
        if days < REPORT_THRESHOLDS["stopped_days"]:
            continue
        stage_name = project["current_stage_name"] or "Sem etapa"
        if open_pending_by_project.get(project["id"], 0):
            next_action = "Resolver pendencias abertas"
        elif stage_key(stage_name) == "cartorio":
            next_action = "Cobrar retorno do cartorio"
        elif not (project["current_responsible_name"] or project["responsavel_geral_nome"]):
            next_action = "Definir responsavel"
        else:
            next_action = "Revisar etapa com responsavel"
        rows.append({
            "project_id": project["id"],
            "project_name": project["nome"],
            "cliente_nome": project["cliente_nome"] or project["proprietario"] or "-",
            "stage_name": stage_name,
            "responsible": project["current_responsible_name"] or project["responsavel_geral_nome"] or "Sem responsavel",
            "open_days": days,
            "next_action": next_action,
        })
    return sorted(rows, key=lambda item: -item["open_days"])


def build_reports_context():
    # ---------- Projetos enriquecidos ----------
    projects = query_db(
        """
        SELECT DISTINCT
            p.*,
            COALESCE(NULLIF(c.nome_exibicao, ''), NULLIF(pf.nome_completo, ''), NULLIF(pj.razao_social, ''), NULLIF(c.nome, ''), NULLIF(p.proprietario, '')) AS cliente_nome,
            ct.nome AS cartorio_nome,
            cpe.data_inicio AS stage_data_inicio,
            cpe.status AS current_stage_status,
            COALESCE(cpe.stage_name, cem.nome) AS current_stage_name,
            COALESCE(cpe.stage_order, cem.ordem) AS current_stage_order,
            cpe.stage_key AS current_stage_template_key,
            u_stage.id AS current_responsible_id,
            u_stage.nome AS current_responsible_name,
            u_project.nome AS responsavel_geral_nome,
            COALESCE(h.entered_at, cpe.data_inicio, p.atualizado_em, p.criado_em) AS current_entered_at
        FROM projetos p
        LEFT JOIN clientes c ON c.id = p.cliente_id
        LEFT JOIN pessoas_fisicas pf ON pf.cliente_id = c.id
        LEFT JOIN pessoas_juridicas pj ON pj.cliente_id = c.id
        LEFT JOIN cartorios ct ON ct.id = p.cartorio_id
        LEFT JOIN projeto_etapas cpe ON cpe.id = p.etapa_atual_id
        LEFT JOIN etapas_modelo cem ON cem.id = cpe.etapa_modelo_id
        LEFT JOIN usuarios u_stage ON u_stage.id = cpe.responsavel_id
        LEFT JOIN usuarios u_project ON u_project.id = p.responsavel_geral_id
        LEFT JOIN project_stage_history h ON h.project_id = p.id AND h.stage_id = p.etapa_atual_id AND h.exited_at IS NULL
        ORDER BY p.nome
        """
    )
    project_dicts = []
    for p in projects:
        item = dict(p)
        raw_current_key = item.get("current_stage_template_key")
        item["current_stage_key"] = (
            PROCESS_STAGE_TO_LEGACY_STAGE.get(raw_current_key, stage_key(item.get("current_stage_name") or ""))
            if raw_current_key
            else stage_key(item.get("current_stage_name") or "")
        )
        project_dicts.append(item)

    # ---------- Etapas dos projetos (com applicability) ----------
    project_stages = query_db(
        """
        SELECT
            pe.id,
            pe.projeto_id,
            pe.stage_key,
            pe.stage_name,
            pe.applicability,
            pe.status,
            pe.data_inicio,
            pe.data_fim,
            pe.external_actor_type,
            pe.workflow_active,
            pe.responsavel_id
        FROM projeto_etapas pe
        JOIN etapas_modelo em ON em.id = pe.etapa_modelo_id
        WHERE em.ativa = 1
          AND COALESCE(pe.show_in_project, 1) = 1
        ORDER BY pe.projeto_id, COALESCE(pe.stage_order, em.ordem), pe.id
        """
    )
    project_stage_dicts = [dict(s) for s in project_stages]

    # ---------- Checklist dos projetos ----------
    checklist_items = query_db(
        """
        SELECT
            pci.id,
            pci.project_id,
            pci.project_stage_id,
            pci.stage_key,
            pci.stage_name,
            pci.title,
            pci.status,
            pci.requirement_level,
            pci.criticality,
            pci.blocks_stage_completion,
            pci.blocks_process_completion,
            pci.responsible_name,
            pci.created_at,
            pci.updated_at
        FROM project_checklist_items pci
        WHERE pci.active = 1
        ORDER BY pci.project_id, pci.order_index, pci.id
        """
    )
    checklist_dicts = [dict(it) for it in checklist_items]

    # ---------- Historico de etapas ----------
    histories = query_db("SELECT * FROM project_stage_history ORDER BY entered_at")
    history_dicts = [dict(h) for h in histories]

    # ---------- Pendencias abertas ----------
    pending_rows = query_db(
        """
        SELECT projeto_id, COUNT(*) AS total
        FROM pendencias
        WHERE lower(status) NOT IN ('resolvida', 'cancelada')
        GROUP BY projeto_id
        """
    )
    open_pending_by_project = {row["projeto_id"]: row["total"] for row in pending_rows}

    # ---------- Metricas novas (Fase 5) ----------
    stage_metrics_v2 = calculate_stage_metrics_v2(
        project_dicts, project_stage_dicts, history_dicts, checklist_dicts
    )
    process_type_metrics = calculate_process_type_metrics(
        project_dicts, project_stage_dicts, history_dicts, checklist_dicts,
        process_name_fn=process_type_name,
    )
    responsible_metrics_v2 = calculate_responsible_metrics_v2(
        project_dicts, project_stage_dicts, history_dicts, checklist_dicts
    )
    city_metrics_v2 = calculate_city_metrics_v2(project_dicts, process_name_fn=process_type_name)
    external_actor_metrics = calculate_external_actor_metrics(
        project_dicts, project_stage_dicts, history_dicts
    )
    stopped_projects_v2 = calculate_stopped_projects_v2(
        project_dicts, project_stage_dicts, open_pending_by_project, checklist_dicts
    )
    checklist_pending_report = calculate_checklist_pending_report(project_dicts, checklist_dicts)
    bottlenecks_v2 = build_bottleneck_suggestions_v2(stage_metrics_v2)[:6]

    summary = build_operational_summary_v2(
        project_dicts,
        stage_metrics_v2,
        process_type_metrics,
        responsible_metrics_v2,
        checklist_dicts,
        open_pending_by_project,
    )

    # ---------- Metricas legadas (compatibilidade) ----------
    stages_legacy = query_db("SELECT * FROM etapas_modelo WHERE ativa = 1 ORDER BY ordem")
    stage_metrics_legacy = calculate_stage_metrics(list(stages_legacy), project_dicts, history_dicts)
    responsible_metrics_legacy = calculate_responsible_metrics(project_dicts, history_dicts)
    city_metrics_legacy = calculate_city_metrics(project_dicts)
    registry_metrics_legacy = calculate_registry_metrics(project_dicts, history_dicts, open_pending_by_project)
    stopped_legacy = calculate_stopped_projects(project_dicts, open_pending_by_project)

    return {
        # Visao geral
        "summary": summary,
        # Etapas (v2 — considera applicability)
        "stage_metrics": stage_metrics_v2,
        # Gargalos (v2)
        "bottlenecks": bottlenecks_v2,
        # Processos
        "process_type_metrics": process_type_metrics,
        # Responsaveis (v2)
        "responsible_metrics": responsible_metrics_v2,
        # Cidades (v2)
        "city_metrics": city_metrics_v2,
        # Cartorios/orgaos externos (v2)
        "external_actor_metrics": external_actor_metrics,
        # Projetos parados (v2)
        "stopped_projects": stopped_projects_v2,
        # Pendencias de checklist obrigatorio
        "checklist_pending_report": checklist_pending_report,
        # Limiares
        "thresholds": REPORT_THRESHOLDS_V2,
        # Legados para nao quebrar outros possiveis usos
        "stage_metrics_legacy": stage_metrics_legacy,
        "responsible_metrics_legacy": responsible_metrics_legacy,
        "city_metrics_legacy": city_metrics_legacy,
        "registry_metrics": registry_metrics_legacy,
    }


def get_reports_context_cached():
    now_monotonic = time.monotonic()
    cached = _reports_cache.get("value")
    if cached is not None and now_monotonic < _reports_cache.get("expires_at", 0.0):
        return cached
    context = build_reports_context()
    _reports_cache["value"] = context
    _reports_cache["expires_at"] = now_monotonic + REPORTS_CACHE_TTL_SECONDS
    return context


def _run_due_status_updates(db, today, now_iso):
    db.execute(
        """
        UPDATE projeto_etapas
        SET status = 'atrasado', atraso_origem = COALESCE(atraso_origem, 'interno')
        WHERE prazo IS NOT NULL
          AND prazo != ''
          AND prazo < %s
          AND id IN (SELECT etapa_atual_id FROM projetos WHERE etapa_atual_id IS NOT NULL)
          AND lower(status) NOT IN ('concluido', 'cancelado', 'aguardando externo', 'atrasado')
        """,
        (today,),
    )
    db.execute(
        """
        UPDATE tarefas
        SET status = 'atrasado'
        WHERE prazo IS NOT NULL
          AND prazo != ''
          AND prazo < %s
          AND lower(status) NOT IN ('concluido', 'cancelado', 'aguardando externo', 'atrasado')
        """,
        (today,),
    )
    db.execute(
        """
        UPDATE exigencias_cartorio
        SET status = 'atrasado', atualizado_em = %s
        WHERE prazo_resposta IS NOT NULL
          AND prazo_resposta != ''
          AND prazo_resposta < %s
          AND lower(status) NOT IN ('concluido', 'cancelado', 'atrasado')
        """,
        (now_iso, today),
    )
    db.commit()


def _background_due_status_refresh(today, now_iso):
    global _due_statuses_next_refresh, _refreshing_due_statuses
    try:
        db = connect_db()
        try:
            _run_due_status_updates(db, today, now_iso)
        finally:
            db.close()
        invalidate_runtime_caches()
        _due_statuses_next_refresh = time.monotonic() + DUE_STATUS_REFRESH_TTL_SECONDS
    except Exception:
        app.logger.exception("Falha ao atualizar status vencidos em background.")
        _due_statuses_next_refresh = time.monotonic() + 30.0
    finally:
        _refreshing_due_statuses = False


def refresh_due_statuses(force=False):
    """Marca etapas/tarefas/exigencias vencidas como atrasadas.

    O caminho normal (TTL) roda em uma thread de background para nunca
    segurar o carregamento da pagina; force=True mantem o comportamento
    sincrono na conexao do request.
    """
    global _due_statuses_next_refresh, _refreshing_due_statuses
    now_monotonic = time.monotonic()
    if not force and now_monotonic < _due_statuses_next_refresh:
        return
    today = app_today().isoformat()
    now_iso = app_now_iso()
    if force:
        _refreshing_due_statuses = True
        db = get_db()
        try:
            _run_due_status_updates(db, today, now_iso)
            invalidate_runtime_caches()
            _due_statuses_next_refresh = time.monotonic() + DUE_STATUS_REFRESH_TTL_SECONDS
        except Exception:
            db.rollback()
            raise
        finally:
            _refreshing_due_statuses = False
        return
    with _due_refresh_lock:
        if time.monotonic() < _due_statuses_next_refresh or _refreshing_due_statuses:
            return
        _refreshing_due_statuses = True
    threading.Thread(
        target=_background_due_status_refresh,
        args=(today, now_iso),
        daemon=True,
        name="geogestao-due-refresh",
    ).start()


def record_event(project_id, event_type, description, user_id=None):
    if user_id is None:
        user = getattr(g, "user", None)
        user_id = user["id"] if user else None
    execute_db(
        "INSERT INTO eventos_historico (projeto_id, usuario_id, tipo_evento, descricao, criado_em) VALUES (%s, %s, %s, %s, %s)",
        (project_id, user_id, event_type, description, app_now_iso()),
    )


def delete_project_records(db, project_id):
    if table_columns(db, "projeto_pagamentos"):
        db.execute("DELETE FROM projeto_pagamentos WHERE projeto_id = %s", (project_id,))
    if table_columns(db, "projeto_custos"):
        db.execute("DELETE FROM projeto_custos WHERE projeto_id = %s", (project_id,))
    db.execute("DELETE FROM apontamentos_tempo WHERE projeto_id = %s", (project_id,))
    db.execute("DELETE FROM eventos_historico WHERE projeto_id = %s", (project_id,))
    db.execute("DELETE FROM movimentacoes_etapa WHERE projeto_id = %s", (project_id,))
    db.execute("DELETE FROM notificacoes WHERE projeto_id = %s", (project_id,))
    db.execute("DELETE FROM pendencias WHERE projeto_id = %s", (project_id,))
    db.execute("DELETE FROM exigencias_cartorio WHERE projeto_id = %s", (project_id,))
    db.execute("DELETE FROM tarefas WHERE projeto_id = %s", (project_id,))
    db.execute("DELETE FROM project_checklist_items WHERE project_id = %s", (project_id,))
    db.execute("DELETE FROM project_stage_history WHERE project_id = %s", (project_id,))
    db.execute("DELETE FROM checklist_itens WHERE projeto_etapa_id IN (SELECT id FROM projeto_etapas WHERE projeto_id = %s)", (project_id,))
    db.execute("DELETE FROM projeto_etapas WHERE projeto_id = %s", (project_id,))
    db.execute("DELETE FROM projetos WHERE id = %s", (project_id,))


def delete_client_records(db, cliente_id):
    linked_projects = scalar(db, "SELECT COUNT(*) FROM projetos WHERE cliente_id = %s", (cliente_id,))
    if linked_projects:
        return False
    pf_rows = db.execute("SELECT id FROM pessoas_fisicas WHERE cliente_id = %s", (cliente_id,)).fetchall()
    for pf in pf_rows:
        db.execute("DELETE FROM conjuges WHERE pessoa_fisica_id = %s", (pf["id"],))
        db.execute("DELETE FROM enderecos_proprietario WHERE pessoa_fisica_id = %s", (pf["id"],))
    imovel_rows = db.execute("SELECT imovel_id FROM clientes_imoveis WHERE cliente_id = %s", (cliente_id,)).fetchall()
    db.execute("DELETE FROM clientes_imoveis WHERE cliente_id = %s", (cliente_id,))
    for row in imovel_rows:
        still_linked = scalar(db, "SELECT COUNT(*) FROM clientes_imoveis WHERE imovel_id = %s", (row["imovel_id"],))
        if not still_linked:
            db.execute("DELETE FROM vertices_imovel WHERE imovel_id = %s", (row["imovel_id"],))
            db.execute("DELETE FROM imoveis WHERE id = %s", (row["imovel_id"],))
    db.execute("DELETE FROM procuradores WHERE cliente_id = %s", (cliente_id,))
    db.execute("DELETE FROM pessoas_juridicas WHERE cliente_id = %s", (cliente_id,))
    db.execute("DELETE FROM pessoas_fisicas WHERE cliente_id = %s", (cliente_id,))
    db.execute("DELETE FROM clientes WHERE id = %s", (cliente_id,))
    return True


def update_stage_progress(stage_id):
    counts = query_db(
        """
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN concluido = 1 THEN 1 ELSE 0 END) AS done
        FROM checklist_itens
        WHERE projeto_etapa_id = %s
        """,
        (stage_id,),
        one=True,
    )
    total = counts["total"] or 0
    done = counts["done"] or 0
    progress = int((done / total) * 100) if total else 0
    execute_db("UPDATE projeto_etapas SET progresso = %s WHERE id = %s", (progress, stage_id))
    return progress


def project_checklist_stage_counts(stage_id):
    """Done/total/progress da etapa com base no checklist do processo (project_checklist_items)."""
    row = query_db(
        """
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN status = %s THEN 1 ELSE 0 END) AS done
        FROM project_checklist_items
        WHERE project_stage_id = %s AND active = 1 AND status != %s
        """,
        (CHECKLIST_STATUS_DONE, stage_id, CHECKLIST_STATUS_NOT_APPLICABLE),
        one=True,
    )
    total = row["total"] or 0
    done = row["done"] or 0
    progress = int((done / total) * 100) if total else 0
    return done, total, progress


def is_office_elaboration_stage(stage):
    """A trava de documentos do cartorio vale somente na etapa Escritorio (elaboracao).

    Conferencia e as demais etapas avancam livres, mesmo com checklist pendente.
    """
    if not stage:
        return False
    key = stage["stage_key"] if "stage_key" in stage else None
    if key:
        return key == "ESCRITORIO"
    return stage_key(stage["etapa_nome"] or "") == "escritorio"


def external_stage_type(stage):
    if not stage:
        return None
    key = (stage["stage_key"] if "stage_key" in stage else "") or ""
    name_key = stage_key(stage["etapa_nome"] or "")
    if key in ("PREFEITURA", "ORGAO_EXTERNO") or name_key in ("prefeitura", "cartorio"):
        return EXTERNAL_PROTOCOL_SCOPE
    return None


def external_stage_label(tipo_orgao):
    if tipo_orgao == EXTERNAL_PROTOCOL_SCOPE:
        return "Orgao externo"
    return EXTERNAL_ORGAO_LABELS.get(tipo_orgao, "Orgao externo")


def find_project_stage_by_external_type(db, project_id, tipo_orgao):
    current = db.execute(
        """
        SELECT pe.*, COALESCE(pe.stage_name, em.nome) AS etapa_nome, COALESCE(pe.stage_order, em.ordem) AS etapa_ordem
        FROM projetos p
        JOIN projeto_etapas pe ON pe.id = p.etapa_atual_id
        JOIN etapas_modelo em ON em.id = pe.etapa_modelo_id
        WHERE p.id = %s
          AND COALESCE(pe.show_in_project, 1) = 1
        LIMIT 1
        """,
        (project_id,),
    ).fetchone()
    if external_stage_type(current) == EXTERNAL_PROTOCOL_SCOPE:
        return current
    row = db.execute(
        """
        SELECT pe.*, COALESCE(pe.stage_name, em.nome) AS etapa_nome, COALESCE(pe.stage_order, em.ordem) AS etapa_ordem
        FROM projeto_etapas pe
        JOIN etapas_modelo em ON em.id = pe.etapa_modelo_id
        WHERE pe.projeto_id = %s
          AND pe.stage_key = 'ORGAO_EXTERNO'
          AND COALESCE(pe.show_in_project, 1) = 1
        ORDER BY COALESCE(pe.stage_order, em.ordem), pe.id
        LIMIT 1
        """,
        (project_id,),
    ).fetchone()
    if row:
        return row
    row = db.execute(
        """
        SELECT pe.*, COALESCE(pe.stage_name, em.nome) AS etapa_nome, COALESCE(pe.stage_order, em.ordem) AS etapa_ordem
        FROM projeto_etapas pe
        JOIN etapas_modelo em ON em.id = pe.etapa_modelo_id
        WHERE pe.projeto_id = %s
          AND pe.stage_key = 'PREFEITURA'
          AND COALESCE(pe.show_in_project, 1) = 1
        ORDER BY COALESCE(pe.stage_order, em.ordem), pe.id
        LIMIT 1
        """,
        (project_id,),
    ).fetchone()
    if row:
        return row
    return db.execute(
        """
        SELECT pe.*, COALESCE(pe.stage_name, em.nome) AS etapa_nome, COALESCE(pe.stage_order, em.ordem) AS etapa_ordem
        FROM projeto_etapas pe
        JOIN etapas_modelo em ON em.id = pe.etapa_modelo_id
        WHERE pe.projeto_id = %s
          AND lower(em.nome) IN ('cartorio', 'orgao externo', 'prefeitura')
          AND COALESCE(pe.show_in_project, 1) = 1
        ORDER BY COALESCE(pe.stage_order, em.ordem), pe.id
        LIMIT 1
        """,
        (project_id,),
    ).fetchone()


def protocol_withdrawal_task_marker(protocol_id):
    return f"RETIRAR_PROTOCOLO:{protocol_id}"


def parse_iso_date_or_today(value):
    try:
        return date.fromisoformat(str(value or "")[:10])
    except ValueError:
        return app_today()


def add_business_days(start_date, days):
    current = start_date
    added = 0
    while added < days:
        current += timedelta(days=1)
        if current.weekday() < 5:
            added += 1
    return current


def external_protocol_check_date(data_protocolo):
    return add_business_days(parse_iso_date_or_today(data_protocolo), 15).isoformat()


def normalize_external_orgao(value):
    value = (value or "").strip().upper()
    return value if value in EXTERNAL_ORGAO_LABELS else "CARTORIO"


def ensure_protocol_withdrawal_task(project_id, stage_id, protocol_id, tipo_orgao, responsible_id, due_date=None):
    if not responsible_id:
        return None
    marker = protocol_withdrawal_task_marker(protocol_id)
    title = f"Retirar protocolo em {external_stage_label(tipo_orgao)}"
    description = f"{marker}\nRetirar protocolo e registrar a retirada no sistema."
    due = due_date or app_today().isoformat()
    existing = query_db(
        """
        SELECT id
        FROM tarefas
        WHERE projeto_id = %s
          AND descricao LIKE %s
          AND lower(COALESCE(status, '')) NOT IN ('concluido', 'cancelado')
        ORDER BY id DESC
        LIMIT 1
        """,
        (project_id, f"{marker}%"),
        one=True,
    )
    if existing:
        execute_db(
            """
            UPDATE tarefas
            SET projeto_etapa_id = %s, titulo = %s, descricao = %s, responsavel_id = %s,
                prioridade = 'Alta', status = 'em andamento', prazo = %s
            WHERE id = %s
            """,
            (stage_id, title, description, responsible_id, due, existing["id"]),
        )
        return existing["id"]
    return execute_db(
        """
        INSERT INTO tarefas
            (projeto_id, projeto_etapa_id, titulo, descricao, responsavel_id, prioridade, status, prazo, criado_em)
        VALUES (%s, %s, %s, %s, %s, 'Alta', 'em andamento', %s, %s)
        """,
        (project_id, stage_id, title, description, responsible_id, due, app_now_iso()),
    )


def complete_protocol_withdrawal_tasks(project_id, protocol_id):
    marker = protocol_withdrawal_task_marker(protocol_id)
    execute_db(
        """
        UPDATE tarefas
        SET status = 'concluido', concluido_em = COALESCE(concluido_em, %s)
        WHERE projeto_id = %s
          AND descricao LIKE %s
          AND lower(COALESCE(status, '')) NOT IN ('concluido', 'cancelado')
        """,
        (app_now_iso(), project_id, f"{marker}%"),
    )


def cancel_protocol_withdrawal_tasks(project_id, protocol_id):
    marker = protocol_withdrawal_task_marker(protocol_id)
    execute_db(
        """
        UPDATE tarefas
        SET status = 'cancelado'
        WHERE projeto_id = %s
          AND descricao LIKE %s
          AND lower(COALESCE(status, '')) NOT IN ('concluido', 'cancelado')
        """,
        (project_id, f"{marker}%"),
    )


def external_stage_protocol_summary(project_id, tipo_orgao, stage_id=None):
    orgao_filter = "" if tipo_orgao == EXTERNAL_PROTOCOL_SCOPE else "AND e.tipo_orgao = %s"
    params = [project_id]
    if orgao_filter:
        params.append(tipo_orgao)
    stage_filter = ""
    if stage_id:
        stage_filter = "AND e.etapa_id = %s"
        params.append(stage_id)
    rows = query_db(
        f"""
        SELECT e.*, u.nome AS responsavel_nome
        FROM exigencias_cartorio e
        LEFT JOIN usuarios u ON u.id = e.responsavel_id
        WHERE e.projeto_id = %s
          AND COALESCE(e.tipo_registro, 'exigencia') = 'protocolo'
          {orgao_filter}
          {stage_filter}
        ORDER BY COALESCE(e.prazo_resposta, e.data_protocolo, '9999-12-31'), e.id
        """,
        params,
    )
    withdrawn = [row for row in rows if row["data_retirada"] and (row["status"] or "").lower() == "concluido"]
    ready = [row for row in rows if row["data_pronto_retirada"] and not row["data_retirada"]]
    pending_deadlines = [row["prazo_resposta"] for row in rows if row["prazo_resposta"] and not row["data_retirada"]]
    protocol_count = len(rows)
    withdrawn_count = len(withdrawn)
    pending_count = protocol_count - withdrawn_count
    all_withdrawn = protocol_count > 0 and pending_count == 0
    if not protocol_count:
        state = "Aguardando protocolo"
    elif all_withdrawn:
        state = "Retirado"
    elif ready:
        state = "Pronto para retirada"
    else:
        state = "Protocolado"
    return {
        "protocol_count": protocol_count,
        "withdrawn_count": withdrawn_count,
        "pending_count": pending_count,
        "ready_count": len(ready),
        "all_withdrawn": all_withdrawn,
        "check_date": min(pending_deadlines) if pending_deadlines else "",
        "check_date_label": format_date(min(pending_deadlines)) if pending_deadlines else "-",
        "withdrawal_label": f"{withdrawn_count}/{protocol_count} retirados" if protocol_count else "Pendente",
        "state": state,
        "state_ok": all_withdrawn,
    }


def external_protocol_payload(protocol):
    return {
        "id": protocol["id"],
        "descricao": protocol["descricao"],
        "numero_protocolo": protocol["numero_protocolo"] or "",
        "data_protocolo": protocol["data_protocolo"] or "",
        "data_protocolo_label": format_date(protocol["data_protocolo"]) if protocol["data_protocolo"] else "-",
        "prazo_resposta": protocol["prazo_resposta"] or "",
        "prazo_resposta_label": format_date(protocol["prazo_resposta"]) if protocol["prazo_resposta"] else "-",
        "status": protocol["status"] or "",
        "tipo_orgao": protocol["tipo_orgao"] or "CARTORIO",
        "tipo_orgao_label": EXTERNAL_ORGAO_LABELS.get(protocol["tipo_orgao"] or "CARTORIO", protocol["tipo_orgao"] or "Orgao externo"),
        "responsavel_id": protocol["responsavel_id"],
        "responsavel_nome": protocol["responsavel_nome"] if "responsavel_nome" in protocol.keys() else "",
        "data_pronto_retirada": protocol["data_pronto_retirada"] or "",
        "data_retirada": protocol["data_retirada"] or "",
        "is_ready": bool(protocol["data_pronto_retirada"] and not protocol["data_retirada"]),
        "is_withdrawn": bool(protocol["data_retirada"] and (protocol["status"] or "").lower() == "concluido"),
    }


def load_external_protocol(project_id, protocol_id):
    return query_db(
        """
        SELECT e.*, u.nome AS responsavel_nome
        FROM exigencias_cartorio e
        LEFT JOIN usuarios u ON u.id = e.responsavel_id
        WHERE e.id = %s AND e.projeto_id = %s
        """,
        (protocol_id, project_id),
        one=True,
    )


def external_stage_all_protocols_withdrawn(project_id, tipo_orgao, stage_id=None):
    summary = external_stage_protocol_summary(project_id, tipo_orgao, stage_id)
    return summary["all_withdrawn"]


def external_stage_has_any_records(project_id, tipo_orgao, stage_id=None):
    orgao_filter = "" if tipo_orgao == EXTERNAL_PROTOCOL_SCOPE else "AND tipo_orgao = %s"
    params = [project_id]
    if orgao_filter:
        params.append(tipo_orgao)
    stage_filter = ""
    if stage_id:
        stage_filter = "AND etapa_id = %s"
        params.append(stage_id)
    return bool(
        scalar(
            get_db(),
            f"""
            SELECT COUNT(*)
            FROM exigencias_cartorio
            WHERE projeto_id = %s
              AND COALESCE(tipo_registro, 'exigencia') = 'protocolo'
              {orgao_filter}
              {stage_filter}
            """,
            params,
        )
    )


def can_finish_external_stage(project_id, stage):
    tipo_orgao = external_stage_type(stage)
    if not tipo_orgao:
        return True, None
    status = ((stage["status"] if "status" in stage else "") or "").lower()
    if status == "nao aplicavel":
        return True, None
    applicability = (stage["applicability"] if "applicability" in stage else "") or ""
    stage_id = stage["id"] if "id" in stage else None
    if applicability in (APPLICABILITY_CONDITIONAL, APPLICABILITY_OPTIONAL) and not external_stage_has_any_records(project_id, tipo_orgao, stage_id):
        return True, None
    if not external_stage_all_protocols_withdrawn(project_id, tipo_orgao, stage_id):
        return False, "Registre um protocolo ou avance sem protocolo nesta etapa. Se ja houver protocolo, registre a retirada antes de concluir."
    return True, None


def maybe_advance_external_stage_after_withdrawal(project_id, tipo_orgao, responsible_id=None):
    db = get_db()
    project = db.execute("SELECT * FROM projetos WHERE id = %s", (project_id,)).fetchone()
    if not project:
        return None
    current_stage_id = project["etapa_atual_id"] or infer_current_stage_id_db(db, project_id)
    current_stage = load_project_stage_for_action(current_stage_id, project_id) if current_stage_id else None
    if external_stage_type(current_stage) != EXTERNAL_PROTOCOL_SCOPE:
        return None
    can_finish, _message = can_finish_external_stage(project_id, current_stage)
    if not can_finish:
        return None
    now = app_now_iso()
    db.execute(
        "UPDATE projeto_etapas SET status = 'concluido', progresso = 100, data_fim = COALESCE(data_fim, %s) WHERE id = %s",
        (now, current_stage["id"]),
    )
    db.commit()
    completed_stage = load_project_stage_for_action(current_stage["id"], project_id)
    next_stage = advance_project_after_stage_completion(project_id, completed_stage, responsible_id, reason="retirada_orgao_externo")
    record_event(project_id, "retirada_orgao_externo", f"{external_stage_label(tipo_orgao)} retirado; etapa concluida.")
    return next_stage


def count_blocking_checklist_pending(stage_id):
    """Itens obrigatorios do checklist que bloqueiam a conclusao da etapa e ainda estao pendentes.

    Mesma regra do required_pending exibido na matriz: obrigatorio + bloqueia etapa +
    nao concluido/nao aplicavel. Enquanto houver item assim, a etapa nao pode avancar.
    """
    row = query_db(
        """
        SELECT COUNT(*) AS pendentes
        FROM project_checklist_items
        WHERE project_stage_id = %s
          AND active = 1
          AND requirement_level = %s
          AND blocks_stage_completion = 1
          AND status NOT IN (%s, %s)
        """,
        (stage_id, REQUIREMENT_REQUIRED, CHECKLIST_STATUS_DONE, CHECKLIST_STATUS_NOT_APPLICABLE),
        one=True,
    )
    return row["pendentes"] or 0


def load_stage_rows(project_id):
    return [dict(row) for row in query_db(
        """
        WITH selected_stages AS (
            SELECT pe.id
            FROM projeto_etapas pe
            JOIN etapas_modelo em ON em.id = pe.etapa_modelo_id
            WHERE pe.projeto_id = %s
              AND em.ativa = 1
              AND COALESCE(pe.show_in_project, 1) = 1
        ),
        pci_stats AS (
            SELECT
                pci.project_stage_id,
                COUNT(*) AS active_count,
                COUNT(*) FILTER (WHERE pci.status != %s) AS total,
                COUNT(*) FILTER (WHERE pci.status = %s) AS done,
                COUNT(*) FILTER (
                    WHERE pci.requirement_level = %s
                      AND pci.blocks_stage_completion = 1
                      AND pci.status NOT IN (%s, %s)
                ) AS required_pending
            FROM project_checklist_items pci
            JOIN selected_stages ss ON ss.id = pci.project_stage_id
            WHERE pci.active = 1
            GROUP BY pci.project_stage_id
        ),
        pci_next AS (
            SELECT DISTINCT ON (pci.project_stage_id)
                pci.project_stage_id,
                pci.title
            FROM project_checklist_items pci
            JOIN selected_stages ss ON ss.id = pci.project_stage_id
            WHERE pci.active = 1
              AND pci.status NOT IN (%s, %s)
            ORDER BY pci.project_stage_id, pci.order_index, pci.id
        ),
        ci_stats AS (
            SELECT
                ci.projeto_etapa_id,
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE ci.concluido = 1) AS done
            FROM checklist_itens ci
            JOIN selected_stages ss ON ss.id = ci.projeto_etapa_id
            GROUP BY ci.projeto_etapa_id
        ),
        ci_next AS (
            SELECT DISTINCT ON (ci.projeto_etapa_id)
                ci.projeto_etapa_id,
                ci.titulo
            FROM checklist_itens ci
            JOIN selected_stages ss ON ss.id = ci.projeto_etapa_id
            WHERE ci.concluido = 0
            ORDER BY ci.projeto_etapa_id, ci.id
        ),
        task_next AS (
            SELECT DISTINCT ON (t.projeto_etapa_id)
                t.projeto_etapa_id,
                t.titulo
            FROM tarefas t
            JOIN selected_stages ss ON ss.id = t.projeto_etapa_id
            WHERE lower(COALESCE(t.status, '')) != 'concluido'
            ORDER BY
                t.projeto_etapa_id,
                CASE t.prioridade WHEN 'Alta' THEN 0 WHEN 'Media' THEN 1 WHEN 'Baixa' THEN 2 ELSE 3 END,
                COALESCE(t.prazo, '9999-12-31'),
                t.id
        )
        SELECT
            pe.*,
            COALESCE(pe.stage_name, em.nome) AS etapa_nome,
            COALESCE(pe.stage_order, em.ordem) AS etapa_ordem,
            em.nome AS legacy_etapa_nome,
            em.ordem AS legacy_etapa_ordem,
            u.nome AS responsavel_nome,
            CASE
                WHEN COALESCE(pci_stats.active_count, 0) > 0 THEN COALESCE(pci_stats.total, 0)
                ELSE COALESCE(ci_stats.total, 0)
            END AS checklist_total,
            CASE
                WHEN COALESCE(pci_stats.active_count, 0) > 0 THEN COALESCE(pci_stats.done, 0)
                ELSE COALESCE(ci_stats.done, 0)
            END AS checklist_done,
            COALESCE(pci_next.title, ci_next.titulo) AS proximo_checklist,
            COALESCE(pci_stats.required_pending, 0) AS required_pending,
            task_next.titulo AS tarefa_ativa
        FROM projeto_etapas pe
        JOIN etapas_modelo em ON em.id = pe.etapa_modelo_id
        LEFT JOIN usuarios u ON u.id = pe.responsavel_id
        LEFT JOIN pci_stats ON pci_stats.project_stage_id = pe.id
        LEFT JOIN pci_next ON pci_next.project_stage_id = pe.id
        LEFT JOIN ci_stats ON ci_stats.projeto_etapa_id = pe.id
        LEFT JOIN ci_next ON ci_next.projeto_etapa_id = pe.id
        LEFT JOIN task_next ON task_next.projeto_etapa_id = pe.id
        WHERE pe.projeto_id = %s
          AND em.ativa = 1
          AND COALESCE(pe.show_in_project, 1) = 1
        ORDER BY COALESCE(pe.stage_order, em.ordem), pe.id
        """,
        (
            project_id,
            CHECKLIST_STATUS_NOT_APPLICABLE,
            CHECKLIST_STATUS_DONE,
            REQUIREMENT_REQUIRED,
            CHECKLIST_STATUS_DONE,
            CHECKLIST_STATUS_NOT_APPLICABLE,
            CHECKLIST_STATUS_DONE,
            CHECKLIST_STATUS_NOT_APPLICABLE,
            project_id,
        ),
    )]


def load_matrix_stage_rows(project_id):
    project = query_db("SELECT etapa_atual_id FROM projetos WHERE id = %s", (project_id,), one=True)
    current_stage_id = project["etapa_atual_id"] if project else None
    global_stages = query_db("SELECT * FROM etapas_modelo WHERE ativa = 1 ORDER BY ordem")
    project_stages = load_stage_rows(project_id)
    stages_by_model = {}
    for stage in project_stages:
        stages_by_model.setdefault(stage["etapa_modelo_id"], []).append(stage)

    matrix_rows = []
    for global_stage in global_stages:
        candidates = stages_by_model.get(global_stage["id"], [])
        selected = None
        if candidates:
            selected = next((stage for stage in candidates if stage["id"] == current_stage_id), None)
            if not selected:
                selected = next(
                    (
                        stage for stage in candidates
                        if stage.get("workflow_active", 1)
                        and str(stage.get("status") or "").lower() not in ("nao aplicavel", "cancelado")
                    ),
                    None,
                )
            selected = selected or candidates[0]

        if selected:
            row = dict(selected)
            row["etapa_ordem"] = global_stage["ordem"]
            row["etapa_nome"] = global_stage["nome"]
            matrix_rows.append(row)
        else:
            matrix_rows.append({
                "id": None,
                "projeto_id": project_id,
                "etapa_modelo_id": global_stage["id"],
                "etapa_nome": global_stage["nome"],
                "legacy_etapa_nome": global_stage["nome"],
                "etapa_ordem": global_stage["ordem"],
                "status": "nao aplicavel",
                "responsavel_nome": None,
                "prazo": None,
                "progresso": 0,
                "checklist_total": 0,
                "checklist_done": 0,
                "required_pending": 0,
                "proximo_checklist": None,
                "tarefa_ativa": None,
                "workflow_active": 0,
                "show_in_project": 0,
            })
    return matrix_rows


def load_matrix_stage_rows_bulk(projects, global_stages=None):
    project_ids = [project["id"] for project in projects]
    if not project_ids:
        return {}

    if global_stages is None:
        global_stages = [dict(row) for row in get_active_stage_models()]
    else:
        global_stages = [dict(row) for row in global_stages]
    placeholders = ",".join("%s" for _ in project_ids)
    active_stage_ids = [project["etapa_atual_id"] for project in projects if project["etapa_atual_id"]]
    stats_placeholders = ",".join("%s" for _ in active_stage_ids)
    selected_stages_sql = (
        f"""
                SELECT pe.id
                FROM projeto_etapas pe
                WHERE pe.id IN ({stats_placeholders})
            """
        if active_stage_ids
        else "SELECT NULL::integer AS id WHERE FALSE"
    )
    stage_stats_params = [
        CHECKLIST_STATUS_NOT_APPLICABLE,
        CHECKLIST_STATUS_DONE,
        REQUIREMENT_REQUIRED,
        CHECKLIST_STATUS_DONE,
        CHECKLIST_STATUS_NOT_APPLICABLE,
        CHECKLIST_STATUS_DONE,
        CHECKLIST_STATUS_NOT_APPLICABLE,
    ]
    params = active_stage_ids + stage_stats_params + project_ids
    project_stages = [
        dict(row)
        for row in query_db(
            f"""
            WITH selected_stages AS (
                {selected_stages_sql}
            ),
            pci_stats AS (
                SELECT
                    pci.project_stage_id,
                    COUNT(*) AS active_count,
                    COUNT(*) FILTER (WHERE pci.status != %s) AS total,
                    COUNT(*) FILTER (WHERE pci.status = %s) AS done,
                    COUNT(*) FILTER (
                        WHERE pci.requirement_level = %s
                          AND pci.blocks_stage_completion = 1
                          AND pci.status NOT IN (%s, %s)
                    ) AS required_pending
                FROM project_checklist_items pci
                JOIN selected_stages ss ON ss.id = pci.project_stage_id
                WHERE pci.active = 1
                GROUP BY pci.project_stage_id
            ),
            pci_next AS (
                SELECT DISTINCT ON (pci.project_stage_id)
                    pci.project_stage_id,
                    pci.title
                FROM project_checklist_items pci
                JOIN selected_stages ss ON ss.id = pci.project_stage_id
                WHERE pci.active = 1
                  AND pci.status NOT IN (%s, %s)
                ORDER BY pci.project_stage_id, pci.order_index, pci.id
            ),
            ci_stats AS (
                SELECT
                    ci.projeto_etapa_id,
                    COUNT(*) AS total,
                    COUNT(*) FILTER (WHERE ci.concluido = 1) AS done
                FROM checklist_itens ci
                JOIN selected_stages ss ON ss.id = ci.projeto_etapa_id
                GROUP BY ci.projeto_etapa_id
            ),
            ci_next AS (
                SELECT DISTINCT ON (ci.projeto_etapa_id)
                    ci.projeto_etapa_id,
                    ci.titulo
                FROM checklist_itens ci
                JOIN selected_stages ss ON ss.id = ci.projeto_etapa_id
                WHERE ci.concluido = 0
                ORDER BY ci.projeto_etapa_id, ci.id
            ),
            task_next AS (
                SELECT DISTINCT ON (t.projeto_etapa_id)
                    t.projeto_etapa_id,
                    t.titulo
                FROM tarefas t
                JOIN selected_stages ss ON ss.id = t.projeto_etapa_id
                WHERE lower(COALESCE(t.status, '')) != 'concluido'
                ORDER BY
                    t.projeto_etapa_id,
                    CASE t.prioridade WHEN 'Alta' THEN 0 WHEN 'Media' THEN 1 WHEN 'Baixa' THEN 2 ELSE 3 END,
                    COALESCE(t.prazo, '9999-12-31')
            )
            SELECT
                pe.*,
                COALESCE(pe.stage_name, em.nome) AS etapa_nome,
                COALESCE(pe.stage_order, em.ordem) AS etapa_ordem,
                em.nome AS legacy_etapa_nome,
                em.ordem AS legacy_etapa_ordem,
                u.nome AS responsavel_nome,
                CASE
                    WHEN COALESCE(pci_stats.active_count, 0) > 0 THEN COALESCE(pci_stats.total, 0)
                    ELSE COALESCE(ci_stats.total, 0)
                END AS checklist_total,
                CASE
                    WHEN COALESCE(pci_stats.active_count, 0) > 0 THEN COALESCE(pci_stats.done, 0)
                    ELSE COALESCE(ci_stats.done, 0)
                END AS checklist_done,
                COALESCE(pci_next.title, ci_next.titulo) AS proximo_checklist,
                COALESCE(pci_stats.required_pending, 0) AS required_pending,
                task_next.titulo AS tarefa_ativa
            FROM projeto_etapas pe
            JOIN etapas_modelo em ON em.id = pe.etapa_modelo_id
            LEFT JOIN usuarios u ON u.id = pe.responsavel_id
            LEFT JOIN pci_stats ON pci_stats.project_stage_id = pe.id
            LEFT JOIN pci_next ON pci_next.project_stage_id = pe.id
            LEFT JOIN ci_stats ON ci_stats.projeto_etapa_id = pe.id
            LEFT JOIN ci_next ON ci_next.projeto_etapa_id = pe.id
            LEFT JOIN task_next ON task_next.projeto_etapa_id = pe.id
            WHERE pe.projeto_id IN ({placeholders})
              AND em.ativa = 1
              AND COALESCE(pe.show_in_project, 1) = 1
            ORDER BY pe.projeto_id, COALESCE(pe.stage_order, em.ordem), pe.id
            """,
            params,
        )
    ]
    stages_by_project_model = {}
    external_model_id = next((stage["id"] for stage in global_stages if stage_key(stage["nome"]) == "cartorio"), None)
    for stage in project_stages:
        model_id = stage["etapa_modelo_id"]
        if external_model_id and (
            (stage.get("stage_key") or "") == "PREFEITURA"
            or stage_key(stage.get("legacy_etapa_nome") or "") == "prefeitura"
        ):
            model_id = external_model_id
        stages_by_project_model.setdefault(stage["projeto_id"], {}).setdefault(model_id, []).append(stage)

    current_stage_by_project = {project["id"]: project["etapa_atual_id"] for project in projects}
    rows_by_project = {}
    for project_id in project_ids:
        project_rows = []
        stages_by_model = stages_by_project_model.get(project_id, {})
        current_stage_id = current_stage_by_project.get(project_id)
        for global_stage in global_stages:
            candidates = stages_by_model.get(global_stage["id"], [])
            selected = None
            if candidates:
                selected = next((stage for stage in candidates if stage["id"] == current_stage_id), None)
                if not selected:
                    selected = next(
                        (
                            stage for stage in candidates
                            if stage.get("workflow_active", 1)
                            and str(stage.get("status") or "").lower() not in ("nao aplicavel", "cancelado")
                        ),
                        None,
                    )
                selected = selected or candidates[0]

            if selected:
                row = dict(selected)
                row["etapa_ordem"] = global_stage["ordem"]
                row["etapa_nome"] = global_stage["nome"]
                project_rows.append(row)
            else:
                project_rows.append({
                    "id": None,
                    "projeto_id": project_id,
                    "etapa_modelo_id": global_stage["id"],
                    "etapa_nome": global_stage["nome"],
                    "legacy_etapa_nome": global_stage["nome"],
                    "etapa_ordem": global_stage["ordem"],
                    "status": "nao aplicavel",
                    "responsavel_nome": None,
                    "prazo": None,
                    "progresso": 0,
                    "checklist_total": 0,
                    "checklist_done": 0,
                    "required_pending": 0,
                    "proximo_checklist": None,
                    "tarefa_ativa": None,
                    "workflow_active": 0,
                    "show_in_project": 0,
                })
        rows_by_project[project_id] = project_rows
    return rows_by_project


def load_project_stage_for_action(stage_id, project_id=None):
    params = [stage_id]
    project_filter = ""
    if project_id is not None:
        project_filter = "AND pe.projeto_id = %s"
        params.append(project_id)
    return query_db(
        f"""
        SELECT
            pe.*,
            COALESCE(pe.stage_name, em.nome) AS etapa_nome,
            COALESCE(pe.stage_order, em.ordem) AS etapa_ordem,
            em.nome AS legacy_etapa_nome,
            em.ordem AS legacy_etapa_ordem
        FROM projeto_etapas pe
        JOIN etapas_modelo em ON em.id = pe.etapa_modelo_id
        WHERE pe.id = %s
          {project_filter}
          AND em.ativa = 1
          AND COALESCE(pe.show_in_project, 1) = 1
        """,
        tuple(params),
        one=True,
    )


def get_stage_blocking_checklist_items(stage_id):
    return query_db(
        """
        SELECT *
        FROM project_checklist_items
        WHERE project_stage_id = %s
          AND active = 1
          AND requirement_level = %s
          AND blocks_stage_completion = 1
          AND status NOT IN (%s, %s)
        ORDER BY order_index, id
        """,
        (stage_id, REQUIREMENT_REQUIRED, CHECKLIST_STATUS_DONE, CHECKLIST_STATUS_NOT_APPLICABLE),
    )


def flash_stage_blockers(blockers):
    titles = ", ".join(item["title"] for item in blockers[:4])
    suffix = "..." if len(blockers) > 4 else ""
    flash(f"Conclua ou marque como nao aplicavel os itens obrigatorios antes de concluir a etapa: {titles}{suffix}", "warning")


def get_next_applicable_stage(project_id, current_stage):
    return query_db(
        """
        SELECT
            pe.*,
            COALESCE(pe.stage_name, em.nome) AS etapa_nome,
            COALESCE(pe.stage_order, em.ordem) AS etapa_ordem
        FROM projeto_etapas pe
        JOIN etapas_modelo em ON em.id = pe.etapa_modelo_id
        WHERE pe.projeto_id = %s
          AND COALESCE(pe.show_in_project, 1) = 1
          AND COALESCE(pe.workflow_active, 1) = 1
          AND lower(pe.status) NOT IN ('concluido', 'cancelado', 'nao aplicavel')
          AND COALESCE(pe.stage_order, em.ordem) > %s
        ORDER BY COALESCE(pe.stage_order, em.ordem), pe.id
        LIMIT 1
        """,
        (project_id, current_stage["etapa_ordem"]),
        one=True,
    )


def advance_project_after_stage_completion(project_id, completed_stage, responsible_id=None, reason="conclusao_etapa"):
    project = query_db("SELECT * FROM projetos WHERE id = %s", (project_id,), one=True)
    if not project or not completed_stage or project["etapa_atual_id"] != completed_stage["id"]:
        return None

    now = app_now_iso()
    next_stage = get_next_applicable_stage(project_id, completed_stage)
    if next_stage:
        execute_db(
            """
            UPDATE projeto_etapas
            SET status = 'em andamento', data_inicio = COALESCE(data_inicio, %s), data_fim = NULL,
                responsavel_id = COALESCE(responsavel_id, %s), progresso = CASE WHEN COALESCE(progresso, 0) < 10 THEN 10 ELSE progresso END
            WHERE id = %s
            """,
            (now, responsible_id, next_stage["id"]),
        )
        execute_db(
            "UPDATE projetos SET etapa_atual_id = %s, status = 'Em andamento', atualizado_em = %s WHERE id = %s",
            (next_stage["id"], now, project_id),
        )
        execute_db(
            """
            INSERT INTO movimentacoes_etapa
                (projeto_id, etapa_anterior_id, etapa_nova_id, etapa_anterior, etapa_nova, motivo, observacao, responsavel_id, usuario_id, criado_em)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                project_id,
                completed_stage["id"],
                next_stage["id"],
                completed_stage["etapa_nome"],
                next_stage["etapa_nome"],
                reason,
                "Avanco automatico apos conclusao de etapa.",
                responsible_id or next_stage["responsavel_id"],
                g.user["id"] if getattr(g, "user", None) else None,
                now,
            ),
        )
        record_stage_history_transition(project_id, completed_stage, next_stage, now, responsible_id or next_stage["responsavel_id"], reason)
        return next_stage

    execute_db(
        "UPDATE projetos SET status = 'Concluido', atualizado_em = %s WHERE id = %s",
        (now, project_id),
    )
    execute_db(
        """
        UPDATE project_stage_history
        SET exited_at = COALESCE(exited_at, %s)
        WHERE project_id = %s AND stage_id = %s AND exited_at IS NULL
        """,
        (now, project_id, completed_stage["id"]),
    )
    return None


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
        if getattr(g, "user", None) is None:
            session.clear()
            return redirect(url_for("login"))
        return view(**kwargs)

    return wrapped_view


@app.before_request
def load_logged_user():
    g.user = None
    user_id = session.get("user_id")
    if user_id:
        # Cache curto: evita uma ida ao banco em todo request. Qualquer escrita
        # (execute_db) invalida o cache, entao alteracoes de usuario valem na hora.
        g.user = get_cached_lookup(
            ("logged_user", user_id),
            lambda: query_db(
                "SELECT * FROM usuarios WHERE id = %s AND ativo = 1",
                (user_id,),
                one=True,
            ),
            ttl_seconds=USER_CACHE_TTL_SECONDS,
        )


def format_date(value):
    if not value:
        return "-"
    try:
        return datetime.fromisoformat(value).strftime("%d/%m/%Y")
    except ValueError:
        return value


def app_now():
    return datetime.now(APP_TIMEZONE).replace(tzinfo=None, microsecond=0)


def app_now_iso():
    return app_now().isoformat(timespec="seconds")


def app_today():
    return app_now().date()


def format_datetime(value):
    if not value:
        return "-"
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo:
            parsed = parsed.astimezone(APP_TIMEZONE).replace(tzinfo=None)
        return parsed.strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return value


def is_overdue(value, status=None):
    if not value or str(status or "").lower() in ("concluido", "cancelado", "aguardando externo"):
        return False
    try:
        return datetime.fromisoformat(value).date() < app_today()
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


def normalize_lookup(value):
    text = unicodedata.normalize("NFD", str(value or ""))
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return "".join(ch for ch in text.lower() if ch.isalnum())


def parse_currency_value(value):
    parsed = parse_decimal_br(value)
    if parsed is None:
        return None
    try:
        return float(parsed)
    except (TypeError, ValueError):
        return None


def get_cliente_display_name(cliente_id):
    if not cliente_id:
        return ""
    row = query_db(
        """
        SELECT
            COALESCE(
                NULLIF(c.nome_exibicao, ''),
                NULLIF(pf.nome_completo, ''),
                NULLIF(pj.razao_social, ''),
                NULLIF(c.nome, '')
            ) AS nome_display
        FROM clientes c
        LEFT JOIN pessoas_fisicas pf ON pf.cliente_id = c.id
        LEFT JOIN pessoas_juridicas pj ON pj.cliente_id = c.id
        WHERE c.id = %s
        """,
        (cliente_id,),
        one=True,
    )
    return row["nome_display"] if row and row["nome_display"] else ""


def _fetch_cliente_autocomplete_options_uncached():
    rows = query_db(
        """
        SELECT
            c.id,
            c.tipo_cliente,
            c.status_cadastro,
            c.nome,
            c.nome_exibicao,
            c.cpf_cnpj,
            c.telefone,
            c.email,
            pf.nome_completo AS pf_nome,
            pf.cpf AS pf_cpf,
            pf.email AS pf_email,
            pf.telefone AS pf_telefone,
            ep.cidade AS pf_cidade,
            ep.uf AS pf_uf,
            pj.razao_social AS pj_razao_social,
            pj.nome_fantasia AS pj_nome_fantasia,
            pj.cnpj AS pj_cnpj,
            pj.email AS pj_email,
            pj.telefone AS pj_telefone,
            pj.cidade AS pj_cidade,
            pj.uf AS pj_uf,
            pr.nome_completo AS procurador_nome,
            pr.cpf AS procurador_cpf,
            pr.email AS procurador_email,
            pr.telefone AS procurador_telefone,
            COALESCE(
                NULLIF(c.nome_exibicao, ''),
                NULLIF(pf.nome_completo, ''),
                NULLIF(pj.razao_social, ''),
                NULLIF(c.nome, '')
            ) AS nome_display,
            COALESCE(ep.cidade, pj.cidade) AS cidade_display,
            COALESCE(ep.uf, pj.uf) AS uf_display
        FROM clientes c
        LEFT JOIN pessoas_fisicas pf ON pf.cliente_id = c.id
        LEFT JOIN enderecos_proprietario ep ON ep.pessoa_fisica_id = pf.id
        LEFT JOIN pessoas_juridicas pj ON pj.cliente_id = c.id
        LEFT JOIN LATERAL (
            SELECT *
            FROM procuradores
            WHERE cliente_id = c.id
            ORDER BY principal DESC, id
            LIMIT 1
        ) pr ON TRUE
        ORDER BY
            lower(COALESCE(
                NULLIF(c.nome_exibicao, ''),
                NULLIF(pf.nome_completo, ''),
                NULLIF(pj.razao_social, ''),
                NULLIF(c.nome, '')
            )),
            lower(COALESCE(c.nome, ''))
        """
    )
    options = []
    for row in rows:
        nome = row["nome_display"] or row["nome"] or f"Cliente #{row['id']}"
        search = " ".join(
            str(value or "")
            for value in (
                nome,
                row["nome"],
                row["nome_exibicao"],
                row["cpf_cnpj"],
                row["telefone"],
                row["email"],
                row["pf_nome"],
                row["pf_cpf"],
                row["pf_email"],
                row["pf_telefone"],
                row["pj_razao_social"],
                row["pj_nome_fantasia"],
                row["pj_cnpj"],
                row["pj_email"],
                row["pj_telefone"],
                row["cidade_display"],
                row["uf_display"],
                row["procurador_nome"],
                row["procurador_cpf"],
                row["procurador_email"],
                row["procurador_telefone"],
            )
        )
        options.append(
            {
                "id": row["id"],
                "nome": nome,
                "tipo_cliente": row["tipo_cliente"],
                "status_cadastro": row["status_cadastro"],
                "cidade": row["cidade_display"] or "",
                "uf": row["uf_display"] or "",
                "search": search,
            }
        )
    return options


def fetch_cliente_autocomplete_options():
    return get_cached_lookup("cliente_autocomplete_options", _fetch_cliente_autocomplete_options_uncached)


def get_active_stage_models():
    return get_cached_lookup(
        "active_stage_models",
        lambda: query_db(
            """
            SELECT id,
                   CASE WHEN lower(nome) = 'cartorio' THEN 'Orgao externo' ELSE nome END AS nome,
                   ordem, cor_padrao, ativa
            FROM etapas_modelo
            WHERE ativa = 1 AND lower(nome) != 'prefeitura'
            ORDER BY ordem
            """
        ),
    )


def get_active_users():
    return get_cached_lookup(
        "active_users",
        lambda: query_db("SELECT * FROM usuarios WHERE ativo = 1 ORDER BY nome"),
    )


def get_cartorio_options():
    return get_cached_lookup(
        "cartorio_options",
        lambda: query_db("SELECT * FROM cartorios ORDER BY nome"),
    )


def get_matrix_summary_counts(today_iso, in_7):
    return get_cached_lookup(
        ("matrix_summary_counts", today_iso, in_7),
        lambda: query_db(
            """
            SELECT
                (
                    SELECT COUNT(*)
                    FROM projeto_etapas pe
                    JOIN etapas_modelo em ON em.id = pe.etapa_modelo_id
                    WHERE em.ativa = 1
                      AND pe.id IN (SELECT etapa_atual_id FROM projetos WHERE etapa_atual_id IS NOT NULL)
                      AND pe.prazo BETWEEN %s AND %s
                      AND lower(pe.status) NOT IN ('concluido', 'cancelado')
                ) AS sete_dias,
                (
                    SELECT COUNT(*)
                    FROM projeto_etapas
                    WHERE lower(status) = 'atrasado'
                      AND id IN (SELECT etapa_atual_id FROM projetos WHERE etapa_atual_id IS NOT NULL)
                ) AS atrasados,
                (
                    SELECT COUNT(*)
                    FROM projetos p
                    JOIN projeto_etapas pe ON pe.id = p.etapa_atual_id
                    JOIN etapas_modelo em ON em.id = pe.etapa_modelo_id
                    WHERE pe.stage_key IN ('ORGAO_EXTERNO', 'PREFEITURA')
                       OR lower(em.nome) IN ('cartorio', 'orgao externo', 'prefeitura')
                ) AS cartorio,
                (
                    SELECT COUNT(*)
                    FROM pendencias
                    WHERE lower(status) NOT IN ('resolvida', 'cancelada')
                ) AS pendencias
            """,
            (today_iso, in_7),
            one=True,
        ),
        ttl_seconds=30,
    )


def get_matrix_static_options():
    def load_options():
        row = query_db(
            """
            SELECT
                COALESCE(
                    (
                        SELECT json_agg(row_to_json(s))
                        FROM (
                            SELECT id,
                                   CASE WHEN lower(nome) = 'cartorio' THEN 'Orgao externo' ELSE nome END AS nome,
                                   ordem, cor_padrao, ativa
                            FROM etapas_modelo
                            WHERE ativa = 1 AND lower(nome) != 'prefeitura'
                            ORDER BY ordem
                        ) s
                    ),
                    '[]'::json
                ) AS etapas,
                COALESCE(
                    (
                        SELECT json_agg(row_to_json(u))
                        FROM (SELECT * FROM usuarios WHERE ativo = 1 ORDER BY nome) u
                    ),
                    '[]'::json
                ) AS usuarios,
                COALESCE(
                    (
                        SELECT json_agg(row_to_json(c))
                        FROM (SELECT * FROM cartorios ORDER BY nome) c
                    ),
                    '[]'::json
                ) AS cartorios,
                COALESCE(
                    (
                        SELECT json_agg(row_to_json(tp))
                        FROM (SELECT * FROM tipos_processo WHERE ativo = 1 ORDER BY ordem, nome) tp
                    ),
                    '[]'::json
                ) AS process_types
            """,
            one=True,
        )
        return {
            "etapas": row["etapas"] or [],
            "usuarios": row["usuarios"] or [],
            "cartorios": row["cartorios"] or [],
            "process_types": row["process_types"] or [],
        }

    return get_cached_lookup("matrix_static_options", load_options)


def find_cliente_option_by_name(nome):
    wanted = normalize_lookup(nome)
    if not wanted:
        return None
    for option in fetch_cliente_autocomplete_options():
        if normalize_lookup(option["nome"]) == wanted:
            return option
    return None


def find_cliente_options_by_name(nome):
    wanted = normalize_lookup(nome)
    if not wanted:
        return []
    return [option for option in fetch_cliente_autocomplete_options() if normalize_lookup(option["nome"]) == wanted]


def create_draft_cliente(nome, origem="criado_no_projeto", duplicate_note=""):
    clean_name = (nome or "").strip()
    if not clean_name:
        return None
    now = app_now_iso()
    observacoes = f"Cliente rascunho. Origem: {origem}."
    if duplicate_note:
        observacoes = f"{observacoes} Diferenciador: {duplicate_note.strip()}"
    db = get_db()
    cursor = db.execute(
        """
        INSERT INTO clientes
            (nome, tipo_cliente, nome_exibicao, quem_assina, status_cadastro, tipo_pessoa, observacoes, criado_em, atualizado_em)
        VALUES (%s, 'PESSOA_FISICA', %s, 'PROPRIETARIO', 'RASCUNHO', 'fisica', %s, %s, %s)
        RETURNING id
        """,
        (
            clean_name,
            clean_name,
            observacoes,
            now,
            now,
        ),
    )
    cliente_id = cursor.fetchone()["id"]
    db.execute(
        """
        INSERT INTO pessoas_fisicas
            (cliente_id, nome_completo, criado_em, atualizado_em)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT DO NOTHING
        """,
        (cliente_id, clean_name, now, now),
    )
    db.commit()
    invalidate_runtime_caches()
    return cliente_id


def resolve_project_cliente(form, fallback_name=""):
    raw_cliente_id = (form.get("cliente_id") or "").strip()
    cliente_nome = (form.get("cliente_nome") or form.get("proprietario") or "").strip()

    if raw_cliente_id:
        display_name = get_cliente_display_name(raw_cliente_id)
        if display_name:
            return raw_cliente_id, display_name

    if cliente_nome:
        existing = find_cliente_option_by_name(cliente_nome)
        if existing:
            return existing["id"], existing["nome"]
        cliente_id = create_draft_cliente(cliente_nome)
        return cliente_id, cliente_nome

    return None, (fallback_name or "").strip()


def get_process_type_options():
    return get_cached_lookup(
        "process_type_options",
        lambda: query_db(
            """
            SELECT *
            FROM tipos_processo
            WHERE ativo = 1
            ORDER BY ordem, nome
            """
        ),
    )


def normalize_project_process_type(value):
    return resolve_process_type_key((value or "").strip())


def normalize_additional_process_types(values, primary_key=None):
    primary = normalize_project_process_type(primary_key) if primary_key else None
    normalized = []
    for value in values or []:
        key = normalize_project_process_type(value)
        if not key or key == "OUTRO" or key == primary or key in normalized:
            continue
        normalized.append(key)
    return normalized


def encode_process_list(values):
    return json.dumps(values or [], ensure_ascii=False)


def decode_process_list(value):
    if not value:
        return []
    try:
        data = json.loads(value)
    except (TypeError, ValueError):
        data = None
    if isinstance(data, list):
        return [str(item) for item in data if item]
    return [part.strip() for part in str(value).split(",") if part.strip()]


def process_service_names(value):
    return [process_type_name(key) or key for key in decode_process_list(value)]


def get_stage_template_for_process(process_type_key):
    return get_config_stage_template_for_process(normalize_project_process_type(process_type_key))


def get_applicable_stages_for_process(process_type_key, include_optional=False, include_conditional=True):
    return get_config_applicable_stages_for_process(
        normalize_project_process_type(process_type_key),
        include_optional=include_optional,
        include_conditional=include_conditional,
    )


def get_non_applicable_stages_for_process(process_type_key):
    return [
        stage_template
        for stage_template in get_stage_template_for_process(process_type_key)
        if stage_template["applicability"] == APPLICABILITY_NOT_APPLICABLE
    ]


def get_checklist_template_for_process(process_type_key):
    return get_config_checklist_template_for_process(normalize_project_process_type(process_type_key))


def get_checklist_template_for_process_stage(process_type_key, stage_key):
    return get_config_checklist_template_for_process_stage(
        normalize_project_process_type(process_type_key),
        stage_key,
    )


def get_checklist_progress(items):
    active_items = [item for item in items if item["status"] != CHECKLIST_STATUS_NOT_APPLICABLE]
    total = len(active_items)
    done = len([item for item in active_items if item["status"] == CHECKLIST_STATUS_DONE])
    required_pending = [
        item for item in active_items
        if item["requirement_level"] == REQUIREMENT_REQUIRED and item["status"] != CHECKLIST_STATUS_DONE
    ]
    critical_pending = [
        item for item in active_items
        if item["criticality"] == CRITICALITY_CRITICAL and item["status"] != CHECKLIST_STATUS_DONE
    ]
    stage_blockers = [
        item for item in active_items
        if item["blocks_stage_completion"] and item["status"] != CHECKLIST_STATUS_DONE
    ]
    process_blockers = [
        item for item in active_items
        if item["blocks_process_completion"] and item["status"] != CHECKLIST_STATUS_DONE
    ]
    return {
        "total": total,
        "done": done,
        "required_pending": len(required_pending),
        "critical_pending": len(critical_pending),
        "percent": int((done / total) * 100) if total else 0,
        "can_advance_stage": True,
        "has_stage_blockers": len(stage_blockers) > 0,
        "can_finish_project": True,
    }


def get_stage_checklist_progress(project_id, stage_key):
    items = query_db(
        """
        SELECT *
        FROM project_checklist_items
        WHERE project_id = %s AND stage_key = %s AND active = 1
        ORDER BY order_index, id
        """,
        (project_id, stage_key),
    )
    return get_checklist_progress(items)


def load_project_checklist_items(project_id):
    return query_db(
        """
        SELECT pci.*, u.nome AS completed_by_name
        FROM project_checklist_items pci
        LEFT JOIN usuarios u ON u.id = pci.completed_by
        WHERE pci.project_id = %s AND pci.active = 1
        ORDER BY
            CASE pci.stage_key
                WHEN 'ORCAMENTO' THEN 1
                WHEN 'DOCUMENTOS' THEN 2
                WHEN 'ANALISE' THEN 3
                WHEN 'PREPARACAO' THEN 4
                WHEN 'MEDICAO' THEN 5
                WHEN 'PROCESSAMENTO' THEN 6
                WHEN 'ESCRITORIO' THEN 7
                WHEN 'CONFERENCIA' THEN 8
                WHEN 'ASSINATURAS' THEN 9
                WHEN 'PREFEITURA' THEN 10
                WHEN 'ORGAO_EXTERNO' THEN 11
                WHEN 'PENDENCIAS' THEN 12
                WHEN 'ENTREGA' THEN 13
                WHEN 'FINALIZADO' THEN 14
                ELSE 999
            END,
            pci.order_index,
            pci.id
        """,
        (project_id,),
    )


def group_project_checklist_by_stage(items):
    grouped = []
    by_stage = {}
    for item in items:
        by_stage.setdefault(item["stage_key"], []).append(item)
    for stage_key_value, stage_items in sorted(
        by_stage.items(),
        key=lambda pair: PROCESS_CHECKLIST_STAGE_ORDER.get(pair[0], 999),
    ):
        grouped.append(
            {
                "stage_key": stage_key_value,
                "stage_name": stage_items[0]["stage_name"] or PROCESS_CHECKLIST_STAGE_NAMES.get(stage_key_value, stage_key_value),
                "stage_items": stage_items,
                "progress": get_checklist_progress(stage_items),
            }
        )
    return grouped


@app.context_processor
def utility_processor():
    return {
        "status_meta": STATUS_META,
        "status_options": list(STATUS_META.keys()),
        "applicability_meta": APPLICABILITY_META,
        "role_labels": ROLE_LABELS,
        "format_date": format_date,
        "format_datetime": format_datetime,
        "is_overdue": is_overdue,
        "file_url": file_url,
        "minutes_to_hours": minutes_to_hours,
        "format_days": format_days,
        "format_currency": format_currency,
        "format_cpf": format_cpf,
        "format_cnpj": format_cnpj,
        "format_cep": format_cep,
        "format_phone": format_phone,
        "process_type_name": process_type_name,
        "process_service_names": process_service_names,
        "checklist_status_done": CHECKLIST_STATUS_DONE,
        "checklist_status_not_started": CHECKLIST_STATUS_NOT_STARTED,
        "checklist_status_in_progress": CHECKLIST_STATUS_IN_PROGRESS,
        "checklist_status_not_applicable": CHECKLIST_STATUS_NOT_APPLICABLE,
        "checklist_requirement_required": REQUIREMENT_REQUIRED,
        "checklist_requirement_recommended": REQUIREMENT_RECOMMENDED,
        "checklist_requirement_optional": REQUIREMENT_OPTIONAL,
        "checklist_requirement_conditional": REQUIREMENT_CONDITIONAL,
        "can_manage": can_manage,
        "can_admin": can_admin,
        "today_iso": app_today().isoformat(),
        "ufs": UFS,
    }


PASSWORD_RESET_REQUEST_MESSAGE = (
    "Se o e-mail informado estiver cadastrado e ativo, enviaremos as instrucoes para redefinir a senha."
)


def password_reset_token_hash(token):
    return hashlib.sha256((token or "").encode("utf-8")).hexdigest()


def password_reset_expires_at():
    minutes = max(5, PASSWORD_RESET_TOKEN_MINUTES)
    return (app_now() + timedelta(minutes=minutes)).isoformat(timespec="seconds")


def request_ip_address():
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or ""


def build_password_reset_url(token):
    path = url_for("reset_password", token=token)
    if APP_PUBLIC_URL:
        return f"{APP_PUBLIC_URL}{path}"
    return url_for("reset_password", token=token, _external=True)


def create_password_reset_token(usuario):
    now = app_now_iso()
    token = secrets.token_urlsafe(32)
    execute_db(
        """
        DELETE FROM senha_reset_tokens
        WHERE usuario_id = %s AND (used_at IS NOT NULL OR expires_at < %s)
        """,
        (usuario["id"], now),
    )
    execute_db(
        """
        UPDATE senha_reset_tokens
        SET used_at = %s
        WHERE usuario_id = %s AND used_at IS NULL
        """,
        (now, usuario["id"]),
    )
    execute_db(
        """
        INSERT INTO senha_reset_tokens
            (usuario_id, token_hash, email, expires_at, request_ip, user_agent, criado_em)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (
            usuario["id"],
            password_reset_token_hash(token),
            usuario["email"],
            password_reset_expires_at(),
            request_ip_address(),
            (request.headers.get("User-Agent") or "")[:300],
            now,
        ),
    )
    return token


def send_password_reset_email(usuario, reset_url):
    if not SMTP_HOST:
        app.logger.warning(
            "SMTP nao configurado. Link de recuperacao para %s nao foi enviado.",
            usuario["email"],
        )
        return False

    message = EmailMessage()
    message["Subject"] = "Recuperacao de senha - GeoGestao"
    message["From"] = SMTP_FROM
    message["To"] = usuario["email"]
    message.set_content(
        "\n".join(
            [
                f"Ola, {usuario['nome']}.",
                "",
                "Recebemos uma solicitacao para redefinir sua senha no GeoGestao.",
                f"Acesse o link abaixo em ate {max(5, PASSWORD_RESET_TOKEN_MINUTES)} minutos:",
                "",
                reset_url,
                "",
                "Se voce nao solicitou essa alteracao, ignore este e-mail.",
            ]
        )
    )

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as smtp:
            if SMTP_USE_TLS:
                smtp.starttls()
            if SMTP_USER:
                smtp.login(SMTP_USER, SMTP_PASSWORD)
            smtp.send_message(message)
        return True
    except Exception:
        app.logger.exception("Falha ao enviar e-mail de recuperacao para %s.", usuario["email"])
        return False


def get_valid_password_reset(token):
    if not token:
        return None
    row = query_db(
        """
        SELECT
            srt.*,
            u.nome AS usuario_nome,
            u.email AS usuario_email,
            u.ativo AS usuario_ativo
        FROM senha_reset_tokens srt
        JOIN usuarios u ON u.id = srt.usuario_id
        WHERE srt.token_hash = %s
        """,
        (password_reset_token_hash(token),),
        one=True,
    )
    if not row or row["used_at"] or not row["usuario_ativo"]:
        return None
    try:
        expires_at = datetime.fromisoformat(row["expires_at"])
    except (TypeError, ValueError):
        return None
    if expires_at < app_now():
        return None
    return row


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        senha = request.form["senha"]
        usuario = query_db("SELECT * FROM usuarios WHERE lower(email) = %s", [email], one=True)
        if usuario and check_password_hash(usuario["senha_hash"], senha) and usuario["ativo"]:
            session.clear()
            session["user_id"] = usuario["id"]
            return redirect(url_for("dashboard"))
        if usuario and check_password_hash(usuario["senha_hash"], senha) and not usuario["ativo"]:
            flash("Seu cadastro ainda aguarda aprovacao de um administrador.", "warning")
            return render_template("login.html")
        flash("E-mail ou senha invalidos.", "danger")
    return render_template("login.html")


@app.route("/forgot-password", methods=["GET", "POST"])
@app.route("/recuperar-senha", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        if not validate_email(email):
            flash("Informe um e-mail valido.", "danger")
            return render_template("forgot_password.html")

        usuario = query_db(
            "SELECT * FROM usuarios WHERE lower(email) = %s AND ativo = 1",
            (email,),
            one=True,
        )
        if usuario:
            token = create_password_reset_token(usuario)
            reset_url = build_password_reset_url(token)
            email_sent = send_password_reset_email(usuario, reset_url)
            if not email_sent:
                app.logger.warning("Solicitacao de recuperacao registrada para %s.", email)

        flash(PASSWORD_RESET_REQUEST_MESSAGE, "success")
        if not SMTP_HOST:
            flash(
                "O envio automatico ainda precisa das variaveis SMTP configuradas no servidor.",
                "warning",
            )
        return redirect(url_for("forgot_password"))
    return render_template("forgot_password.html")


@app.route("/reset-password/<token>", methods=["GET", "POST"])
@app.route("/redefinir-senha/<token>", methods=["GET", "POST"])
def reset_password(token):
    reset = get_valid_password_reset(token)
    if not reset:
        flash("Link de recuperacao invalido ou expirado.", "danger")
        return redirect(url_for("forgot_password"))

    if request.method == "POST":
        password = request.form.get("senha", "")
        password_confirm = request.form.get("senha_confirmacao", "")
        if len(password) < 6:
            flash("A senha deve ter pelo menos 6 caracteres.", "danger")
            return render_template("reset_password.html", reset=reset, token=token)
        if password != password_confirm:
            flash("As senhas nao conferem.", "danger")
            return render_template("reset_password.html", reset=reset, token=token)

        now = app_now_iso()
        execute_db(
            "UPDATE usuarios SET senha_hash = %s WHERE id = %s",
            (generate_password_hash(password), reset["usuario_id"]),
        )
        execute_db(
            """
            UPDATE senha_reset_tokens
            SET used_at = COALESCE(used_at, %s)
            WHERE usuario_id = %s AND used_at IS NULL
            """,
            (now, reset["usuario_id"]),
        )
        session.clear()
        flash("Senha redefinida com sucesso. Entre com a nova senha.", "success")
        return redirect(url_for("login"))

    return render_template("reset_password.html", reset=reset, token=token)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("nome", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("senha", "")
        password_confirm = request.form.get("senha_confirmacao", "")
        if not name or not email or not password:
            flash("Informe nome completo, e-mail e senha.", "danger")
            return render_template("register.html")
        if password != password_confirm:
            flash("As senhas nao conferem.", "danger")
            return render_template("register.html")
        if len(password) < 6:
            flash("A senha deve ter pelo menos 6 caracteres.", "danger")
            return render_template("register.html")
        existing = query_db("SELECT id, ativo FROM usuarios WHERE lower(email) = %s", (email,), one=True)
        if existing:
            if existing["ativo"]:
                flash("Ja existe um usuario ativo com este e-mail.", "danger")
            else:
                flash("Este e-mail ja possui cadastro aguardando aprovacao.", "warning")
            return render_template("register.html")
        execute_db(
            """
            INSERT INTO usuarios (nome, email, senha_hash, perfil_acesso, cargo, ativo)
            VALUES (%s, %s, %s, 'consulta', '', 0)
            """,
            (name, email, generate_password_hash(password)),
        )
        flash("Cadastro enviado. Aguarde a aprovacao de um administrador para entrar.", "success")
        return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def dashboard():
    refresh_due_statuses()
    today = app_today()
    in_7 = (today + timedelta(days=7)).isoformat()
    today_iso = today.isoformat()

    dashboard_counts = query_db(
        """
        SELECT
            (SELECT COUNT(*) FROM projetos) AS total_projects,
            (
                SELECT COUNT(*)
                FROM projetos
                WHERE lower(COALESCE(status, '')) NOT IN ('concluido', 'cancelado')
            ) AS active_projects,
            (
                SELECT COUNT(*)
                FROM exigencias_cartorio
                WHERE lower(COALESCE(status, '')) NOT IN ('concluido', 'cancelado')
                  AND COALESCE(prazo_resposta, '') != '' AND prazo_resposta < %s
            ) AS overdue,
            (
                SELECT COUNT(*)
                FROM projeto_etapas
                WHERE lower(status) = 'aguardando externo'
                  AND id IN (SELECT etapa_atual_id FROM projetos WHERE etapa_atual_id IS NOT NULL)
            ) AS waiting_external,
            (
                SELECT COUNT(*)
                FROM exigencias_cartorio
                WHERE lower(COALESCE(status, '')) NOT IN ('concluido', 'cancelado')
                  AND prazo_resposta BETWEEN %s AND %s
            ) AS due_soon_count,
            (
                SELECT COUNT(*)
                FROM exigencias_cartorio
                WHERE lower(status) NOT IN ('concluido', 'cancelado')
            ) AS exigencias_count,
            (
                SELECT COUNT(*)
                FROM pendencias
                WHERE lower(status) NOT IN ('resolvida', 'cancelada')
            ) AS pendencias_count
        """,
        (today_iso, today_iso, in_7),
        one=True,
    )
    # As 5 prioridades — topo da ordem da matriz, somente projetos ativos.
    priority_projects = query_db(
        """
        SELECT p.id, p.codigo, p.nome,
               COALESCE(NULLIF(c.nome_exibicao, ''), NULLIF(c.nome, ''), p.proprietario) AS cliente_nome,
               em.nome AS etapa_nome, pe.status AS etapa_status,
               deadline.external_deadline,
               deadline.operational_deadline,
               stale.stale_days,
               stale.stale_rank,
               COALESCE(u.nome, ug.nome) AS responsavel_nome
        FROM projetos p
        LEFT JOIN clientes c ON c.id = p.cliente_id
        LEFT JOIN projeto_etapas pe ON pe.id = p.etapa_atual_id
        LEFT JOIN etapas_modelo em ON em.id = pe.etapa_modelo_id
        LEFT JOIN usuarios u ON u.id = pe.responsavel_id
        LEFT JOIN usuarios ug ON ug.id = p.responsavel_geral_id
        LEFT JOIN LATERAL (
            SELECT
                (
                    SELECT MIN(e.prazo_resposta)
                    FROM exigencias_cartorio e
                    WHERE e.projeto_id = p.id
                      AND lower(COALESCE(e.status, '')) NOT IN ('concluido', 'cancelado')
                      AND COALESCE(e.prazo_resposta, '') != ''
                ) AS external_deadline,
                LEAST(
                    NULLIF(pe.prazo, ''),
                    (
                        SELECT MIN(pd.prazo)
                        FROM pendencias pd
                        WHERE pd.projeto_id = p.id
                          AND lower(COALESCE(pd.status, '')) NOT IN ('resolvida', 'cancelada')
                          AND COALESCE(pd.prazo, '') != ''
                    ),
                    (
                        SELECT MIN(e.prazo_resposta)
                        FROM exigencias_cartorio e
                        WHERE e.projeto_id = p.id
                          AND lower(COALESCE(e.status, '')) NOT IN ('concluido', 'cancelado')
                          AND COALESCE(e.prazo_resposta, '') != ''
                    )
                ) AS operational_deadline
        ) deadline ON TRUE
        LEFT JOIN LATERAL (
            SELECT
                GREATEST(
                    0,
                    %s::date - COALESCE(NULLIF(left(p.atualizado_em, 10), ''), NULLIF(left(p.criado_em, 10), ''), %s)::date
                ) AS stale_days,
                CASE
                    WHEN GREATEST(0, %s::date - COALESCE(NULLIF(left(p.atualizado_em, 10), ''), NULLIF(left(p.criado_em, 10), ''), %s)::date) >= 30
                        THEN 2 + FLOOR((GREATEST(0, %s::date - COALESCE(NULLIF(left(p.atualizado_em, 10), ''), NULLIF(left(p.criado_em, 10), ''), %s)::date) - 30) / 30)
                    WHEN GREATEST(0, %s::date - COALESCE(NULLIF(left(p.atualizado_em, 10), ''), NULLIF(left(p.criado_em, 10), ''), %s)::date) >= 15
                        THEN 1
                    ELSE 0
                END AS stale_rank
        ) stale ON TRUE
        WHERE lower(COALESCE(p.status, '')) NOT IN ('concluido', 'cancelado')
        ORDER BY
            CASE
                WHEN deadline.operational_deadline < %s THEN 0
                WHEN deadline.operational_deadline IS NOT NULL THEN 1
                ELSE 2
            END,
            deadline.operational_deadline ASC NULLS LAST,
            CASE WHEN deadline.operational_deadline IS NULL THEN stale.stale_rank ELSE 0 END DESC,
            COALESCE(p.ordem_prioridade, 99999),
            COALESCE(p.criado_em, ''),
            p.id
        LIMIT 5
        """,
        [today_iso, today_iso, today_iso, today_iso, today_iso, today_iso, today_iso, today_iso, today_iso],
    )
    # Quantos projetos em cada etapa (gargalo).
    bottlenecks = query_db(
        """
        SELECT em.id AS etapa_id, em.nome AS etapa_nome, COUNT(pe.id) AS total
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
        ORDER BY COALESCE(e.prazo_resposta, '9999-12-31'), e.id
        LIMIT 6
        """
    )
    pendencias = query_db(
        """
        SELECT pd.descricao, pd.prazo, pd.status, pd.origem,
               p.id AS projeto_id, p.nome AS projeto_nome,
               u.nome AS responsavel_nome
        FROM pendencias pd
        JOIN projetos p ON p.id = pd.projeto_id
        LEFT JOIN usuarios u ON u.id = pd.responsavel_id
        WHERE lower(pd.status) NOT IN ('resolvida', 'cancelada')
        ORDER BY COALESCE(pd.prazo, '9999-12-31'), pd.id
        LIMIT 6
        """
    )
    return render_template(
        "dashboard.html",
        total_projects=dashboard_counts["total_projects"],
        active_projects=dashboard_counts["active_projects"],
        overdue=dashboard_counts["overdue"],
        waiting_external=dashboard_counts["waiting_external"],
        due_soon_count=dashboard_counts["due_soon_count"],
        priority_projects=priority_projects,
        bottlenecks=bottlenecks,
        total_bottlenecks=total_bottlenecks,
        exigencias=exigencias,
        exigencias_count=dashboard_counts["exigencias_count"],
        pendencias=pendencias,
        pendencias_count=dashboard_counts["pendencias_count"],
        today_iso=today_iso,
    )


@app.route("/projects")
@login_required
def projects():
    refresh_due_statuses()

    today_iso = app_today().isoformat()
    in_7 = (app_today() + timedelta(days=7)).isoformat()
    filters = request.args.to_dict()
    sql_filters = []
    params = []
    q = filters.get("q", "").strip()
    if q:
        sql_filters.append(
            """
            (
                p.nome LIKE %s OR p.codigo LIKE %s OR p.proprietario LIKE %s OR p.cidade LIKE %s
                OR c.nome LIKE %s OR c.nome_exibicao LIKE %s
                OR pf.nome_completo LIKE %s OR pf.cpf LIKE %s
                OR pj.razao_social LIKE %s OR pj.nome_fantasia LIKE %s OR pj.cnpj LIKE %s
                OR pr.nome_completo LIKE %s OR pr.cpf LIKE %s
                OR ct.nome LIKE %s OR ct.cidade LIKE %s OR ct.uf LIKE %s
                OR p.tipo_servico LIKE %s OR p.tipo_servico_legado LIKE %s OR tp.nome LIKE %s OR tp.categoria LIKE %s
                OR u.nome LIKE %s OR ur.nome LIKE %s
            )
            """
        )
        like_q = f"%{q}%"
        params.extend([like_q] * 22)
    if filters.get("cidade"):
        sql_filters.append("p.cidade LIKE %s")
        params.append(f"%{filters['cidade']}%")
    if filters.get("cliente_id"):
        sql_filters.append("p.cliente_id = %s")
        params.append(filters["cliente_id"])
    if filters.get("cartorio_id"):
        sql_filters.append("p.cartorio_id = %s")
        params.append(filters["cartorio_id"])
    if filters.get("responsavel_id"):
        sql_filters.append(
            """
            (
                p.responsavel_geral_id = %s
                OR EXISTS (
                    SELECT 1 FROM projeto_etapas pe2
                    WHERE pe2.id = p.etapa_atual_id AND pe2.responsavel_id = %s
                )
            )
            """
        )
        params.extend([filters["responsavel_id"], filters["responsavel_id"]])
    if filters.get("status"):
        sql_filters.append(
            "(lower(p.status) = %s OR EXISTS (SELECT 1 FROM projeto_etapas pe3 WHERE pe3.projeto_id = p.id AND lower(pe3.status) = %s))"
        )
        params.extend([filters["status"], filters["status"]])
    if filters.get("prioridade"):
        sql_filters.append("p.prioridade = %s")
        params.append(filters["prioridade"])
    if filters.get("tipo_servico"):
        sql_filters.append("p.tipo_servico = %s")
        params.append(normalize_project_process_type(filters["tipo_servico"]))
    if filters.get("etapa_id"):
        sql_filters.append(
            """
            EXISTS (
                SELECT 1
                FROM projeto_etapas pe4
                WHERE pe4.projeto_id = p.id
                  AND pe4.etapa_modelo_id = %s
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
                EXISTS (SELECT 1 FROM projeto_etapas pe7 WHERE pe7.id = p.etapa_atual_id AND pe7.prazo < %s AND lower(pe7.status) NOT IN ('concluido', 'cancelado', 'aguardando externo'))
                OR EXISTS (SELECT 1 FROM pendencias pd2 WHERE pd2.projeto_id = p.id AND pd2.prazo < %s AND lower(pd2.status) NOT IN ('resolvida', 'cancelada'))
            )
            """
        )
        params.extend([today_iso, today_iso])
    if filters.get("sem_responsavel") == "1":
        sql_filters.append(
            """
            (
                p.responsavel_geral_id IS NULL
                AND (
                    pea.id IS NULL
                    OR pea.responsavel_id IS NULL
                )
            )
            """
        )
    prazo_filter = filters.get("prazo")
    if prazo_filter == "vencido":
        sql_filters.append(
            "EXISTS (SELECT 1 FROM projeto_etapas pe5 WHERE pe5.id = p.etapa_atual_id AND pe5.prazo < %s AND lower(pe5.status) NOT IN ('concluido', 'cancelado', 'aguardando externo'))"
        )
        params.append(today_iso)
    elif prazo_filter == "7dias":
        sql_filters.append(
            "EXISTS (SELECT 1 FROM projeto_etapas pe6 WHERE pe6.id = p.etapa_atual_id AND pe6.prazo BETWEEN %s AND %s AND lower(pe6.status) NOT IN ('concluido', 'cancelado'))"
        )
        params.extend([today_iso, in_7])
    elif prazo_filter == "sem_prazo":
        sql_filters.append(
            """
            (
                (pea.prazo IS NULL OR pea.prazo = '')
                AND NOT EXISTS (
                    SELECT 1 FROM pendencias pdp
                    WHERE pdp.projeto_id = p.id
                      AND COALESCE(pdp.prazo, '') != ''
                      AND lower(COALESCE(pdp.status, '')) NOT IN ('resolvida', 'cancelada')
                )
                AND NOT EXISTS (
                    SELECT 1 FROM exigencias_cartorio epp
                    WHERE epp.projeto_id = p.id
                      AND COALESCE(epp.prazo_resposta, '') != ''
                      AND lower(COALESCE(epp.status, '')) NOT IN ('concluido', 'cancelado')
                )
            )
            """
        )

    where_clause = "WHERE " + " AND ".join(sql_filters) if sql_filters else ""
    order_clause = """
            CASE
                WHEN deadline.operational_deadline < %s THEN 0
                WHEN deadline.operational_deadline IS NOT NULL THEN 1
                ELSE 2
            END,
            deadline.operational_deadline ASC NULLS LAST,
            CASE WHEN deadline.operational_deadline IS NULL THEN stale.stale_rank ELSE 0 END DESC,
            sort_ordem_prioridade,
            sort_criado_em,
            p.id
    """
    projetos = query_db(
        f"""
        SELECT
            p.*,
            COALESCE(
                NULLIF(c.nome_exibicao, ''),
                NULLIF(pf.nome_completo, ''),
                NULLIF(pj.razao_social, ''),
                NULLIF(c.nome, ''),
                NULLIF(CASE WHEN p.proprietario = p.codigo THEN '' ELSE p.proprietario END, '')
            ) AS cliente_nome,
            ct.nome AS cartorio_nome,
            ct.cidade AS cartorio_cidade,
            ct.uf AS cartorio_uf,
            tp.nome AS tipo_processo_nome,
            tp.usa_orgao_externo AS tipo_processo_orgao_externo,
            u.nome AS responsavel_nome,
            ur.nome AS responsavel_etapa_nome,
            COALESCE(p.ordem_prioridade, 99999) AS sort_ordem_prioridade,
            COALESCE(p.criado_em, '') AS sort_criado_em,
            deadline.external_deadline,
            deadline.operational_deadline,
            stale.stale_days,
            stale.stale_rank
        FROM projetos p
        LEFT JOIN clientes c ON c.id = p.cliente_id
        LEFT JOIN pessoas_fisicas pf ON pf.cliente_id = c.id
        LEFT JOIN pessoas_juridicas pj ON pj.cliente_id = c.id
        LEFT JOIN LATERAL (
            SELECT *
            FROM procuradores
            WHERE cliente_id = c.id
            ORDER BY principal DESC, id
            LIMIT 1
        ) pr ON TRUE
        LEFT JOIN cartorios ct ON ct.id = p.cartorio_id
        LEFT JOIN tipos_processo tp ON tp.chave = p.tipo_servico
        LEFT JOIN usuarios u ON u.id = p.responsavel_geral_id
        LEFT JOIN projeto_etapas pea ON pea.id = p.etapa_atual_id
        LEFT JOIN usuarios ur ON ur.id = pea.responsavel_id
        LEFT JOIN LATERAL (
            SELECT
                (
                    SELECT MIN(e.prazo_resposta)
                    FROM exigencias_cartorio e
                    WHERE e.projeto_id = p.id
                      AND lower(COALESCE(e.status, '')) NOT IN ('concluido', 'cancelado')
                      AND COALESCE(e.prazo_resposta, '') != ''
                ) AS external_deadline,
                LEAST(
                    NULLIF(pea.prazo, ''),
                    (
                        SELECT MIN(pd.prazo)
                        FROM pendencias pd
                        WHERE pd.projeto_id = p.id
                          AND lower(COALESCE(pd.status, '')) NOT IN ('resolvida', 'cancelada')
                          AND COALESCE(pd.prazo, '') != ''
                    ),
                    (
                        SELECT MIN(e.prazo_resposta)
                        FROM exigencias_cartorio e
                        WHERE e.projeto_id = p.id
                          AND lower(COALESCE(e.status, '')) NOT IN ('concluido', 'cancelado')
                          AND COALESCE(e.prazo_resposta, '') != ''
                    )
                ) AS operational_deadline
        ) deadline ON TRUE
        LEFT JOIN LATERAL (
            SELECT
                GREATEST(
                    0,
                    %s::date - COALESCE(NULLIF(left(p.atualizado_em, 10), ''), NULLIF(left(p.criado_em, 10), ''), %s)::date
                ) AS stale_days,
                CASE
                    WHEN GREATEST(0, %s::date - COALESCE(NULLIF(left(p.atualizado_em, 10), ''), NULLIF(left(p.criado_em, 10), ''), %s)::date) >= 30
                        THEN 2 + FLOOR((GREATEST(0, %s::date - COALESCE(NULLIF(left(p.atualizado_em, 10), ''), NULLIF(left(p.criado_em, 10), ''), %s)::date) - 30) / 30)
                    WHEN GREATEST(0, %s::date - COALESCE(NULLIF(left(p.atualizado_em, 10), ''), NULLIF(left(p.criado_em, 10), ''), %s)::date) >= 15
                        THEN 1
                    ELSE 0
                END AS stale_rank
        ) stale ON TRUE
        {where_clause}
        ORDER BY
            {order_clause}
        """,
        [today_iso, today_iso, today_iso, today_iso, today_iso, today_iso, today_iso, today_iso] + params + [today_iso],
    )
    matrix_options = get_matrix_static_options()
    etapas = matrix_options["etapas"]
    matrix_rows_by_project = load_matrix_stage_rows_bulk(projetos, etapas)
    matrix = [(project, matrix_rows_by_project.get(project["id"], [])) for project in projetos]
    active_stage_ids = [project["etapa_atual_id"] for project, _ in matrix if project["etapa_atual_id"]]
    matrix_checklists = {}
    pending_by_stage = {}
    pending_by_project = {}
    if active_stage_ids:
        placeholders = ",".join("%s" for _ in active_stage_ids)
        # Checklist do processo (por tipo) — somente a tarefa, sem selos, agrupado por etapa do projeto.
        for item in query_db(
            f"""
            SELECT id, project_stage_id AS projeto_etapa_id, title AS titulo,
                   CASE WHEN status = %s THEN 1 ELSE 0 END AS concluido
            FROM project_checklist_items
            WHERE project_stage_id IN ({placeholders}) AND active = 1 AND status != %s
            ORDER BY project_stage_id, order_index, id
            """,
            [CHECKLIST_STATUS_DONE] + active_stage_ids + [CHECKLIST_STATUS_NOT_APPLICABLE],
        ):
            matrix_checklists.setdefault(item["projeto_etapa_id"], []).append(item)
    project_ids = [project["id"] for project, _ in matrix]
    if project_ids:
        placeholders = ",".join("%s" for _ in project_ids)
        for pending in query_db(
            f"""
            SELECT pd.*, u.nome AS responsavel_nome
            FROM pendencias pd
            LEFT JOIN usuarios u ON u.id = pd.responsavel_id
            WHERE pd.projeto_id IN ({placeholders})
              AND lower(pd.status) NOT IN ('resolvida', 'cancelada')
            ORDER BY COALESCE(pd.prazo, '9999-12-31'), pd.id
            """,
            project_ids,
        ):
            pending_by_stage.setdefault(pending["etapa_id"], []).append(pending)
            pending_by_project.setdefault(pending["projeto_id"], []).append(pending)
    # Proxima etapa real de cada projeto (mesma regra de get_next_applicable_stage),
    # em lote. A matriz nao serve para isso: ela colapsa etapas por modelo global e
    # a ordem global pode ter saltos (modelos desativados), escondendo a proxima etapa.
    next_stage_by_project = {}
    if project_ids:
        placeholders = ",".join("%s" for _ in project_ids)
        for stage in query_db(
            f"""
            SELECT DISTINCT ON (pe.projeto_id)
                pe.projeto_id,
                pe.id,
                COALESCE(pe.stage_name, em.nome) AS etapa_nome
            FROM projetos p
            JOIN projeto_etapas cur ON cur.id = p.etapa_atual_id
            JOIN etapas_modelo cem ON cem.id = cur.etapa_modelo_id
            JOIN projeto_etapas pe ON pe.projeto_id = p.id
            JOIN etapas_modelo em ON em.id = pe.etapa_modelo_id
            WHERE p.id IN ({placeholders})
              AND COALESCE(pe.show_in_project, 1) = 1
              AND COALESCE(pe.workflow_active, 1) = 1
              AND lower(pe.status) NOT IN ('concluido', 'cancelado', 'nao aplicavel')
              AND COALESCE(pe.stage_order, em.ordem) > COALESCE(cur.stage_order, cem.ordem)
            ORDER BY pe.projeto_id, COALESCE(pe.stage_order, em.ordem), pe.id
            """,
            project_ids,
        ):
            next_stage_by_project[stage["projeto_id"]] = stage
    notes_by_project = {}
    if project_ids:
        project_placeholders = ",".join("%s" for _ in project_ids)
        for note in query_db(
            f"""
            SELECT e.*, u.nome AS usuario_nome
            FROM eventos_historico e
            LEFT JOIN usuarios u ON u.id = e.usuario_id
            WHERE e.projeto_id IN ({project_placeholders}) AND e.tipo_evento = 'anotacao'
            ORDER BY e.criado_em DESC
            """,
            project_ids,
        ):
            notes_by_project.setdefault(note["projeto_id"], []).append(note)
    external_controls_by_project = {}
    if project_ids:
        project_placeholders = ",".join("%s" for _ in project_ids)
        for item in query_db(
            f"""
            SELECT e.*, u.nome AS responsavel_nome
            FROM exigencias_cartorio e
            LEFT JOIN usuarios u ON u.id = e.responsavel_id
            WHERE e.projeto_id IN ({project_placeholders})
              AND COALESCE(e.tipo_registro, 'exigencia') = 'protocolo'
            ORDER BY
                e.projeto_id,
                COALESCE(e.prazo_resposta, e.data_protocolo, '9999-12-31'),
                e.id
            """,
            project_ids,
        ):
            external_controls_by_project.setdefault(item["projeto_id"], {}).setdefault(EXTERNAL_PROTOCOL_SCOPE, []).append(item)
    summary_counts = get_matrix_summary_counts(today_iso, in_7)
    summary = {
        "ativos": len([project for project, _ in matrix if str(project["status"] or "").lower() not in ("concluido", "cancelado")]),
        "sete_dias": summary_counts["sete_dias"],
        "atrasados": summary_counts["atrasados"],
        "cartorio": summary_counts["cartorio"],
        "pendencias": summary_counts["pendencias"],
    }
    return render_template(
        "projects.html",
        projects=matrix,
        matrix_checklists=matrix_checklists,
        pending_by_stage=pending_by_stage,
        pending_by_project=pending_by_project,
        next_stage_by_project=next_stage_by_project,
        notes_by_project=notes_by_project,
        external_controls_by_project=external_controls_by_project,
        summary=summary,
        etapas=etapas,
        usuarios=matrix_options["usuarios"],
        cartorios=matrix_options["cartorios"],
        process_types=matrix_options["process_types"],
        external_orgao_options=EXTERNAL_ORGAO_OPTIONS,
        external_orgao_labels=EXTERNAL_ORGAO_LABELS,
        filters=filters,
        today_iso=today_iso,
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
            COALESCE(tp.nome, p.tipo_servico_legado, p.tipo_servico) AS tipo_processo,
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
        LEFT JOIN tipos_processo tp ON tp.chave = p.tipo_servico
        LEFT JOIN projeto_etapas pe ON pe.id = p.etapa_atual_id
        LEFT JOIN etapas_modelo em ON em.id = pe.etapa_modelo_id
        LEFT JOIN usuarios u ON u.id = pe.responsavel_id
        ORDER BY p.proprietario, p.nome
        """
    )
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow(["Codigo", "Proprietario", "Projeto", "Cliente", "Cidade", "Cartorio", "Tipo processo", "Etapa atual", "Responsavel", "Status etapa", "Prazo etapa", "Prioridade", "Status projeto", "Pasta"])
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

    if request.method == "POST":
        next_number = query_db("SELECT COUNT(*) + 1 AS total FROM projetos", one=True)["total"]
        codigo = f"GG-{next_number:03d}"
        nome = request.form["nome"].strip()
        if not nome:
            flash("Informe o nome do projeto.", "danger")
            return redirect(url_for("project_create"))

        cliente_id, cliente_nome = resolve_project_cliente(request.form, nome)
        if not cliente_nome:
            flash("Informe o Cliente / Proprietario do projeto.", "danger")
            return redirect(url_for("project_create"))

        process_key = normalize_project_process_type(request.form.get("tipo_servico"))
        additional_processes = normalize_additional_process_types(request.form.getlist("servicos_adicionais"), process_key)
        valor = parse_currency_value(request.form.get("valor", "").strip())

        db = get_db()
        try:
            created = app_now_iso()
            project_id = db.execute(
                """
                INSERT INTO projetos
                    (codigo, nome, proprietario, cliente_id, cidade, uf, cartorio_id, tipo_servico, servicos_adicionais, valor, caminho_pasta, observacoes, criado_em, atualizado_em)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    codigo,
                    nome,
                    cliente_nome,
                    cliente_id,
                    request.form.get("cidade", "").strip(),
                    request.form.get("uf", "").strip().upper(),
                    request.form.get("cartorio_id") or None,
                    process_key,
                    encode_process_list(additional_processes),
                    valor,
                    request.form.get("caminho_pasta", "").strip(),
                    request.form.get("observacoes", "").strip(),
                    created,
                    created,
                ),
            ).fetchone()["id"]
            initialize_project_workflow(db, project_id, process_key, user_id=g.user["id"])
            initial_stage_key = request.form.get("initial_stage_key") or "ORCAMENTO"
            initial_stage = set_project_initial_stage(db, project_id, initial_stage_key)
            assign_project_order_to_end(db, project_id)
            db.execute(
                "INSERT INTO eventos_historico (projeto_id, usuario_id, tipo_evento, descricao, criado_em) VALUES (%s, %s, %s, %s, %s)",
                (project_id, g.user["id"], "projeto_criado", f"Projeto {codigo} criado.", app_now_iso()),
            )
            if initial_stage:
                db.execute(
                    "INSERT INTO eventos_historico (projeto_id, usuario_id, tipo_evento, descricao, criado_em) VALUES (%s, %s, %s, %s, %s)",
                    (
                        project_id,
                        g.user["id"],
                        "etapa_inicial_definida",
                        f"Projeto iniciado na etapa {initial_stage['display_name']}.",
                        app_now_iso(),
                    ),
                )
            db.commit()
            invalidate_runtime_caches()
        except Exception:
            db.rollback()
            raise
        flash("Projeto criado com sucesso.", "success")
        return redirect(url_for("project_detail", project_id=project_id))

    return render_template(
        "project_form.html",
        clientes_json=fetch_cliente_autocomplete_options(),
        cartorios=get_cartorio_options(),
        process_types=get_process_type_options(),
        initial_stage_options=get_process_initial_stage_options(),
    )


@app.route("/api/projects/reorder", methods=["POST"])
@login_required
def api_projects_reorder():
    """Salva nova ordem de prioridade da matriz. Recebe lista de IDs na nova ordem."""
    if not can_manage():
        return jsonify({"ok": False, "error": "Permissao negada"}), 403
    data = request.get_json() or {}
    ids = data.get("ids", [])
    if not ids:
        return jsonify({"ok": False, "error": "Sem IDs"}), 400
    db = get_db()
    for i, project_id in enumerate(ids, 1):
        db.execute("UPDATE projetos SET ordem_prioridade = %s WHERE id = %s", (i, project_id))
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/project/<int:project_id>/set-top", methods=["POST"])
@login_required
def api_project_set_top(project_id):
    """Move o projeto para a posicao 1 da matriz (maior prioridade)."""
    if not can_manage():
        return jsonify({"ok": False, "error": "Permissao negada"}), 403
    db = get_db()
    all_ids = [row["id"] for row in db.execute(
        "SELECT id FROM projetos ORDER BY COALESCE(ordem_prioridade, 99999), COALESCE(criado_em, ''), id"
    ).fetchall()]
    if project_id in all_ids:
        all_ids.remove(project_id)
    all_ids.insert(0, project_id)
    for i, pid in enumerate(all_ids, 1):
        db.execute("UPDATE projetos SET ordem_prioridade = %s WHERE id = %s", (i, pid))
    db.commit()
    return jsonify({"ok": True})


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
        cartorio_id = execute_db("INSERT INTO cartorios (nome) VALUES (%s)", (nome,))
        invalidate_runtime_caches()
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


# --- Integracao Dropbox: abre a pasta do projeto pelo Dropbox (web ou app desktop) ---
# O app usa um refresh token unico da empresa (env: DROPBOX_APP_KEY/SECRET/REFRESH_TOKEN)
# com escopos somente de metadados e links; sem acesso ao conteudo dos arquivos.

_dropbox_lock = threading.Lock()
_dropbox_cache = {"access_token": None, "expires_at": 0.0, "root_namespace_id": None}


def dropbox_enabled():
    return bool(DROPBOX_APP_KEY and DROPBOX_APP_SECRET and DROPBOX_REFRESH_TOKEN)


def configured_dropbox_path_aliases():
    aliases = []
    for raw_alias in (DROPBOX_PATH_ALIASES_RAW or "").split(";"):
        if "=" not in raw_alias:
            continue
        local_prefix, dropbox_prefix = raw_alias.split("=", 1)
        local_prefix = local_prefix.strip().strip('"').rstrip("\\/")
        dropbox_prefix = dropbox_prefix.strip().strip('"').replace("\\", "/").rstrip("/")
        if local_prefix and dropbox_prefix:
            if not dropbox_prefix.startswith("/"):
                dropbox_prefix = "/" + dropbox_prefix
            aliases.append((local_prefix, dropbox_prefix))
    return aliases


def _dropbox_access_token():
    with _dropbox_lock:
        if _dropbox_cache["access_token"] and time.time() < _dropbox_cache["expires_at"] - 300:
            return _dropbox_cache["access_token"]
    body = urlencode({
        "grant_type": "refresh_token",
        "refresh_token": DROPBOX_REFRESH_TOKEN,
        "client_id": DROPBOX_APP_KEY,
        "client_secret": DROPBOX_APP_SECRET,
    }).encode()
    req = urllib.request.Request("https://api.dropboxapi.com/oauth2/token", data=body, method="POST")
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode())
    with _dropbox_lock:
        _dropbox_cache["access_token"] = data["access_token"]
        _dropbox_cache["expires_at"] = time.time() + int(data.get("expires_in", 14400))
    return data["access_token"]


def _dropbox_api(endpoint, payload, use_path_root=True):
    """Chama a API do Dropbox. Retorna (json, None) ou (None, error_summary)."""
    token = _dropbox_access_token()
    headers = {"Authorization": "Bearer " + token, "Content-Type": "application/json"}
    if use_path_root:
        # Conta Business: sem este header os caminhos resolvem na pasta do membro,
        # nao no espaco da equipe (onde ficam /SC/Pastas/...).
        headers["Dropbox-API-Path-Root"] = json.dumps({".tag": "root", "root": _dropbox_root_namespace()})
    req = urllib.request.Request(
        "https://api.dropboxapi.com/2/" + endpoint,
        data=json.dumps(payload).encode(),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode()), None
    except urllib.error.HTTPError as err:
        try:
            detail = json.loads(err.read().decode()).get("error_summary", "")
        except Exception:
            detail = ""
        return None, detail or f"http_{err.code}"


def _dropbox_root_namespace():
    with _dropbox_lock:
        if _dropbox_cache["root_namespace_id"]:
            return _dropbox_cache["root_namespace_id"]
    account, error = _dropbox_api("users/get_current_account", None, use_path_root=False)
    if not account:
        raise RuntimeError(f"Dropbox get_current_account falhou: {error}")
    namespace_id = account["root_info"]["root_namespace_id"]
    with _dropbox_lock:
        _dropbox_cache["root_namespace_id"] = namespace_id
    return namespace_id


def dropbox_path_from_raw(raw_path):
    """Extrai o caminho Dropbox de um caminho cadastrado.

    Aceita '/SC/Pastas/X' (ja no formato Dropbox), aliases configurados como
    'Y:\\PASTAS=/SC/Pastas' ou um caminho local sincronizado como
    'C:\\SC Dropbox\\SC\\Pastas\\X' (tudo apos a pasta '* Dropbox').
    """
    path = (raw_path or "").strip().strip('"')
    if not path:
        return None
    if path.startswith("/"):
        return path.rstrip("/") or None
    normalized = path.replace("/", "\\").rstrip("\\")
    for local_prefix, dropbox_prefix in configured_dropbox_path_aliases():
        local_normalized = local_prefix.replace("/", "\\").rstrip("\\")
        lower_path = normalized.lower()
        lower_prefix = local_normalized.lower()
        if lower_path == lower_prefix or lower_path.startswith(lower_prefix + "\\"):
            rest = normalized[len(local_normalized):].lstrip("\\")
            return (dropbox_prefix + ("/" + rest.replace("\\", "/") if rest else "")).rstrip("/")
    parts = [part for part in path.replace("/", "\\").split("\\") if part]
    for index, part in enumerate(parts):
        if part.lower().endswith(" dropbox"):
            rest = parts[index + 1:]
            return "/" + "/".join(rest) if rest else None
    return None


def dropbox_web_url(dropbox_path):
    """URL da pasta no dropbox.com. Quem tem o app desktop abre de la no Explorer."""
    return "https://www.dropbox.com/home" + quote(dropbox_path, safe="/")


def local_dropbox_candidates(dropbox_path):
    """Caminhos locais possiveis da pasta sincronizada, via info.json oficial do Dropbox."""
    candidates = []
    for base in (os.environ.get("APPDATA"), os.environ.get("LOCALAPPDATA")):
        if not base:
            continue
        try:
            with open(os.path.join(base, "Dropbox", "info.json"), encoding="utf-8") as fh:
                info = json.load(fh)
        except (OSError, ValueError):
            continue
        for entry in info.values():
            if not isinstance(entry, dict):
                continue
            for key in ("root_path", "path"):
                root = entry.get(key)
                if root:
                    candidate = os.path.join(root, dropbox_path.strip("/").replace("/", "\\"))
                    if candidate not in candidates:
                        candidates.append(candidate)
    return candidates


def folder_path_candidates(raw_path):
    path = (raw_path or "").strip().strip('"')
    if not path:
        return []
    normalized = path.replace("/", "\\")
    candidates = [path]
    if normalized != path:
        candidates.append(normalized)
    if len(normalized) >= 3 and normalized[1:3] == ":\\":
        drive = normalized[0].upper()
        rest = normalized[3:].lstrip("\\")
        if drive in ("X", "Y") and rest:
            candidates.extend([
                f"\\\\wdserver\\{rest}",
                f"\\\\wdserver\\{drive}\\{rest}",
                f"\\\\wdserver\\{drive}$\\{rest}",
            ])
    unique = []
    for candidate in candidates:
        if candidate and candidate not in unique:
            unique.append(candidate)
    return unique


@app.route("/api/open-folder", methods=["POST"])
@login_required
def api_open_folder():
    """Abre a pasta do projeto.

    - App rodando na maquina do usuario (Windows): abre direto no Explorer,
      inclusive a pasta sincronizada do Dropbox.
    - App hospedado (Render): devolve a URL da pasta no dropbox.com; quem tem o
      app desktop abre no Explorer a partir de la, quem nao tem navega online.
    """
    data = request.get_json(silent=True) or {}
    path = (data.get("path") or "").strip()
    if not path:
        return jsonify({"error": "Caminho nao informado"}), 400

    stripped = path.strip('"').strip()
    if stripped.lower().startswith(("https://www.dropbox.com/", "https://dropbox.com/")):
        return jsonify({"url": stripped})

    dropbox_path = dropbox_path_from_raw(path)

    # 1) Instalacao local no Windows: tenta abrir no Explorer.
    if hasattr(os, "startfile"):
        candidates = folder_path_candidates(path)
        if dropbox_path:
            candidates.extend(local_dropbox_candidates(dropbox_path))
        resolved_path = next((candidate for candidate in candidates if os.path.isdir(candidate)), None)
        if resolved_path:
            try:
                os.startfile(resolved_path)  # type: ignore[attr-defined]
                return jsonify({"ok": True, "path": resolved_path})
            except Exception:
                pass  # cai para o Dropbox web

    # 2) Hospedado ou pasta local indisponivel: abre pelo Dropbox.
    if dropbox_path:
        if dropbox_enabled():
            try:
                meta, error = _dropbox_api("files/get_metadata", {"path": dropbox_path})
            except Exception:
                meta, error = None, "api_indisponivel"
            if meta:
                return jsonify({"url": dropbox_web_url(meta.get("path_display") or dropbox_path)})
            if error and error.startswith("path/not_found"):
                return jsonify({
                    "error": f"Pasta nao encontrada no Dropbox: {dropbox_path}. Verifique o caminho cadastrado.",
                }), 404
        # Sem credenciais ou API fora do ar: abre a URL construida mesmo assim.
        return jsonify({"url": dropbox_web_url(dropbox_path)})

    return jsonify({
        "error": "Pasta nao encontrada. Cadastre o caminho da pasta no Dropbox (ex.: C:\\SC Dropbox\\SC\\Pastas\\...).",
    }), 404


@app.route("/api/add-cliente", methods=["POST"])
@login_required
def api_add_cliente():
    if not can_manage():
        return {"error": "Permissao negada"}, 403

    data = request.get_json() or {}
    nome = (data.get("nome") or "").strip()
    duplicate_confirmed = bool(data.get("confirm_duplicate"))
    duplicate_note = (data.get("duplicate_note") or "").strip()
    if not nome:
        return {"error": "Nome obrigatorio"}, 400

    try:
        db = get_db()
        lookup_key = normalize_lookup(nome)
        db.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (lookup_key,))
        matches = find_cliente_options_by_name(nome)
        if matches and not duplicate_confirmed:
            db.rollback()
            return {
                "error": "Ja existe cliente com este nome.",
                "requires_confirmation": True,
                "matches": matches[:5],
            }, 409
        if matches and not duplicate_note:
            db.rollback()
            return {
                "error": "Informe um CPF/CNPJ, telefone ou observacao para diferenciar este cadastro.",
                "requires_detail": True,
                "matches": matches[:5],
            }, 422
        cliente_id = create_draft_cliente(nome, duplicate_note=duplicate_note)
        return {"id": cliente_id, "nome": nome, "search": nome}, 201
    except Exception as e:
        return {"error": str(e)}, 500


def get_project_financial_context(project):
    ensure_financeiro_schema()
    project_id = project["id"]
    costs = query_db(
        """
        SELECT pc.*, u.nome AS usuario_nome
        FROM projeto_custos pc
        LEFT JOIN usuarios u ON u.id = pc.usuario_id
        WHERE pc.projeto_id = %s
          AND lower(COALESCE(pc.status, '')) != 'cancelado'
        ORDER BY COALESCE(pc.data_custo, '') DESC, pc.id DESC
        """,
        (project_id,),
    )
    payments = query_db(
        """
        SELECT pg.*, u.nome AS usuario_nome
        FROM projeto_pagamentos pg
        LEFT JOIN usuarios u ON u.id = pg.usuario_id
        WHERE pg.projeto_id = %s
        ORDER BY COALESCE(pg.data_pagamento, '') DESC, pg.id DESC
        """,
        (project_id,),
    )
    contract_value = float(project["valor"] or 0.0)
    total_costs = sum(float(cost["valor"] or 0.0) for cost in costs)
    total_paid = sum(float(payment["valor"] or 0.0) for payment in payments)
    total_billable = contract_value + total_costs
    balance = round(total_billable - total_paid, 2)
    if total_billable <= 0.005:
        status = "Sem cobranca"
        tone = "secondary"
    elif balance <= 0.005:
        status = "Quitado"
        tone = "success"
    elif total_paid > 0:
        status = "Parcial"
        tone = "warning"
    else:
        status = "Em aberto"
        tone = "primary"
    return {
        "costs": costs,
        "payments": payments,
        "contract_value": contract_value,
        "total_costs": total_costs,
        "total_paid": total_paid,
        "total_billable": total_billable,
        "balance": balance,
        "status": status,
        "tone": tone,
    }


@app.route("/project/<int:project_id>")
@login_required
def project_detail(project_id):
    refresh_due_statuses()
    project = query_db(
        """
        SELECT
            p.*,
            COALESCE(
                NULLIF(c.nome_exibicao, ''),
                NULLIF(pf.nome_completo, ''),
                NULLIF(pj.razao_social, ''),
                NULLIF(c.nome, ''),
                NULLIF(CASE WHEN p.proprietario = p.codigo THEN '' ELSE p.proprietario END, '')
            ) AS cliente_nome,
            ct.nome AS cartorio_nome,
            tp.nome AS tipo_processo_nome,
            u.nome AS responsavel_geral_nome
        FROM projetos p
        LEFT JOIN clientes c ON c.id = p.cliente_id
        LEFT JOIN pessoas_fisicas pf ON pf.cliente_id = c.id
        LEFT JOIN pessoas_juridicas pj ON pj.cliente_id = c.id
        LEFT JOIN cartorios ct ON ct.id = p.cartorio_id
        LEFT JOIN tipos_processo tp ON tp.chave = p.tipo_servico
        LEFT JOIN usuarios u ON u.id = p.responsavel_geral_id
        WHERE p.id = %s
        """,
        (project_id,),
        one=True,
    )
    if not project:
        flash("Projeto nao encontrado.", "danger")
        return redirect(url_for("projects"))

    db = get_db()
    workflow_initialized = project_has_workflow_initialized_db(db, project_id)
    if not scalar(db, "SELECT COUNT(*) FROM project_checklist_items WHERE project_id = %s", (project_id,)):
        create_project_checklist_from_template(db, project_id, project["tipo_servico"])
        db.commit()
        invalidate_runtime_caches()
    else:
        updated_links = sync_project_checklist_stage_links(db, project_id)
        if updated_links:
            db.commit()
            invalidate_runtime_caches()

    etapas = load_stage_rows(project_id)
    exigencias = query_db(
        """
        SELECT e.*, c.nome AS cartorio_nome, u.nome AS responsavel_nome
        FROM exigencias_cartorio e
        LEFT JOIN cartorios c ON c.id = e.cartorio_id
        LEFT JOIN usuarios u ON u.id = e.responsavel_id
        WHERE e.projeto_id = %s
        ORDER BY
            CASE COALESCE(e.tipo_orgao, 'CARTORIO') WHEN 'PREFEITURA' THEN 0 ELSE 1 END,
            CASE COALESCE(e.tipo_registro, 'exigencia') WHEN 'protocolo' THEN 0 ELSE 1 END,
            COALESCE(e.prazo_resposta, e.data_protocolo, '9999-12-31'),
            e.id
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
        WHERE pd.projeto_id = %s
        ORDER BY
            CASE WHEN lower(pd.status) IN ('resolvida', 'cancelada') THEN 1 ELSE 0 END,
            COALESCE(pd.prazo, '9999-12-31')
        """,
        (project_id,),
    )
    historico = query_db(
        """
        SELECT e.*, u.nome AS usuario_nome
        FROM eventos_historico e
        LEFT JOIN usuarios u ON u.id = e.usuario_id
        WHERE e.projeto_id = %s
        ORDER BY e.criado_em DESC
        """,
        (project_id,),
    )
    # Tempo por etapa: quando o projeto entrou e saiu de cada fase.
    stage_history_rows = query_db(
        "SELECT * FROM project_stage_history WHERE project_id = %s ORDER BY entered_at, id",
        (project_id,),
    )
    stage_timeline = [
        {
            "stage_name": row["stage_name"],
            "entered_at": row["entered_at"],
            "exited_at": row["exited_at"],
            "responsible_name": row["responsible_name"],
            "em_andamento": not row["exited_at"],
            "duracao": format_days(calculate_days_between(row["entered_at"], row["exited_at"])),
        }
        for row in stage_history_rows
    ]
    project_open_days = format_days(calculate_days_between(project["criado_em"])) if project["criado_em"] else "-"
    financeiro_context = get_project_financial_context(project) if can_admin() else None
    return render_template(
        "project_detail.html",
        project=project,
        etapas=etapas,
        workflow_initialized=workflow_initialized,
        exigencias=exigencias,
        pendencias=pendencias,
        historico=historico,
        stage_timeline=stage_timeline,
        project_open_days=project_open_days,
        usuarios=get_active_users(),
        clientes_json=fetch_cliente_autocomplete_options(),
        cartorios=get_cartorio_options(),
        process_types=get_process_type_options(),
        servicos_adicionais=decode_process_list(project["servicos_adicionais"]),
        financeiro=financeiro_context,
        categorias_custo=CATEGORIAS_CUSTO,
        formas_pagamento=FORMAS_PAGAMENTO,
        external_orgao_options=EXTERNAL_ORGAO_OPTIONS,
        external_orgao_labels=EXTERNAL_ORGAO_LABELS,
    )


@app.route("/project/<int:project_id>/action", methods=["POST"])
@login_required
def project_action(project_id):
    project = query_db("SELECT * FROM projetos WHERE id = %s", (project_id,), one=True)
    if not project:
        flash("Projeto nao encontrado.", "danger")
        return redirect(url_for("projects"))

    action = request.form.get("action")
    if action == "delete_project":
        if not can_admin():
            flash("Somente administrador pode excluir projetos.", "danger")
            return redirect(url_for("project_detail", project_id=project_id))
        project_name = project["nome"]
        db = get_db()
        delete_project_records(db, project_id)
        initialize_project_order(db)
        db.commit()
        flash(f"Projeto {project_name} excluido.", "success")
        return redirect(url_for("projects"))

    if action == "update_project":
        if not can_manage():
            flash("Permissao negada.", "danger")
            return redirect(url_for("project_detail", project_id=project_id))
        valor = parse_currency_value(request.form.get("valor", "").strip())
        project_name = request.form.get("nome", "").strip() or project["nome"]
        cliente_id, cliente_nome = resolve_project_cliente(request.form, project_name)
        new_process_key = normalize_project_process_type(request.form.get("tipo_servico"))
        additional_processes = normalize_additional_process_types(request.form.getlist("servicos_adicionais"), new_process_key)
        old_process_key = normalize_project_process_type(project["tipo_servico"])
        workflow_initialized = project_has_workflow_initialized_db(get_db(), project_id)

        execute_db(
            """
            UPDATE projetos
            SET nome = %s, proprietario = %s, cliente_id = %s, cidade = %s, uf = %s, cartorio_id = %s, tipo_servico = %s, servicos_adicionais = %s,
                prioridade = %s, status = %s, prazo_critico = %s, responsavel_geral_id = %s, caminho_pasta = %s,
                observacoes = %s, valor = %s, atualizado_em = %s
            WHERE id = %s
            """,
            (
                project_name,
                cliente_nome,
                cliente_id,
                request.form.get("cidade", "").strip(),
                request.form.get("uf", "").strip().upper(),
                request.form.get("cartorio_id") or None,
                new_process_key,
                encode_process_list(additional_processes),
                request.form.get("prioridade", "Media"),
                request.form.get("status", "Em andamento"),
                request.form.get("prazo_critico") or None,
                request.form.get("responsavel_geral_id") or None,
                request.form.get("caminho_pasta", "").strip(),
                request.form.get("observacoes", "").strip(),
                valor,
                app_now_iso(),
                project_id,
            ),
        )
        if new_process_key != old_process_key:
            if workflow_initialized:
                flash("Tipo de processo alterado. Este projeto ja possui etapas/checklist; revise o fluxo antes de recriar modelos.", "warning")
            else:
                db = get_db()
                initialize_project_workflow(db, project_id, new_process_key, user_id=g.user["id"], force=True)
                db.commit()
        elif workflow_initialized and str(project["cartorio_id"] or "") != str(request.form.get("cartorio_id") or ""):
            # Cartorio mudou: adiciona ao checklist os documentos exigidos pelo novo cartorio.
            db = get_db()
            create_project_checklist_from_template(db, project_id, new_process_key)
            sync_project_checklist_stage_links(db, project_id)
            db.commit()
        record_event(project_id, "projeto_atualizado", "Dados principais do projeto atualizados.")
        flash("Projeto atualizado.", "success")

    elif action == "update_responsible":
        if not can_manage():
            flash("Permissao negada.", "danger")
            return redirect(url_for("project_detail", project_id=project_id))
        responsible_id = request.form.get("responsavel_id") or None
        now = app_now_iso()
        db = get_db()
        db.execute(
            "UPDATE projetos SET responsavel_geral_id = %s, atualizado_em = %s WHERE id = %s",
            (responsible_id, now, project_id),
        )
        current_stage_id = project["etapa_atual_id"] or infer_current_stage_id_db(db, project_id)
        if current_stage_id:
            db.execute(
                "UPDATE projeto_etapas SET responsavel_id = %s WHERE id = %s",
                (responsible_id, current_stage_id),
            )
            db.execute(
                """
                UPDATE project_stage_history
                SET responsible_id = %s,
                    responsible_name = (SELECT nome FROM usuarios WHERE id = %s)
                WHERE project_id = %s AND stage_id = %s AND exited_at IS NULL
                """,
                (responsible_id, responsible_id, project_id, current_stage_id),
            )
        db.commit()
        label = query_db("SELECT nome FROM usuarios WHERE id = %s", (responsible_id,), one=True) if responsible_id else None
        record_event(project_id, "responsavel_atualizado", f"Responsavel definido como {label['nome'] if label else 'sem responsavel'}.")
        flash("Responsavel atualizado.", "success")

    elif action == "apply_process_model":
        if not can_manage():
            flash("Permissao negada.", "danger")
            return redirect(url_for("project_detail", project_id=project_id))
        db = get_db()
        if project_has_workflow_initialized_db(db, project_id):
            create_project_checklist_from_template(db, project_id, project["tipo_servico"])
            sync_project_checklist_stage_links(db, project_id)
            db.commit()
            flash("Este projeto ja possui fluxo por modelo. Itens faltantes foram conferidos sem duplicar.", "info")
        else:
            result = initialize_project_workflow(db, project_id, project["tipo_servico"], user_id=g.user["id"], force=True)
            db.commit()
            flash(f"Modelo aplicado: {result['created_stages']} etapas e {result['created_checklist']} itens de checklist criados.", "success")

    elif action == "update_stage":
        stage_id = request.form.get("etapa_id")
        old_stage = load_project_stage_for_action(stage_id, project_id)
        if not old_stage:
            flash("Etapa nao encontrada.", "danger")
            return redirect(url_for("project_detail", project_id=project_id))
        status = request.form.get("status", "nao iniciado")
        progress = old_stage["progresso"] or 0
        if "progresso" in request.form:
            progress = int(request.form.get("progresso") or 0)
        data_inicio = old_stage["data_inicio"]
        data_fim = old_stage["data_fim"]
        if status == "em andamento" and not data_inicio:
            data_inicio = app_now_iso()
        if status == "concluido":
            if is_office_elaboration_stage(old_stage) and count_blocking_checklist_pending(old_stage["id"]):
                flash("Conclua os documentos do cartorio antes de concluir a etapa Escritorio.", "danger")
                return redirect(request.form.get("next") or url_for("project_detail", project_id=project_id))
            can_finish_external, external_message = can_finish_external_stage(project_id, old_stage)
            if not can_finish_external:
                flash(external_message, "danger")
                return redirect(request.form.get("next") or url_for("project_detail", project_id=project_id))
            data_fim = app_now_iso()
            progress = 100
        execute_db(
            """
            UPDATE projeto_etapas
            SET status = %s, responsavel_id = %s, prazo = %s, progresso = %s, subetapa_ativa = %s,
                atraso_origem = %s, observacoes = %s, data_inicio = %s, data_fim = %s
            WHERE id = %s
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
        next_stage = None
        if status == "concluido":
            completed_stage = load_project_stage_for_action(stage_id, project_id)
            next_stage = advance_project_after_stage_completion(
                project_id,
                completed_stage,
                request.form.get("responsavel_id") or old_stage["responsavel_id"],
            )
        record_event(project_id, "etapa_atualizada", f"Etapa {old_stage['etapa_nome']} atualizada para {STATUS_META.get(status, {}).get('label', status)}.")
        if next_stage:
            flash(f"Etapa concluida. Projeto avancou para {next_stage['etapa_nome']}.", "success")
        else:
            flash("Etapa atualizada.", "success")

    elif action == "move_stage":
        if not can_manage():
            flash("Permissao negada.", "danger")
            return redirect(url_for("project_detail", project_id=project_id))
        new_stage_id = request.form.get("nova_etapa_id")
        new_stage = load_project_stage_for_action(new_stage_id, project_id)
        if not new_stage:
            flash("Etapa de destino invalida.", "danger")
            return redirect(request.form.get("next") or url_for("project_detail", project_id=project_id))

        db = get_db()
        old_stage_id = project["etapa_atual_id"] or infer_current_stage_id_db(db, project_id)
        old_stage = load_project_stage_for_action(old_stage_id, project_id)

        redirect_url = request.form.get("next") or url_for("project_detail", project_id=project_id)

        if old_stage and old_stage["id"] != new_stage["id"]:
            # Ordena pelas COLUNAS globais usadas pelo projeto (mesma sequencia mostrada na matriz),
            # e nao pelo stage_order do modelo (que pode ter saltos/repeticoes por tipo de processo).
            old_col = old_stage["legacy_etapa_ordem"]
            new_col = new_stage["legacy_etapa_ordem"]
            is_advance = new_col > old_col
            is_return = new_col < old_col
            # Avanco na sequencia real do projeto (stage_order), que enxerga tambem
            # movimentos dentro da mesma coluna global (ex.: Escritorio -> Conferencia).
            is_forward = (new_stage["etapa_ordem"] or 0) > (old_stage["etapa_ordem"] or 0)

            if is_forward and is_office_elaboration_stage(old_stage):
                blocking_pending = count_blocking_checklist_pending(old_stage["id"])
                if blocking_pending:
                    flash("Conclua os documentos do cartorio antes de avancar da etapa Escritorio.", "danger")
                    return redirect(redirect_url)
            if is_forward and external_stage_type(old_stage):
                can_finish_external, external_message = can_finish_external_stage(project_id, old_stage)
                if not can_finish_external:
                    flash(external_message, "danger")
                    return redirect(redirect_url)

            if is_advance:
                # Bloqueia o avanco enquanto houver pendencia aberta no projeto.
                open_pendencias = scalar(
                    db,
                    "SELECT COUNT(*) FROM pendencias WHERE projeto_id = %s AND lower(status) NOT IN ('resolvida', 'cancelada')",
                    (project_id,),
                )
                if open_pendencias:
                    flash("Resolva as pendencias abertas deste projeto antes de avancar para a proxima etapa.", "danger")
                    return redirect(redirect_url)

                # So permite avancar para a proxima coluna utilizada (sem pular etapas).
                used_cols = sorted({row["legacy_etapa_ordem"] for row in load_stage_rows(project_id)})
                next_cols = [col for col in used_cols if col > old_col]
                if not next_cols or new_col != next_cols[0]:
                    flash("Nao e permitido pular etapas. Avance apenas para a proxima etapa em sequencia.", "danger")
                    return redirect(redirect_url)

            if is_return:
                observacao = request.form.get("observacao", "").strip()
                if not observacao:
                    flash("Justificativa obrigatoria ao retornar uma etapa. Descreva o motivo.", "danger")
                    return redirect(redirect_url)

        motivo_form = request.form.get("motivo", "")
        is_return_move = old_stage and new_stage["legacy_etapa_ordem"] < old_stage["legacy_etapa_ordem"]
        if not motivo_form:
            motivo = "retorno" if is_return_move else "avanco"
        else:
            motivo = motivo_form
        observacao = request.form.get("observacao", "").strip()
        is_rework = motivo in ("retorno", "exigencia_cartorio", "retrabalho", "pendencia_externa") or is_return_move
        now = app_now_iso()

        if old_stage and old_stage["id"] != new_stage["id"]:
            old_status = "atencao" if is_rework else "concluido"
            execute_db(
                """
                UPDATE projeto_etapas
                SET status = %s, data_fim = %s, progresso = CASE WHEN %s = 'concluido' THEN 100 ELSE progresso END
                WHERE id = %s
                """,
                (old_status, None if is_rework else now, old_status, old_stage["id"]),
            )

        new_status = "retrabalho" if is_rework else "em andamento"
        execute_db(
            """
            UPDATE projeto_etapas
            SET status = %s, responsavel_id = COALESCE(%s, responsavel_id), prazo = COALESCE(%s, prazo),
                data_inicio = COALESCE(data_inicio, %s), data_fim = NULL, subetapa_ativa = COALESCE(NULLIF(%s, ''), subetapa_ativa)
            WHERE id = %s
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
            "UPDATE projetos SET etapa_atual_id = %s, status = %s, atualizado_em = %s WHERE id = %s",
            (new_stage["id"], "Atencao" if is_rework else "Em andamento", now, project_id),
        )
        execute_db(
            """
            INSERT INTO movimentacoes_etapa
                (projeto_id, etapa_anterior_id, etapa_nova_id, etapa_anterior, etapa_nova, motivo, observacao, responsavel_id, usuario_id, criado_em)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
        record_stage_history_transition(
            project_id,
            old_stage,
            new_stage,
            now,
            request.form.get("responsavel_id") or new_stage["responsavel_id"],
            motivo,
        )
        pending_description = request.form.get("pendencia_descricao", "").strip()
        if pending_description:
            execute_db(
                """
                INSERT INTO pendencias
                    (projeto_id, etapa_id, descricao, origem, responsavel_id, prazo, status, data_abertura, criado_em, atualizado_em)
                VALUES (%s, %s, %s, %s, %s, %s, 'aberta', %s, %s, %s)
                """,
                (
                    project_id,
                    new_stage["id"],
                    pending_description,
                    "cartorio" if motivo == "exigencia_cartorio" else "interna",
                    request.form.get("responsavel_id") or new_stage["responsavel_id"],
                    request.form.get("prazo") or None,
                    app_today().isoformat(),
                    now,
                    now,
                ),
            )
        # Ao retornar uma etapa, a justificativa do retorno vira uma pendencia que precisa ser
        # resolvida antes de o projeto poder avancar novamente.
        elif is_return_move and observacao:
            execute_db(
                """
                INSERT INTO pendencias
                    (projeto_id, etapa_id, descricao, origem, responsavel_id, status, data_abertura, criado_em, atualizado_em)
                VALUES (%s, %s, %s, 'interna', %s, 'aberta', %s, %s, %s)
                """,
                (
                    project_id,
                    new_stage["id"],
                    observacao,
                    request.form.get("responsavel_id") or new_stage["responsavel_id"],
                    app_today().isoformat(),
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
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                    app_now_iso(),
                ),
            )
            record_event(project_id, "tarefa_criada", f"Tarefa criada: {title}.")
            flash(f"Tarefa #{task_id} criada.", "success")

    elif action == "add_checklist":
        title = request.form.get("titulo", "").strip()
        stage_id = request.form.get("etapa_id")
        if title and stage_id:
            execute_db("INSERT INTO checklist_itens (projeto_etapa_id, titulo) VALUES (%s, %s)", (stage_id, title))
            update_stage_progress(stage_id)
            record_event(project_id, "checklist_adicionado", f"Checklist adicionado: {title}.")
            flash("Item de checklist adicionado.", "success")

    elif action == "toggle_checklist":
        item_id = request.form.get("item_id")
        item = query_db("SELECT * FROM checklist_itens WHERE id = %s", (item_id,), one=True)
        if item:
            new_value = 0 if item["concluido"] else 1
            execute_db(
                "UPDATE checklist_itens SET concluido = %s, concluido_por = %s, concluido_em = %s WHERE id = %s",
                (
                    new_value,
                    g.user["id"] if new_value else None,
                    app_now_iso() if new_value else None,
                    item_id,
                ),
            )
            progress = update_stage_progress(item["projeto_etapa_id"])
            record_event(project_id, "checklist_atualizado", f"Checklist atualizado: {item['titulo']} ({progress}%).")
            flash("Checklist atualizado.", "success")

    elif action == "toggle_project_checklist":
        item_id = request.form.get("item_id")
        item = query_db(
            "SELECT * FROM project_checklist_items WHERE id = %s AND project_id = %s",
            (item_id, project_id),
            one=True,
        )
        if item:
            new_status = CHECKLIST_STATUS_NOT_STARTED if item["status"] == CHECKLIST_STATUS_DONE else CHECKLIST_STATUS_DONE
            execute_db(
                """
                UPDATE project_checklist_items
                SET status = %s, completed_at = %s, completed_by = %s, updated_at = %s
                WHERE id = %s
                """,
                (
                    new_status,
                    app_now_iso() if new_status == CHECKLIST_STATUS_DONE else None,
                    g.user["id"] if new_status == CHECKLIST_STATUS_DONE else None,
                    app_now_iso(),
                    item_id,
                ),
            )
            record_event(project_id, "checklist_processo_atualizado", f"Checklist do processo atualizado: {item['title']}.")
            flash("Checklist atualizado.", "success")

    elif action == "mark_project_checklist_not_applicable":
        item_id = request.form.get("item_id")
        item = query_db(
            "SELECT * FROM project_checklist_items WHERE id = %s AND project_id = %s",
            (item_id, project_id),
            one=True,
        )
        if item:
            now = app_now_iso()
            execute_db(
                """
                UPDATE project_checklist_items
                SET status = %s, completed_at = NULL, completed_by = NULL,
                    observation = COALESCE(NULLIF(%s, ''), observation, 'Marcado como nao aplicavel.'),
                    updated_at = %s
                WHERE id = %s
                """,
                (
                    CHECKLIST_STATUS_NOT_APPLICABLE,
                    request.form.get("observation", "").strip(),
                    now,
                    item_id,
                ),
            )
            record_event(project_id, "checklist_processo_nao_aplicavel", f"Checklist marcado como nao aplicavel: {item['title']}.")
            flash("Item marcado como nao aplicavel.", "info")

    elif action == "add_pending":
        description = request.form.get("descricao", "").strip()
        if description:
            now = app_now_iso()
            pending_id = execute_db(
                """
                INSERT INTO pendencias
                    (projeto_id, etapa_id, descricao, origem, responsavel_id, prazo, status, data_abertura, criado_em, atualizado_em)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    project_id,
                    request.form.get("etapa_id") or None,
                    description,
                    request.form.get("origem", "interna"),
                    request.form.get("responsavel_id") or None,
                    request.form.get("prazo") or None,
                    request.form.get("status", "aberta"),
                    app_today().isoformat(),
                    now,
                    now,
                ),
            )
            if request.form.get("etapa_id"):
                execute_db("UPDATE projeto_etapas SET status = 'atencao' WHERE id = %s AND lower(status) NOT IN ('concluido', 'cancelado')", (request.form.get("etapa_id"),))
                if str(request.form.get("etapa_id")) == str(project["etapa_atual_id"]):
                    execute_db("UPDATE projetos SET status = 'Atencao', atualizado_em = %s WHERE id = %s", (now, project_id))
            record_event(project_id, "pendencia_criada", f"Pendencia #{pending_id} registrada: {description}.")
            flash("Pendencia registrada.", "success")

    elif action == "resolve_pending":
        pending_id = request.form.get("pendencia_id")
        execute_db(
            "UPDATE pendencias SET status = 'resolvida', data_resolucao = %s, atualizado_em = %s WHERE id = %s AND projeto_id = %s",
            (app_today().isoformat(), app_now_iso(), pending_id, project_id),
        )
        record_event(project_id, "pendencia_resolvida", f"Pendencia #{pending_id} resolvida.")
        flash("Pendencia resolvida.", "success")

    elif action == "add_external_protocol":
        tipo_orgao = normalize_external_orgao(request.form.get("tipo_orgao", "CARTORIO"))
        stage = find_project_stage_by_external_type(get_db(), project_id, tipo_orgao)
        data_protocolo = request.form.get("data_protocolo") or app_today().isoformat()
        data_limite = external_protocol_check_date(data_protocolo)
        numero_protocolo = request.form.get("numero_protocolo", "").strip()
        if not numero_protocolo:
            flash("Informe o numero do protocolo.", "danger")
            return redirect(request.form.get("next") or url_for("project_detail", project_id=project_id))
        descricao = request.form.get("descricao", "").strip() or f"Protocolo em {external_stage_label(tipo_orgao)}"
        protocolo_id = execute_db(
            """
            INSERT INTO exigencias_cartorio
                (projeto_id, cartorio_id, etapa_id, tipo_orgao, tipo_registro, data_protocolo, numero_protocolo,
                 data_recebimento, prazo_resposta, descricao, status, responsavel_id, observacoes, criado_em, atualizado_em)
            VALUES (%s, %s, %s, %s, 'protocolo', %s, %s, NULL, %s, %s, 'aguardando externo', NULL, %s, %s, %s)
            """,
            (
                project_id,
                request.form.get("cartorio_id") or project["cartorio_id"],
                stage["id"] if stage else None,
                tipo_orgao,
                data_protocolo,
                numero_protocolo,
                data_limite,
                descricao,
                request.form.get("observacoes", "").strip(),
                app_now_iso(),
                app_now_iso(),
            ),
        )
        if stage and project["etapa_atual_id"] == stage["id"]:
            execute_db(
                "UPDATE projeto_etapas SET status = 'aguardando externo', subetapa_ativa = %s WHERE id = %s",
                (f"Protocolado em {external_stage_label(tipo_orgao)}", stage["id"]),
            )
        record_event(project_id, "protocolo_externo", f"Protocolo #{protocolo_id} registrado em {external_stage_label(tipo_orgao)}.")
        flash("Protocolo registrado.", "success")

    elif action == "add_exigencia":
        tipo_orgao = normalize_external_orgao(request.form.get("tipo_orgao", "CARTORIO"))
        description = request.form.get("descricao", "").strip()
        prazo_resposta = request.form.get("prazo_resposta") or None
        if not description:
            flash("Informe a descricao da exigencia.", "danger")
        elif not prazo_resposta:
            flash("Informe o prazo de resposta da exigencia.", "danger")
        else:
            external_stage = find_project_stage_by_external_type(get_db(), project_id, tipo_orgao)
            exigencia_id = execute_db(
                """
                INSERT INTO exigencias_cartorio
                    (projeto_id, cartorio_id, etapa_id, tipo_orgao, tipo_registro, data_recebimento, prazo_resposta,
                     descricao, status, responsavel_id, observacoes, criado_em, atualizado_em)
                VALUES (%s, %s, %s, %s, 'exigencia', %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    project_id,
                    request.form.get("cartorio_id") or project["cartorio_id"],
                    external_stage["id"] if external_stage else None,
                    tipo_orgao,
                    request.form.get("data_recebimento") or app_today().isoformat(),
                    prazo_resposta,
                    description,
                    request.form.get("status", "em andamento"),
                    request.form.get("responsavel_id") or None,
                    request.form.get("observacoes", "").strip(),
                    app_now_iso(),
                    app_now_iso(),
                ),
            )
            if external_stage:
                execute_db("UPDATE projeto_etapas SET status = 'atencao', subetapa_ativa = %s WHERE id = %s", ("Exigencia em correcao", external_stage["id"]))
            origem_externa = normalize_text(external_stage_label(tipo_orgao)) or "orgaoexterno"
            execute_db(
                """
                INSERT INTO pendencias
                    (projeto_id, etapa_id, descricao, origem, responsavel_id, prazo, status, data_abertura, criado_em, atualizado_em)
                VALUES (%s, %s, %s, %s, %s, %s, 'aberta', %s, %s, %s)
                """,
                (
                    project_id,
                    external_stage["id"] if external_stage else None,
                    description,
                    origem_externa,
                    request.form.get("responsavel_id") or project["responsavel_geral_id"],
                    prazo_resposta,
                    app_today().isoformat(),
                    app_now_iso(),
                    app_now_iso(),
                ),
            )
            execute_db(
                """
                INSERT INTO tarefas
                    (projeto_id, projeto_etapa_id, titulo, descricao, responsavel_id, prioridade, status, prazo, criado_em)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    project_id,
                    external_stage["id"] if external_stage else None,
                    f"Responder exigencia de {external_stage_label(tipo_orgao)}",
                    description,
                    request.form.get("responsavel_id") or project["responsavel_geral_id"],
                    "Alta",
                    "em andamento",
                    prazo_resposta,
                    app_now_iso(),
                ),
            )
            record_event(project_id, "exigencia_criada", f"Exigencia #{exigencia_id} registrada.")
            flash("Exigencia registrada e tarefa criada.", "success")

    elif action == "update_exigencia":
        exigencia_id = request.form.get("exigencia_id")
        prazo_resposta = request.form.get("prazo_resposta") or None
        tipo_registro = request.form.get("tipo_registro", "exigencia")
        protocol_action = request.form.get("protocol_action", "")
        data_retirada = request.form.get("data_retirada") or None
        data_pronto_retirada = request.form.get("data_pronto_retirada") or None
        status = request.form.get("status", "em andamento")
        responsavel_id = request.form.get("responsavel_id") or None
        if tipo_registro == "protocolo":
            if protocol_action == "ready":
                if not responsavel_id:
                    flash("Escolha o responsavel pela retirada.", "danger")
                    return redirect(request.form.get("next") or url_for("project_detail", project_id=project_id))
                data_pronto_retirada = data_pronto_retirada or app_today().isoformat()
                status = "pronto para retirada"
            elif protocol_action == "withdrawn":
                data_pronto_retirada = data_pronto_retirada or app_today().isoformat()
                data_retirada = data_retirada or app_today().isoformat()
                status = "concluido"
            elif data_retirada:
                status = "concluido"
            elif data_pronto_retirada and status not in ("concluido", "cancelado"):
                status = "pronto para retirada"
        else:
            if data_retirada:
                status = "concluido"
            elif data_pronto_retirada and status not in ("concluido", "cancelado"):
                status = "pronto para retirada"
        if tipo_registro == "exigencia" and not prazo_resposta:
            flash("Informe o prazo de resposta da exigencia.", "danger")
        else:
            exigencia_row = query_db("SELECT * FROM exigencias_cartorio WHERE id = %s AND projeto_id = %s", (exigencia_id, project_id), one=True)
            if exigencia_row and tipo_registro == "protocolo":
                prazo_resposta = prazo_resposta or exigencia_row["prazo_resposta"] or external_protocol_check_date(exigencia_row["data_protocolo"])
            execute_db(
                """
                UPDATE exigencias_cartorio
                SET status = %s, responsavel_id = %s, prazo_resposta = %s,
                    data_pronto_retirada = %s, data_retirada = %s, atualizado_em = %s
                WHERE id = %s AND projeto_id = %s
                """,
                (
                    status,
                    responsavel_id,
                    prazo_resposta,
                    data_pronto_retirada,
                    data_retirada,
                    app_now_iso(),
                    exigencia_id,
                    project_id,
                ),
            )
            record_event(project_id, "exigencia_atualizada", f"Exigencia #{exigencia_id} atualizada.")
            if exigencia_row and tipo_registro == "protocolo" and status == "pronto para retirada":
                ensure_protocol_withdrawal_task(
                    project_id,
                    exigencia_row["etapa_id"],
                    exigencia_row["id"],
                    exigencia_row["tipo_orgao"] or "CARTORIO",
                    responsavel_id,
                    data_pronto_retirada,
                )
                record_event(project_id, "protocolo_pronto_retirada", f"Protocolo #{exigencia_id} pronto para retirada.")
            if exigencia_row and status in ("concluido", "cancelado"):
                execute_db(
                    """
                    UPDATE pendencias
                    SET status = 'resolvida', data_resolucao = COALESCE(data_resolucao, %s), atualizado_em = %s
                    WHERE projeto_id = %s
                      AND descricao = %s
                      AND (%s IS NULL OR etapa_id = %s)
                      AND lower(COALESCE(status, '')) NOT IN ('resolvida', 'cancelada')
                    """,
                    (
                        app_today().isoformat(),
                        app_now_iso(),
                        project_id,
                        exigencia_row["descricao"],
                        exigencia_row["etapa_id"],
                        exigencia_row["etapa_id"],
                    ),
                )
            if exigencia_row and tipo_registro == "protocolo" and status == "concluido":
                complete_protocol_withdrawal_tasks(project_id, exigencia_row["id"])
            next_stage = None
            if data_retirada and exigencia_row:
                next_stage = maybe_advance_external_stage_after_withdrawal(
                    project_id,
                    exigencia_row["tipo_orgao"] or "CARTORIO",
                    request.form.get("responsavel_id") or project["responsavel_geral_id"],
                )
            if next_stage:
                flash(f"Registro atualizado. Projeto avancou para {next_stage['etapa_nome']}.", "success")
            else:
                flash("Registro atualizado.", "success")

    elif action == "add_time":
        minutes = int(request.form.get("duracao_minutos") or 0)
        if minutes > 0:
            execute_db(
                """
                INSERT INTO apontamentos_tempo
                    (projeto_id, etapa_id, tarefa_id, usuario_id, inicio, fim, duracao_minutos, tipo_tempo, observacoes, criado_em)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                    app_now_iso(),
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


@app.route("/api/project/<int:project_id>/external-protocol", methods=["POST"])
@login_required
def api_add_external_protocol(project_id):
    data = request.get_json() or {}
    project = query_db("SELECT * FROM projetos WHERE id = %s", (project_id,), one=True)
    if not project:
        return jsonify({"ok": False, "error": "Projeto nao encontrado."}), 404
    tipo_orgao = normalize_external_orgao(data.get("tipo_orgao") or "CARTORIO")
    numero_protocolo = (data.get("numero_protocolo") or "").strip()
    if not numero_protocolo:
        return jsonify({"ok": False, "error": "Informe o numero do protocolo."}), 400
    data_protocolo = data.get("data_protocolo") or app_today().isoformat()
    data_limite = external_protocol_check_date(data_protocolo)
    descricao = (data.get("descricao") or "").strip() or f"Protocolo em {external_stage_label(tipo_orgao)}"
    stage = find_project_stage_by_external_type(get_db(), project_id, tipo_orgao)
    protocolo_id = execute_db(
        """
        INSERT INTO exigencias_cartorio
            (projeto_id, cartorio_id, etapa_id, tipo_orgao, tipo_registro, data_protocolo, numero_protocolo,
             data_recebimento, prazo_resposta, descricao, status, responsavel_id, observacoes, criado_em, atualizado_em)
        VALUES (%s, %s, %s, %s, 'protocolo', %s, %s, NULL, %s, %s, 'aguardando externo', NULL, %s, %s, %s)
        """,
        (
            project_id,
            data.get("cartorio_id") or project["cartorio_id"],
            stage["id"] if stage else None,
            tipo_orgao,
            data_protocolo,
            numero_protocolo,
            data_limite,
            descricao,
            (data.get("observacoes") or "").strip(),
            app_now_iso(),
            app_now_iso(),
        ),
    )
    if stage and project["etapa_atual_id"] == stage["id"]:
        execute_db(
            "UPDATE projeto_etapas SET status = 'aguardando externo', subetapa_ativa = %s WHERE id = %s",
            (f"Protocolado em {external_stage_label(tipo_orgao)}", stage["id"]),
        )
    record_event(project_id, "protocolo_externo", f"Protocolo #{protocolo_id} registrado em {external_stage_label(tipo_orgao)}.")
    protocol = load_external_protocol(project_id, protocolo_id)
    return jsonify({
        "ok": True,
        "protocol": external_protocol_payload(protocol),
        "summary": external_stage_protocol_summary(project_id, EXTERNAL_PROTOCOL_SCOPE, stage["id"] if stage else None),
    })


@app.route("/api/project/<int:project_id>/external-protocol/<int:protocol_id>", methods=["POST"])
@login_required
def api_update_external_protocol(project_id, protocol_id):
    data = request.get_json() or {}
    action = (data.get("action") or "").strip()
    protocol = load_external_protocol(project_id, protocol_id)
    if not protocol or (protocol["tipo_registro"] or "exigencia") != "protocolo":
        return jsonify({"ok": False, "error": "Protocolo nao encontrado."}), 404
    protocol_stage_id = protocol["etapa_id"]
    tipo_orgao = normalize_external_orgao(protocol["tipo_orgao"] or "CARTORIO")

    if action == "delete":
        cancel_protocol_withdrawal_tasks(project_id, protocol_id)
        execute_db("DELETE FROM exigencias_cartorio WHERE id = %s AND projeto_id = %s", (protocol_id, project_id))
        record_event(project_id, "protocolo_excluido", f"Protocolo #{protocol_id} excluido.")
        summary = external_stage_protocol_summary(project_id, EXTERNAL_PROTOCOL_SCOPE, protocol_stage_id)
        project = query_db("SELECT etapa_atual_id FROM projetos WHERE id = %s", (project_id,), one=True)
        if summary["protocol_count"] == 0 and project and project["etapa_atual_id"] == protocol["etapa_id"]:
            execute_db(
                "UPDATE projeto_etapas SET status = 'em andamento', subetapa_ativa = NULL WHERE id = %s",
                (protocol["etapa_id"],),
            )
        return jsonify({
            "ok": True,
            "deleted": True,
            "protocol_id": protocol_id,
            "summary": summary,
        })

    responsible_id = data.get("responsavel_id") or protocol["responsavel_id"]
    today = app_today().isoformat()
    next_stage = None
    if action == "ready":
        if not responsible_id:
            return jsonify({"ok": False, "error": "Escolha o responsavel pela retirada."}), 400
        execute_db(
            """
            UPDATE exigencias_cartorio
            SET status = 'pronto para retirada',
                responsavel_id = %s,
                data_pronto_retirada = COALESCE(data_pronto_retirada, %s),
                atualizado_em = %s
            WHERE id = %s AND projeto_id = %s
            """,
            (responsible_id, today, app_now_iso(), protocol_id, project_id),
        )
        ensure_protocol_withdrawal_task(
            project_id,
            protocol["etapa_id"],
            protocol_id,
            tipo_orgao,
            responsible_id,
            today,
        )
        record_event(project_id, "protocolo_pronto_retirada", f"Protocolo #{protocol_id} pronto para retirada.")
    elif action == "withdrawn":
        execute_db(
            """
            UPDATE exigencias_cartorio
            SET status = 'concluido',
                responsavel_id = COALESCE(%s, responsavel_id),
                data_pronto_retirada = COALESCE(data_pronto_retirada, %s),
                data_retirada = COALESCE(data_retirada, %s),
                atualizado_em = %s
            WHERE id = %s AND projeto_id = %s
            """,
            (responsible_id, today, today, app_now_iso(), protocol_id, project_id),
        )
        complete_protocol_withdrawal_tasks(project_id, protocol_id)
        next_stage = maybe_advance_external_stage_after_withdrawal(project_id, tipo_orgao, responsible_id)
        record_event(project_id, "retirada_orgao_externo", f"Protocolo #{protocol_id} retirado.")
    else:
        return jsonify({"ok": False, "error": "Acao invalida."}), 400

    protocol = load_external_protocol(project_id, protocol_id)
    payload = {
        "ok": True,
        "protocol": external_protocol_payload(protocol),
        "summary": external_stage_protocol_summary(project_id, EXTERNAL_PROTOCOL_SCOPE, protocol_stage_id),
    }
    if next_stage:
        payload["next_stage"] = {"id": next_stage["id"], "nome": next_stage["etapa_nome"]}
    return jsonify(payload)


@app.route("/api/project/<int:project_id>/external-stage/skip", methods=["POST"])
@login_required
def api_skip_external_stage(project_id):
    data = request.get_json() or {}
    project = query_db("SELECT * FROM projetos WHERE id = %s", (project_id,), one=True)
    if not project:
        return jsonify({"ok": False, "error": "Projeto nao encontrado."}), 404
    stage_id = data.get("stage_id") or project["etapa_atual_id"]
    stage = load_project_stage_for_action(stage_id, project_id)
    if not stage or external_stage_type(stage) != EXTERNAL_PROTOCOL_SCOPE:
        return jsonify({"ok": False, "error": "Etapa externa nao encontrada."}), 404
    if project["etapa_atual_id"] != stage["id"]:
        return jsonify({"ok": False, "error": "Esta nao e a etapa atual do projeto."}), 400
    if external_stage_has_any_records(project_id, EXTERNAL_PROTOCOL_SCOPE, stage["id"]):
        return jsonify({"ok": False, "error": "Ja existe protocolo nesta etapa. Retire ou exclua os protocolos antes de avancar sem protocolo."}), 400

    now = app_now_iso()
    execute_db(
        "UPDATE projeto_etapas SET status = 'nao aplicavel', progresso = 100, data_fim = COALESCE(data_fim, %s), subetapa_ativa = %s WHERE id = %s",
        (now, "Sem protocolo nesta etapa", stage["id"]),
    )
    completed_stage = load_project_stage_for_action(stage["id"], project_id)
    next_stage = advance_project_after_stage_completion(project_id, completed_stage, stage["responsavel_id"])
    record_event(project_id, "orgao_externo_nao_aplicavel", f"Etapa {stage['etapa_nome']} avancada sem protocolo externo.")
    payload = {"ok": True, "message": "Etapa avancada sem protocolo."}
    if next_stage:
        payload["next_stage"] = {"id": next_stage["id"], "nome": next_stage["etapa_nome"]}
        payload["message"] = f"Etapa avancada para {next_stage['etapa_nome']}."
    else:
        payload["message"] = "Etapa avancada e projeto concluido."
    return jsonify(payload)


@app.route("/api/checklist/add", methods=["POST"])
@login_required
def api_add_checklist_item():
    data = request.get_json() or {}
    titulo = (data.get("titulo") or "").strip()
    stage_id = data.get("stage_id")
    if not titulo or not stage_id:
        return jsonify({"ok": False, "error": "Dados incompletos"}), 400
    stage = query_db("SELECT * FROM projeto_etapas WHERE id = %s", (stage_id,), one=True)
    if not stage:
        return jsonify({"ok": False, "error": "Etapa nao encontrada"}), 404
    item_id = execute_db("INSERT INTO checklist_itens (projeto_etapa_id, titulo) VALUES (%s, %s)", (stage_id, titulo))
    progress = update_stage_progress(stage_id)
    done = query_db("SELECT COUNT(*) AS n FROM checklist_itens WHERE projeto_etapa_id = %s AND concluido = 1", (stage_id,), one=True)["n"]
    total = query_db("SELECT COUNT(*) AS n FROM checklist_itens WHERE projeto_etapa_id = %s", (stage_id,), one=True)["n"]
    return jsonify({"ok": True, "id": item_id, "titulo": titulo, "concluido": False, "progress": progress, "done": done, "total": total})


@app.route("/api/checklist/<int:item_id>/toggle", methods=["POST"])
@login_required
def api_toggle_checklist(item_id):
    from flask import jsonify
    item = query_db("SELECT * FROM checklist_itens WHERE id = %s", (item_id,), one=True)
    if not item:
        return jsonify({"ok": False, "error": "Item nao encontrado"}), 404
    new_value = 0 if item["concluido"] else 1
    now = app_now_iso()
    execute_db(
        "UPDATE checklist_itens SET concluido = %s, concluido_por = %s, concluido_em = %s WHERE id = %s",
        (new_value, g.user["id"] if new_value else None, now if new_value else None, item_id),
    )
    progress = update_stage_progress(item["projeto_etapa_id"])
    done = query_db("SELECT COUNT(*) AS n FROM checklist_itens WHERE projeto_etapa_id = %s AND concluido = 1", (item["projeto_etapa_id"],), one=True)["n"]
    total = query_db("SELECT COUNT(*) AS n FROM checklist_itens WHERE projeto_etapa_id = %s", (item["projeto_etapa_id"],), one=True)["n"]
    return jsonify({"ok": True, "concluido": bool(new_value), "progress": progress, "done": done, "total": total})


@app.route("/api/project/<int:project_id>/note", methods=["POST"])
@login_required
def api_add_project_note(project_id):
    """Adiciona uma anotacao livre ao projeto (popup da matriz)."""
    data = request.get_json() or {}
    texto = (data.get("texto") or "").strip()
    if not texto:
        return jsonify({"ok": False, "error": "Escreva a anotacao."}), 400
    if not query_db("SELECT id FROM projetos WHERE id = %s", (project_id,), one=True):
        return jsonify({"ok": False, "error": "Projeto nao encontrado"}), 404
    now = app_now_iso()
    note_id = execute_db(
        "INSERT INTO eventos_historico (projeto_id, usuario_id, tipo_evento, descricao, criado_em) VALUES (%s, %s, 'anotacao', %s, %s)",
        (project_id, g.user["id"], texto, now),
    )
    return jsonify({"ok": True, "id": note_id, "texto": texto, "autor": g.user["nome"], "data": format_datetime(now)})


@app.route("/api/project-checklist/<int:item_id>/toggle", methods=["POST"])
@login_required
def api_toggle_project_checklist(item_id):
    """Marca/desmarca um item do checklist do processo (usado no popup da matriz)."""
    item = query_db("SELECT * FROM project_checklist_items WHERE id = %s", (item_id,), one=True)
    if not item:
        return jsonify({"ok": False, "error": "Item nao encontrado"}), 404
    new_status = CHECKLIST_STATUS_NOT_STARTED if item["status"] == CHECKLIST_STATUS_DONE else CHECKLIST_STATUS_DONE
    now = app_now_iso()
    execute_db(
        "UPDATE project_checklist_items SET status = %s, completed_at = %s, completed_by = %s, updated_at = %s WHERE id = %s",
        (
            new_status,
            now if new_status == CHECKLIST_STATUS_DONE else None,
            g.user["id"] if new_status == CHECKLIST_STATUS_DONE else None,
            now,
            item_id,
        ),
    )
    done = total = progress = 0
    required_pending = 0
    if item["project_stage_id"]:
        done, total, progress = project_checklist_stage_counts(item["project_stage_id"])
        required_pending = count_blocking_checklist_pending(item["project_stage_id"])
        execute_db("UPDATE projeto_etapas SET progresso = %s WHERE id = %s", (progress, item["project_stage_id"]))
    return jsonify({
        "ok": True,
        "concluido": new_status == CHECKLIST_STATUS_DONE,
        "progress": progress,
        "done": done,
        "total": total,
        "required_pending": required_pending,
    })


@app.route("/api/project-checklist/add", methods=["POST"])
@login_required
def api_add_project_checklist_item():
    """Adiciona um item livre ao checklist do processo de uma etapa (popup da matriz)."""
    data = request.get_json() or {}
    titulo = (data.get("titulo") or "").strip()
    stage_id = data.get("stage_id")
    if not titulo or not stage_id:
        return jsonify({"ok": False, "error": "Dados incompletos"}), 400
    stage = query_db("SELECT * FROM projeto_etapas WHERE id = %s", (stage_id,), one=True)
    if not stage:
        return jsonify({"ok": False, "error": "Etapa nao encontrada"}), 404
    now = app_now_iso()
    order_index = query_db(
        "SELECT COALESCE(MAX(order_index), 0) + 1 AS n FROM project_checklist_items WHERE project_stage_id = %s",
        (stage_id,),
        one=True,
    )["n"]
    try:
        item_id = execute_db(
            """
            INSERT INTO project_checklist_items
                (project_id, project_stage_id, process_type_key, stage_key, stage_name, title, status,
                 requirement_level, criticality, blocks_stage_completion, blocks_process_completion,
                 requires_attachment, allows_observation, order_index, active, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 0, 0, 0, 1, %s, 1, %s, %s)
            """,
            (
                stage["projeto_id"],
                stage_id,
                stage["process_type_key"],
                stage["stage_key"],
                stage["stage_name"],
                titulo,
                CHECKLIST_STATUS_NOT_STARTED,
                REQUIREMENT_RECOMMENDED,
                CRITICALITY_LOW,
                order_index,
                now,
                now,
            ),
        )
    except psycopg2.errors.UniqueViolation:
        return jsonify({"ok": False, "error": "Ja existe um item com esse nome nesta etapa."}), 409
    done, total, progress = project_checklist_stage_counts(stage_id)
    execute_db("UPDATE projeto_etapas SET progresso = %s WHERE id = %s", (progress, stage_id))
    return jsonify({"ok": True, "id": item_id, "titulo": titulo, "concluido": False, "progress": progress, "done": done, "total": total})


@app.route("/stage/<int:stage_id>/quick", methods=["POST"])
@login_required
def stage_quick(stage_id):
    stage = load_project_stage_for_action(stage_id)
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
        data_inicio = data_inicio or app_now_iso()
    elif action == "pause":
        status = "atencao"
    elif action == "finish":
        if is_office_elaboration_stage(stage) and count_blocking_checklist_pending(stage_id):
            flash("Conclua os documentos do cartorio antes de concluir a etapa Escritorio.", "danger")
            return redirect(request.form.get("next") or url_for("project_detail", project_id=stage["projeto_id"]))
        can_finish_external, external_message = can_finish_external_stage(stage["projeto_id"], stage)
        if not can_finish_external:
            flash(external_message, "danger")
            return redirect(request.form.get("next") or url_for("project_detail", project_id=stage["projeto_id"]))
        status = "concluido"
        progress = 100
        data_fim = app_now_iso()
    execute_db(
        "UPDATE projeto_etapas SET status = %s, progresso = %s, data_inicio = %s, data_fim = %s WHERE id = %s",
        (status, progress, data_inicio, data_fim, stage_id),
    )
    next_stage = None
    if action == "finish":
        completed_stage = load_project_stage_for_action(stage_id)
        next_stage = advance_project_after_stage_completion(stage["projeto_id"], completed_stage, stage["responsavel_id"])
    record_event(stage["projeto_id"], "acao_rapida_etapa", f"Acao rapida em {stage['etapa_nome']}: {STATUS_META.get(status, {}).get('label', status)}.")
    if next_stage:
        flash(f"Etapa concluida. Projeto avancou para {next_stage['etapa_nome']}.", "success")
    else:
        flash("Etapa atualizada.", "success")
    return redirect(request.form.get("next") or url_for("project_detail", project_id=stage["projeto_id"]))


@app.route("/task/<int:task_id>/quick", methods=["POST"])
@login_required
def task_quick(task_id):
    task = query_db("SELECT * FROM tarefas WHERE id = %s", (task_id,), one=True)
    if not task:
        flash("Tarefa nao encontrada.", "danger")
        return redirect(url_for("my_missions"))
    action = request.form.get("quick_action")
    status = task["status"] or "nao iniciado"
    data_inicio = task["data_inicio"]
    concluido_em = task["concluido_em"]
    if action == "start":
        status = "em andamento"
        data_inicio = data_inicio or app_now_iso()
    elif action == "pause":
        status = "atencao"
    elif action == "finish":
        status = "concluido"
        concluido_em = app_now_iso()
    execute_db(
        "UPDATE tarefas SET status = %s, data_inicio = %s, concluido_em = %s WHERE id = %s",
        (status, data_inicio, concluido_em, task_id),
    )
    if action == "finish" and (task["descricao"] or "").startswith("RETIRAR_PROTOCOLO:"):
        marker_line = (task["descricao"] or "").splitlines()[0]
        raw_protocol_id = marker_line.replace("RETIRAR_PROTOCOLO:", "", 1).strip()
        if raw_protocol_id.isdigit():
            protocol = query_db(
                "SELECT * FROM exigencias_cartorio WHERE id = %s AND projeto_id = %s",
                (int(raw_protocol_id), task["projeto_id"]),
                one=True,
            )
            if protocol:
                today = app_today().isoformat()
                execute_db(
                    """
                    UPDATE exigencias_cartorio
                    SET status = 'concluido',
                        data_pronto_retirada = COALESCE(data_pronto_retirada, %s),
                        data_retirada = COALESCE(data_retirada, %s),
                        atualizado_em = %s
                    WHERE id = %s AND projeto_id = %s
                    """,
                    (today, today, app_now_iso(), protocol["id"], task["projeto_id"]),
                )
                next_stage = maybe_advance_external_stage_after_withdrawal(
                    task["projeto_id"],
                    protocol["tipo_orgao"] or "CARTORIO",
                    task["responsavel_id"],
                )
                if next_stage:
                    flash(f"Retirada registrada. Projeto avancou para {next_stage['etapa_nome']}.", "success")
                else:
                    flash("Retirada registrada.", "success")
                record_event(task["projeto_id"], "retirada_orgao_externo", f"Protocolo #{protocol['id']} retirado via Minhas missoes.")
                return redirect(request.form.get("next") or url_for("my_missions"))
    record_event(task["projeto_id"], "acao_rapida_tarefa", f"Tarefa {task['titulo']} atualizada para {STATUS_META.get(status, {}).get('label', status)}.")
    flash("Tarefa atualizada.", "success")
    return redirect(request.form.get("next") or url_for("my_missions"))


@app.route("/pending/<int:pending_id>/quick", methods=["POST"])
@login_required
def pending_quick(pending_id):
    pending = query_db("SELECT * FROM pendencias WHERE id = %s", (pending_id,), one=True)
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
        resolved_at = app_today().isoformat()
    elif action == "cancel":
        status = "cancelada"
        resolved_at = app_today().isoformat()
    execute_db(
        "UPDATE pendencias SET status = %s, data_resolucao = %s, atualizado_em = %s WHERE id = %s",
        (status, resolved_at, app_now_iso(), pending_id),
    )
    record_event(pending["projeto_id"], "pendencia_atualizada", f"Pendencia #{pending_id} atualizada para {status}.")
    flash("Pendencia atualizada.", "success")
    return redirect(request.form.get("next") or url_for("my_missions"))


def get_first_imovel_for_client(cliente_id):
    return query_db(
        """
        SELECT i.*, ci.id AS vinculo_id, ci.papel, ci.percentual_participacao, ci.principal
        FROM clientes_imoveis ci
        JOIN imoveis i ON i.id = ci.imovel_id
        WHERE ci.cliente_id = %s
        ORDER BY ci.principal DESC, ci.id
        LIMIT 1
        """,
        (cliente_id,),
        one=True,
    )


def load_cliente_documental(cliente_id):
    cliente = query_db("SELECT * FROM clientes WHERE id = %s", (cliente_id,), one=True)
    if not cliente:
        return None
    pf = query_db("SELECT * FROM pessoas_fisicas WHERE cliente_id = %s", (cliente_id,), one=True)
    conjuge = None
    endereco = None
    if pf:
        conjuge = query_db("SELECT * FROM conjuges WHERE pessoa_fisica_id = %s", (pf["id"],), one=True)
        endereco = query_db("SELECT * FROM enderecos_proprietario WHERE pessoa_fisica_id = %s", (pf["id"],), one=True)
    pj = query_db("SELECT * FROM pessoas_juridicas WHERE cliente_id = %s", (cliente_id,), one=True)
    procuradores = query_db(
        "SELECT * FROM procuradores WHERE cliente_id = %s ORDER BY principal DESC, id",
        (cliente_id,),
    )
    procurador = procuradores[0] if procuradores else None
    imoveis = query_db(
        """
        SELECT i.*, ci.id AS vinculo_id, ci.papel, ci.percentual_participacao, ci.principal
        FROM clientes_imoveis ci
        JOIN imoveis i ON i.id = ci.imovel_id
        WHERE ci.cliente_id = %s
        ORDER BY ci.principal DESC, i.nome_imovel
        """,
        (cliente_id,),
    )
    vertices_by_imovel = {}
    for imovel in imoveis:
        vertices_by_imovel[imovel["id"]] = query_db(
            "SELECT * FROM vertices_imovel WHERE imovel_id = %s ORDER BY ordem, id",
            (imovel["id"],),
        )
    context = {
        "cliente": row_to_plain_dict(cliente),
        "pessoa_fisica": row_to_plain_dict(pf),
        "conjuge": row_to_plain_dict(conjuge),
        "pessoa_juridica": row_to_plain_dict(pj),
        "endereco": row_to_plain_dict(endereco),
        "procurador": row_to_plain_dict(procurador),
        "procuradores": [row_to_plain_dict(row) for row in procuradores],
        "imoveis": [row_to_plain_dict(row) for row in imoveis],
        "vertices_by_imovel": {key: [row_to_plain_dict(row) for row in rows] for key, rows in vertices_by_imovel.items()},
    }
    context["completeness"] = get_cadastro_completeness(context)
    context["cliente_pendencias"] = get_cliente_pendencias(context)
    context["document_readiness"] = get_document_readiness(context)
    context["document_context"] = build_documento_context(
        context,
        context["imoveis"][0] if context["imoveis"] else {},
        context["vertices_by_imovel"].get(context["imoveis"][0]["id"], []) if context["imoveis"] else [],
    )
    return context


def load_clientes_documental_batch(client_rows):
    client_ids = [row["id"] for row in client_rows]
    if not client_ids:
        return {}

    def placeholders(values):
        return ",".join("%s" for _ in values)

    def first_by(rows, key):
        indexed = {}
        for row in rows:
            indexed.setdefault(row[key], row)
        return indexed

    def group_by(rows, key):
        grouped = {}
        for row in rows:
            grouped.setdefault(row[key], []).append(row)
        return grouped

    client_placeholders = placeholders(client_ids)
    pf_rows = query_db(
        f"SELECT * FROM pessoas_fisicas WHERE cliente_id IN ({client_placeholders}) ORDER BY cliente_id, id",
        client_ids,
    )
    pj_rows = query_db(
        f"SELECT * FROM pessoas_juridicas WHERE cliente_id IN ({client_placeholders}) ORDER BY cliente_id, id",
        client_ids,
    )
    procurador_rows = query_db(
        f"SELECT * FROM procuradores WHERE cliente_id IN ({client_placeholders}) ORDER BY cliente_id, principal DESC, id",
        client_ids,
    )
    imovel_rows = query_db(
        f"""
        SELECT i.*, ci.id AS vinculo_id, ci.cliente_id, ci.papel, ci.percentual_participacao, ci.principal
        FROM clientes_imoveis ci
        JOIN imoveis i ON i.id = ci.imovel_id
        WHERE ci.cliente_id IN ({client_placeholders})
        ORDER BY ci.cliente_id, ci.principal DESC, i.nome_imovel
        """,
        client_ids,
    )

    pfs_by_client = first_by(pf_rows, "cliente_id")
    pjs_by_client = first_by(pj_rows, "cliente_id")
    procuradores_by_client = first_by(procurador_rows, "cliente_id")
    procuradores_grouped_by_client = group_by(procurador_rows, "cliente_id")
    imoveis_by_client = group_by(imovel_rows, "cliente_id")

    pf_ids = [row["id"] for row in pf_rows]
    conjuges_by_pf = {}
    enderecos_by_pf = {}
    if pf_ids:
        pf_placeholders = placeholders(pf_ids)
        conjuges_by_pf = first_by(
            query_db(
                f"SELECT * FROM conjuges WHERE pessoa_fisica_id IN ({pf_placeholders}) ORDER BY pessoa_fisica_id, id",
                pf_ids,
            ),
            "pessoa_fisica_id",
        )
        enderecos_by_pf = first_by(
            query_db(
                f"SELECT * FROM enderecos_proprietario WHERE pessoa_fisica_id IN ({pf_placeholders}) ORDER BY pessoa_fisica_id, id",
                pf_ids,
            ),
            "pessoa_fisica_id",
        )

    imovel_ids = [row["id"] for row in imovel_rows]
    vertices_by_imovel = {}
    if imovel_ids:
        imovel_placeholders = placeholders(imovel_ids)
        vertices_by_imovel = group_by(
            query_db(
                f"SELECT * FROM vertices_imovel WHERE imovel_id IN ({imovel_placeholders}) ORDER BY imovel_id, ordem, id",
                imovel_ids,
            ),
            "imovel_id",
        )

    contexts = {}
    for client in client_rows:
        client_id = client["id"]
        pf = pfs_by_client.get(client_id)
        pf_id = pf["id"] if pf else None
        imoveis = imoveis_by_client.get(client_id, [])
        context = {
            "cliente": row_to_plain_dict(client),
            "pessoa_fisica": row_to_plain_dict(pf),
            "conjuge": row_to_plain_dict(conjuges_by_pf.get(pf_id)),
            "pessoa_juridica": row_to_plain_dict(pjs_by_client.get(client_id)),
            "endereco": row_to_plain_dict(enderecos_by_pf.get(pf_id)),
            "procurador": row_to_plain_dict(procuradores_by_client.get(client_id)),
            "procuradores": [
                row_to_plain_dict(row) for row in procuradores_grouped_by_client.get(client_id, [])
            ],
            "imoveis": [row_to_plain_dict(row) for row in imoveis],
            "vertices_by_imovel": {
                imovel["id"]: [row_to_plain_dict(row) for row in vertices_by_imovel.get(imovel["id"], [])]
                for imovel in imoveis
            },
        }
        context["completeness"] = get_cadastro_completeness(context)
        context["cliente_pendencias"] = get_cliente_pendencias(context)
        context["document_readiness"] = get_document_readiness(context)
        context["document_context"] = build_documento_context(
            context,
            context["imoveis"][0] if context["imoveis"] else {},
            context["vertices_by_imovel"].get(context["imoveis"][0]["id"], []) if context["imoveis"] else [],
        )
        contexts[client_id] = context
    return contexts


def row_to_plain_dict(row):
    if row is None:
        return {}
    return {key: row[key] for key in row.keys()}


def get_form_value(name, default=""):
    return request.form.get(name, default).strip()


def form_decimal(name):
    value = parse_decimal_br(get_form_value(name))
    return float(value) if value not in (None, "") else None


REPRESENTATIVE_FORM_FIELDS = [
    "id",
    "tipo_representacao",
    "nome_completo",
    "cpf",
    "rg",
    "orgao_expedidor_rg",
    "nacionalidade",
    "profissao_ocupacao",
    "sexo",
    "estado_civil",
    "regime_casamento",
    "nome_pai",
    "nome_mae",
    "data_nascimento",
    "uf_nascimento",
    "cidade_nascimento",
    "email",
    "telefone",
    "cep",
    "uf",
    "cidade",
    "bairro",
    "logradouro",
    "numero",
    "complemento",
    "texto_adicional",
]


def representative_type(value):
    value = (value or "").strip().upper()
    return value if value in REPRESENTATIVE_TYPES else "PROCURADOR"


def parse_representantes_form(form):
    rows = []
    lists = {
        field: form.getlist(f"rep_{field}")
        for field in REPRESENTATIVE_FORM_FIELDS
    }
    total = max([len(values) for values in lists.values()] or [0])
    for index in range(total):
        row = {}
        for field in REPRESENTATIVE_FORM_FIELDS:
            values = lists[field]
            row[field] = values[index].strip() if index < len(values) and values[index] is not None else ""
        row["tipo_representacao"] = representative_type(row.get("tipo_representacao"))
        row["cpf"] = only_digits(row.get("cpf"))
        row["cep"] = only_digits(row.get("cep"))
        if any(row.get(field) for field in row if field != "tipo_representacao"):
            rows.append(row)

    if not rows and (form.get("proc_nome_completo") or form.get("proc_cpf")):
        rows.append(
            {
                "id": "",
                "tipo_representacao": representative_type(form.get("proc_tipo_representacao")),
                "nome_completo": form.get("proc_nome_completo", "").strip(),
                "cpf": only_digits(form.get("proc_cpf")),
                "rg": form.get("proc_rg", "").strip(),
                "orgao_expedidor_rg": form.get("proc_orgao_expedidor_rg", "").strip(),
                "nacionalidade": form.get("proc_nacionalidade", "").strip(),
                "profissao_ocupacao": form.get("proc_profissao_ocupacao", "").strip(),
                "sexo": form.get("proc_sexo", "").strip(),
                "estado_civil": form.get("proc_estado_civil", "").strip(),
                "regime_casamento": form.get("proc_regime_casamento", "").strip(),
                "nome_pai": form.get("proc_nome_pai", "").strip(),
                "nome_mae": form.get("proc_nome_mae", "").strip(),
                "data_nascimento": form.get("proc_data_nascimento", "").strip(),
                "uf_nascimento": form.get("proc_uf_nascimento", "").strip(),
                "cidade_nascimento": form.get("proc_cidade_nascimento", "").strip(),
                "email": form.get("proc_email", "").strip(),
                "telefone": form.get("proc_telefone", "").strip(),
                "cep": only_digits(form.get("proc_cep")),
                "uf": form.get("proc_uf", "").strip(),
                "cidade": form.get("proc_cidade", "").strip(),
                "bairro": form.get("proc_bairro", "").strip(),
                "logradouro": form.get("proc_logradouro", "").strip(),
                "numero": form.get("proc_numero", "").strip(),
                "complemento": form.get("proc_complemento", "").strip(),
                "texto_adicional": form.get("proc_texto_adicional", "").strip(),
            }
        )
    return rows


def validate_cliente_form(form):
    errors = []
    warnings = []
    tipo_cliente = form.get("tipo_cliente") or "PESSOA_FISICA"
    pf_cpf = only_digits(form.get("pf_cpf"))
    pj_cnpj = only_digits(form.get("pj_cnpj"))
    representantes = parse_representantes_form(form)
    representante_principal = representantes[0] if representantes else {}
    conj_cpf = only_digits(form.get("conj_cpf"))
    sigef = form.get("imovel_codigo_certificacao_sigef") or ""
    cep_fields = [
        ("pf_end_cep", "CEP do proprietario"),
        ("pj_cep", "CEP da empresa"),
    ]
    cidade_fields = [
        ("pf_end_cidade", "pf_end_uf", "cidade do proprietario"),
        ("pj_cidade", "pj_uf", "cidade da empresa"),
    ]

    if pf_cpf and not validate_cpf(pf_cpf):
        errors.append("CPF da pessoa fisica invalido.")
    if conj_cpf and not validate_cpf(conj_cpf):
        errors.append("CPF do conjuge invalido.")
    if pj_cnpj and not validate_cnpj(pj_cnpj):
        errors.append("CNPJ invalido.")

    for field, label in [
        ("pf_email", "E-mail da pessoa fisica"),
        ("conj_email", "E-mail do conjuge"),
        ("pj_email", "E-mail da empresa"),
    ]:
        if form.get(field) and not validate_email(form.get(field)):
            errors.append(f"{label} invalido.")

    for field, label in cep_fields:
        if form.get(field) and not validate_cep(form.get(field)):
            errors.append(f"{label} invalido.")

    for city_field, uf_field, label in cidade_fields:
        if form.get(city_field) and form.get(uf_field) and not validate_cidade_uf(form.get(city_field), form.get(uf_field)):
            warnings.append(f"Verifique se a {label} corresponde ao UF selecionado.")

    for field, label in [
        ("pf_data_nascimento", "Data de nascimento da pessoa fisica"),
        ("conj_data_nascimento", "Data de nascimento do conjuge"),
    ]:
        if form.get(field) and not validate_date(form.get(field)):
            errors.append(f"{label} invalida.")

    for index, representante in enumerate(representantes, start=1):
        label = REPRESENTATIVE_TYPES.get(representante["tipo_representacao"], "Representante")
        if representante.get("cpf") and not validate_cpf(representante["cpf"]):
            errors.append(f"CPF do {label.lower()} {index} invalido.")
        if representante.get("email") and not validate_email(representante["email"]):
            errors.append(f"E-mail do {label.lower()} {index} invalido.")
        if representante.get("cep") and not validate_cep(representante["cep"]):
            errors.append(f"CEP do {label.lower()} {index} invalido.")
        if representante.get("cidade") and representante.get("uf") and not validate_cidade_uf(representante["cidade"], representante["uf"]):
            warnings.append(f"Verifique se a cidade do {label.lower()} {index} corresponde ao UF selecionado.")
        if representante.get("data_nascimento") and not validate_date(representante["data_nascimento"]):
            errors.append(f"Data de nascimento do {label.lower()} {index} invalida.")

    if sigef and not validate_uuid_like(sigef):
        warnings.append("Codigo SIGEF nao parece um UUID. O cadastro foi salvo como rascunho para revisao.")

    if tipo_cliente == "PESSOA_JURIDICA":
        if not pj_cnpj:
            warnings.append("Pessoa juridica sem CNPJ fica como cadastro incompleto.")
        if not form.get("pj_razao_social"):
            warnings.append("Pessoa juridica sem razao social fica como cadastro incompleto.")
        if not representante_principal.get("cpf") or not representante_principal.get("nome_completo"):
            warnings.append("Pessoa juridica exige representante/procurador para documentos.")
    else:
        if not pf_cpf:
            warnings.append("Pessoa fisica sem CPF fica como cadastro incompleto.")
        if not form.get("pf_nome_completo"):
            warnings.append("Pessoa fisica sem nome completo fica como cadastro incompleto.")

    return errors, warnings


def save_cliente_documental():
    form = request.form
    errors, warnings = validate_cliente_form(form)
    if errors:
        for error in errors:
            flash(error, "danger")
        return None

    now = app_now_iso()
    cliente_id = form.get("cliente_id") or None
    tipo_cliente = form.get("tipo_cliente") or "PESSOA_FISICA"
    quem_assina = "PROCURADOR" if tipo_cliente == "PESSOA_JURIDICA" else (form.get("quem_assina") or "PROPRIETARIO")
    nome_exibicao = (
        form.get("pj_razao_social")
        if tipo_cliente == "PESSOA_JURIDICA"
        else form.get("pf_nome_completo")
    ) or form.get("nome_exibicao") or "Cliente em rascunho"
    tipo_pessoa = "juridica" if tipo_cliente == "PESSOA_JURIDICA" else "fisica"
    cpf_cnpj = only_digits(form.get("pj_cnpj") if tipo_cliente == "PESSOA_JURIDICA" else form.get("pf_cpf"))
    telefone = form.get("pj_telefone") if tipo_cliente == "PESSOA_JURIDICA" else form.get("pf_telefone")
    email = form.get("pj_email") if tipo_cliente == "PESSOA_JURIDICA" else form.get("pf_email")

    if cliente_id:
        execute_db(
            """
            UPDATE clientes
            SET nome = %s, tipo_cliente = %s, nome_exibicao = %s, quem_assina = %s, tipo_pessoa = %s,
                cpf_cnpj = %s, telefone = %s, email = %s, observacoes = %s, atualizado_em = %s
            WHERE id = %s
            """,
            (
                nome_exibicao,
                tipo_cliente,
                nome_exibicao,
                quem_assina,
                tipo_pessoa,
                cpf_cnpj,
                telefone,
                email,
                form.get("observacoes", "").strip(),
                now,
                cliente_id,
            ),
        )
        cliente_id = int(cliente_id)
    else:
        cliente_id = execute_db(
            """
            INSERT INTO clientes
                (nome, tipo_cliente, nome_exibicao, quem_assina, status_cadastro, tipo_pessoa, cpf_cnpj, telefone, email, observacoes, criado_em, atualizado_em)
            VALUES (%s, %s, %s, %s, 'RASCUNHO', %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                nome_exibicao,
                tipo_cliente,
                nome_exibicao,
                quem_assina,
                tipo_pessoa,
                cpf_cnpj,
                telefone,
                email,
                form.get("observacoes", "").strip(),
                now,
                now,
            ),
        )

    if tipo_cliente == "PESSOA_JURIDICA":
        upsert_pessoa_juridica(cliente_id, now)
    else:
        pf_id = upsert_pessoa_fisica(cliente_id, now)
        upsert_endereco_pf(pf_id, now)
        upsert_conjuge(pf_id, now)

    if quem_assina == "PROCURADOR" or tipo_cliente == "PESSOA_JURIDICA":
        sync_procuradores(cliente_id, now)
    else:
        execute_db("DELETE FROM procuradores WHERE cliente_id = %s", (cliente_id,))

    upsert_imovel_vinculado(cliente_id, now)
    refresh_cliente_status(cliente_id)

    for warning in warnings:
        flash(warning, "warning")
    flash("Cadastro de cliente salvo.", "success")
    return cliente_id


def upsert_pessoa_fisica(cliente_id, now):
    existing = query_db("SELECT id FROM pessoas_fisicas WHERE cliente_id = %s", (cliente_id,), one=True)
    estado_civil = get_form_value("pf_estado_civil") or None
    regime_casamento = get_form_value("pf_regime_casamento") if estado_civil in ("CASADO", "UNIAO_ESTAVEL") else None
    incluir_conjuge = 1 if estado_civil in ("CASADO", "UNIAO_ESTAVEL") and request.form.get("pf_incluir_conjuge") else 0
    values = (
        get_form_value("pf_sexo") or None,
        get_form_value("pf_nome_completo") or None,
        get_form_value("pf_nacionalidade") or None,
        estado_civil,
        regime_casamento,
        incluir_conjuge,
        get_form_value("pf_profissao_ocupacao") or None,
        get_form_value("pf_rg") or None,
        get_form_value("pf_orgao_expedidor_rg") or None,
        only_digits(get_form_value("pf_cpf")) or None,
        get_form_value("pf_nome_pai") or None,
        get_form_value("pf_nome_mae") or None,
        get_form_value("pf_data_nascimento") or None,
        get_form_value("pf_uf_nascimento") or None,
        get_form_value("pf_cidade_nascimento") or None,
        get_form_value("pf_email") or None,
        get_form_value("pf_telefone") or None,
        now,
    )
    if existing:
        execute_db(
            """
            UPDATE pessoas_fisicas
            SET sexo = %s, nome_completo = %s, nacionalidade = %s, estado_civil = %s, regime_casamento = %s,
                incluir_conjuge = %s, profissao_ocupacao = %s, rg = %s, orgao_expedidor_rg = %s, cpf = %s,
                nome_pai = %s, nome_mae = %s, data_nascimento = %s, uf_nascimento = %s, cidade_nascimento = %s,
                email = %s, telefone = %s, atualizado_em = %s
            WHERE id = %s
            """,
            values + (existing["id"],),
        )
        return existing["id"]
    return execute_db(
        """
        INSERT INTO pessoas_fisicas
            (sexo, nome_completo, nacionalidade, estado_civil, regime_casamento, incluir_conjuge,
             profissao_ocupacao, rg, orgao_expedidor_rg, cpf, nome_pai, nome_mae, data_nascimento,
             uf_nascimento, cidade_nascimento, email, telefone, atualizado_em, cliente_id, criado_em)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        values + (cliente_id, now),
    )


def upsert_conjuge(pessoa_fisica_id, now):
    existing = query_db("SELECT id FROM conjuges WHERE pessoa_fisica_id = %s", (pessoa_fisica_id,), one=True)
    pf = query_db("SELECT estado_civil, regime_casamento, incluir_conjuge FROM pessoas_fisicas WHERE id = %s", (pessoa_fisica_id,), one=True)
    if not pf or not requires_conjuge(pf["estado_civil"], pf["regime_casamento"], bool(pf["incluir_conjuge"])):
        if existing:
            execute_db("DELETE FROM conjuges WHERE id = %s", (existing["id"],))
        return None
    has_data = any(get_form_value(field) for field in [
        "conj_nome_completo", "conj_cpf", "conj_profissao_ocupacao", "conj_rg", "conj_data_nascimento",
        "conj_email", "conj_telefone",
    ])
    if not has_data:
        if existing:
            execute_db("DELETE FROM conjuges WHERE id = %s", (existing["id"],))
        return None
    values = (
        get_form_value("conj_sexo") or None,
        get_form_value("conj_nome_completo") or None,
        only_digits(get_form_value("conj_cpf")) or None,
        get_form_value("conj_profissao_ocupacao") or None,
        get_form_value("conj_nacionalidade") or None,
        get_form_value("conj_rg") or None,
        get_form_value("conj_orgao_expedidor_rg") or None,
        get_form_value("conj_uf_nascimento") or None,
        get_form_value("conj_cidade_nascimento") or None,
        get_form_value("conj_data_nascimento") or None,
        get_form_value("conj_email") or None,
        get_form_value("conj_telefone") or None,
        now,
    )
    if existing:
        execute_db(
            """
            UPDATE conjuges
            SET sexo = %s, nome_completo = %s, cpf = %s, profissao_ocupacao = %s, nacionalidade = %s, rg = %s,
                orgao_expedidor_rg = %s, uf_nascimento = %s, cidade_nascimento = %s, data_nascimento = %s,
                email = %s, telefone = %s, atualizado_em = %s
            WHERE id = %s
            """,
            values + (existing["id"],),
        )
        return existing["id"]
    return execute_db(
        """
        INSERT INTO conjuges
            (sexo, nome_completo, cpf, profissao_ocupacao, nacionalidade, rg, orgao_expedidor_rg,
             uf_nascimento, cidade_nascimento, data_nascimento, email, telefone, atualizado_em, pessoa_fisica_id, criado_em)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        values + (pessoa_fisica_id, now),
    )


def upsert_endereco_pf(pessoa_fisica_id, now):
    existing = query_db("SELECT id FROM enderecos_proprietario WHERE pessoa_fisica_id = %s", (pessoa_fisica_id,), one=True)
    values = (
        get_form_value("pf_end_logradouro") or None,
        get_form_value("pf_end_uf") or None,
        get_form_value("pf_end_cidade") or None,
        get_form_value("pf_end_bairro") or None,
        only_digits(get_form_value("pf_end_cep")) or None,
        get_form_value("pf_end_numero") or None,
        get_form_value("pf_end_complemento") or None,
        now,
    )
    if existing:
        execute_db(
            """
            UPDATE enderecos_proprietario
            SET logradouro = %s, uf = %s, cidade = %s, bairro = %s, cep = %s, numero = %s, complemento = %s, atualizado_em = %s
            WHERE id = %s
            """,
            values + (existing["id"],),
        )
        return existing["id"]
    return execute_db(
        """
        INSERT INTO enderecos_proprietario
            (logradouro, uf, cidade, bairro, cep, numero, complemento, atualizado_em, pessoa_fisica_id, criado_em)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        values + (pessoa_fisica_id, now),
    )


def upsert_pessoa_juridica(cliente_id, now):
    existing = query_db("SELECT id FROM pessoas_juridicas WHERE cliente_id = %s", (cliente_id,), one=True)
    values = (
        get_form_value("pj_razao_social") or None,
        get_form_value("pj_nome_fantasia") or None,
        only_digits(get_form_value("pj_cnpj")) or None,
        get_form_value("pj_logradouro") or None,
        get_form_value("pj_uf") or None,
        get_form_value("pj_cidade") or None,
        get_form_value("pj_bairro") or None,
        only_digits(get_form_value("pj_cep")) or None,
        get_form_value("pj_numero") or None,
        get_form_value("pj_complemento") or None,
        get_form_value("pj_email") or None,
        get_form_value("pj_telefone") or None,
        now,
    )
    if existing:
        execute_db(
            """
            UPDATE pessoas_juridicas
            SET razao_social = %s, nome_fantasia = %s, cnpj = %s, logradouro = %s, uf = %s, cidade = %s, bairro = %s,
                cep = %s, numero = %s, complemento = %s, email = %s, telefone = %s, atualizado_em = %s
            WHERE id = %s
            """,
            values + (existing["id"],),
        )
        return existing["id"]
    return execute_db(
        """
        INSERT INTO pessoas_juridicas
            (razao_social, nome_fantasia, cnpj, logradouro, uf, cidade, bairro, cep, numero, complemento,
             email, telefone, atualizado_em, cliente_id, criado_em)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        values + (cliente_id, now),
    )


def sync_procuradores(cliente_id, now):
    representantes = parse_representantes_form(request.form)
    db = get_db()
    try:
        db.execute("DELETE FROM procuradores WHERE cliente_id = %s", (cliente_id,))
        for index, representante in enumerate(representantes):
            db.execute(
                """
                INSERT INTO procuradores
                    (cliente_id, tipo_representacao, principal, sexo, nome_completo, estado_civil, regime_casamento,
                     profissao_ocupacao, nacionalidade, rg, orgao_expedidor_rg, cpf, nome_pai, nome_mae,
                     data_nascimento, uf_nascimento, cidade_nascimento, email, telefone, texto_adicional,
                     logradouro, uf, cidade, bairro, cep, numero, complemento, criado_em, atualizado_em)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    cliente_id,
                    representative_type(representante.get("tipo_representacao")),
                    1 if index == 0 else 0,
                    representante.get("sexo") or None,
                    representante.get("nome_completo") or None,
                    representante.get("estado_civil") or None,
                    representante.get("regime_casamento") or None,
                    representante.get("profissao_ocupacao") or None,
                    representante.get("nacionalidade") or None,
                    representante.get("rg") or None,
                    representante.get("orgao_expedidor_rg") or None,
                    only_digits(representante.get("cpf")) or None,
                    representante.get("nome_pai") or None,
                    representante.get("nome_mae") or None,
                    representante.get("data_nascimento") or None,
                    representante.get("uf_nascimento") or None,
                    representante.get("cidade_nascimento") or None,
                    representante.get("email") or None,
                    representante.get("telefone") or None,
                    representante.get("texto_adicional") or None,
                    representante.get("logradouro") or None,
                    representante.get("uf") or None,
                    representante.get("cidade") or None,
                    representante.get("bairro") or None,
                    only_digits(representante.get("cep")) or None,
                    representante.get("numero") or None,
                    representante.get("complemento") or None,
                    now,
                    now,
                ),
            )
        db.commit()
        invalidate_runtime_caches()
    except Exception:
        db.rollback()
        raise


def upsert_imovel_vinculado(cliente_id, now):
    existing_id = request.form.get("imovel_id") or None
    linked_existing = request.form.get("existing_imovel_id") or None
    has_new_data = any(get_form_value(field) for field in [
        "imovel_nome_imovel", "imovel_cartorio_comarca", "imovel_numero_certidao",
        "imovel_codigo_certificacao_sigef", "imovel_codigo_sncr"
    ])
    if linked_existing and not existing_id:
        ensure_cliente_imovel_link(cliente_id, int(linked_existing), now, principal=1)
        return int(linked_existing)
    if not has_new_data and not existing_id:
        return None

    values = (
        get_form_value("imovel_nome_imovel") or None,
        get_form_value("imovel_nome_terreno") or None,
        get_form_value("imovel_cartorio_comarca") or None,
        get_form_value("imovel_cns_cartorio") or None,
        get_form_value("imovel_tipo_certidao") or None,
        get_form_value("imovel_numero_certidao") or None,
        get_form_value("imovel_estado_imovel") or None,
        get_form_value("imovel_cidade_imovel") or None,
        get_form_value("imovel_localidade_denominacao") or None,
        form_decimal("imovel_valor_imovel_terra_nua"),
        form_decimal("imovel_area_antiga_m2"),
        form_decimal("imovel_nova_area_m2"),
        form_decimal("imovel_perimetro_m"),
        get_form_value("imovel_codigo_certificacao_sigef") or None,
        get_form_value("imovel_codigo_sncr") or None,
        get_form_value("imovel_estrada_acesso") or None,
        get_form_value("imovel_ponto_referencia") or None,
        form_decimal("imovel_distancia_ponto_referencia_km"),
        get_form_value("imovel_observacoes") or None,
        now,
    )
    if existing_id:
        execute_db(
            """
            UPDATE imoveis
            SET nome_imovel = %s, nome_terreno = %s, cartorio_comarca = %s, cns_cartorio = %s, tipo_certidao = %s,
                numero_certidao = %s, estado_imovel = %s, cidade_imovel = %s, localidade_denominacao = %s,
                valor_imovel_terra_nua = %s, area_antiga_m2 = %s, nova_area_m2 = %s, perimetro_m = %s,
                codigo_certificacao_sigef = %s, codigo_sncr = %s, estrada_acesso = %s, ponto_referencia = %s,
                distancia_ponto_referencia_km = %s, observacoes = %s, atualizado_em = %s
            WHERE id = %s
            """,
            values + (existing_id,),
        )
        imovel_id = int(existing_id)
    else:
        imovel_id = execute_db(
            """
            INSERT INTO imoveis
                (nome_imovel, nome_terreno, cartorio_comarca, cns_cartorio, tipo_certidao, numero_certidao,
                 estado_imovel, cidade_imovel, localidade_denominacao, valor_imovel_terra_nua, area_antiga_m2,
                 nova_area_m2, perimetro_m, codigo_certificacao_sigef, codigo_sncr, estrada_acesso,
                 ponto_referencia, distancia_ponto_referencia_km, observacoes, atualizado_em, criado_em)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            values + (now,),
        )
    ensure_cliente_imovel_link(cliente_id, imovel_id, now, principal=1)
    upsert_vertices(imovel_id, now)
    return imovel_id


def ensure_cliente_imovel_link(cliente_id, imovel_id, now, principal=0):
    existing = query_db(
        "SELECT id FROM clientes_imoveis WHERE cliente_id = %s AND imovel_id = %s",
        (cliente_id, imovel_id),
        one=True,
    )
    if principal:
        execute_db("UPDATE clientes_imoveis SET principal = 0 WHERE cliente_id = %s", (cliente_id,))
    if existing:
        execute_db(
            """
            UPDATE clientes_imoveis
            SET papel = %s, percentual_participacao = %s, principal = %s, atualizado_em = %s
            WHERE id = %s
            """,
            (
                get_form_value("vinculo_papel") or "PROPRIETARIO",
                form_decimal("vinculo_percentual_participacao"),
                1 if principal or request.form.get("vinculo_principal") else 0,
                now,
                existing["id"],
            ),
        )
        return existing["id"]
    return execute_db(
        """
        INSERT INTO clientes_imoveis
            (cliente_id, imovel_id, papel, percentual_participacao, principal, criado_em, atualizado_em)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (
            cliente_id,
            imovel_id,
            get_form_value("vinculo_papel") or "PROPRIETARIO",
            form_decimal("vinculo_percentual_participacao"),
            1 if principal or request.form.get("vinculo_principal") else 0,
            now,
            now,
        ),
    )


def upsert_vertices(imovel_id, now):
    codigos = request.form.getlist("vert_codigo_vertice[]")
    if not codigos:
        return
    execute_db("DELETE FROM vertices_imovel WHERE imovel_id = %s", (imovel_id,))
    longitudes = request.form.getlist("vert_longitude[]")
    latitudes = request.form.getlist("vert_latitude[]")
    altitudes = request.form.getlist("vert_altitude_m[]")
    destinos = request.form.getlist("vert_codigo_vertice_destino[]")
    azimutes = request.form.getlist("vert_azimute[]")
    distancias = request.form.getlist("vert_distancia_m[]")
    confrontacoes = request.form.getlist("vert_confrontacao[]")
    for index, codigo in enumerate(codigos):
        if not any([
            codigo.strip(),
            value_at(longitudes, index),
            value_at(latitudes, index),
            value_at(destinos, index),
            value_at(confrontacoes, index),
        ]):
            continue
        execute_db(
            """
            INSERT INTO vertices_imovel
                (imovel_id, ordem, codigo_vertice, longitude, latitude, altitude_m, codigo_vertice_destino,
                 azimute, distancia_m, confrontacao, criado_em, atualizado_em)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                imovel_id,
                index + 1,
                codigo.strip(),
                value_at(longitudes, index),
                value_at(latitudes, index),
                parse_float_at(altitudes, index),
                value_at(destinos, index),
                value_at(azimutes, index),
                parse_float_at(distancias, index),
                value_at(confrontacoes, index),
                now,
                now,
            ),
        )


def value_at(values, index):
    return values[index].strip() if index < len(values) and values[index] else None


def parse_float_at(values, index):
    value = value_at(values, index)
    parsed = parse_decimal_br(value)
    return float(parsed) if parsed not in (None, "") else None


def refresh_cliente_status(cliente_id):
    context = load_cliente_documental(cliente_id)
    pendencias = context["cliente_pendencias"]
    status = pendencias["statusCadastro"]
    execute_db(
        "UPDATE clientes SET status_cadastro = %s, atualizado_em = %s WHERE id = %s",
        (status, app_now_iso(), cliente_id),
    )


def empty_cliente_context():
    context = {
        "cliente": {
            "id": "",
            "tipo_cliente": "PESSOA_FISICA",
            "nome_exibicao": "",
            "quem_assina": "PROPRIETARIO",
            "status_cadastro": "RASCUNHO",
            "observacoes": "",
        },
        "pessoa_fisica": {},
        "conjuge": {},
        "pessoa_juridica": {},
        "endereco": {},
        "procurador": {},
        "procuradores": [],
        "imoveis": [],
        "vertices_by_imovel": {},
    }
    context["completeness"] = get_cadastro_completeness(context)
    context["cliente_pendencias"] = get_cliente_pendencias(context)
    context["document_readiness"] = get_document_readiness(context)
    context["document_context"] = build_documento_context(context, {}, [])
    return context


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
        WHERE pe.responsavel_id = %s
          AND pe.id = p.etapa_atual_id
          AND lower(pe.status) NOT IN ('concluido', 'cancelado')
          AND em.ativa = 1
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
        WHERE t.responsavel_id = %s AND lower(COALESCE(t.status, '')) NOT IN ('concluido', 'cancelado')
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
        WHERE pd.responsavel_id = %s AND lower(COALESCE(pd.status, '')) NOT IN ('resolvida', 'cancelada')
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
        if request.form.get("action") == "delete_client":
            if not can_admin():
                flash("Somente administrador pode excluir clientes.", "danger")
                return redirect(url_for("clients"))
            cliente_id = request.form.get("cliente_id")
            cliente = query_db("SELECT nome, nome_exibicao FROM clientes WHERE id = %s", (cliente_id,), one=True)
            if not cliente:
                flash("Cliente nao encontrado.", "danger")
                return redirect(url_for("clients"))
            db = get_db()
            if delete_client_records(db, cliente_id):
                db.commit()
                flash(f"Cliente {cliente['nome_exibicao'] or cliente['nome']} excluido.", "success")
            else:
                db.rollback()
                flash("Nao foi possivel excluir: este cliente possui projeto vinculado.", "warning")
            return redirect(url_for("clients"))
        cliente_id = save_cliente_documental()
        if cliente_id:
            return redirect(url_for("clients"))
        return redirect(url_for("clients"))

    filters = request.args.to_dict()
    where = []
    params = []
    if filters.get("tipo_cliente"):
        where.append("c.tipo_cliente = %s")
        params.append(filters["tipo_cliente"])
    if filters.get("status_cadastro"):
        where.append("c.status_cadastro = %s")
        params.append(filters["status_cadastro"])
    if filters.get("cidade"):
        where.append("(ep.cidade LIKE %s OR pj.cidade LIKE %s)")
        params.extend([f"%{filters['cidade']}%", f"%{filters['cidade']}%"])
    if filters.get("com_procurador") == "1":
        where.append("pr.id IS NOT NULL")
    where_clause = "WHERE " + " AND ".join(where) if where else ""
    rows = query_db(
        f"""
        SELECT
            c.*,
            pf.cpf AS pf_cpf,
            pf.nome_completo AS pf_nome_completo,
            pf.email AS pf_email_doc,
            pf.telefone AS pf_telefone_doc,
            pj.cnpj AS pj_cnpj,
            pj.razao_social AS pj_razao_social,
            pj.nome_fantasia AS pj_nome_fantasia,
            pj.email AS pj_email_doc,
            pj.telefone AS pj_telefone_doc,
            COALESCE(ep.uf, pj.uf) AS uf_cadastro,
            COALESCE(ep.cidade, pj.cidade) AS cidade_cadastro,
            pr.nome_completo AS procurador_nome_doc,
            pr.cpf AS procurador_cpf_doc,
            (SELECT COUNT(*) FROM projetos p WHERE p.cliente_id = c.id) AS projetos
        FROM clientes c
        LEFT JOIN pessoas_fisicas pf ON pf.cliente_id = c.id
        LEFT JOIN pessoas_juridicas pj ON pj.cliente_id = c.id
        LEFT JOIN enderecos_proprietario ep ON ep.pessoa_fisica_id = pf.id
        LEFT JOIN LATERAL (
            SELECT *
            FROM procuradores
            WHERE cliente_id = c.id
            ORDER BY principal DESC, id
            LIMIT 1
        ) pr ON TRUE
        {where_clause}
        ORDER BY lower(COALESCE(NULLIF(c.nome_exibicao, ''), c.nome, '')), lower(COALESCE(c.nome, ''))
        """,
        params,
    )
    client_contexts = load_clientes_documental_batch(rows)
    client_meta = {
        client_id: context["cliente_pendencias"]
        for client_id, context in client_contexts.items()
    }
    return render_template(
        "clients.html",
        clients=rows,
        filters=filters,
        active=empty_cliente_context(),
        client_contexts=client_contexts,
        client_meta=client_meta,
        tipos_cliente=TIPOS_CLIENTE,
        quem_assina_options=QUEM_ASSINA,
        sexos=SEXOS,
        estados_civis=ESTADOS_CIVIS,
        regimes_casamento=REGIMES_CASAMENTO,
        status_cadastro_options=STATUS_CADASTRO,
        ufs=UFS,
        representative_types=REPRESENTATIVE_TYPES,
    )


@app.route("/cartorios", methods=["GET", "POST"])
@login_required
def cartorios():
    if request.method == "POST":
        if not can_manage():
            flash("Permissao negada.", "danger")
            return redirect(url_for("cartorios"))
        action = request.form.get("action", "create")
        cartorio_id = request.form.get("cartorio_id")
        name = request.form.get("nome", "").strip()
        values = (
            name,
            request.form.get("cns", "").strip(),
            request.form.get("cidade", "").strip(),
            request.form.get("uf", "").strip().upper(),
            request.form.get("contato", "").strip(),
            request.form.get("email", "").strip(),
            request.form.get("telefone", "").strip(),
            request.form.get("whatsapp", "").strip(),
            request.form.get("oficial", "").strip(),
            request.form.get("observacoes", "").strip(),
        )
        if not name:
            flash("Informe o nome do cartorio/orgao.", "danger")
            return redirect(url_for("cartorios"))
        if action == "update" and cartorio_id:
            execute_db(
                """
                UPDATE cartorios
                SET nome = %s, cns = %s, cidade = %s, uf = %s, contato = %s,
                    email = %s, telefone = %s, whatsapp = %s, oficial = %s, observacoes = %s
                WHERE id = %s
                """,
                values + (cartorio_id,),
            )
            flash("Cartorio/orgao atualizado.", "success")
        else:
            execute_db(
                """
                INSERT INTO cartorios
                    (nome, cns, cidade, uf, contato, email, telefone, whatsapp, oficial, observacoes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                values,
            )
            flash("Cartorio/orgao cadastrado.", "success")
        invalidate_runtime_caches()
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
    cartorio_catalog = [
        {
            "id": row["id"],
            "nome": row["nome"] or "",
            "cns": row["cns"] or "",
            "cidade": row["cidade"] or "",
            "uf": (row["uf"] or "").upper(),
            "contato": row["contato"] or "",
            "email": row["email"] or "",
            "telefone": row["telefone"] or "",
            "whatsapp": row["whatsapp"] or "",
            "oficial": row["oficial"] or "",
            "observacoes": row["observacoes"] or "",
        }
        for row in rows
        if row["nome"] or row["cns"] or row["cidade"] or row["uf"]
    ]
    return render_template("cartorios.html", cartorios=rows, cartorio_catalog=cartorio_catalog)


@app.route("/cartorios/checklist", methods=["GET", "POST"])
@login_required
def cartorios_checklist():
    """Gestao da documentacao obrigatoria (etapa Escritorio) por tipo de processo e cartorio."""
    if not can_manage():
        flash("Permissao negada.", "danger")
        return redirect(url_for("cartorios"))

    process_types = query_db(
        "SELECT chave, nome FROM tipos_processo WHERE ativo = 1 ORDER BY ordem, nome"
    )
    cartorio_options = query_db("SELECT id, nome FROM cartorios ORDER BY nome")

    raw_cartorio = (request.values.get("cartorio_id") or "").strip()
    selected_cartorio_id = int(raw_cartorio) if raw_cartorio.isdigit() else None
    valid_process_keys = {process_type["chave"] for process_type in process_types}
    selected_process = (request.values.get("process_type") or "").strip()
    if selected_process not in valid_process_keys:
        selected_process = process_types[0]["chave"] if process_types else ""

    def manager_redirect():
        args = {"process_type": selected_process}
        if selected_cartorio_id:
            args["cartorio_id"] = selected_cartorio_id
        return redirect(url_for("cartorios_checklist", **args))

    def scope_items(db, process_key, cartorio_id):
        return db.execute(
            """
            SELECT * FROM cartorio_checklist_templates
            WHERE process_type_key = %s AND cartorio_id IS NOT DISTINCT FROM %s AND active = 1
            ORDER BY order_index, id
            """,
            (process_key, cartorio_id),
        ).fetchall()

    if request.method == "POST":
        action = request.form.get("action", "")
        db = get_db()
        now = app_now_iso()

        if action == "add":
            titulo = (request.form.get("titulo") or "").strip()
            modelo_referencia = (request.form.get("modelo_referencia") or "").strip()
            observacoes = (request.form.get("observacoes") or "").strip()
            if not titulo:
                flash("Informe o nome do documento.", "danger")
                return manager_redirect()
            duplicate = first_row(
                db,
                """
                SELECT id FROM cartorio_checklist_templates
                WHERE process_type_key = %s AND cartorio_id IS NOT DISTINCT FROM %s
                  AND lower(title) = lower(%s) AND active = 1
                  AND lower(COALESCE(modelo_referencia, '')) = lower(%s)
                """,
                (selected_process, selected_cartorio_id, titulo, modelo_referencia),
            )
            if duplicate:
                flash("Ja existe um documento com esse nome e modelo nesta lista.", "warning")
                return manager_redirect()
            next_order = scalar(
                db,
                """
                SELECT COALESCE(MAX(order_index), 0) + 1 FROM cartorio_checklist_templates
                WHERE process_type_key = %s AND cartorio_id IS NOT DISTINCT FROM %s AND active = 1
                """,
                (selected_process, selected_cartorio_id),
            )
            db.execute(
                """
                INSERT INTO cartorio_checklist_templates
                    (cartorio_id, process_type_key, title, modelo_referencia, observacoes, order_index, active, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, 1, %s, %s)
                """,
                (selected_cartorio_id, selected_process, titulo, modelo_referencia, observacoes, next_order, now, now),
            )
            synced = sync_cartorio_checklist_to_projects(db, selected_process, selected_cartorio_id)
            db.commit()
            flash(f"Documento adicionado. Checklist atualizado em {synced} projeto(s) em andamento.", "success")
            return manager_redirect()

        if action == "remove":
            raw_item_id = (request.form.get("item_id") or "").strip()
            item = first_row(
                db,
                "SELECT * FROM cartorio_checklist_templates WHERE id = %s AND active = 1",
                (raw_item_id,),
            ) if raw_item_id.isdigit() else None
            if not item:
                flash("Documento nao encontrado.", "danger")
                return manager_redirect()
            item_cartorio_id = item["cartorio_id"] if "cartorio_id" in item.keys() else None
            if selected_cartorio_id and item_cartorio_id is None:
                db.execute(
                    """
                    INSERT INTO cartorio_checklist_exclusions
                        (cartorio_id, process_type_key, template_id, created_at)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (cartorio_id, process_type_key, template_id) DO NOTHING
                    """,
                    (selected_cartorio_id, selected_process, item["id"], now),
                )
                synced = sync_cartorio_checklist_to_projects(db, selected_process, selected_cartorio_id)
                db.commit()
                flash(f"Documento removido apenas deste cartorio. Checklist atualizado em {synced} projeto(s) em andamento.", "success")
                return manager_redirect()
            if (item_cartorio_id or None) != (selected_cartorio_id or None):
                flash("Documento nao pertence a lista selecionada.", "danger")
                return manager_redirect()
            db.execute(
                "UPDATE cartorio_checklist_templates SET active = 0, updated_at = %s WHERE id = %s",
                (now, item["id"]),
            )
            db.commit()
            flash("Documento removido da lista (projetos existentes nao sao alterados).", "success")
            return manager_redirect()

        if action in ("move_up", "move_down"):
            items = scope_items(db, selected_process, selected_cartorio_id)
            index = next(
                (i for i, item in enumerate(items) if str(item["id"]) == request.form.get("item_id")),
                None,
            )
            if index is None:
                return manager_redirect()
            neighbor = index - 1 if action == "move_up" else index + 1
            if not (0 <= neighbor < len(items)):
                return manager_redirect()
            # Reatribui a ordem inteira: corrige empates herdados de order_index repetido.
            order = [item["id"] for item in items]
            order[index], order[neighbor] = order[neighbor], order[index]
            for position, item_id in enumerate(order, 1):
                db.execute(
                    "UPDATE cartorio_checklist_templates SET order_index = %s, updated_at = %s WHERE id = %s",
                    (position, now, item_id),
                )
            db.commit()
            return manager_redirect()

        if action == "copy":
            source_raw = (request.form.get("source") or "").strip()
            copy_all_types = request.form.get("copy_all_types") == "1"
            source_cartorio_id = int(source_raw) if source_raw.isdigit() else None
            if source_raw != "system" and (source_cartorio_id or None) == (selected_cartorio_id or None):
                flash("Origem e destino sao a mesma lista.", "warning")
                return manager_redirect()
            process_keys = (
                [process_type["chave"] for process_type in process_types]
                if copy_all_types
                else [selected_process]
            )
            copied = 0
            affected_keys = []
            for process_key in process_keys:
                if source_raw == "system":
                    source_documents = [
                        {
                            "title": template["title"],
                            "modelo_referencia": "",
                            "observacoes": template["description"] or template["help_text"] or "",
                        }
                        for template in get_checklist_template_for_process_stage(process_key, "ESCRITORIO")
                    ]
                else:
                    source_documents = [
                        {
                            "title": row["title"],
                            "modelo_referencia": row["modelo_referencia"] or "",
                            "observacoes": row["observacoes"] or "",
                        }
                        for row in scope_items(db, process_key, source_cartorio_id)
                    ]
                if not source_documents:
                    continue
                existing = {
                    ((row["title"] or "").lower(), (row["modelo_referencia"] or "").lower())
                    for row in scope_items(db, process_key, selected_cartorio_id)
                }
                next_order = scalar(
                    db,
                    """
                    SELECT COALESCE(MAX(order_index), 0) FROM cartorio_checklist_templates
                    WHERE process_type_key = %s AND cartorio_id IS NOT DISTINCT FROM %s AND active = 1
                    """,
                    (process_key, selected_cartorio_id),
                )
                added_here = 0
                for document in source_documents:
                    key = ((document["title"] or "").lower(), (document["modelo_referencia"] or "").lower())
                    if key in existing:
                        continue
                    next_order += 1
                    db.execute(
                        """
                        INSERT INTO cartorio_checklist_templates
                            (cartorio_id, process_type_key, title, modelo_referencia, observacoes, order_index, active, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, 1, %s, %s)
                        """,
                        (
                            selected_cartorio_id,
                            process_key,
                            document["title"],
                            document["modelo_referencia"],
                            document["observacoes"],
                            next_order,
                            now,
                            now,
                        ),
                    )
                    existing.add(key)
                    added_here += 1
                if added_here:
                    copied += added_here
                    affected_keys.append(process_key)
            synced = 0
            for process_key in affected_keys:
                synced += sync_cartorio_checklist_to_projects(db, process_key, selected_cartorio_id)
            db.commit()
            if copied:
                flash(f"{copied} documento(s) copiado(s). Checklist atualizado em {synced} projeto(s) em andamento.", "success")
            else:
                flash("Nada para copiar: a origem esta vazia ou os documentos ja existem no destino.", "warning")
            return manager_redirect()

        flash("Acao invalida.", "danger")
        return manager_redirect()

    db = get_db()
    items = get_cartorio_checklist_rows(db, selected_process, selected_cartorio_id)
    inherited_source = (
        "Padrao geral"
        if selected_cartorio_id and any(item["cartorio_id"] is None for item in items)
        else None
    )

    return render_template(
        "cartorios_checklist.html",
        process_types=process_types,
        cartorio_options=cartorio_options,
        selected_cartorio_id=selected_cartorio_id,
        selected_process=selected_process,
        items=items,
        inherited_source=inherited_source,
    )


@app.route("/users", methods=["GET", "POST"])
@login_required
def users():
    if not can_admin():
        flash("Somente administrador pode gerenciar usuarios.", "danger")
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        action = request.form.get("action", "create")
        user_id = request.form.get("user_id")
        name = request.form.get("nome", "").strip()
        email = request.form.get("email", "").strip().lower()
        role = request.form.get("perfil_acesso", "tecnico")
        cargo = request.form.get("cargo", "").strip()
        password = request.form.get("senha", "").strip()

        if role not in ROLE_LABELS:
            role = "tecnico"

        if action == "create":
            flash("Novos usuarios devem solicitar cadastro pela tela de login para passar pela aprovacao.", "warning")
        elif action in ("approve", "update") and user_id:
            target = query_db("SELECT * FROM usuarios WHERE id = %s", (user_id,), one=True)
            if not target:
                flash("Usuario nao encontrado.", "danger")
            elif not name or not email:
                flash("Nome e e-mail sao obrigatorios.", "danger")
            else:
                existing = query_db("SELECT id FROM usuarios WHERE lower(email) = %s AND id != %s", (email, user_id), one=True)
                if existing:
                    flash("Ja existe outro usuario com este e-mail.", "danger")
                else:
                    active_value = 1 if action == "approve" else int(request.form.get("ativo", target["ativo"]) or 0)
                    if int(user_id) == g.user["id"]:
                        active_value = 1
                    execute_db(
                        "UPDATE usuarios SET nome = %s, email = %s, perfil_acesso = %s, cargo = %s, ativo = %s WHERE id = %s",
                        (name, email, role, cargo, active_value, user_id),
                    )
                    if password and int(user_id) == g.user["id"]:
                        execute_db("UPDATE usuarios SET senha_hash = %s WHERE id = %s", (generate_password_hash(password), user_id))
                    elif password:
                        flash("Por seguranca, voce so pode alterar a sua propria senha.", "warning")
                    flash("Usuario aprovado." if action == "approve" else "Usuario atualizado.", "success")
        elif action == "delete" and user_id:
            if int(user_id) == g.user["id"]:
                flash("Voce nao pode excluir o proprio usuario.", "danger")
            else:
                target = query_db("SELECT id, ativo FROM usuarios WHERE id = %s", (user_id,), one=True)
                if not target:
                    flash("Usuario nao encontrado.", "danger")
                elif target["ativo"]:
                    execute_db("UPDATE usuarios SET ativo = 0, cargo = COALESCE(NULLIF(cargo, ''), 'Excluido') WHERE id = %s", (user_id,))
                    flash("Usuario removido do acesso ativo.", "success")
                else:
                    try:
                        execute_db("DELETE FROM usuarios WHERE id = %s", (user_id,))
                        flash("Usuario excluido.", "success")
                    except psycopg2.errors.ForeignKeyViolation:
                        execute_db("UPDATE usuarios SET ativo = 0, cargo = COALESCE(NULLIF(cargo, ''), 'Excluido') WHERE id = %s", (user_id,))
                        flash("Usuario possui historico vinculado e foi mantido inativo.", "warning")
        return redirect(url_for("users"))
    rows = query_db("SELECT * FROM usuarios ORDER BY ativo DESC, lower(nome)")
    pending_users = [row for row in rows if not row["ativo"] and row["perfil_acesso"] == "consulta" and not (row["cargo"] or "").strip()]
    active_users = [row for row in rows if row["ativo"]]
    return render_template("users.html", users=rows, pending_users=pending_users, active_users=active_users)


_financeiro_schema_ready = False


def ensure_financeiro_schema():
    """Cria as tabelas financeiras se ainda nao existirem (uma verificacao por processo)."""
    global _financeiro_schema_ready
    if _financeiro_schema_ready:
        return
    db = get_db()
    # Sem FOREIGN KEY: o papel do banco nao tem privilegio REFERENCES nas tabelas
    # existentes; a exclusao em cascata e manual (delete_project_records).
    db.execute_statements(
        """
        CREATE TABLE IF NOT EXISTS projeto_pagamentos (
            id SERIAL PRIMARY KEY,
            projeto_id INTEGER NOT NULL,
            valor DOUBLE PRECISION NOT NULL,
            forma_pagamento TEXT,
            data_pagamento TEXT,
            observacoes TEXT,
            criado_em TEXT NOT NULL,
            usuario_id INTEGER
        );

        CREATE INDEX IF NOT EXISTS idx_projeto_pagamentos_projeto
            ON projeto_pagamentos (projeto_id, data_pagamento DESC, id DESC)
        ;

        CREATE TABLE IF NOT EXISTS projeto_custos (
            id SERIAL PRIMARY KEY,
            projeto_id INTEGER NOT NULL,
            descricao TEXT NOT NULL,
            categoria TEXT,
            valor DOUBLE PRECISION NOT NULL,
            data_custo TEXT,
            observacoes TEXT,
            status TEXT NOT NULL DEFAULT 'a_cobrar',
            criado_em TEXT NOT NULL,
            usuario_id INTEGER,
            registro_uid TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_projeto_custos_projeto
            ON projeto_custos (projeto_id, data_custo DESC, id DESC)
        """
    )
    # registro_uid: identificador unico de cada envio do formulario. Permite
    # aceitar pagamentos identicos de proposito e ignorar reenvios do mesmo
    # formulario (clique duplo, F5 reenviando o POST).
    add_column_if_missing(db, "projeto_pagamentos", "registro_uid", "TEXT")
    db.execute_statements(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_projeto_pagamentos_registro_uid ON projeto_pagamentos (registro_uid)"
    )
    add_column_if_missing(db, "projeto_custos", "descricao", "TEXT")
    add_column_if_missing(db, "projeto_custos", "categoria", "TEXT")
    add_column_if_missing(db, "projeto_custos", "valor", "DOUBLE PRECISION DEFAULT 0")
    add_column_if_missing(db, "projeto_custos", "data_custo", "TEXT")
    add_column_if_missing(db, "projeto_custos", "observacoes", "TEXT")
    add_column_if_missing(db, "projeto_custos", "registro_uid", "TEXT")
    add_column_if_missing(db, "projeto_custos", "status", "TEXT DEFAULT 'a_cobrar'")
    add_column_if_missing(db, "projeto_custos", "criado_em", "TEXT")
    add_column_if_missing(db, "projeto_custos", "usuario_id", "INTEGER")
    db.execute_statements(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_projeto_custos_registro_uid ON projeto_custos (registro_uid)"
    )
    db.commit()
    _financeiro_schema_ready = True


def require_admin_or_redirect():
    if can_admin():
        return None
    flash("Somente administrador pode acessar o financeiro.", "danger")
    return redirect(url_for("dashboard"))


def parse_payment_date(raw):
    raw = (raw or "").strip()
    if raw:
        try:
            return datetime.fromisoformat(raw).date().isoformat()
        except ValueError:
            pass
    return app_today().isoformat()


@app.route("/financeiro")
@login_required
def financeiro():
    denied = require_admin_or_redirect()
    if denied:
        return denied
    ensure_financeiro_schema()

    rows = query_db(
        """
        SELECT
            p.id, p.codigo, p.nome, p.status, p.valor, p.caminho_pasta,
            COALESCE(NULLIF(c.nome_exibicao, ''), NULLIF(c.nome, ''), p.proprietario) AS cliente_nome,
            em.nome AS etapa_nome, pe.status AS etapa_status,
            prog.total_etapas, prog.etapas_concluidas,
            pag.total_pago, pag.qtd_pagamentos, pag.ultimo_pagamento,
            cust.total_custos, cust.qtd_custos, cust.ultimo_custo
        FROM projetos p
        LEFT JOIN clientes c ON c.id = p.cliente_id
        LEFT JOIN projeto_etapas pe ON pe.id = p.etapa_atual_id
        LEFT JOIN etapas_modelo em ON em.id = pe.etapa_modelo_id
        LEFT JOIN LATERAL (
            SELECT
                COUNT(*) FILTER (
                    WHERE lower(COALESCE(pe2.status, '')) NOT IN ('nao aplicavel', 'cancelado')
                ) AS total_etapas,
                COUNT(*) FILTER (
                    WHERE lower(COALESCE(pe2.status, '')) = 'concluido'
                ) AS etapas_concluidas
            FROM projeto_etapas pe2
            WHERE pe2.projeto_id = p.id
              AND COALESCE(pe2.workflow_active, 1) = 1
              AND COALESCE(pe2.show_in_project, 1) = 1
        ) prog ON TRUE
        LEFT JOIN LATERAL (
            SELECT COALESCE(SUM(pg.valor), 0) AS total_pago,
                   COUNT(*) AS qtd_pagamentos,
                   MAX(pg.data_pagamento) AS ultimo_pagamento
            FROM projeto_pagamentos pg
            WHERE pg.projeto_id = p.id
        ) pag ON TRUE
        LEFT JOIN LATERAL (
            SELECT
                COALESCE(SUM(pc.valor) FILTER (
                    WHERE lower(COALESCE(pc.status, '')) != 'cancelado'
                ), 0) AS total_custos,
                COUNT(*) FILTER (
                    WHERE lower(COALESCE(pc.status, '')) != 'cancelado'
                ) AS qtd_custos,
                MAX(pc.data_custo) FILTER (
                    WHERE lower(COALESCE(pc.status, '')) != 'cancelado'
                ) AS ultimo_custo
            FROM projeto_custos pc
            WHERE pc.projeto_id = p.id
        ) cust ON TRUE
        WHERE lower(COALESCE(p.status, '')) != 'cancelado'
          AND (
              lower(COALESCE(p.status, '')) != 'concluido'
              OR COALESCE(p.valor, 0) + cust.total_custos - pag.total_pago > 0.005
          )
        ORDER BY lower(p.nome)
        """
    )

    em_aberto = []
    concluidos_pendentes = []
    quase_prontos = []
    sem_valor_count = 0
    total_carteira = 0.0
    a_receber_ativos = 0.0
    a_receber_concluidos = 0.0
    quase_prontos_saldo = 0.0
    custos_a_cobrar = 0.0

    for row in rows:
        item = dict(row)
        valor = float(item["valor"] or 0.0)
        pago = float(item["total_pago"] or 0.0)
        custos = float(item["total_custos"] or 0.0)
        saldo = round(valor + custos - pago, 2)
        total = item["total_etapas"] or 0
        done = item["etapas_concluidas"] or 0
        item["pct"] = int(done / total * 100) if total else 0
        item["qtd_pagamentos"] = int(item["qtd_pagamentos"] or 0)
        item["qtd_custos"] = int(item["qtd_custos"] or 0)
        item["total_pago"] = pago
        item["total_custos"] = custos
        item["total_cobravel"] = valor + custos
        item["saldo"] = saldo
        item["tem_valor"] = valor > 0.005
        item["tem_cobranca"] = item["total_cobravel"] > 0.005
        if (item["status"] or "").lower() == "concluido":
            concluidos_pendentes.append(item)
            a_receber_concluidos += max(saldo, 0.0)
            custos_a_cobrar += custos
            continue
        em_aberto.append(item)
        if item["tem_valor"]:
            total_carteira += valor
        else:
            sem_valor_count += 1
        custos_a_cobrar += custos
        if item["tem_cobranca"]:
            a_receber_ativos += max(saldo, 0.0)
        if item["tem_cobranca"] and item["pct"] >= FINANCEIRO_QUASE_PRONTO_PCT and saldo > 0.005:
            quase_prontos.append(item)
            quase_prontos_saldo += saldo
    quase_prontos.sort(key=lambda item: (-item["pct"], -item["saldo"]))

    recebido = query_db(
        """
        SELECT
            COALESCE(SUM(valor), 0) AS total,
            COALESCE(SUM(valor) FILTER (WHERE data_pagamento >= %s), 0) AS ultimos_30d
        FROM projeto_pagamentos
        """,
        ((app_today() - timedelta(days=30)).isoformat(),),
        one=True,
    )

    payments_by_project = {}
    costs_by_project = {}
    history_project_ids = [
        item["id"]
        for item in em_aberto + concluidos_pendentes
        if item["qtd_pagamentos"] or item["qtd_custos"]
    ]
    payment_project_ids = [item["id"] for item in em_aberto + concluidos_pendentes if item["qtd_pagamentos"]]
    if payment_project_ids:
        placeholders = ",".join("%s" for _ in payment_project_ids)
        for payment in query_db(
            f"""
            SELECT pg.*, u.nome AS usuario_nome
            FROM projeto_pagamentos pg
            LEFT JOIN usuarios u ON u.id = pg.usuario_id
            WHERE pg.projeto_id IN ({placeholders})
            ORDER BY COALESCE(pg.data_pagamento, '') DESC, pg.id DESC
            """,
            payment_project_ids,
        ):
            payments_by_project.setdefault(payment["projeto_id"], []).append(payment)
    cost_project_ids = [item["id"] for item in em_aberto + concluidos_pendentes if item["qtd_custos"]]
    if cost_project_ids:
        placeholders = ",".join("%s" for _ in cost_project_ids)
        for cost in query_db(
            f"""
            SELECT pc.*, u.nome AS usuario_nome
            FROM projeto_custos pc
            LEFT JOIN usuarios u ON u.id = pc.usuario_id
            WHERE pc.projeto_id IN ({placeholders})
              AND lower(COALESCE(pc.status, '')) != 'cancelado'
            ORDER BY COALESCE(pc.data_custo, '') DESC, pc.id DESC
            """,
            cost_project_ids,
        ):
            costs_by_project.setdefault(cost["projeto_id"], []).append(cost)

    return render_template(
        "financeiro.html",
        em_aberto=em_aberto,
        concluidos_pendentes=concluidos_pendentes,
        quase_prontos=quase_prontos,
        payments_by_project=payments_by_project,
        costs_by_project=costs_by_project,
        formas_pagamento=FORMAS_PAGAMENTO,
        categorias_custo=CATEGORIAS_CUSTO,
        history_project_ids=history_project_ids,
        quase_pronto_pct=FINANCEIRO_QUASE_PRONTO_PCT,
        resumo={
            "total_a_receber": a_receber_ativos + a_receber_concluidos,
            "a_receber_ativos": a_receber_ativos,
            "a_receber_concluidos": a_receber_concluidos,
            "total_carteira": total_carteira,
            "custos_a_cobrar": custos_a_cobrar,
            "recebido_total": float(recebido["total"] or 0.0),
            "recebido_30d": float(recebido["ultimos_30d"] or 0.0),
            "quase_prontos_count": len(quase_prontos),
            "quase_prontos_saldo": quase_prontos_saldo,
            "sem_valor_count": sem_valor_count,
        },
    )


@app.route("/financeiro/pagamento", methods=["POST"])
@login_required
def financeiro_registrar_pagamento():
    denied = require_admin_or_redirect()
    if denied:
        return denied
    ensure_financeiro_schema()
    projeto_id = request.form.get("projeto_id")
    projeto = query_db("SELECT id, nome, valor FROM projetos WHERE id = %s", (projeto_id,), one=True)
    if not projeto:
        flash("Projeto nao encontrado.", "danger")
        return redirect(url_for("financeiro"))
    valor = parse_currency_value(request.form.get("valor", "").strip())
    if not valor or valor <= 0:
        flash("Informe um valor de pagamento maior que zero.", "danger")
        return redirect(url_for("financeiro"))
    forma = request.form.get("forma_pagamento", "")
    if forma not in FORMAS_PAGAMENTO:
        forma = "OUTRO"
    data_pagamento = parse_payment_date(request.form.get("data_pagamento"))
    # Identificador unico do envio: cada abertura do modal gera um novo, entao
    # pagamentos iguais de proposito entram; so o reenvio do MESMO formulario
    # (clique duplo, F5 reenviando) e ignorado.
    registro_uid = (request.form.get("registro_uid") or "").strip()[:64] or secrets.token_hex(16)
    if query_db("SELECT id FROM projeto_pagamentos WHERE registro_uid = %s", (registro_uid,), one=True):
        flash("Este pagamento ja havia sido salvo — o envio repetido foi ignorado.", "info")
        return redirect(url_for("financeiro"))
    try:
        execute_db(
            """
            INSERT INTO projeto_pagamentos
                (projeto_id, valor, forma_pagamento, data_pagamento, observacoes, criado_em, usuario_id, registro_uid)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                projeto["id"],
                valor,
                forma,
                data_pagamento,
                request.form.get("observacoes", "").strip(),
                app_now_iso(),
                g.user["id"],
                registro_uid,
            ),
        )
    except psycopg2.errors.UniqueViolation:
        flash("Este pagamento ja havia sido salvo — o envio repetido foi ignorado.", "info")
        return redirect(url_for("financeiro"))
    total_pago = scalar(
        get_db(), "SELECT COALESCE(SUM(valor), 0) FROM projeto_pagamentos WHERE projeto_id = %s", (projeto["id"],)
    )
    total_custos = scalar(
        get_db(),
        """
        SELECT COALESCE(SUM(valor), 0)
        FROM projeto_custos
        WHERE projeto_id = %s AND lower(COALESCE(status, '')) != 'cancelado'
        """,
        (projeto["id"],),
    )
    saldo = round(float(projeto["valor"] or 0.0) + float(total_custos or 0.0) - float(total_pago or 0.0), 2)
    if projeto["valor"] and saldo < -0.005:
        flash(
            f"Pagamento registrado. Atencao: o total pago supera o valor do projeto em {format_currency(abs(saldo))}.",
            "warning",
        )
    elif projeto["valor"]:
        flash(f"Pagamento de {format_currency(valor)} registrado. Saldo restante: {format_currency(max(saldo, 0))}.", "success")
    else:
        flash(f"Pagamento de {format_currency(valor)} registrado. Defina o valor do projeto para acompanhar o saldo.", "success")
    return redirect(url_for("financeiro"))


@app.route("/financeiro/custo", methods=["POST"])
@login_required
def financeiro_registrar_custo():
    denied = require_admin_or_redirect()
    if denied:
        return denied
    ensure_financeiro_schema()
    projeto_id = request.form.get("projeto_id")
    projeto = query_db("SELECT id, nome, caminho_pasta FROM projetos WHERE id = %s", (projeto_id,), one=True)
    if not projeto:
        flash("Projeto nao encontrado.", "danger")
        return redirect(url_for("financeiro"))

    descricao = (request.form.get("descricao") or "").strip()
    if not descricao:
        flash("Informe a descricao do custo.", "danger")
        return redirect(url_for("financeiro"))
    valor = parse_currency_value(request.form.get("valor", "").strip())
    if not valor or valor <= 0:
        flash("Informe um valor de custo maior que zero.", "danger")
        return redirect(url_for("financeiro"))
    categoria = request.form.get("categoria", "")
    if categoria not in CATEGORIAS_CUSTO:
        categoria = "OUTRO"
    data_custo = parse_payment_date(request.form.get("data_custo"))
    registro_uid = (request.form.get("registro_uid") or "").strip()[:64] or secrets.token_hex(16)
    if query_db("SELECT id FROM projeto_custos WHERE registro_uid = %s", (registro_uid,), one=True):
        flash("Este custo ja havia sido salvo; o envio repetido foi ignorado.", "info")
        return redirect(url_for("financeiro"))

    try:
        execute_db(
            """
            INSERT INTO projeto_custos
                (projeto_id, descricao, categoria, valor, data_custo, observacoes, status,
                 criado_em, usuario_id, registro_uid)
            VALUES (%s, %s, %s, %s, %s, %s, 'a_cobrar', %s, %s, %s)
            """,
            (
                projeto["id"],
                descricao,
                categoria,
                valor,
                data_custo,
                request.form.get("observacoes", "").strip(),
                app_now_iso(),
                g.user["id"],
                registro_uid,
            ),
        )
    except psycopg2.errors.UniqueViolation:
        flash("Este custo ja havia sido salvo; o envio repetido foi ignorado.", "info")
        return redirect(url_for("financeiro"))

    record_event(
        projeto["id"],
        "custo_financeiro",
        f"Custo registrado: {descricao} ({CATEGORIAS_CUSTO.get(categoria, 'Outro custo')}) - {format_currency(valor)}.",
    )
    flash(f"Custo de {format_currency(valor)} registrado para cobranca futura.", "success")
    return redirect(url_for("financeiro"))


@app.route("/financeiro/pagamento/<int:payment_id>/excluir", methods=["POST"])
@login_required
def financeiro_excluir_pagamento(payment_id):
    denied = require_admin_or_redirect()
    if denied:
        return denied
    ensure_financeiro_schema()
    payment = query_db("SELECT id, valor FROM projeto_pagamentos WHERE id = %s", (payment_id,), one=True)
    if not payment:
        flash("Pagamento nao encontrado.", "danger")
        return redirect(url_for("financeiro"))
    execute_db("DELETE FROM projeto_pagamentos WHERE id = %s", (payment_id,))
    flash(f"Pagamento de {format_currency(payment['valor'])} excluido.", "success")
    return redirect(url_for("financeiro"))


@app.route("/financeiro/custo/<int:cost_id>/cancelar", methods=["POST"])
@login_required
def financeiro_cancelar_custo(cost_id):
    denied = require_admin_or_redirect()
    if denied:
        return denied
    ensure_financeiro_schema()
    cost = query_db(
        """
        SELECT pc.id, pc.projeto_id, pc.valor, pc.descricao, pc.status
        FROM projeto_custos pc
        WHERE pc.id = %s
        """,
        (cost_id,),
        one=True,
    )
    if not cost or (cost["status"] or "").lower() == "cancelado":
        flash("Custo nao encontrado.", "danger")
        return redirect(url_for("financeiro"))
    execute_db("UPDATE projeto_custos SET status = 'cancelado' WHERE id = %s", (cost_id,))
    record_event(
        cost["projeto_id"],
        "custo_financeiro_cancelado",
        f"Custo cancelado: {cost['descricao']} - {format_currency(cost['valor'])}.",
    )
    flash(f"Custo de {format_currency(cost['valor'])} cancelado.", "success")
    return redirect(url_for("financeiro"))


@app.route("/financeiro/projeto/<int:project_id>/valor", methods=["POST"])
@login_required
def financeiro_definir_valor(project_id):
    denied = require_admin_or_redirect()
    if denied:
        return denied
    projeto = query_db("SELECT id FROM projetos WHERE id = %s", (project_id,), one=True)
    if not projeto:
        flash("Projeto nao encontrado.", "danger")
        return redirect(url_for("financeiro"))
    valor = parse_currency_value(request.form.get("valor", "").strip())
    if valor is None or valor < 0:
        flash("Informe um valor valido para o projeto.", "danger")
        return redirect(url_for("financeiro"))
    execute_db("UPDATE projetos SET valor = %s WHERE id = %s", (valor, project_id))
    flash(f"Valor do projeto atualizado para {format_currency(valor)}.", "success")
    return redirect(url_for("financeiro"))


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
            CASE COALESCE(e.tipo_orgao, 'CARTORIO') WHEN 'PREFEITURA' THEN 0 ELSE 1 END,
            COALESCE(e.prazo_resposta, e.data_protocolo, '9999-12-31'),
            e.id
        """
    )
    return render_template("cartorio_board.html", exigencias=exigencias, external_orgao_labels=EXTERNAL_ORGAO_LABELS)


@app.route("/reports")
@login_required
def reports():
    refresh_due_statuses()
    return render_template("reports.html", **get_reports_context_cached())


if __name__ == "__main__":
    if "--init-db" in sys.argv:
        init_db()
        print("Banco inicializado.")
        raise SystemExit(0)
    if os.environ.get("GEOGESTAO_AUTO_INIT_DB", "0") == "1":
        init_db()
    port = int(os.environ.get("PORT", "5000"))
    debug = os.environ.get("GEOGESTAO_DEBUG", "1") == "1"
    app.run(debug=debug, use_reloader=debug, host="127.0.0.1", port=port)
