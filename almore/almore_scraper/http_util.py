"""HTTP com a biblioteca padrão.

O DuckDuckGo HTML responde ao urllib e devolve o desafio de bot para o
cliente `requests`, então a busca não usa requests.
"""

from __future__ import annotations

import http.cookiejar
import ipaddress
import logging
import random
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

log = logging.getLogger("almore")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


@dataclass
class RespostaHttp:
    status: int
    url_final: str
    corpo: str
    content_type: str


def url_segura(url: str) -> bool:
    partes = urllib.parse.urlparse(url)
    if partes.scheme not in {"http", "https"}:
        return False
    host = (partes.hostname or "").lower().rstrip(".")
    if not host or host in {"localhost", "metadata.google.internal"}:
        return False
    if host.endswith(".local") or host.endswith(".internal"):
        return False
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return True
    return ip.is_global


def _decodificar(bruto: bytes, content_type: str) -> str:
    charset = "utf-8"
    match = None
    if content_type:
        import re

        match = re.search(r"charset=([\w.-]+)", content_type, re.I)
    if match:
        charset = match.group(1)
    try:
        return bruto.decode(charset, "replace")
    except LookupError:
        return bruto.decode("utf-8", "replace")


class ClienteHttp:
    def __init__(self) -> None:
        jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    def solicitar(
        self,
        url: str,
        dados: dict[str, str] | None = None,
        *,
        timeout: float = 20,
        max_bytes: int = 1_500_000,
        tentativas: int = 2,
    ) -> RespostaHttp | None:
        if not url_segura(url):
            log.info("URL ignorada por segurança: %s", url[:120])
            return None
        corpo_post = urllib.parse.urlencode(dados).encode() if dados is not None else None
        cabecalhos = {
            "User-Agent": USER_AGENT,
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        if corpo_post is not None:
            cabecalhos["Content-Type"] = "application/x-www-form-urlencoded"
        espera = 2.0
        ultimo_erro = ""
        for tentativa in range(1, tentativas + 1):
            requisicao = urllib.request.Request(url, data=corpo_post, headers=cabecalhos)
            try:
                with self.opener.open(requisicao, timeout=timeout) as resposta:
                    bruto = resposta.read(max_bytes)
                    return RespostaHttp(
                        status=getattr(resposta, "status", 200),
                        url_final=resposta.geturl(),
                        corpo=_decodificar(bruto, resposta.headers.get("Content-Type", "")),
                        content_type=resposta.headers.get("Content-Type", ""),
                    )
            except urllib.error.HTTPError as erro:
                bruto = erro.read(80_000) if erro.fp else b""
                if erro.code in {429, 503} and tentativa < tentativas:
                    time.sleep(espera + random.random())
                    espera *= 2
                    ultimo_erro = f"HTTP {erro.code}"
                    continue
                return RespostaHttp(
                    status=erro.code,
                    url_final=url,
                    corpo=_decodificar(bruto, erro.headers.get("Content-Type", "") if erro.headers else ""),
                    content_type=erro.headers.get("Content-Type", "") if erro.headers else "",
                )
            except (urllib.error.URLError, TimeoutError, OSError) as erro:
                ultimo_erro = type(erro).__name__
                if tentativa < tentativas:
                    time.sleep(espera + random.random())
                    espera *= 2
                    continue
                log.warning("Falha de rede em %s: %s", url[:120], ultimo_erro)
                return None
        return None


def pausar(intervalo: tuple[float, float]) -> None:
    minimo, maximo = intervalo
    if maximo <= 0:
        return
    time.sleep(random.uniform(max(0.0, minimo), maximo))
