"""Sincroniza no banco um ou todos os tipos de processo definidos no codigo.

Uso:
    python scripts/sync_process_type.py AVERBACAO_CERTIFICACAO
    python scripts/sync_process_type.py ALL
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import app as geogestao  # noqa: E402
from process_types import PROCESS_TYPE_BY_KEY  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Sincroniza tipos de processo no banco configurado.")
    parser.add_argument("process_type_key", choices=["ALL", *sorted(PROCESS_TYPE_BY_KEY)])
    args = parser.parse_args()
    selected = set(PROCESS_TYPE_BY_KEY) if args.process_type_key == "ALL" else {args.process_type_key}

    with geogestao.app.app_context():
        db = geogestao.connect_db(use_pool=False)
        try:
            geogestao.seed_process_types(db, selected)
            geogestao.seed_process_stage_templates(db, selected)
            geogestao.seed_process_checklist_templates(db, selected)
            geogestao.normalize_stage_models(db)
            moved_projects = geogestao.sync_existing_project_workflows(db, selected)
            for process_type_key in sorted(selected):
                projects = db.execute(
                    "SELECT id FROM projetos WHERE tipo_servico = %s ORDER BY id",
                    (process_type_key,),
                ).fetchall()
                for project in projects:
                    geogestao.create_project_checklist_from_template(db, project["id"], process_type_key)
                    geogestao.sync_project_checklist_stage_links(db, project["id"])
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    print(f"Tipos de processo sincronizados: {', '.join(sorted(selected))}. Projetos reposicionados: {moved_projects}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
