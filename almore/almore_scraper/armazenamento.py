"""CSV mestre, CSV do dia e resumo da execução."""

from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path

from almore_scraper.modelos import CAMPOS, Candidato


def caminho_master(diretorio: Path) -> Path:
    return diretorio / "mentores_master.csv"


def caminho_dia(diretorio: Path, dia: date) -> Path:
    return diretorio / f"mentores_{dia.isoformat()}.csv"


def caminho_resumo(diretorio: Path) -> Path:
    return diretorio / "last_run.json"


def ler_csv(caminho: Path) -> list[dict[str, str]]:
    if not caminho.exists() or caminho.stat().st_size == 0:
        return []
    with caminho.open(encoding="utf-8-sig", newline="") as arquivo:
        leitor = csv.DictReader(arquivo)
        campos = leitor.fieldnames or []
        faltando = [campo for campo in CAMPOS if campo not in campos]
        if faltando:
            raise ValueError(f"{caminho} não tem as colunas {', '.join(faltando)}")
        return [{campo: (linha.get(campo) or "").strip() for campo in CAMPOS} for linha in leitor]


def escrever_csv(caminho: Path, linhas: list[dict[str, str]]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_suffix(caminho.suffix + ".tmp")
    with temporario.open("w", encoding="utf-8-sig", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=CAMPOS, extrasaction="ignore", lineterminator="\n")
        escritor.writeheader()
        for linha in linhas:
            escritor.writerow({campo: linha.get(campo, "") for campo in CAMPOS})
    temporario.replace(caminho)


def candidato_de_linha(linha: dict[str, str]) -> Candidato:
    return Candidato(**{campo: linha.get(campo, "") for campo in CAMPOS})


def salvar_resultados(
    diretorio: Path,
    dia: date,
    existentes: list[dict[str, str]],
    novos: list[Candidato],
) -> tuple[Path | None, Path]:
    master = caminho_master(diretorio)
    diario = caminho_dia(diretorio, dia)
    if not novos:
        return (diario if diario.exists() else None), master
    linhas = list(existentes)
    linhas.extend(candidato.registro() for candidato in novos)
    escrever_csv(master, linhas)
    do_dia = [linha for linha in linhas if linha.get("data_entrada") == dia.isoformat()]
    if do_dia:
        escrever_csv(diario, do_dia)
        return diario, master
    return None, master


def salvar_resumo(diretorio: Path, resumo: dict) -> None:
    caminho = caminho_resumo(diretorio)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(resumo, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
