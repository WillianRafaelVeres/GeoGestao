"""
report_helpers.py
Metricas de relatorio gerencial para o GeoGestao / TopoFlow.

Todas as funcoes recebem listas de dicts simples (nenhuma acessa o banco diretamente).
Importar em app.py e chamar a partir de build_reports_context().
"""

from datetime import datetime

# ---------------------------------------------------------------------------
# Constantes locais — espelhadas de process_stage_templates / process_checklist_templates
# ---------------------------------------------------------------------------

APPLICABILITY_NOT_APPLICABLE = "NAO_APLICAVEL"

CHECKLIST_DONE_STATUSES = {"CONCLUIDO", "NAO_APLICAVEL"}
REQUIREMENT_REQUIRED = "OBRIGATORIO"
CRITICALITY_CRITICAL = "CRITICA"

ACTIVE_PROJECT_EXCLUDE = {"concluido", "cancelado"}

MACRO_STAGE_ORDER = [
    ("ORCAMENTO",      "Orcamento"),
    ("DOCUMENTOS",     "Documentos"),
    ("ANALISE",        "Analise / Viabilidade"),
    ("PREPARACAO",     "Preparacao"),
    ("MEDICAO",        "Medicao / Campo"),
    ("PROCESSAMENTO",  "Processamento"),
    ("ESCRITORIO",     "Escritorio / Pecas tecnicas"),
    ("CONFERENCIA",    "Conferencia"),
    ("ASSINATURAS",    "Assinaturas / Anuencias"),
    ("ORGAO_EXTERNO",  "Orgao externo"),
    ("PENDENCIAS",     "Pendencias / Exigencias"),
    ("ENTREGA",        "Entrega / Encerramento"),
    ("FINALIZADO",     "Finalizado"),
]

STAGE_LABELS_LOCAL = {
    "ORCAMENTO":     "Orcamento",
    "DOCUMENTOS":    "Documentos",
    "ANALISE":       "Analise / Viabilidade",
    "PREPARACAO":    "Preparacao",
    "MEDICAO":       "Medicao / Campo",
    "PROCESSAMENTO": "Processamento",
    "ESCRITORIO":    "Escritorio / Pecas tecnicas",
    "CONFERENCIA":   "Conferencia",
    "ASSINATURAS":   "Assinaturas / Anuencias",
    "ORGAO_EXTERNO": "Orgao externo",
    "PENDENCIAS":    "Pendencias / Exigencias",
    "ENTREGA":       "Entrega / Encerramento",
    "FINALIZADO":    "Finalizado",
}

# Conjunto dos macro stage keys validos
_MACRO_KEYS = {k for k, _ in MACRO_STAGE_ORDER}

# Mapeamento de chaves legadas (lowercase/sem acento) para macro stage key
# Cobre projetos criados antes dos modelos de processo serem aplicados
LEGACY_KEY_TO_MACRO = {
    "orcamento":      "ORCAMENTO",
    "documentos":     "DOCUMENTOS",
    "analise":        "ANALISE",
    "preparacao":     "PREPARACAO",
    "medicao":        "MEDICAO",
    "campo":          "MEDICAO",
    "processamento":  "PROCESSAMENTO",
    "escritorio":     "ESCRITORIO",
    "documentacao":   "ESCRITORIO",
    "planta":         "ESCRITORIO",
    "conferencia":    "CONFERENCIA",
    "assinaturas":    "ASSINATURAS",
    "cartorio":       "ORGAO_EXTERNO",
    "orgaoexterno":   "ORGAO_EXTERNO",
    "orgao":          "ORGAO_EXTERNO",
    "pendencia":      "PENDENCIAS",
    "pendencias":     "PENDENCIAS",
    "entrega":        "ENTREGA",
    "finalizado":     "FINALIZADO",
    "finalizacao":    "FINALIZADO",
    "arquivado":      "FINALIZADO",
}


def _to_macro_key(raw):
    """Normaliza qualquer stage key (legacy ou novo) para a chave macro canonica."""
    if not raw:
        return ""
    upper = str(raw).upper()
    if upper in _MACRO_KEYS:
        return upper
    # Tenta como chave legada (normaliza: so alfanumerico, minusculo)
    normalized = "".join(c for c in str(raw).lower() if c.isalnum())
    return LEGACY_KEY_TO_MACRO.get(normalized, upper)


