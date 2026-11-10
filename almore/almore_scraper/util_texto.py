"""Normalização de texto em português."""

from __future__ import annotations

import re
import unicodedata

PARTICULAS = {"da", "de", "do", "dos", "das", "e", "di", "du"}


def dobrar(texto: str) -> str:
    """Minúsculas sem acento, para comparação."""
    base = unicodedata.normalize("NFKD", texto or "")
    sem = "".join(caractere for caractere in base if not unicodedata.combining(caractere))
    return sem.casefold()


def espacos(texto: str) -> str:
    return re.sub(r"\s+", " ", texto or "").strip()


def uma_linha(texto: str, limite: int) -> str:
    limpo = espacos(texto)
    if len(limpo) <= limite:
        return limpo
    return limpo[: limite - 1].rstrip() + "…"


def tokens_nome(nome: str) -> list[str]:
    partes = re.sub(r"[^a-z0-9]+", " ", dobrar(nome)).split()
    return [parte for parte in partes if parte not in PARTICULAS and len(parte) >= 2]


def chave_pessoa(nome: str) -> str:
    tokens = [token for token in tokens_nome(nome) if len(token) >= 3]
    if len(tokens) < 2:
        return ""
    return " ".join(tokens)


def frase_no_trecho(texto: str, inicio: int, fim: int, limite: int = 180) -> str:
    if not texto:
        return ""
    esquerda = max(texto.rfind(".", 0, inicio), texto.rfind("!", 0, inicio), texto.rfind("?", 0, inicio), texto.rfind("\n", 0, inicio))
    ini = 0 if esquerda < 0 else esquerda + 1
    direita_candidatos = [pos for pos in (texto.find(".", fim), texto.find("!", fim), texto.find("?", fim), texto.find("\n", fim)) if pos >= 0]
    fin = min(direita_candidatos) + 1 if direita_candidatos else min(len(texto), fim + 80)
    return uma_linha(texto[ini:fin], limite)
