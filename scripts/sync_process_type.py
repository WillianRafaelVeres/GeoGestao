"""Sincroniza no banco um tipo de processo definido no codigo.

Uso:
    python scripts/sync_process_type.py AVERBACAO_CERTIFICACAO
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
    parser = argparse.ArgumentParser(description="Sincroniza um tipo de processo no banco configurado.")
    parser.add_argument("process_type_key", choices=sorted(PROCESS_TYPE_BY_KEY))
    args = parser.parse_args()
    selected = {args.process_type_key}

    with geogestao.app.app_context():
        db = geogestao.connect_db(use_pool=False)
        try:
            geogestao.seed_process_types(db, selected)
            geogestao.seed_process_stage_templates(db, selected)
            geogestao.seed_process_checklist_templates(db, selected)
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    print(f"Tipo de processo {args.process_type_key} sincronizado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