def _stage_name_to_macro_key(name):
    """Converte nome de etapa de exibicao para chave macro canonica."""
    normalized = "".join(c for c in (name or "").lower() if c.isalnum())
    return LEGACY_KEY_TO_MACRO.get(normalized, "")


EXTERNAL_ACTOR_LABELS = {
    "CARTORIO":       "Cartorio",
    "SIGEF_INCRA":    "SIGEF/INCRA",
    "SICAR":          "SICAR/Orgao ambiental",
    "SNCR_INCRA":     "SNCR/INCRA",
    "PREFEITURA":     "Prefeitura",
    "ADVOGADO_FORUM": "Advogado/Forum",
    "MISTO":          "Misto",
    "NENHUM":         "Nenhum",
}

# Limiares operacionais — ajustar aqui se necessario
THRESHOLDS = {
    "attention_days":            5,
    "bottleneck_days":           10,
    "attention_active_count":    5,
    "bottleneck_active_count":   10,
    "stopped_days":              7,
    "critical_stopped_days":     15,
    "responsible_attention":     5,
    "responsible_overload":      12,
    "ext_actor_attention_days":  10,
}


# ---------------------------------------------------------------------------
# Utilitarios internos
# ---------------------------------------------------------------------------

def _parse_dt(value):
    if not value:
        return None
    text = str(value).strip()
    try:
        if len(text) == 10:
            return datetime.fromisoformat(f"{text}T00:00:00")
        return datetime.fromisoformat(text[:19])
    except ValueError:
        return None


def _days_between(start, end=None):
    s = _parse_dt(start) if not isinstance(start, datetime) else start
    e = _parse_dt(end) if end and not isinstance(end, datetime) else end
    if not s:
        return 0.0
    e = e or datetime.now()
    return max((e - s).total_seconds(), 0.0) / 86400.0


def _is_active(project):
    return str(project.get("status") or "").lower() not in ACTIVE_PROJECT_EXCLUDE


def _checklist_pending(item):
    return str(item.get("status") or "").upper() not in CHECKLIST_DONE_STATUSES


def _project_open_days(project):
    entered = (
        project.get("current_entered_at")
        or project.get("stage_data_inicio")
        or project.get("atualizado_em")
        or project.get("criado_em")
    )
    return _days_between(entered)


def _is_stopped(project):
    return _project_open_days(project) >= THRESHOLDS["stopped_days"]


def _stage_status(avg_days, active_count, max_open_days, completed_count):
    if not completed_count and not active_count:
        return "Sem dados", "muted", 0
    # Aplica limiares mesmo sem historico completo (usa max_open_days como proxy)
    if (
        (avg_days or 0) >= THRESHOLDS["bottleneck_days"]
        or (max_open_days or 0) >= THRESHOLDS["bottleneck_days"]
        or active_count >= THRESHOLDS["bottleneck_active_count"]
    ):
        return "Gargalo", "red", 3
    if (
        (avg_days or 0) >= THRESHOLDS["attention_days"]
        or (max_open_days or 0) >= THRESHOLDS["attention_days"]
        or active_count >= THRESHOLDS["attention_active_count"]
    ):
        return "Atencao", "amber", 2
    if active_count > 0 and avg_days is None:
        return "Sem historico", "muted", 1
    return "Normal", "green", 1


def _responsible_status(active_count, avg_days, max_open_days):
    if (
        active_count >= THRESHOLDS["responsible_overload"]
        or (avg_days or 0) >= THRESHOLDS["bottleneck_days"]
    ):
        return "Sobrecarga", "red", 3
    if (
        active_count >= THRESHOLDS["responsible_attention"]
        or (max_open_days or 0) >= THRESHOLDS["attention_days"]
    ):
        return "Atencao", "amber", 2
    return "Normal", "green", 1


# ---------------------------------------------------------------------------
# calculate_checklist_metrics — uso geral
# ---------------------------------------------------------------------------

