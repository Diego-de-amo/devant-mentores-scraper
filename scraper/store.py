"""Leitura e gravação dos CSVs. Campos vazios ficam vazios."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from scraper.config import COLUMNS
from scraper.textutil import excel_safe

FUNNEL_MAP = {
    "nome": "nome",
    "instagram_handle": "instagram_handle",
    "instagram_url": "instagram_url",
    "linkedin_url": "linkedin_url",
    "site": "site_mentoria",
    "tema": "tema_principal",
    "cidade_uf": "cidade_estado",
    "seguidores": "seguidores_aproximados",
    "menciona_ia": "menciona_ia_ou_parceiro_ia",
    "fonte_url": "fonte_url",
    "data_entrada": "data_entrada",
}


def load_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        rows = []
        for row in reader:
            rows.append({column: (row.get(column) or "").strip() for column in COLUMNS})
        return rows


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: excel_safe((row.get(column) or "").replace("\n", " ").strip()) for column in COLUMNS})


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def rows_from_funnel(path: Path) -> list[dict[str, str]]:
    path = Path(path)
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        rows = []
        for source in reader:
            row = {column: "" for column in COLUMNS}
            for target, origin in FUNNEL_MAP.items():
                row[target] = (source.get(origin) or "").strip()
            rows.append(row)
        return rows
