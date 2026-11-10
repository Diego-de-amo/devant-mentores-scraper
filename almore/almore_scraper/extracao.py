"""Extração de campos a partir de HTML, títulos e snippets. Não completa lacunas."""

from __future__ import annotations

import base64
import html
import json
import re
import urllib.parse
from dataclasses import dataclass, field
from datetime import date, timedelta

from bs4 import BeautifulSoup

from almore_scraper.cidades import UFS, extrair_cidade
from almore_scraper.util_texto import dobrar, espacos, tokens_nome

_HANDLE = re.compile(r"^[A-Za-z0-9._]{2,30}$")
RESERVADOS = {
    "p", "reel", "reels", "stories", "explore", "accounts", "about", "directory",
    "legal", "developer", "tv", "tags", "locations", "instagram", "facebook",
    "meta", "share", "challenge", "direct", "emails", "privacy", "safety",
    "nametag", "popular", "web", "oauth", "ads", "api", "graphql", "www",
    "com", "stories", "live", "ar", "guides",
}

_MESES = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5, "junho": 6,
    "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
}

PALAVRAS_NEGOCIO = {
    "mentoria", "mentor", "mentora", "negocio", "negocios", "loja", "lojas", "auto",
    "autopecas", "ecommerce", "digital", "marketing", "escola", "grupo", "programa",
    "metodo", "restaurante", "restaurantes", "academia", "curso", "cursos", "online",
    "brasil", "hotmart", "instagram", "empresa", "empresas", "gestao", "vendas",
    "shop", "store", "oficial", "consultoria", "treinamento", "treinamentos",
}

PLATAFORMAS = {
    "hotmart.com", "kiwify.com.br", "eduzz.com", "monetizze.com.br", "braip.com",
    "herospark.com", "tmb.com.br", "greenn.com.br", "linktr.ee", "beacons.ai",
    "bio.site", "taplink.cc",
}

DOMINIOS_SEM_SITE = {
    "instagram.com", "facebook.com", "fb.com", "tiktok.com", "twitter.com", "x.com",
    "youtube.com", "youtu.be", "linkedin.com", "pinterest.com", "reddit.com",
    "quora.com", "wikipedia.org", "google.com", "bing.com", "duckduckgo.com",
    "whatsapp.com", "wa.me", "t.me", "medium.com", "amazon.com", "amazon.com.br",
    "mercadolivre.com.br", "shopee.com.br", "sebrae.com.br", "gov.br", "senac.br",
    "senai.br", "globo.com", "uol.com.br", "terra.com.br", "exame.com",
    "infomoney.com.br", "estadao.com.br", "folha.uol.com.br", "veja.abril.com.br",
    "startse.com", "ecommercebrasil.com.br", "pegn.globo.com", "forbes.com.br",
    "istoedinheiro.com.br", "metropoles.com", "r7.com", "ig.com.br",
    "catho.com.br", "gupy.io", "indeed.com", "glassdoor.com", "glassdoor.com.br",
    "contabeis.com.br", "jornalcontabil.com.br", "portalcontabil.com.br",
}

_GENERICOS = re.compile(
    r"^(o que e|como |guia |por que|mentoria para|mentor para|programa de mentoria para|"
    r"curso de|artigo|blog\b|home\b|inicio\b|confira|veja |descubra|lista |ranking\b|melhores |\d+ )"
)


@dataclass
class Pagina:
    titulo: str = ""
    descricao: str = ""
    texto: str = ""
    handles: list[tuple[str, str]] = field(default_factory=list)
    linkedins: list[str] = field(default_factory=list)
    cidade_uf: str = ""
    nome_json: str = ""
    site_json: str = ""


def host_de(url: str) -> str:
    bruto = urllib.parse.urlparse(url).hostname or ""
    host = bruto.lower().rstrip(".")
    if host.startswith("www."):
        host = host[4:]
    return host


def host_e(host: str, dominios: set[str]) -> bool:
    return any(host == dominio or host.endswith("." + dominio) for dominio in dominios)