def calculate_checklist_metrics(checklist_items):
    """Retorna agregado de metricas para uma lista de itens de checklist."""
    total = len(checklist_items)
    completed = sum(1 for it in checklist_items if not _checklist_pending(it))
    pending_required = sum(
        1 for it in checklist_items
        if _checklist_pending(it)
        and str(it.get("requirement_level") or "").upper() == REQUIREMENT_REQUIRED
    )
    pending_critical = sum(
        1 for it in checklist_items
        if _checklist_pending(it)
        and str(it.get("criticality") or "").upper() == CRITICALITY_CRITICAL
    )
    blocks_stage = sum(
        1 for it in checklist_items
        if _checklist_pending(it) and it.get("blocks_stage_completion")
    )
    blocks_process = sum(
        1 for it in checklist_items
        if _checklist_pending(it) and it.get("blocks_process_completion")
    )
    percent = int(completed / total * 100) if total else 0
    return {
        "total": total,
        "completed": completed,
        "pending_required": pending_required,
        "pending_critical": pending_critical,
        "blocks_stage": blocks_stage,
        "blocks_process": blocks_process,
        "percent": percent,
    }


# ---------------------------------------------------------------------------
# calculate_stage_metrics_v2 — considera applicability
# ---------------------------------------------------------------------------

def calculate_stage_metrics_v2(projects, project_stages, histories, checklist_items):
    """
    Calcula metricas por etapa macro.

    Inclui projetos sem modelo (legados) via mapeamento de chave legada.
    NAO_APLICAVEL nunca conta como ativo ou atrasado.
    """
    # Index de etapas por projeto
    stages_by_project = {}
    for s in project_stages:
        stages_by_project.setdefault(int(s["projeto_id"]), []).append(s)

    # Index de historico — normaliza todas as chaves para macro key
    completed_hist_by_key = {}
    open_hist_by_proj_key = {}
    for h in histories:
        raw = h.get("stage_key") or ""
        macro = _to_macro_key(raw) or _stage_name_to_macro_key(h.get("stage_name") or "")
        if not macro:
            continue
        if h.get("exited_at"):
            completed_hist_by_key.setdefault(macro, []).append(h)
        else:
            open_hist_by_proj_key[(int(h["project_id"]), macro)] = h

    # current stage key por projeto — usa template key OU fallback pelo nome da etapa
    current_key_by_proj = {}
    for p in projects:
        raw = p.get("current_stage_template_key") or ""
        if raw:
            current_key_by_proj[int(p["id"])] = _to_macro_key(raw)
        else:
            # Legado: tenta pelo nome da etapa atual
            stage_name = p.get("current_stage_name") or ""
            current_key_by_proj[int(p["id"])] = _stage_name_to_macro_key(stage_name)

    metrics = []
    for order_idx, (stage_key, stage_name) in enumerate(MACRO_STAGE_ORDER, 1):
        # Projetos ativos nessa etapa (com modelo OU legados via fallback)
        # Exclui etapas NAO_APLICAVEL (projetos com modelo que marcariam isso)
        active_in_stage = []
        for p in projects:
            if not _is_active(p):
                continue
            pid = int(p["id"])
            if current_key_by_proj.get(pid) != stage_key:
                continue
            # Verifica se etapa e NAO_APLICAVEL para esse projeto
            is_not_applicable = any(
                str(s.get("stage_key") or "").upper() == stage_key
                and str(s.get("applicability") or "").upper() == APPLICABILITY_NOT_APPLICABLE
                for s in stages_by_project.get(pid, [])
            )
            if not is_not_applicable:
                active_in_stage.append(p)

        # Historicos concluidos
        completed_hists = completed_hist_by_key.get(stage_key, [])
        completed_proj_ids = {int(h["project_id"]) for h in completed_hists}

        # Tempo medio (somente projetos que concluiram)
        completed_days = [
            _days_between(h["entered_at"], h["exited_at"])
            for h in completed_hists
            if h.get("entered_at") and h.get("exited_at")
        ]
        avg_days = sum(completed_days) / len(completed_days) if completed_days else None

        # Maior tempo atual (projetos ativos nessa etapa)
        open_days = []
        for p in active_in_stage:
            pid = int(p["id"])
            open_h = open_hist_by_proj_key.get((pid, stage_key))
            if open_h and open_h.get("entered_at"):
                open_days.append(_days_between(open_h["entered_at"]))
            else:
                # Fallback: tempo desde inicio da etapa ou do projeto
                for s in stages_by_project.get(pid, []):
                    if _to_macro_key(str(s.get("stage_key") or "")) == stage_key:
                        d = _days_between(s.get("data_inicio"))
                        if d > 0:
                            open_days.append(d)
                            break
                else:
                    open_days.append(_project_open_days(p))
        max_open_days = max(open_days) if open_days else None

        status, tone, score = _stage_status(
            avg_days, len(active_in_stage), max_open_days, len(completed_proj_ids)
        )

        metrics.append({
            "stage_key": stage_key,
            "stage_name": stage_name,
            "order": order_idx,
            "active_count": len(active_in_stage),
            "completed_count": len(completed_proj_ids),
            "avg_days": avg_days,
            "max_open_days": max_open_days,
            "status": status,
            "tone": tone,
            "score": score,
            # Campos mantidos por compatibilidade mas nao exibidos como foco
            "applicable_count": 0,
            "not_applicable_count": 0,
            "without_model_count": 0,
            "not_started": 0,
            "pending_required_checklist": 0,
        })

    return metrics


