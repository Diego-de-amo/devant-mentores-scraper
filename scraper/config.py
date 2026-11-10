"""Limites, consultas e exclusões da busca diária."""

from __future__ import annotations

MAX_NOVOS = 20
MAX_FOLLOWERS = 50_000
MIN_QUERIES = 8
MAX_QUERIES = 14
STOP_AFTER_NOVOS = 28
MAX_PAGE_FETCHES = 10
MAX_IG_PROFILES = 12
SEARCH_PAUSE_SECONDS = 3.2
PAGE_PAUSE_SECONDS = 1.2
IG_PAUSE_SECONDS = 12.0

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

COLUMNS = [
    "nome",
    "instagram_handle",
    "instagram_url",
    "linkedin_url",
    "site",
    "tema",
    "cidade_uf",
    "seguidores",
    "menciona_ia",
    "ultimos_posts",
    "fonte_url",
    "data_entrada",
]

# Consultas genéricas em português. A primeira página de cada uma basta:
# a página 2 do DuckDuckGo HTML repetiu a primeira neste tipo de IP.
QUERIES = [
    "mentor de contadores instagram",
    "mentora de contadores instagram",
    "mentoria para contadores",
    "mentoria para escritório contábil",
    "mentor para contadores instagram",
    "comunidade de contadores mentoria",
    "mentoria para contadores hotmart",
    "donos de escritório contábil mentoria",
    "mentoria contábil hotmart",
    "marketing para contadores mentoria instagram",
    "imersão para contadores escritório",
    "mentor de contadores linkedin",
    "clube de contadores comunidade mentoria",
    "programa de mentoria escritórios contábeis",
]

# Nomes que a Devant não quer abordar, mesmo que um dia saiam do mestre.
BLOCKED_NAMES = [
    "anderson hernandes",
    "fellipe guerra",
    "felipe guerra",
    "lucas lima",
    "contador revoltado",
    "lucas presa de lima",
    "anderson souza",
    "elcio guioto",
]

BLOCKED_HANDLES = [
    "andersonhernandesoficial",
    "contadorevoltado",
    "prof.fellipeguerra",
]

UFS = {
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS",
    "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC",
    "SP", "SE", "TO",
}

SKIP_HOSTS = {
    "duckduckgo.com",
    "html.duckduckgo.com",
    "yahoo.com",
    "search.yahoo.com",
    "br.search.yahoo.com",
    "r.search.yahoo.com",
    "google.com",
    "webcache.googleusercontent.com",
    "canva.com",
    "imginn.com",
    "picuki.com",
    "dumpor.com",
    "greatfon.com",
    "pixwox.com",
    "facebook.com",
    "tiktok.com",
    "wikipedia.org",
    "amazon.com",
    "pinterest.com",
    "twitter.com",
    "x.com",
}

ARTICLE_PATH_MARKERS = (
    "/blog/",
    "/noticias/",
    "/noticia/",
    "/news/",
    "/forum/",
    "/posts-para-",
    "/artigo/",
)

NEGATIVE_TITLE_PHRASES = (
    "guia completo",
    "o que e ",
    "como escolher",
    "como usar",
    "melhores influenciadores",
    "dicas de",
    "ideias de post",
    "100 ideias",
    "referencias no mercado",
)

STRONG_PHRASES = (
    "mentor de contadores",
    "mentora de contadores",
    "mentor de contadoras",
    "mentora de contadoras",
    "mentor para contadores",
    "mentora para contadores",
    "mentor para contadoras",
    "mentora para contadoras",
    "mentoria para contadores",
    "mentoria para contadoras",
    "mentoria para escritorios",
    "mentor de escritorios",
    "mentoria para donos de escritorio",
    "donos de escritorio contabil",
    "empresarios contabeis",
)

OFFER_WORDS = (
    "mentoria",
    "curso",
    "comunidade",
    "imersao",
    "formacao",
    "metodo",
    "clube",
    "hotmart",
    "turma",
)

AUDIENCE_PHRASES = (
    "contadores",
    "contador",
    "contadoras",
    "contadora",
    "escritorios contabeis",
    "escritorio contabil",
    "contabilista",
    "contabilistas",
)

ROLE_WORDS = {
    "mentor",
    "mentora",
    "mentores",
    "mentoria",
    "mentorias",
    "contador",
    "contadora",
    "contadores",
    "contadoras",
    "contabil",
    "curso",
    "cursos",
    "comunidade",
    "instagram",
    "oficial",
    "para",
    "por",
    "com",
    "sem",
    "de",
    "do",
    "da",
    "dos",
    "das",
    "e",
    "em",
    "no",
    "na",
    "os",
    "as",
    "um",
    "uma",
    "the",
    "and",
    "metodologia",
    "metodo",
    "programa",
    "imersao",
    "formacao",
    "hotmart",
    "linkedin",
    "youtube",
    "facebook",
    "instagram",
    "escritorio",
    "escritorios",
    "tributaria",
    "tributario",
    "digital",
    "online",
}

GENERIC_HOST_LABELS = {
    "www",
    "com",
    "br",
    "app",
    "blog",
    "loja",
    "mail",
    "instagram",
    "facebook",
    "linkedin",
    "hotmart",
    "linktree",
    "linktr",
    "bio",
    "beacons",
    "youtube",
    "google",
    "wix",
    "wordpress",
    "blogspot",
    "myshopify",
    "canva",
    "medium",
    "contabeis",
    "globo",
    "uol",
    "terra",
    "g1",
}

IG_RESERVED = {
    "p",
    "reel",
    "reels",
    "stories",
    "explore",
    "accounts",
    "about",
    "directory",
    "legal",
    "tv",
    "tags",
    "locations",
    "developer",
    "privacy",
    "share",
    "direct",
    "emails",
    "challenge",
}