DOMINIOS_MEGA = {
    "amazon.com", "amazon.com.br", "g4business.com", "g4educacao.com",
    "mercadolivre.com.br", "shopee.com.br", "magazineluiza.com.br", "ifood.com.br",
}


def dominio_mega(url: str) -> bool:
    return host_e(host_de(url), DOMINIOS_MEGA)


def url_http(url: str) -> bool:
    esquema = urllib.parse.urlparse(url or "").scheme.lower()
    return esquema in {"http", "https"} and bool(host_de(url))


def dominio_contabil(url: str) -> bool:
    host = host_de(url)
    return any(pedaço in host for pedaço in ("contabil", "contador", "contadora"))


def plataforma(url: str) -> bool:
    return host_e(host_de(url), PLATAFORMAS)


def serve_como_site(url: str) -> bool:
    if not url_http(url):
        return False
    host = host_de(url)
    if not host or plataforma(url) or dominio_contabil(url):
        return False
    return not host_e(host, DOMINIOS_SEM_SITE)


def origem_do_site(url: str) -> str:
    if not serve_como_site(url):
        return ""
    partes = urllib.parse.urlparse(url)
    return f"{partes.scheme}://{partes.netloc}/"


def limpar_url_ddg(href: str) -> str:
    href = html.unescape((href or "").strip())
    if href.startswith("//"):
        href = "https:" + href
    if not href:
        return ""
    partes = urllib.parse.urlparse(href)
    host = (partes.hostname or "").lower()
    if "duckduckgo.com" in host:
        if "ad_domain" in href or partes.path.startswith("/y.js"):
            return ""
        if partes.path.startswith("/l/"):
            destino = (urllib.parse.parse_qs(partes.query).get("uddg") or [""])[0]
            return urllib.parse.unquote(destino) if destino else ""
        return ""
    if href.startswith("http://") or href.startswith("https://"):
        return href
    return ""


def decodificar_bing(url: str) -> str:
    bruto = html.unescape(url or "")
    partes = urllib.parse.urlparse(bruto)
    codificado = (urllib.parse.parse_qs(partes.query).get("u") or [""])[0]
    if not codificado:
        return ""
    carga = codificado[2:] if codificado.startswith("a1") else codificado
    carga += "=" * ((4 - len(carga) % 4) % 4)
    try:
        destino = base64.b64decode(carga).decode("utf-8", "replace")
    except Exception:
        return ""
    return destino if url_http(destino) else ""


def handle_valido(handle: str) -> str:
    handle = (handle or "").strip().strip(".")
    if not _HANDLE.match(handle):
        return ""
    if handle.casefold() in RESERVADOS:
        return ""
    return handle


def handle_de_url(url: str) -> str:
    if not url or "instagram.com" not in url.lower():
        return ""
    match = re.search(r"instagram\.com/(?:@)?([A-Za-z0-9._]{2,30})(?:[/?#]|$)", html.unescape(url), re.I)
    if not match:
        return ""
    return handle_valido(match.group(1))


def handle_de_titulo(titulo: str) -> str:
    match = re.search(r"\(@([A-Za-z0-9._]{2,30})\)", titulo or "")
    if not match:
        return ""
    return handle_valido(match.group(1))


def url_e_perfil(url: str, handle: str) -> bool:
    if not handle:
        return False
    caminho = urllib.parse.urlparse(url).path.strip("/")
    return caminho.lower() in {handle.lower(), f"{handle.lower()}/reels"}


def linkedin_de_url(url: str) -> str:
    match = re.search(r"linkedin\.com/(in|company)/([A-Za-z0-9\-_%]+)", html.unescape(url or ""), re.I)
    if not match:
        return ""
    tipo, slug = match.group(1).lower(), urllib.parse.unquote(match.group(2)).strip("/")
    if slug.lower() in {"pub", "dir", "jobs", "search"}:
        return ""
    return f"https://www.linkedin.com/{tipo}/{slug}"


def preferir_linkedin(atual: str, novo: str) -> str:
    if not novo:
        return atual
    if not atual:
        return novo
    if "/in/" in novo and "/company/" in atual:
        return novo
    return atual