# ---------------------------------------------------------------------------
# calculate_process_type_metrics
# ---------------------------------------------------------------------------

def calculate_process_type_metrics(projects, project_stages, histories, checklist_items, process_name_fn=None):
    """
    Agrupa metricas por tipo de processo.

    Cada tipo de processo tem fluxo proprio — o relatorio mostra gargalos
    dentro de cada tipo, sem comparar CAR com Retificacao como se fossem iguais.
    """
    stages_by_project = {}
    for s in project_stages:
        stages_by_project.setdefault(int(s["projeto_id"]), []).append(s)

    checklist_by_project = {}
    for it in checklist_items:
        checklist_by_project.setdefault(int(it["project_id"]), []).append(it)

    histories_by_project = {}
    for h in histories:
        histories_by_project.setdefault(int(h["project_id"]), []).append(h)

    # Agrupar projetos por tipo
    grouped = {}
    for p in projects:
        process_key = str(p.get("tipo_servico") or "OUTRO").upper()
        if process_key not in grouped:
            nome = process_name_fn(process_key) if process_name_fn else process_key
            grouped[process_key] = {
                "process_key": process_key,
                "process_name": nome,
                "active_count": 0,
                "finished_count": 0,
                "project_ids": [],
            }
        item = grouped[process_key]
        item["project_ids"].append(int(p["id"]))
        if _is_active(p):
            item["active_count"] += 1
        else:
            item["finished_count"] += 1

    rows = []
    for process_key, item in grouped.items():
        project_ids = set(item["project_ids"])

        # Tempo total do processo por projeto
        total_days_list = []
        stage_time_by_key = {}

        for pid in project_ids:
            ph = histories_by_project.get(pid, [])
            if not ph:
                continue
            starts = [_parse_dt(h["entered_at"]) for h in ph if h.get("entered_at")]
            ends = [_parse_dt(h["exited_at"]) for h in ph if h.get("exited_at")]
            if starts:
                total_days_list.append(
                    _days_between(min(starts), max(ends) if ends else datetime.now())
                )
            for h in ph:
                sk = str(h.get("stage_key") or "").upper()
                if sk and h.get("exited_at") and h.get("entered_at"):
                    d = _days_between(h["entered_at"], h["exited_at"])
                    stage_time_by_key.setdefault(sk, []).append(d)

        avg_total_days = sum(total_days_list) / len(total_days_list) if total_days_list else None

        # Etapa mais lenta dentro do tipo de processo
        slowest_stage_key = None
        slowest_avg = 0.0
        for sk, days_list in stage_time_by_key.items():
            avg = sum(days_list) / len(days_list) if days_list else 0.0
            if avg > slowest_avg:
                slowest_avg = avg
                slowest_stage_key = sk

        # Checklist obrigatorio pendente nos projetos ativos
        pending_required = sum(
            1 for pid in project_ids
            for it in checklist_by_project.get(pid, [])
            if _checklist_pending(it)
            and str(it.get("requirement_level") or "").upper() == REQUIREMENT_REQUIRED
        )

        # Projetos parados
        stopped_count = sum(
            1 for p in projects
            if int(p["id"]) in project_ids and _is_active(p) and _is_stopped(p)
        )

        # Status
        if stopped_count >= 3 or (avg_total_days and avg_total_days >= 30) or pending_required >= 5:
            status, tone = "Atencao", "amber"
        elif item["active_count"] == 0 and not avg_total_days:
            status, tone = "Sem dados", "muted"
        else:
            status, tone = "Normal", "green"

        slowest_name = (
            STAGE_LABELS_LOCAL.get(slowest_stage_key, slowest_stage_key.replace("_", " ").title())
            if slowest_stage_key else None
        )

        rows.append({
            "process_key": process_key,
            "process_name": item["process_name"],
            "active_count": item["active_count"],
            "finished_count": item["finished_count"],
            "avg_total_days": avg_total_days,
            "slowest_stage": slowest_name,
            "slowest_stage_days": round(slowest_avg, 1) if slowest_avg else None,
            "pending_required_checklist": pending_required,
            "stopped_count": stopped_count,
            "status": status,
            "tone": tone,
        })

    return sorted(rows, key=lambda r: (-r["active_count"], r["process_name"]))


