"""Busca pública. DuckDuckGo HTML é o provedor principal; Bing só entra se for pertinente."""

from __future__ import annotations

import logging
import urllib.parse
from collections import Counter

from almore_scraper.extracao import (
    eh_anomalia_ddg,
    parse_bing,
    parse_ddg,
    relevante,
)
from almore_scraper.http_util import ClienteHttp, pausar
from almore_scraper.modelos import ResultadoBusca

log = logging.getLogger("almore")


class Buscador:
    def __init__(self, cliente: ClienteHttp, pausa: tuple[float, float]) -> None:
        self.cliente = cliente
        self.pausa = pausa
        self.buscas = 0
        self.anomalias = 0
        self.provedores: Counter[str] = Counter()
        self.bloqueios: Counter[str] = Counter()
        self._cache: dict[str, list[ResultadoBusca]] = {}
        self.anomalias_seguidas = 0

    def buscar(self, consulta: str, paginas: int = 1) -> list[ResultadoBusca]:
        chave = f"{consulta.strip().casefold()}|{paginas}"
        if chave in self._cache:
            return list(self._cache[chave])
        resultados = self._buscar_ddg(consulta, paginas)
        if not resultados and self.anomalias_seguidas < 3:
            resultados = self._buscar_bing(consulta)
        self._cache[chave] = list(resultados)
        return resultados

    def _buscar_ddg(self, consulta: str, paginas: int) -> list[ResultadoBusca]:
        acumulado: list[ResultadoBusca] = []
        vistos: set[str] = set()
        formulario: dict[str, str] | None = None
        for pagina in range(max(1, paginas)):
            if pagina == 0:
                resposta = self._post_ddg({"q": consulta, "kl": "br-pt"})
            else:
                if not formulario:
                    break
                resposta = self._post_ddg(formulario)
            if resposta is None:
                break
            if eh_anomalia_ddg(resposta.corpo) or resposta.status == 202:
                self.anomalias += 1
                self.anomalias_seguidas += 1
                self.bloqueios["duckduckgo"] += 1
                log.warning("DuckDuckGo pediu desafio na consulta: %s", consulta[:140])
                if pagina == 0 and self.anomalias_seguidas < 3:
                    pausar((8.0, 12.0))
                    resposta = self._post_ddg({"q": consulta, "kl": "br-pt"})
                    if resposta is None or eh_anomalia_ddg(resposta.corpo) or resposta.status == 202:
                        self.anomalias += 1
                        break
                else:
                    break
            else:
                self.anomalias_seguidas = 0
            lote, formulario = parse_ddg(resposta.corpo)
            if not lote:
                log.info("DuckDuckGo sem resultados: %s", consulta[:140])
                break
            for titulo, url, snippet in lote:
                if url in vistos:
                    continue
                vistos.add(url)
                acumulado.append(ResultadoBusca(titulo, url, snippet, "duckduckgo"))
            self.provedores["duckduckgo"] += 1
        return acumulado

    def _post_ddg(self, dados: dict[str, str]):
        self.buscas += 1
        resposta = self.cliente.solicitar(
            "https://html.duckduckgo.com/html/",
            dados,
            timeout=25,
        )
        pausar(self.pausa)
        return resposta

    def _buscar_bing(self, consulta: str) -> list[ResultadoBusca]:
        self.buscas += 1
        url = "https://www.bing.com/search?" + urllib.parse.urlencode(
            {"q": consulta, "setlang": "pt-BR", "cc": "BR", "count": "15"}
        )
        resposta = self.cliente.solicitar(url, timeout=25)
        pausar(self.pausa)
        if resposta is None:
            return []
        if resposta.status in {429, 503} or "captcha" in resposta.corpo[:4000].lower():
            self.bloqueios["bing"] += 1
            log.warning("Bing bloqueou ou limitou a consulta")
            return []
        lote = parse_bing(resposta.corpo)
        if not relevante(lote, consulta):
            self.bloqueios["bing_irrelevante"] += 1
            log.info("Bing devolveu resultados fora da consulta; ignorados")
            return []
        self.provedores["bing"] += 1
        return [ResultadoBusca(titulo, url, snippet, "bing") for titulo, url, snippet in lote]