def parse_seguidores(texto: str) -> int | None:
    if not texto:
        return None
    dobrado = dobrar(texto)
    unidade = re.search(
        r"(\d+(?:[.,]\d+)?)\s*(k|mil|milhao|milhoes|m|mi)\s*(?:de\s+)?(followers|seguidores)\b",
        dobrado,
    )
    if unidade:
        return _escalar(unidade.group(1), unidade.group(2))
    milhar = re.search(r"(\d{1,3}(?:[.,]\d{3})+)\s*(followers|seguidores)\b", dobrado)
    if milhar:
        return int(re.sub(r"[.,]", "", milhar.group(1)))
    simples = re.search(r"(\d+)\s*(followers|seguidores)\b", dobrado)
    if simples:
        return int(simples.group(1))
    return None


def _escalar(numero: str, unidade: str) -> int | None:
    multiplicador = 1000 if unidade in {"k", "mil"} else 1_000_000
    if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", numero):
        base = float(int(re.sub(r"[.,]", "", numero)))
    else:
        base = float(numero.replace(",", "."))
    valor = int(round(base * multiplicador))
    if valor < 0 or valor > 500_000_000:
        return None
    return valor


def extrair_data(texto: str) -> date | None:
    if not texto:
        return None
    ingles = re.search(
        r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),\s+(\d{4})",
        texto,
        re.I,
    )
    if ingles:
        try:
            return date(int(ingles.group(3)), _MESES[ingles.group(1).lower()], int(ingles.group(2)))
        except ValueError:
            return None
    portugues = re.search(
        r"\b(\d{1,2})\s+de\s+(janeiro|fevereiro|mar[cç]o|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)\s+de\s+(\d{4})",
        texto,
        re.I,
    )
    if portugues:
        mes = dobrar(portugues.group(2))
        try:
            return date(int(portugues.group(3)), _MESES[mes], int(portugues.group(1)))
        except (KeyError, ValueError):
            return None
    return None


def post_aproveitavel(texto: str, hoje: date, meses: int = 18) -> bool:
    encontrada = extrair_data(texto)
    if encontrada is None:
        return True
    return encontrada >= hoje - timedelta(days=30 * meses)


def legenda_de_snippet(snippet: str, titulo: str) -> str:
    match = re.search(r":\s*[\"“](.+)", snippet or "")
    bruto = match.group(1) if match else ""
    if not bruto:
        return ""
    bruto = html.unescape(bruto).strip(" \"”")
    bruto = espacos(bruto)
    bruto = re.sub(r"(\.\.\.|…)\s*$", "", bruto).strip()
    if dobrar(bruto) in {"instagram", "post", "reel"}:
        return ""
    return bruto[:140]


def formatar_posts(pares: list[tuple[str, str]]) -> str:
    partes: list[str] = []
    for url, legenda in pares[:3]:
        if not url:
            continue
        partes.append(f"{url} | {legenda}" if legenda else url)
    return " ;; ".join(partes)


def url_de_post(url: str) -> str:
    match = re.search(r"instagram\.com/(p|reel|reels)/([A-Za-z0-9_-]{5,})", url or "", re.I)
    if not match:
        return ""
    tipo = "reel" if match.group(1).lower().startswith("reel") else "p"
    return f"https://www.instagram.com/{tipo}/{match.group(2)}/"


def post_do_handle(url: str, texto: str, handle: str) -> bool:
    if not url_de_post(url) or not handle:
        return False
    return handle.casefold() in dobrar(texto or "")


def parece_pessoa(nome: str) -> bool:
    from almore_scraper.util_texto import PARTICULAS, tokens_nome

    tokens = tokens_nome(nome)
    if not (2 <= len(tokens) <= 5):
        return False
    if any(token in PALAVRAS_NEGOCIO for token in tokens):
        return False
    originais = [parte for parte in (nome or "").replace("’", "'").split() if dobrar(parte) not in PARTICULAS]
    if len(originais) < 2:
        return False
    for parte in originais:
        limpo = parte.strip(".,;:|()[]")
        if not limpo or not limpo[0].isupper():
            return False
    return True


