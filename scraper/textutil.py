"""Normalização, seguidores, IA e cidade. Não inventa o que o texto não diz."""

from __future__ import annotations

import html
import re
import unicodedata
from datetime import datetime

from scraper.config import UFS

_FOLLOWER_RE = re.compile(
    r"(?P<num>\d{1,3}(?:[.\s]\d{3})+|\d+(?:[.,]\d+)?)\s*(?P<suf>mil|[KkMm])?\s*"
    r"(?:followers|seguidores)\b",
    re.IGNORECASE,
)

_CITY_RE = re.compile(
    r"\b([A-ZÁÉÍÓÚÃÕÂÊÔÇ][\wÀ-ÿ]+(?:\s+[A-ZÁÉÍÓÚÃÕÂÊÔÇ][\wÀ-ÿ]+){0,2})\s*/\s*([A-Z]{2})\b"
)

_AI_PHRASES = (
    (re.compile(r"intelig[eê]ncia artificial", re.IGNORECASE), "inteligência artificial"),
    (re.compile(r"\bchatgpt\b", re.IGNORECASE), "chatgpt"),
    (re.compile(r"\bchat\s*gpt\b", re.IGNORECASE), "chat gpt"),
    (re.compile(r"\bopenai\b", re.IGNORECASE), "openai"),
    (re.compile(r"\bia generativa\b", re.IGNORECASE), "ia generativa"),
    (re.compile(r"(?<![A-Za-zÀ-ÿ])IA(?![A-Za-zÀ-ÿ])"), "IA"),
)

_MONTHS_EN = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}

_MONTHS_PT = {
    "janeiro": 1,
    "fevereiro": 2,
    "marco": 3,
    "março": 3,
    "abril": 4,
    "maio": 5,
    "junho": 6,
    "julho": 7,
    "agosto": 8,
    "setembro": 9,
    "outubro": 10,
    "novembro": 11,
    "dezembro": 12,
}

_CITY_STOP = {
    "instagram",
    "mentor",
    "mentora",
    "mentoria",
    "contadores",
    "contador",
    "linkedin",
    "brasil",
    "hotmart",
    "youtube",
}


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    text = html.unescape(value)
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\xa0", " ").replace("\u200b", "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def fold(value: str | None) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.casefold()
    text = re.sub(r"[^a-z0-9./@]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_followers(text: str) -> tuple[int | None, bool]:
    """Devolve (número, arredondado).

    `18K Followers` vira (18000, True). `1,075 seguidores` vira (1075, False).
    Sem menção a seguidores, devolve (None, False).
    """
    match = _FOLLOWER_RE.search(text or "")
    if not match:
        return None, False
    number = _parse_follower_number(match.group("num"), match.group("suf") or "")
    if number is None:
        return None, False
    rounded = bool(match.group("suf"))
    return number, rounded


def followers_label(number: int | None, rounded: bool) -> str:
    if number is None:
        return ""
    return f"~{number}" if rounded else str(number)


def _parse_follower_number(raw_number: str, suffix: str) -> int | None:
    raw = raw_number.strip().replace(" ", "")
    suffix = suffix.lower()
    try:
        if suffix == "mil":
            return int(float(raw.replace(".", "").replace(",", ".")) * 1000)
        if suffix in {"k", "m"}:
            value = float(raw.replace(",", "."))
            factor = 1000 if suffix == "k" else 1_000_000
            return int(value * factor)
        if re.fullmatch(r"\d{1,3}(\.\d{3})+", raw):
            return int(raw.replace(".", ""))
        if re.fullmatch(r"\d{1,3}(,\d{3})+", raw):
            return int(raw.replace(",", ""))
        if re.fullmatch(r"\d+", raw):
            return int(raw)
    except ValueError:
        return None
    return None


def find_city_uf(text: str) -> str:
    for city, uf in _CITY_RE.findall(text or ""):
        if uf not in UFS:
            continue
        if fold(city) in _CITY_STOP:
            continue
        if any(char.isdigit() for char in city):
            continue
        return f"{city}/{uf}"
    return ""


def ia_evidence(text: str) -> str:
    """Trecho curto se o texto fala de IA. Vazio se não houver menção."""
    source = clean_text(text)
    if not source:
        return ""
    for pattern, _label in _AI_PHRASES:
        match = pattern.search(source)
        if not match:
            continue
        start = max(0, match.start() - 50)
        end = min(len(source), match.end() + 70)
        snippet = source[start:end].strip(" -|.,;:")
        snippet = re.sub(r"\s+", " ", snippet)
        if len(snippet) > 160:
            snippet = snippet[:157].rstrip() + "..."
        return snippet
    return ""


def menciona_ia_field(text: str, inspected: bool) -> str:
    evidence = ia_evidence(text)
    if evidence:
        return f"sim: {evidence}"
    if inspected:
        return "não: sem menção de IA na bio, na página ou nos trechos consultados"
    return ""


def parse_post_date(text: str) -> datetime | None:
    english = re.search(
        r"\bon\s+([A-Za-z]+)\s+(\d{1,2}),\s+(\d{4})",
        text or "",
        re.IGNORECASE,
    )
    if english:
        month = _MONTHS_EN.get(english.group(1).lower())
        if month:
            try:
                return datetime(int(english.group(3)), month, int(english.group(2)))
            except ValueError:
                return None
    portuguese = re.search(
        r"\bem\s+(\d{1,2})\s+de\s+([A-Za-zçÇ]+)\s+de\s+(\d{4})",
        text or "",
        re.IGNORECASE,
    )
    if portuguese:
        month = _MONTHS_PT.get(portuguese.group(2).lower())
        if month:
            try:
                return datetime(int(portuguese.group(3)), month, int(portuguese.group(1)))
            except ValueError:
                return None
    return None


def quoted_snippet(text: str, limit: int = 220) -> str:
    source = clean_text(text).replace('""', '"')
    chosen = ""
    instagram_quote = re.search(r"Instagram\s*:\s*[\"“]+(.+?)[\"”]+", source, re.IGNORECASE)
    if instagram_quote:
        chosen = instagram_quote.group(1)
    if not chosen:
        quotes = re.findall(r"[“\"]([^”\"]{12,400})[”\"]", source)
        if quotes:
            chosen = max(quotes, key=len)
    if not chosen and re.search(r"instagram\s*:", source, re.IGNORECASE):
        chosen = re.split(r"Instagram\s*:\s*", source, flags=re.IGNORECASE)[-1]
    if not chosen:
        chosen = re.sub(
            r"^.*?\d[\d.,]*\s*[KkMm]?\s*(?:followers|seguidores)\b.{0,90}?[–-]\s*",
            "",
            source,
            count=1,
            flags=re.IGNORECASE,
        )
    chosen = chosen.strip(" |“”\"'-–—")
    chosen = re.sub(r"\s+", " ", chosen)
    if len(chosen) > limit:
        chosen = chosen[: limit - 1].rstrip() + "…"
    return chosen


def excel_safe(value: str) -> str:
    # @ é o prefixo do handle e não pode virar aspas. =, + e - abrem fórmula no Excel.
    if value and value[0] in "=+-":
        return "'" + value
    return value
