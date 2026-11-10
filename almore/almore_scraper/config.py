"""Leitura de almore/config/nichos.yml."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import yaml

from almore_scraper.util_texto import dobrar, espacos

RAIZ = Path(__file__).resolve().parents[1]
CONFIG_PADRAO = RAIZ / "config" / "nichos.yml"
DADOS_PADRAO = RAIZ / "data"


@dataclass
class Nicho:
    id: str
    nome: str
    termos: list[str]
    consultas_extras: list[str] = field(default_factory=list)


@dataclass
class Config:
    alvo_por_dia: int = 50
    nichos_por_rodada: int = 8
    max_por_nicho: int = 12
    teto_seguidores: int = 150_000
    preferencia_seguidores: int = 100_000
    max_buscas: int = 100
    max_paginas_por_consulta: int = 2
    max_fetches: int = 45
    max_enriquecimentos: int = 60
    pausa_busca: tuple[float, float] = (2.0, 4.2)
    pausa_fetch: tuple[float, float] = (0.6, 1.4)
    pausa_instagram: tuple[float, float] = (8.0, 16.0)
    falhas_instagram_para_desligar: int = 2
    templates: list[str] = field(default_factory=list)
    ignorar_handles: set[str] = field(default_factory=set)
    nichos: list[Nicho] = field(default_factory=list)

    def consultas(self, nicho: Nicho) -> list[str]:
        saida: list[str] = []
        vistos: set[str] = set()

        def adicionar(consulta: str) -> None:
            limpa = espacos(consulta)
            chave = dobrar(limpa)
            if limpa and chave not in vistos:
                vistos.add(chave)
                saida.append(limpa)

        for extra in nicho.consultas_extras:
            adicionar(extra)
        if nicho.termos:
            for modelo in self.templates:
                adicionar(modelo.format(termo=nicho.termos[0]))
        if len(saida) < 3 and len(nicho.termos) > 1 and self.templates:
            adicionar(self.templates[0].format(termo=nicho.termos[1]))
        return saida[:4]


def _par_pausa(bloco: dict, chave_min: str, chave_max: str, padrao: tuple[float, float]) -> tuple[float, float]:
    if chave_min not in bloco and chave_max not in bloco:
        return padrao
    minimo = float(bloco.get(chave_min, padrao[0]))
    maximo = float(bloco.get(chave_max, padrao[1]))
    if maximo < minimo:
        minimo, maximo = maximo, minimo
    return (minimo, maximo)


def carregar_config(caminho: Path | None = None) -> Config:
    arquivo = caminho or CONFIG_PADRAO
    with arquivo.open(encoding="utf-8") as handle:
        bruto = yaml.safe_load(handle) or {}
    if not isinstance(bruto, dict):
        raise ValueError(f"Configuração inválida em {arquivo}")

    nichos: list[Nicho] = []
    ids: set[str] = set()
    for item in bruto.get("nichos") or []:
        nicho = Nicho(
            id=str(item["id"]).strip(),
            nome=str(item["nome"]).strip(),
            termos=[str(termo).strip() for termo in item.get("termos") or [] if str(termo).strip()],
            consultas_extras=[str(extra).strip() for extra in item.get("consultas_extras") or [] if str(extra).strip()],
        )
        if not nicho.id or not nicho.nome:
            raise ValueError("Cada nicho precisa de id e nome")
        if nicho.id in ids:
            raise ValueError(f"Nicho duplicado: {nicho.id}")
        if "contab" in dobrar(nicho.id) or "contab" in dobrar(nicho.nome):
            raise ValueError(f"Nicho de contabilidade não é permitido: {nicho.id}")
        ids.add(nicho.id)
        nichos.append(nicho)
    if not nichos:
        raise ValueError("A configuração não tem nichos")

    config = Config(
        alvo_por_dia=int(bruto.get("alvo_por_dia", 50)),
        nichos_por_rodada=int(bruto.get("nichos_por_rodada", 8)),
        max_por_nicho=int(bruto.get("max_por_nicho", 12)),
        teto_seguidores=int(bruto.get("teto_seguidores", 150_000)),
        preferencia_seguidores=int(bruto.get("preferencia_seguidores", 100_000)),
        max_buscas=int(bruto.get("max_buscas", 100)),
        max_paginas_por_consulta=int(bruto.get("max_paginas_por_consulta", 2)),
        max_fetches=int(bruto.get("max_fetches", 45)),
        max_enriquecimentos=int(bruto.get("max_enriquecimentos", 60)),
        pausa_busca=_par_pausa(bruto, "pausa_busca_min", "pausa_busca_max", (2.0, 4.2)),
        pausa_fetch=_par_pausa(bruto, "pausa_fetch_min", "pausa_fetch_max", (0.6, 1.4)),
        pausa_instagram=_par_pausa(bruto, "pausa_instagram_min", "pausa_instagram_max", (8.0, 16.0)),
        falhas_instagram_para_desligar=int(bruto.get("falhas_instagram_para_desligar", 2)),
        templates=[str(item) for item in bruto.get("templates") or []],
        ignorar_handles={str(item).strip().lstrip("@").lower() for item in bruto.get("ignorar_handles") or []},
        nichos=nichos,
    )
    if config.alvo_por_dia < 1:
        raise ValueError("alvo_por_dia precisa ser positivo")
    if config.teto_seguidores < config.preferencia_seguidores:
        raise ValueError("teto_seguidores não pode ser menor que preferencia_seguidores")
    if not config.templates:
        raise ValueError("Inclua ao menos um template de consulta")
    return config


def nichos_do_dia(nichos: list[Nicho], dia: date, quantidade: int, inicio: int = 0) -> list[Nicho]:
    if not nichos or quantidade <= 0:
        return []
    cursor = (dia.toordinal() + inicio) % len(nichos)
    return [nichos[(cursor + deslocamento) % len(nichos)] for deslocamento in range(min(quantidade, len(nichos)))]
