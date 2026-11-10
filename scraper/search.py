"""Busca pública em DuckDuckGo HTML e Yahoo Brasil.

Os dois responderam com resultados reais a partir de IP de datacenter.
Bing HTML devolveu um feed de notícias sem relação com a consulta, e o
operador site: no DuckDuckGo disparou página de anomalia (HTTP 202).
Por isso a descoberta não usa site: nem Bing.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Callable
from urllib.parse import parse_qs, unquote, urlencode, urlsplit

import requests
from bs4 import BeautifulSoup

from scraper.config import SEARCH_PAUSE_SECONDS, USER_AGENT
from scraper.textutil import clean_text

_PAUSE = SEARCH_PAUSE_SECONDS


@dataclass
class Hit:
    url: str
    title: str
    snippet: str
    query: str
    engine: str


class SearchBlocked(RuntimeError):
    """O buscador pediu captcha, anomalia ou limite."""


def unwrap_duckduckgo(url: str) -> str:
    if url.startswith("//"):
        url = "https:" + url
    parts = urlsplit(url)
    target = parse_qs(parts.query).get("uddg", [""])[0]
    return unquote(target) if target else url


def unwrap_yahoo(url: str) -> str:
    match = re.search(r"/RU=([^/]+)", url)
    if match:
        return unquote(match.group(1))
    parts = urlsplit(url)
    target = parse_qs(parts.query).get("RU", [""])[0]
    return unquote(target) if target else url


def _session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
            "Accept": "text/html,application/xhtml+xml",
        }
    )
    return session


def _get(session: requests.Session, url: str) -> str:
    response = session.get(url, timeout=(8, 25))
    if response.status_code in {202, 429, 403}:
        raise SearchBlocked(f"HTTP {response.status_code} em {urlsplit(url).netloc}")
    response.raise_for_status()
    text = response.text
    lowered = text.lower()
    if "anomaly-modal" in lowered or "unfortunately, bots" in lowered or "bots use duckduckgo" in lowered:
        raise SearchBlocked("DuckDuckGo exibiu página de anomalia")
    if "consent.yahoo" in response.url or "guce.yahoo" in response.url:
        raise SearchBlocked("Yahoo pediu consentimento")
    return text


def _duckduckgo_once(query: str, session: requests.Session) -> list[Hit]:
    url = "https://html.duckduckgo.com/html/?" + urlencode({"q": query, "kl": "br-pt"})
    html = _get(session, url)
    soup = BeautifulSoup(html, "html.parser")
    hits: list[Hit] = []
    for link in soup.select("a.result__a"):
        href = unwrap_duckduckgo(link.get("href") or "")
        if not href.startswith("http") or "duckduckgo.com/y.js" in href or "ad_domain=" in href:
            continue
        title = clean_text(link.get_text(" ", strip=True))
        snippet = ""
        block = link.find_parent("div", class_=re.compile(r"result"))
        if block:
            snip = block.select_one(".result__snippet")
            if snip:
                snippet = clean_text(snip.get_text(" ", strip=True))
        hits.append(Hit(url=href, title=title, snippet=snippet, query=query, engine="duckduckgo"))
    return hits


def search_duckduckgo(query: str, session: requests.Session | None = None) -> list[Hit]:
    session = session or _session()
    try:
        return _duckduckgo_once(query, session)
    except SearchBlocked:
        time.sleep(8)
        return _duckduckgo_once(query, session)


def search_yahoo(query: str, session: requests.Session | None = None) -> list[Hit]:
    session = session or _session()
    url = "https://br.search.yahoo.com/search?" + urlencode({"p": query, "ei": "UTF-8"})
    html = _get(session, url)
    soup = BeautifulSoup(html, "html.parser")
    hits: list[Hit] = []
    for block in soup.select("div.dd.algo"):
        anchor = block.select_one("h3 a") or block.select_one("a[href]")
        if not anchor:
            continue
        href = unwrap_yahoo(anchor.get("href") or "")
        if not href.startswith("http"):
            continue
        title = clean_text(anchor.get("aria-label") or "")
        if not title:
            span = block.select_one("h3 span")
            title = clean_text(span.get_text(" ", strip=True) if span else anchor.get_text(" ", strip=True))
        title = re.sub(r"^.*›\s*", "", title).strip()
        paragraph = block.find("p")
        snippet = clean_text(paragraph.get_text(" ", strip=True) if paragraph else "")
        hits.append(Hit(url=href, title=title, snippet=snippet, query=query, engine="yahoo"))
    return hits


def search_with_pause(
    engines: list[tuple[str, Callable[[str], list[Hit]]]],
    query: str,
    pause: float = _PAUSE,
) -> tuple[list[Hit], dict[str, str]]:
    """Roda cada motor. Se um bloquear, registra e segue para o outro."""
    found: list[Hit] = []
    errors: dict[str, str] = {}
    for name, engine in engines:
        try:
            found.extend(engine(query))
        except SearchBlocked as exc:
            errors[name] = str(exc)
        except requests.RequestException as exc:
            errors[name] = f"{type(exc).__name__}: {exc}"
        if pause:
            time.sleep(pause)
    return found, errors