_TOKENS_GENERICOS = {
    "mentoria", "mentor", "mentora", "para", "donos", "dono", "empresario", "empresarios",
    "empresarial", "programa", "curso", "cursos", "online", "brasil", "negocio", "negocios",
    "como", "guia", "melhores", "metodo", "comunidade", "escola", "imersao", "jornada",
    "clube", "treinamento", "treinamentos", "consultoria", "empresa", "empresas", "digital",
    "marketing", "grupo", "oficial", "seu", "sua", "sobre", "com", "dos", "das",
}

_SIGLA = re.compile(r"\b[a-z]\.(?:[a-z]\.){1,}")


def nome_generico(nome: str) -> bool:
    dobrado = dobrar(espacos(nome))
    if dobrado in {"mentoria", "mentor", "mentora", "instagram", "linkedin", "hotmart", "blog", "artigo"}:
        return True
    if _GENERICOS.match(dobrado):
        return True
    if _SIGLA.search(dobrado):
        return False
    distintivos = [token for token in tokens_nome(nome) if token not in _TOKENS_GENERICOS and len(token) >= 3]
    if re.match(r"^(mentoria|mentor|metodo|programa|curso|comunidade|escola|jornada|clube)\b", dobrado):
        return not distintivos
    return False


def nome_aceitavel(nome: str) -> bool:
    limpo = espacos(nome)
    if len(limpo) < 3 or len(limpo) > 120 or limpo.count(" ") > 12:
        return False
    if "," in limpo or "(@" in limpo:
        return False
    if nome_generico(limpo) or nome_e_contabilidade(limpo):
        return False
    if re.fullmatch(r"https?://\S+", limpo):
        return False
    if dobrar(limpo) in {"mercado livre", "shopee", "amazon", "hotmart", "instagram", "facebook"}:
        return False
    if dobrar(limpo).startswith(("a plataforma", "o programa que", "clique ", "saiba ")):
        return False
    if re.search(r"\b(entenda como|saiba como|veja como|confira como)\b", dobrar(limpo)):
        return False
    tokens = [token for token in tokens_nome(limpo) if len(token) >= 3]
    if tokens and all(token.startswith("mentor") for token in tokens):
        return False
    return True


def nome_e_contabilidade(nome: str) -> bool:
    return bool(re.search(r"\b(contabilidade|contabil|escritorio contabil)\b", dobrar(nome or "")))


def nome_de_titulo(titulo: str) -> str:
    texto = re.sub(r"\s*\(@.*$", "", titulo or "")
    texto = re.sub(
        r"\s*[\-–|•·]\s*(Instagram|LinkedIn|Facebook|YouTube|Hotmart|Kiwify|Eduzz)\b.*$",
        "",
        texto,
        flags=re.I,
    )
    texto = re.sub(r"\s*\(@[^)]+\)", "", texto)
    texto = espacos(texto)
    partes = [espacos(parte) for parte in re.split(r"\s+[|•·\-–]\s+", texto) if espacos(parte)]
    pessoas = [parte for parte in partes if parece_pessoa(parte) and nome_aceitavel(parte)]
    if pessoas:
        return pessoas[0]
    for parte in partes:
        if nome_aceitavel(parte):
            return parte
    if nome_aceitavel(texto):
        return texto
    return ""


def pessoa_de_texto(texto: str) -> str:
    padroes = [
        r"(?:criad[oa]|fundad[oa]|desenvolvid[oa])\s+por\s+([A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÁÉÍÓÚÂÊÔÃÕÇáéíóúâêôãõç.'’-]+(?:\s+(?:da|de|do|dos|das|e)\s+|\s+)[A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÁÉÍÓÚÂÊÔÃÕÇáéíóúâêôãõç.'’-]+)",
        r"\b([A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÁÉÍÓÚÂÊÔÃÕÇáéíóúâêôãõç.'’-]+\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÁÉÍÓÚÂÊÔÃÕÇáéíóúâêôãõç.'’-]+)\s*,?\s+fundador(?:a)?\b",
    ]
    for padrao in padroes:
        match = re.search(padrao, texto or "")
        if match and parece_pessoa(match.group(1)) and nome_aceitavel(match.group(1)):
            return espacos(match.group(1))
    return ""


