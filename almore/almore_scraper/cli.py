"""Linha de comando: python -m almore_scraper"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

from almore_scraper.config import DADOS_PADRAO, carregar_config
from almore_scraper.pipeline import executar


def _data(valor: str) -> date:
    return date.fromisoformat(valor)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        stream=sys.stdout,
        force=True,
    )
    parser = argparse.ArgumentParser(description="Coleta mentores de negócios para a Almore, fora da contabilidade.")
    parser.add_argument("--config", type=Path, default=None, help="YAML de nichos. Padrão: almore/config/nichos.yml")
    parser.add_argument("--diretorio", type=Path, default=DADOS_PADRAO, help="Pasta dos CSVs")
    parser.add_argument("--data", type=_data, default=None, help="Data de entrada YYYY-MM-DD. Padrão: hoje em São Paulo")
    parser.add_argument("--max", type=int, default=None, help="Máximo de mentores novos")
    parser.add_argument("--max-buscas", type=int, default=None, help="Teto de consultas aos buscadores")
    parser.add_argument("--nichos", default="", help="IDs separados por vírgula. Vazio usa a rotação do dia")
    parser.add_argument("--sem-instagram", action="store_true", help="Não chama o Instaloader")
    args = parser.parse_args(argv)
    try:
        config = carregar_config(args.config)
        ids = [item.strip() for item in args.nichos.split(",") if item.strip()] or None
        resumo = executar(
            config,
            args.diretorio,
            args.data,
            nichos_ids=ids,
            alvo=args.max,
            max_buscas=args.max_buscas,
            sem_instagram=args.sem_instagram,
        )
    except Exception as erro:
        logging.getLogger("almore").exception("Falha fatal: %s", erro)
        return 1
    print(f"Novos mentores: {resumo['novos']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