# ---------------------------------------------------------------------------
# calculate_responsible_metrics_v2
# ---------------------------------------------------------------------------

def calculate_responsible_metrics_v2(projects, project_stages, histories, checklist_items):
    """
    Desempenho por responsavel — mostra carga e tempo sem julgar injustamente.
    """
    checklist_by_project = {}
    for it in checklist_items:
        checklist_by_project.setdefault(int(it["project_id"]), []).append(it)

    metrics = {}

    for p in projects:
        if not _is_active(p):
            continue
        resp_id = p.get("current_responsible_id") or p.get("responsavel_geral_id") or "none"
        name = p.get("current_responsible_name") or p.get("responsavel_geral_nome") or "Sem responsavel"
        item = metrics.setdefault(resp_id, {
            "responsible": name,
            "active_count": 0,
            "completed_proj_ids": set(),
            "completed_days": [],
            "open_days": [],
            "pending_required_cl": 0,
        })
        item["active_count"] += 1
        item["open_days"].append(_project_open_days(p))

        # Checklist obrigatorio pendente sob esse responsavel
        pid = int(p["id"])
        item["pending_required_cl"] += sum(
            1 for it in checklist_by_project.get(pid, [])
            if _checklist_pending(it)
            and str(it.get("requirement_level") or "").upper() == REQUIREMENT_REQUIRED
        )

    for h in histories:
        if not h.get("exited_at"):
            continue
        resp_id = h.get("responsible_id") or "none"
        name = h.get("responsible_name") or "Sem responsavel"
        item = metrics.setdefault(resp_id, {
            "responsible": name,
            "active_count": 0,
            "completed_proj_ids": set(),
            "completed_days": [],
            "open_days": [],
            "pending_required_cl": 0,
        })
        item["completed_proj_ids"].add(int(h["project_id"]))
        item["completed_days"].append(_days_between(h["entered_at"], h["exited_at"]))

    rows = []
    for item in metrics.values():
        avg_days = None
        if item["completed_days"]:
            avg_days = sum(item["completed_days"]) / len(item["completed_days"])
        elif item["open_days"]:
            avg_days = sum(item["open_days"]) / len(item["open_days"])
        max_open = max(item["open_days"]) if item["open_days"] else None
        status, tone, score = _responsible_status(item["active_count"], avg_days, max_open)
        rows.append({
            "responsible": item["responsible"],
            "active_count": item["active_count"],
            "completed_count": len(item["completed_proj_ids"]),
            "avg_days": avg_days,
            "max_open_days": max_open,
            "pending_required_checklist": item["pending_required_cl"],
            "status": status,
            "tone": tone,
            "score": score,
        })

    return sorted(rows, key=lambda r: (-r["score"], -r["active_count"], r["responsible"]))


# ---------------------------------------------------------------------------
# calculate_city_metrics_v2
# ---------------------------------------------------------------------------

def calculate_city_metrics_v2(projects, process_name_fn=None):
    """
    Distribuicao geografica com contagem de projetos parados e tipo mais comum.
    """
    total = max(len(projects), 1)
    grouped = {}

    for p in projects:
        city = p.get("cidade") or "Sem cidade"
        uf = p.get("uf") or ""
        label = f"{city}/{uf}" if uf else city

        item = grouped.setdefault(label, {
            "city": label,
            "total": 0,
            "active": 0,
            "finished": 0,
            "stopped": 0,
            "process_counts": {},
        })
        item["total"] += 1
        pk = str(p.get("tipo_servico") or "OUTRO").upper()
        item["process_counts"][pk] = item["process_counts"].get(pk, 0) + 1

        if _is_active(p):
            item["active"] += 1
            if _is_stopped(p):
                item["stopped"] += 1
        else:
            item["finished"] += 1

    rows = []
    for item in grouped.values():
        most_common_key = max(item["process_counts"], key=item["process_counts"].get) if item["process_counts"] else None
        most_common_name = process_name_fn(most_common_key) if (process_name_fn and most_common_key) else most_common_key
        item["percent"] = item["total"] / total * 100
        item["most_common_process"] = most_common_name
        del item["process_counts"]
        rows.append(item)

    return sorted(rows, key=lambda r: (-r["total"], r["city"]))


