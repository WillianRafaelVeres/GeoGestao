import argparse
import csv
import sys
import unicodedata
from pathlib import Path

from app import app_now_iso, connect_db


FIELD_ALIASES = {
    "nome": ("nome", "denominacao", "denominação", "serventia", "cartorio", "cartório"),
    "cns": ("cns", "codigo nacional de serventia", "código nacional de serventia", "codigo", "código"),
    "cidade": ("cidade", "municipio", "município"),
    "uf": ("uf", "estado"),
    "email": ("email", "e-mail"),
    "telefone": ("telefone", "fone"),
    "oficial": ("responsavel", "responsável", "oficial", "titular"),
    "observacoes": ("observacoes", "observações", "endereco", "endereço", "bairro"),
}


def normalize_key(value):
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(char for char in text if not unicodedata.combining(char))
    return " ".join(text.strip().lower().replace("_", " ").replace("-", " ").split())


def first_value(row, *aliases):
    normalized = {normalize_key(key): value for key, value in row.items()}
    for alias in aliases:
        value = normalized.get(normalize_key(alias))
        if value:
            return value.strip()
    return ""


def read_rows(path):
    raw = Path(path).read_text(encoding="utf-8-sig")
    sample = raw[:4096]
    dialect = csv.Sniffer().sniff(sample, delimiters=";,")
    reader = csv.DictReader(raw.splitlines(), dialect=dialect)
    for row in reader:
        yield {
            field: first_value(row, *aliases)
            for field, aliases in FIELD_ALIASES.items()
        }


def find_existing(cur, item):
    if item["cns"]:
        cur.execute(
            "SELECT id FROM cartorios WHERE cns = %s LIMIT 1",
            (item["cns"],),
        )
        row = cur.fetchone()
        if row:
            return row[0]
    cur.execute(
        """
        SELECT id FROM cartorios
        WHERE lower(nome) = lower(%s)
          AND COALESCE(uf, '') = %s
          AND lower(COALESCE(cidade, '')) = lower(%s)
        LIMIT 1
        """,
        (item["nome"], item["uf"], item["cidade"]),
    )
    row = cur.fetchone()
    return row[0] if row else None


def import_cartorios(path, overwrite=False):
    db = connect_db(use_pool=False)
    cur = db.cursor()
    created = 0
    updated = 0
    skipped = 0
    now = app_now_iso()
    try:
        for item in read_rows(path):
            item["uf"] = (item["uf"] or "").upper()
            if not item["nome"] or not item["cns"]:
                skipped += 1
                continue
            existing_id = find_existing(cur, item)
            if existing_id:
                if overwrite:
                    cur.execute(
                        """
                        UPDATE cartorios
                        SET nome = %s, cns = %s, cidade = %s, uf = %s,
                            email = %s, telefone = %s, oficial = %s, observacoes = %s
                        WHERE id = %s
                        """,
                        (
                            item["nome"],
                            item["cns"],
                            item["cidade"],
                            item["uf"],
                            item["email"],
                            item["telefone"],
                            item["oficial"],
                            item["observacoes"],
                            existing_id,
                        ),
                    )
                else:
                    cur.execute(
                        """
                        UPDATE cartorios
                        SET cns = CASE WHEN COALESCE(cns, '') = '' THEN %s ELSE cns END,
                            cidade = CASE WHEN COALESCE(cidade, '') = '' THEN %s ELSE cidade END,
                            uf = CASE WHEN COALESCE(uf, '') = '' THEN %s ELSE uf END,
                            email = CASE WHEN COALESCE(email, '') = '' THEN %s ELSE email END,
                            telefone = CASE WHEN COALESCE(telefone, '') = '' THEN %s ELSE telefone END,
                            oficial = CASE WHEN COALESCE(oficial, '') = '' THEN %s ELSE oficial END,
                            observacoes = CASE WHEN COALESCE(observacoes, '') = '' THEN %s ELSE observacoes END
                        WHERE id = %s
                        """,
                        (
                            item["cns"],
                            item["cidade"],
                            item["uf"],
                            item["email"],
                            item["telefone"],
                            item["oficial"],
                            item["observacoes"],
                            existing_id,
                        ),
                    )
                updated += 1
                continue
            cur.execute(
                """
                INSERT INTO cartorios
                    (nome, cns, cidade, uf, contato, email, telefone, whatsapp, oficial, observacoes)
                VALUES (%s, %s, %s, %s, '', %s, %s, '', %s, %s)
                """,
                (
                    item["nome"],
                    item["cns"],
                    item["cidade"],
                    item["uf"],
                    item["email"],
                    item["telefone"],
                    item["oficial"],
                    item["observacoes"] or f"Importado da base CNJ em {now}.",
                ),
            )
            created += 1
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        cur.close()
        db.close()
    return created, updated, skipped


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Importa cartorios/serventias de um CSV exportado da base oficial CNJ/Justica Aberta."
    )
    parser.add_argument("csv_path", help="Caminho do CSV com colunas como CNS, denominacao, UF e municipio.")
    parser.add_argument("--overwrite", action="store_true", help="Sobrescreve campos existentes com os dados do CSV.")
    args = parser.parse_args(argv)
    created, updated, skipped = import_cartorios(args.csv_path, overwrite=args.overwrite)
    print(f"Cartorios criados: {created}")
    print(f"Cartorios atualizados: {updated}")
    print(f"Linhas ignoradas: {skipped}")


if __name__ == "__main__":
    main(sys.argv[1:])
