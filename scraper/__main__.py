"""Ponto de entrada: python -m scraper"""

from __future__ import annotations

import argparse
import json

from scraper.pipeline import main_max, run


def main() -> None:
    parser = argparse.ArgumentParser(description="Busca mentores contábeis brasileiros ainda fora do cadastro.")
    parser.add_argument("--data-dir", default="data", help="Pasta dos CSVs. Padrão: data")
    parser.add_argument("--max", type=int, default=main_max(), help="Quantidade máxima de mentores novos")
    args = parser.parse_args()
    report = run(data_dir=args.data_dir, max_novos=args.max)
    print(json.dumps({k: report[k] for k in ("data", "novos", "arquivo_diario", "instagram", "busca", "mentores")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