# ---------------------------------------------------------------------------
# calculate_external_actor_metrics
# ---------------------------------------------------------------------------

def calculate_external_actor_metrics(projects, project_stages, histories):
    """
    Agrupa projetos por cartorio/orgao externo diferenciado.

    Diferencia CARTORIO, SIGEF/INCRA, PREFEITURA, etc. em vez de tratar tudo igual.
    Usa external_actor_type das etapas ORGAO_EXTERNO quando disponivel.
    """
    stages_by_project = {}
    for s in project_stages:
        stages_by_project.setdefault(int(s["projeto_id"]), []).append(s)

    # Historico de ORGAO_EXTERNO para calcular tempo medio
    ext_days_by_actor = {}
    for h in histories:
        if str(h.get("stage_key") or "").upper() != "ORGAO_EXTERNO":
            continue
        if not (h.get("exited_at") and h.get("entered_at")):
            continue
        pid = int(h["project_id"])
        actor_type = None
        for s in stages_by_project.get(pid, []):
            if str(s.get("stage_key") or "").upper() == "ORGAO_EXTERNO":
                actor_type = s.get("external_actor_type")
                break
        actor_key = (actor_type or "CARTORIO").upper()
        ext_days_by_actor.setdefault(actor_key, []).append(
            _days_between(h["entered_at"], h["exited_at"])
        )

    grouped = {}
    for p in projects:
        pid = int(p["id"])
        stages = stages_by_project.get(pid, [])

        actor_type = None
        for s in stages:
            if str(s.get("stage_key") or "").upper() == "ORGAO_EXTERNO":
                actor_type = s.get("external_actor_type")
                break

        if actor_type and str(actor_type).upper() not in ("NENHUM", "", "NONE"):
            actor_key = str(actor_type).upper()
            actor_label = EXTERNAL_ACTOR_LABELS.get(actor_key, actor_key)
            registry_name = p.get("cartorio_nome") or actor_label
        elif p.get("cartorio_nome"):
            actor_key = "CARTORIO"
            actor_label = "Cartorio"
            registry_name = p["cartorio_nome"]
        else:
            actor_key = "NENHUM"
            actor_label = "Sem cartorio/orgao"
            registry_name = "Sem cartorio/orgao"

        key = f"{actor_key}::{registry_name}"
        item = grouped.setdefault(key, {
            "actor_key": actor_key,
            "actor_label": actor_label,
            "registry": registry_name,
            "total": 0,
            "active": 0,
            "finished": 0,
        })
        item["total"] += 1
        if _is_active(p):
            item["active"] += 1
        else:
            item["finished"] += 1

    rows = []
    for item in grouped.values():
        if item["actor_key"] == "NENHUM":
            continue
        actor_key = item["actor_key"]
        days_list = ext_days_by_actor.get(actor_key, [])
        avg_ext_days = sum(days_list) / len(days_list) if days_list else None

        if item["active"] == 0 and not avg_ext_days:
            status, tone = "Sem dados", "muted"
        elif (avg_ext_days and avg_ext_days >= THRESHOLDS["ext_actor_attention_days"]) or item["active"] >= 5:
            status, tone = "Atencao", "amber"
        else:
            status, tone = "Normal", "green"

        rows.append({
            **item,
            "avg_ext_days": avg_ext_days,
            "status": status,
            "tone": tone,
        })

    return sorted(rows, key=lambda r: (-r["total"], r["registry"]))


# ---------------------------------------------------------------------------
# calculate_stopped_projects_v2
# ---------------------------------------------------------------------------