def extrair_programa(texto: str) -> str:
    if not texto:
        return ""
    match = re.search(
        r"\b((?:M[eé]todo|Programa|Comunidade|Imers[aã]o|Jornada|Clube|Escola|Mentoria)\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ0-9][^|\n]{2,90})",
        texto,
    )
    if not match:
        return ""
    frase = re.split(r"\s+[|•·\-–]\s+", espacos(match.group(1)))[0]
    frase = re.sub(r"\s+(Hotmart|Kiwify|Eduzz|Instagram|LinkedIn)\b.*$", "", frase, flags=re.I).strip(" .")
    if dobrar(frase) in {"mentoria", "metodo", "programa", "comunidade", "escola", "clube", "jornada", "imersao"}:
        return ""
    if len(frase) < 8:
        return ""
    return frase[:120]


def bio_de_snippet(snippet: str) -> str:
    match = re.search(r"on Instagram:\s*[\"“](.+)", snippet or "", re.I)
    if not match:
        match = re.search(r"no Instagram:\s*[\"“](.+)", snippet or "", re.I)
    if not match:
        return ""
    return espacos(html.unescape(match.group(1)).strip(" \"”"))[:500]


def eh_anomalia_ddg(html_texto: str) -> bool:
    return "bots use DuckDuckGo" in (html_texto or "") or "anomaly-modal" in (html_texto or "")


def parse_ddg(html_texto: str) -> tuple[list[tuple[str, str, str]], dict[str, str]]:
    soup = BeautifulSoup(html_texto or "", "html.parser")
    achados: list[tuple[str, str, str]] = []
    for ancora in soup.select("a.result__a"):
        pai = ancora.find_parent(class_="result")
        classes = pai.get("class", []) if pai else []
        if "result--ad" in classes:
            continue
        url = limpar_url_ddg(ancora.get("href") or "")
        if not url:
            continue
        snippet = ""
        if pai:
            bloco = pai.select_one(".result__snippet")
            if bloco:
                snippet = bloco.get_text(" ", strip=True)
        achados.append((ancora.get_text(" ", strip=True), url, snippet))
    formulario: dict[str, str] = {}
    for form in soup.select("form"):
        if form.select_one('input[name="vqd"]'):
            for campo in form.select("input[name]"):
                if (campo.get("type") or "").lower() == "submit":
                    continue
                formulario[campo["name"]] = campo.get("value") or ""
            break
    return achados, formulario


def parse_bing(html_texto: str) -> list[tuple[str, str, str]]:
    soup = BeautifulSoup(html_texto or "", "html.parser")
    achados: list[tuple[str, str, str]] = []
    for bloco in soup.select("li.b_algo"):
        titulo_tag = bloco.select_one("h2")
        ancora = titulo_tag.find("a") if titulo_tag else None
        if ancora is None:
            continue
        url = decodificar_bing(ancora.get("href") or "")
        if not url:
            continue
        snippet_tag = bloco.select_one("p")
        achados.append(
            (
                titulo_tag.get_text(" ", strip=True) if titulo_tag else "",
                url,
                snippet_tag.get_text(" ", strip=True) if snippet_tag else "",
            )
        )
    return achados


_PARADA_RELEVANCIA = {
    "para", "com", "dos", "das", "uma", "por", "que", "empresarios", "empresario",
    "donos", "dono", "mentor", "mentoria", "brasil", "programa", "como", "mais",
}


def relevante(resultados: list[tuple[str, str, str]], consulta: str) -> bool:
    if not resultados:
        return False
    termos = [
        token
        for token in re.sub(r"[^a-z0-9]+", " ", dobrar(consulta)).split()
        if len(token) >= 4 and token not in _PARADA_RELEVANCIA
    ]
    bons = 0
    for titulo, url, snippet in resultados:
        blob = dobrar(f"{titulo} {snippet} {url}")
        if termos and any(termo in blob for termo in termos[:4]):
            bons += 1
        elif not termos and ("mentoria" in blob or "mentor" in blob):
            bons += 1
    return bons >= 1 and bons * 5 >= len(resultados)