def calculate_stopped_projects_v2(projects, project_stages, open_pending_by_project, checklist_items):
    """
    Lista projetos parados com info de checklist e sugestao de acao.

    Criterio: ha mais de THRESHOLDS['stopped_days'] dias na etapa atual.
    """
    checklist_by_project = {}
    for it in checklist_items:
        checklist_by_project.setdefault(int(it["project_id"]), []).append(it)

    rows = []
    for p in projects:
        if not _is_active(p):
            continue
        days = _project_open_days(p)
        if days < THRESHOLDS["stopped_days"]:
            continue

        pid = int(p["id"])
        stage_name = p.get("current_stage_name") or "Sem etapa"
        responsible = p.get("current_responsible_name") or p.get("responsavel_geral_nome") or ""
        has_pending = open_pending_by_project.get(pid, 0) > 0
        current_key = str(p.get("current_stage_template_key") or "").upper()
        is_external = current_key == "ORGAO_EXTERNO"

        proj_cl = checklist_by_project.get(pid, [])
        pending_required = sum(
            1 for it in proj_cl
            if _checklist_pending(it)
            and str(it.get("requirement_level") or "").upper() == REQUIREMENT_REQUIRED
        )

        if not responsible:
            next_action = "Definir responsavel"
        elif pending_required:
            next_action = "Resolver checklist obrigatorio"
        elif has_pending:
            next_action = "Cobrar cliente ou resolver pendencia"
        elif is_external:
            next_action = "Acompanhar orgao externo / cartorio"
        else:
            next_action = "Redistribuir ou revisar capacidade interna"

        rows.append({
            "project_id": pid,
            "project_name": p.get("nome") or "-",
            "cliente_nome": p.get("cliente_nome") or p.get("proprietario") or "-",
            "process_type": str(p.get("tipo_servico") or ""),
            "stage_name": stage_name,
            "responsible": responsible or "Sem responsavel",
            "open_days": days,
            "pending_required_checklist": pending_required,
            "has_open_pendency": has_pending,
            "next_action": next_action,
        })

    return sorted(rows, key=lambda r: -r["open_days"])


# ---------------------------------------------------------------------------
# calculate_checklist_pending_report
# ---------------------------------------------------------------------------

def calculate_checklist_pending_report(projects, checklist_items):
    """
    Lista itens de checklist obrigatorio pendentes em projetos ativos.

    Ordenado por: critico > bloqueia processo > bloqueia etapa > dias pendente.
    """
    project_by_id = {int(p["id"]): p for p in projects}

    rows = []
    for it in checklist_items:
        pid = int(it.get("project_id") or 0)
        p = project_by_id.get(pid)
        if not p or not _is_active(p):
            continue
        if not _checklist_pending(it):
            continue
        if str(it.get("requirement_level") or "").upper() != REQUIREMENT_REQUIRED:
            continue

        created = it.get("created_at") or it.get("updated_at")
        days_pending = _days_between(created)
        crit = str(it.get("criticality") or "").upper()

        rows.append({
            "project_id": pid,
            "project_name": p.get("nome") or "-",
            "process_type": str(p.get("tipo_servico") or ""),
            "stage_key": str(it.get("stage_key") or "").upper(),
            "stage_name": it.get("stage_name") or STAGE_LABELS_LOCAL.get(str(it.get("stage_key") or "").upper(), ""),
            "title": it.get("title") or "-",
            "criticality": crit,
            "criticality_label": _criticality_label(crit),
            "responsible": it.get("responsible_name") or "-",
            "days_pending": days_pending,
            "blocks_stage": bool(it.get("blocks_stage_completion")),
            "blocks_process": bool(it.get("blocks_process_completion")),
        })

    return sorted(rows, key=lambda r: (
        -int(r["criticality"] == CRITICALITY_CRITICAL),
        -int(r["blocks_process"]),
        -int(r["blocks_stage"]),
        -(r["days_pending"] or 0),
    ))


def _criticality_label(crit):
    labels = {
        "CRITICA": "Critica",
        "ALTA": "Alta",
        "MEDIA": "Media",
        "BAIXA": "Baixa",
    }
    return labels.get(crit, crit or "-")


# ---------------------------------------------------------------------------
# build_bottleneck_suggestions_v2
# ---------------------------------------------------------------------------