def _mesmo_as(valor: object) -> list[str]:
    if isinstance(valor, str):
        return [valor]
    if isinstance(valor, list):
        return [item for item in valor if isinstance(item, str)]
    return []


def _andar_jsonld(objeto: object):
    if isinstance(objeto, list):
        for item in objeto:
            yield from _andar_jsonld(item)
    elif isinstance(objeto, dict):
        yield objeto
        if "@graph" in objeto:
            yield from _andar_jsonld(objeto["@graph"])


def analisar_html(html_texto: str, url: str) -> Pagina:
    soup = BeautifulSoup(html_texto or "", "html.parser")
    pagina = Pagina()
    if soup.title:
        pagina.titulo = soup.title.get_text(" ", strip=True)
    for atributo in ({"name": "description"}, {"property": "og:description"}):
        meta = soup.find("meta", attrs=atributo)
        if meta and meta.get("content"):
            pagina.descricao = espacos(meta["content"])
            break

    for script in soup.select('script[type="application/ld+json"]'):
        try:
            carga = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        for nodo in _andar_jsonld(carga):
            if not pagina.nome_json and isinstance(nodo.get("name"), str):
                pagina.nome_json = espacos(nodo["name"])
            endereco = nodo.get("address")
            if isinstance(endereco, dict) and not pagina.cidade_uf:
                local = endereco.get("addressLocality") or ""
                regiao = str(endereco.get("addressRegion") or "")
                if local and regiao.upper() in UFS:
                    pagina.cidade_uf = f"{espacos(str(local))}/{regiao.upper()}"
                elif local:
                    pagina.cidade_uf = extrair_cidade(f"{local} {regiao}")
            for destino in _mesmo_as(nodo.get("sameAs")) + _mesmo_as(nodo.get("url")):
                handle = handle_de_url(destino)
                if handle:
                    pagina.handles.append((handle, pagina.nome_json or pagina.titulo))
                linkedin = linkedin_de_url(destino)
                if linkedin:
                    pagina.linkedins.append(linkedin)
                if serve_como_site(destino) and not pagina.site_json:
                    pagina.site_json = origem_do_site(destino)

    for ancora in soup.find_all("a", href=True):
        if ancora.find_parent(["nav", "footer", "header"]):
            continue
        href = urllib.parse.urljoin(url, ancora["href"])
        handle = handle_de_url(href)
        if handle:
            pagina.handles.append((handle, _contexto_ancora(ancora)))
        linkedin = linkedin_de_url(href)
        if linkedin:
            pagina.linkedins.append(linkedin)

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    pagina.texto = espacos(soup.get_text(" ", strip=True))[:5000]
    if not pagina.cidade_uf:
        pagina.cidade_uf = extrair_cidade(" ".join(parte for parte in (pagina.descricao, pagina.texto[:1500]) if parte))
    # Handles repetidos: preserva o primeiro contexto não vazio.
    vistos: dict[str, str] = {}
    for handle, contexto in pagina.handles:
        chave = handle.lower()
        if chave not in vistos or (not vistos[chave] and contexto):
            vistos[chave] = contexto
    pagina.handles = [(handle, contexto) for handle, contexto in vistos.items()]
    pag_links: list[str] = []
    for link in pagina.linkedins:
        if link not in pag_links:
            pag_links.append(link)
    pagina.linkedins = pag_links
    return pagina


def _contexto_ancora(ancora) -> str:
    texto_ancora = ancora.get_text(" ", strip=True)
    nodo = ancora
    for _ in range(4):
        if nodo is None:
            break
        irmao = nodo.find_previous_sibling(["h1", "h2", "h3", "h4", "strong", "p"])
        if irmao:
            texto = irmao.get_text(" ", strip=True)
            if texto and texto != texto_ancora:
                return espacos(texto)[:160]
        nodo = nodo.parent
    return espacos(texto_ancora)[:160]


def artigo_generico(titulo: str) -> bool:
    return bool(re.match(r"^(o que [eé]|como (escolher|encontrar|funciona|fazer)|guia completo|por que)\b", espacos(titulo), re.I))