def build_bottleneck_suggestions_v2(stage_metrics):
    """
    Gera lista de gargalos com texto explicativo a partir das metricas de etapa.
    """
    bottlenecks = []
    for m in stage_metrics:
        if m["status"] not in ("Gargalo", "Atencao"):
            continue

        avg = m.get("avg_days") or 0
        active = m.get("active_count") or 0
        max_open = m.get("max_open_days") or 0
        pending_cl = m.get("pending_required_checklist") or 0

        parts = []
        if avg >= THRESHOLDS["bottleneck_days"]:
            parts.append(f"media de {avg:.1f} dias".replace(".", ","))
        elif avg >= THRESHOLDS["attention_days"]:
            parts.append(f"media de {avg:.1f} dias".replace(".", ","))
        if active >= THRESHOLDS["bottleneck_active_count"]:
            parts.append(f"{active} projetos ativos acumulados")
        elif active >= THRESHOLDS["attention_active_count"]:
            parts.append(f"{active} projetos ativos")
        if max_open >= THRESHOLDS["bottleneck_days"]:
            parts.append(f"projeto parado ha {max_open:.1f} dias".replace(".", ","))
        if pending_cl:
            parts.append(f"{pending_cl} checklist obrigatorio pendente")

        detail = ", ".join(parts) if parts else "monitorar nos proximos ciclos"
        if m["status"] == "Gargalo":
            suggestion = f"Situacao critica: {detail}. Verificar capacidade ou redistribuir."
        else:
            suggestion = f"Requer atencao: {detail}."

        bottlenecks.append({**m, "suggestion": suggestion})

    return sorted(bottlenecks, key=lambda b: (-b["score"], -(b.get("avg_days") or 0), -b["active_count"]))


# ---------------------------------------------------------------------------
# build_operational_summary_v2
# ---------------------------------------------------------------------------

def build_operational_summary_v2(
    projects,
    stage_metrics,
    process_type_metrics,
    responsible_metrics,
    checklist_items,
    open_pending_by_project,
):
    """
    Calcula os cards de visao geral operacional.
    Cards focados em gestao: ativos, parados, gargalo, cartorio, prazos, responsavel.
    """
    active_projects = [p for p in projects if _is_active(p)]
    active_ids = {int(p["id"]) for p in active_projects}

    # Projetos com prazo critico vencido ou etapa marcada como atrasada
    overdue_projects = [
        p for p in active_projects
        if (p.get("prazo_critico") and _days_between(datetime.now().date().isoformat(), p["prazo_critico"]) < 0)
        or str(p.get("current_stage_status") or "").lower() == "atrasado"
    ]

    # Projetos parados (ha mais de stopped_days na mesma etapa)
    stopped_projects = [p for p in active_projects if _is_stopped(p)]

    # Projetos em cartorio/orgao externo
    cartorio_active = sum(
        1 for p in active_projects
        if _to_macro_key(p.get("current_stage_template_key") or "")
        == "ORGAO_EXTERNO"
        or _stage_name_to_macro_key(p.get("current_stage_name") or "")
        == "ORGAO_EXTERNO"
    )

    # Maior gargalo
    bottlenecks_sorted = [m for m in stage_metrics if m["status"] in ("Gargalo", "Atencao")]
    bottlenecks_sorted = sorted(bottlenecks_sorted, key=lambda m: (-m["score"], -(m.get("avg_days") or 0)))
    main_bottleneck = bottlenecks_sorted[0] if bottlenecks_sorted else None

    # Tipo de processo mais lento
    slowest_process = None
    if process_type_metrics:
        with_days = [r for r in process_type_metrics if r.get("avg_total_days")]
        if with_days:
            slowest_process = max(with_days, key=lambda r: r["avg_total_days"])

    # Responsavel com maior carga
    most_loaded_resp = None
    if responsible_metrics:
        active_resp = [r for r in responsible_metrics if r["active_count"] > 0]
        if active_resp:
            most_loaded_resp = max(active_resp, key=lambda r: r["active_count"])

    return {
        "active_projects": len(active_projects),
        "overdue_projects": len(overdue_projects),
        "stopped_projects": len(stopped_projects),
        "cartorio_active": cartorio_active,
        "main_bottleneck": main_bottleneck,
        "slowest_process": slowest_process,
        "most_loaded_responsible": most_loaded_resp,
        "open_pendencies": sum(open_pending_by_project.values()),
        # Mantidos internamente para compatibilidade com report_helpers legado
        "critical_checklist_pending": 0,
        "required_checklist_pending": 0,
        "without_model_count": 0,
    }
