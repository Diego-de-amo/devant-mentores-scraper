"""Transforma resultados de busca em mentores e aplica o filtro."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import unquote, urlsplit

from scraper.config import (
    ARTICLE_PATH_MARKERS,
    AUDIENCE_PHRASES,
    BLOCKED_HANDLES,
    BLOCKED_NAMES,
    GENERIC_HOST_LABELS,
    IG_RESERVED,
    MAX_FOLLOWERS,
    NEGATIVE_TITLE_PHRASES,
    OFFER_WORDS,
    ROLE_WORDS,
    SKIP_HOSTS,
    STRONG_PHRASES,
)
from scraper.search import Hit
from scraper.textutil import (
    clean_text,
    find_city_uf,
    fold,
    followers_label,
    menciona_ia_field,
    parse_followers,
    parse_post_date,
    quoted_snippet,
)

_HANDLE_RE = re.compile(r"^[A-Za-z0-9._]{2,30}$")
_IG_HEAD_RE = re.compile(
    r"[–—-]\s*(?P<name>[^@\n]{2,90}?)\s+\(@(?P<handle>[A-Za-z0-9._]{2,30})\)"
)
_POST_HANDLE_RE = re.compile(
    r"-\s*([A-Za-z0-9._]{2,30})\s+on\s+",
    re.IGNORECASE,
)


@dataclass
class Post:
    url: str
    caption: str
    date: datetime | None
    handle: str


@dataclass
class Mentor:
    nome: str = ""
    instagram_handle: str = ""
    instagram_url: str = ""
    linkedin_url: str = ""
    site: str = ""
    tema: str = ""
    cidade_uf: str = ""
    seguidores: str = ""
    menciona_ia: str = ""
    ultimos_posts: str = ""
    fonte_url: str = ""
    data_entrada: str = ""
    evidence: str = ""
    followers_num: int | None = None
    followers_rounded: bool = False
    tema_rank: int = 0
    inspected_text: bool = False
    fontes: list[str] = field(default_factory=list)
    posts: list[Post] = field(default_factory=list)

    def to_row(self) -> dict[str, str]:
        fontes = []
        for url in self.fontes:
            if url and url not in fontes:
                fontes.append(url)
        self.finalize_text_fields()
        return {
            "nome": self.nome,
            "instagram_handle": self.instagram_handle,
            "instagram_url": self.instagram_url,
            "linkedin_url": self.linkedin_url,
            "site": self.site,
            "tema": self.tema,
            "cidade_uf": self.cidade_uf,
            "seguidores": followers_label(self.followers_num, self.followers_rounded)
            if self.followers_num is not None
            else self.seguidores,
            "menciona_ia": self.menciona_ia,
            "ultimos_posts": self.ultimos_posts,
            "fonte_url": " | ".join(fontes[:4]),
            "data_entrada": self.data_entrada,
        }

    def finalize_text_fields(self) -> None:
        if self.instagram_handle:
            handle = self.instagram_handle.lstrip("@")
            self.instagram_handle = f"@{handle}"
            self.instagram_url = f"https://www.instagram.com/{handle}/"
        if not self.menciona_ia:
            self.menciona_ia = menciona_ia_field(self.evidence, self.inspected_text)
        if not self.cidade_uf:
            self.cidade_uf = find_city_uf(self.evidence)
        if not self.ultimos_posts and self.posts:
            self.ultimos_posts = format_posts(self.posts)
        if self.fontes and not self.fonte_url:
            self.fonte_url = " | ".join(self.fontes[:4])

    def set_followers(self, number: int | None, rounded: bool) -> None:
        if number is None:
            return
        if self.followers_num is None or (self.followers_rounded and not rounded):
            self.followers_num = number
            self.followers_rounded = rounded
            return
        if not self.followers_rounded and rounded:
            return
        self.followers_num = number
        self.followers_rounded = rounded

    def set_tema(self, tema: str, rank: int) -> None:
        tema = clean_text(tema)
        if not tema:
            return
        if rank >= self.tema_rank:
            self.tema = tema
            self.tema_rank = rank

    def add_fonte(self, url: str) -> None:
        url = clean_text(url)
        if url and url not in self.fontes:
            self.fontes.append(url)

    def identity_tokens(self) -> set[str]:
        tokens: set[str] = set()
        handle = self.instagram_handle.lstrip("@").lower()
        compact = re.sub(r"[^a-z0-9]", "", handle)
        if len(compact) >= 8:
            tokens.add(compact)
        for url in [self.site, self.instagram_url, self.linkedin_url, *self.fontes]:
            host = host_of(url)
            if not host:
                continue
            for label in host.split("."):
                token = re.sub(r"[^a-z0-9]", "", label.lower())
                if len(token) >= 12 and token not in GENERIC_HOST_LABELS:
                    tokens.add(token)
        return tokens


def host_of(url: str) -> str:
    if not url:
        return ""
    if "://" not in url:
        url = "https://" + url
    return urlsplit(url).netloc.lower().removeprefix("www.")


def url_kind(url: str) -> str:
    host = host_of(url)
    path = urlsplit(url if "://" in url else "https://" + url).path.lower()
    if not host or any(host == skip or host.endswith("." + skip) for skip in SKIP_HOSTS):
        return "skip"
    if "youtube.com" in host or host == "youtu.be":
        return "skip"
    if any(marker in path for marker in ("/login", "login.php", "/cadastro", "/painel", "/wp-login", "/carrinho")):
        return "skip"
    if "instagram.com" in host:
        parts = [part for part in path.split("/") if part]
        if not parts:
            return "skip"
        if parts[0] in {"p", "reel", "reels", "tv"}:
            return "instagram_post"
        if parts[0] in IG_RESERVED:
            return "skip"
        if len(parts) >= 2 and parts[1] in {"p", "reel", "reels"}:
            return "instagram_post"
        return "instagram_profile"
    if "linkedin.com" in host:
        return "linkedin" if "/in/" in path else "skip"
    if "hotmart.com" in host:
        if "/produtos/" in path or "/products/" in path:
            return "hotmart"
        return "skip"
    if any(marker in path for marker in ARTICLE_PATH_MARKERS):
        return "article"
    return "page"


def instagram_handle_from_url(url: str) -> str:
    parts = [part for part in urlsplit(url).path.split("/") if part]
    if not parts:
        return ""
    if parts[0] in {"p", "reel", "reels", "tv"}:
        return ""
    if parts[0] in IG_RESERVED:
        return ""
    handle = parts[0].strip("~")
    if not _HANDLE_RE.match(handle) or handle.lower() in IG_RESERVED:
        return ""
    return handle


def instagram_post_from_url(url: str) -> tuple[str, str]:
    """Devolve (handle ou '', url canônica do post)."""
    parts = [part for part in urlsplit(url).path.split("/") if part]
    handle = ""
    kind = ""
    code = ""
    if len(parts) >= 2 and parts[0] in {"p", "reel", "reels", "tv"}:
        kind = "reel" if parts[0] in {"reel", "reels", "tv"} else "p"
        code = parts[1]
    elif len(parts) >= 3 and parts[1] in {"p", "reel", "reels"}:
        handle = parts[0].strip("~")
        kind = "reel" if parts[1] in {"reel", "reels"} else "p"
        code = parts[2]
    if not code or not re.fullmatch(r"[A-Za-z0-9_-]{5,}", code):
        return "", ""
    if handle and (not _HANDLE_RE.match(handle) or handle.lower() in IG_RESERVED):
        handle = ""
    canonical = f"https://www.instagram.com/{kind}/{code}/"
    return handle, canonical


def linkedin_url_from(url: str) -> str:
    match = re.search(r"linkedin\.com/in/([^/?#]+)", url or "", re.IGNORECASE)
    if not match:
        return ""
    slug = unquote(match.group(1)).strip("/")
    if len(slug) < 3 or any(char.isspace() for char in slug):
        return ""
    if slug.lower() in {"company", "school", "feed", "posts"}:
        return ""
    return f"https://www.linkedin.com/in/{slug}/"


def looks_like_person(segment: str) -> bool:
    segment = clean_text(segment).strip(" .|-–—")
    if not segment or len(segment) > 70:
        return False
    folded = fold(segment)
    if any(word in folded for word in ("instagram", "linkedin", "hotmart", "youtube", "facebook")):
        return False
    words = [word for word in re.split(r"\s+", segment) if word]
    if not 2 <= len(words) <= 6:
        return False
    meaningful = []
    for word in words:
        token = fold(word).strip(".")
        if token in ROLE_WORDS or len(token) <= 2:
            continue
        if word[:1].isupper():
            meaningful.append(word)
    if len(meaningful) >= 2:
        return True
    initials = [word for word in words if len(fold(word)) == 2 and word.isupper()]
    return len(meaningful) == 1 and bool(initials)


def looks_like_brand(segment: str) -> bool:
    folded = fold(segment)
    return folded.startswith(("instituto ", "comunidade ", "clube ", "programa "))


def pick_name(raw: str, handle: str = "") -> str:
    raw = clean_text(raw)
    raw = re.sub(r"\s+(\.\.\.|…)\s*$", "", raw)
    raw = re.sub(
        r"\s+[-–—|]\s*(Instagram|LinkedIn|Hotmart|YouTube|Facebook)\s*$",
        "",
        raw,
        flags=re.IGNORECASE,
    )
    raw = re.sub(r"\s+I\s+(?=Mentor)", " | ", raw)
    parts = [part.strip(" .|-–—") for part in re.split(r"\s*[|•–—]\s*|\s+-\s+", raw) if part.strip()]
    for part in parts:
        if looks_like_person(part):
            return clean_text(part)
    if handle:
        for part in parts:
            token = part.strip()
            folded = fold(token)
            if (
                token
                and " " not in token
                and token[:1].isupper()
                and folded not in ROLE_WORDS
                and len(token) >= 3
            ):
                return token
    for part in parts:
        if looks_like_brand(part) and len(part.split()) >= 2:
            return clean_text(part)
    return ""


_ORG_TOKENS = {
    "contabilidade",
    "contabil",
    "treinamentos",
    "treinamento",
    "educacao",
    "consultoria",
    "consultiva",
    "consultivo",
    "growth",
    "imersao",
    "mentoria",
    "curso",
    "cursos",
    "private",
    "conselheiro",
    "academia",
    "brasil",
}

_SHARED_PLATFORMS = {
    "hotmart.com",
    "instagram.com",
    "linkedin.com",
    "facebook.com",
    "youtube.com",
    "youtu.be",
    "linktr.ee",
    "wa.me",
    "bit.ly",
    "bio.link",
    "beacons.ai",
}


def wrong_audience(text: str) -> bool:
    """Mentoria para o cliente final (MEI) não é mentoria para contadores."""
    folded = fold(text)
    if not re.search(r"\bmei\b", folded):
        return False
    accountant = any(
        phrase in folded
        for phrase in (
            "contadores",
            "contadoras",
            "escritorio contabil",
            "escritorios contabeis",
            "donos de escritorio",
            "mentor de contador",
            "mentoria para contador",
        )
    )
    return not accountant


def passes_offer(text: str, url: str = "") -> bool:
    folded = fold(text)
    if any(phrase in folded for phrase in STRONG_PHRASES):
        return True
    has_offer = any(word in folded for word in OFFER_WORDS)
    has_audience = any(phrase in folded for phrase in AUDIENCE_PHRASES)
    if has_offer and has_audience:
        return True
    host = host_of(url)
    if "mentoria" in folded and "contabil" in folded and host:
        if host.endswith(".com.br") or host.endswith("hotmart.com") or host.endswith("instagram.com"):
            return True
    return False


_NOT_A_NAME = {
    "melhor",
    "processo",
    "painel",
    "aluno",
    "entrar",
    "cadastro",
    "clique",
    "inscreva",
    "login",
    "inicial",
    "profissional",
    "contabilistas",
}


def _boilerplate(text: str) -> bool:
    folded = fold(text)
    return any(
        phrase in folded
        for phrase in (
            "veja o perfil",
            "1 bilhao",
            "comunidade profissional de",
            "cadastro inicial",
            "entrar no painel",
            "faca login",
            "faca o login",
        )
    )


def _truncated_name(nome: str) -> bool:
    folded = fold(nome)
    if folded.endswith((" para", " de", " com", " e", " do", " da", " em", " no", " na")):
        return True
    return folded.startswith(("entrar ", "programa ", "painel ", "cadastro ", "clique ", "faca login"))


def _org_like_name(nome: str) -> bool:
    tokens = set(fold(nome).split())
    return bool(tokens & _ORG_TOKENS)


def acceptable_name(nome: str, handle: str = "") -> bool:
    nome = clean_text(nome)
    if not nome or _truncated_name(nome):
        return False
    if looks_like_person(nome) and not _org_like_name(nome):
        meaningful = [token for token in fold(nome).split() if token not in ROLE_WORDS and len(token) > 2]
        if meaningful and all(token in _NOT_A_NAME for token in meaningful):
            return False
        return True
    if looks_like_brand(nome) and not _truncated_name(nome):
        rest = [
            token
            for token in fold(nome).split()
            if token not in ROLE_WORDS
            and token not in {"instituto", "comunidade", "clube", "programa"}
            and token not in _ORG_TOKENS
        ]
        return len(rest) >= 1
    token = fold(nome)
    if handle and " " not in token and len(token) >= 4 and token not in ROLE_WORDS and token not in _ORG_TOKENS:
        return True
    return False


def registrable_domain(url: str) -> str:
    host = host_of(url)
    if not host:
        return ""
    if any(host == platform or host.endswith("." + platform) for platform in _SHARED_PLATFORMS):
        return ""
    parts = host.split(".")
    if len(parts) >= 3 and parts[-2:] == ["com", "br"]:
        return ".".join(parts[-3:])
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return host


def negative_title(title: str) -> bool:
    folded = fold(title)
    return any(phrase in folded for phrase in NEGATIVE_TITLE_PHRASES)


def is_foreign(text: str, url: str) -> bool:
    blob = f"{text} {url}"
    lowered = blob.casefold()
    host = host_of(url)
    foreign_hosts = (
        "co.linkedin.com",
        "mx.linkedin.com",
        "ar.linkedin.com",
        "es.linkedin.com",
        "cl.linkedin.com",
        "pe.linkedin.com",
        "pt.linkedin.com",
        "ec.linkedin.com",
    )
    if any(host == item or host.endswith("." + item) for item in foreign_hosts):
        return True
    if host.endswith(".pt") or host.endswith(".com.mx") or host.endswith(".com.ar"):
        return True
    foreign_words = (
        "mentoría",
        "contaduría",
        "méxico",
        "mexico",
        "colombia",
        "argentina",
        "españa",
        "chile",
        "peru",
        "quiero",
        "también",
        "además",
    )
    brazil_words = (
        "brasil",
        ".com.br",
        "você",
        "voce",
        "escritório",
        "escritorio",
        "contábil",
        "são paulo",
        "sao paulo",
        "br.linkedin.com",
    )
    has_foreign = any(word in lowered for word in foreign_words)
    has_brazil = any(word in lowered for word in brazil_words)
    return has_foreign and not has_brazil


def name_is_blocked(nome: str, extra: list[str] | None = None) -> bool:
    tokens = set(fold(nome).split())
    if not tokens:
        return False
    blocked = list(BLOCKED_NAMES)
    if extra:
        blocked.extend(extra)
    for name in blocked:
        parts = fold(name).split()
        if len(parts) >= 2 and all(part in tokens for part in parts):
            return True
        if len(parts) == 1 and fold(nome) == parts[0]:
            return True
    return False


def handle_is_blocked(handle: str, extra: list[str] | None = None) -> bool:
    token = handle.lstrip("@").lower()
    if not token:
        return False
    blocked = {item.lower() for item in BLOCKED_HANDLES}
    if extra:
        blocked.update(item.lstrip("@").lower() for item in extra)
    return token in blocked


def extract_post(hit: Hit) -> Post | None:
    if url_kind(hit.url) != "instagram_post":
        return None
    handle, canonical = instagram_post_from_url(hit.url)
    if not canonical:
        return None
    if not handle:
        match = _POST_HANDLE_RE.search(hit.snippet)
        if match:
            handle = match.group(1)
    caption = quoted_snippet(hit.snippet, limit=180)
    caption = re.sub(
        r"^.*?\bon\s+[A-Za-z]+\s+\d{1,2},\s+\d{4}:\s*",
        "",
        caption,
        count=1,
        flags=re.IGNORECASE,
    )
    caption = caption.strip(" \"“”")
    if len(caption) > 140:
        caption = caption[:139].rstrip() + "…"
    if caption.lower().startswith(("http", "likes", "0 likes")) or _boilerplate(caption):
        caption = ""
    return Post(
        url=canonical,
        caption=caption,
        date=parse_post_date(f"{hit.title} {hit.snippet}"),
        handle=handle.lstrip("@").lower(),
    )


def format_posts(posts: list[Post]) -> str:
    ordered = sorted(
        posts,
        key=lambda post: (post.date is None, -(post.date.toordinal()) if post.date else 0, post.url),
    )
    seen: set[str] = set()
    parts: list[str] = []
    for post in ordered:
        if post.url in seen:
            continue
        seen.add(post.url)
        if post.caption:
            parts.append(f"{post.url} — {post.caption}")
        else:
            parts.append(post.url)
        if len(parts) == 3:
            break
    return " || ".join(parts)


def mentor_from_hit(hit: Hit) -> tuple[Mentor | None, str]:
    kind = url_kind(hit.url)
    if kind in {"skip", "article", "instagram_post"}:
        return None, "fora_do_perfil" if kind == "article" else "url_ignorada"
    title = clean_text(hit.title)
    snippet = clean_text(hit.snippet)
    if negative_title(title):
        return None, "fora_do_perfil"
    evidence = clean_text(f"{title} {snippet}")
    if is_foreign(evidence, hit.url):
        return None, "fora_do_brasil"

    handle = ""
    linkedin = ""
    site = ""
    if kind == "instagram_profile":
        handle = instagram_handle_from_url(hit.url)
        if not handle:
            return None, "sem_nome"
    elif kind == "linkedin":
        linkedin = linkedin_url_from(hit.url)
        if not linkedin:
            return None, "sem_nome"
    elif kind == "hotmart":
        site = hit.url.split("?")[0]
    else:
        site = hit.url.split("?")[0]

    name = ""
    head = _IG_HEAD_RE.search(snippet)
    if head and (not handle or head.group("handle").lower() == handle.lower()):
        name = pick_name(head.group("name"), handle or head.group("handle"))
        if not handle:
            handle = head.group("handle")
    if not name:
        name = pick_name(title, handle)
    if not name:
        name = pick_name(snippet, handle)
    if name_is_blocked(name) or handle_is_blocked(handle):
        return None, "bloqueado"
    if not name or not acceptable_name(name, handle):
        return None, "sem_nome"
    if wrong_audience(evidence) or not passes_offer(evidence, hit.url):
        return None, "fora_do_perfil"

    number, rounded = parse_followers(snippet)
    if number is not None and number > MAX_FOLLOWERS:
        return None, "acima_de_50k"

    mentor = Mentor(
        nome=name,
        evidence=evidence,
        data_entrada="",
    )
    if handle:
        mentor.instagram_handle = f"@{handle}"
        mentor.instagram_url = f"https://www.instagram.com/{handle}/"
    if linkedin:
        mentor.linkedin_url = linkedin
    if site and "instagram.com" not in site and "linkedin.com" not in site:
        mentor.site = site
    mentor.set_followers(number, rounded)
    tema = quoted_snippet(snippet) or title
    if _boilerplate(tema):
        tema = re.sub(r"\s+[-–—|]\s*(Instagram|LinkedIn|Hotmart)\s*$", "", title, flags=re.IGNORECASE)
        tema = re.sub(r"\s+", " ", tema).strip()
    mentor.set_tema(tema, rank=2 if kind == "instagram_profile" else 1)
    mentor.add_fonte(hit.url.split("?")[0] if kind != "instagram_profile" else mentor.instagram_url)
    if kind == "instagram_profile" and hit.url:
        mentor.add_fonte(mentor.instagram_url)
    return mentor, ""


def merge_mentors(base: Mentor, extra: Mentor) -> Mentor:
    if extra.nome and acceptable_name(extra.nome, extra.instagram_handle) and (
        not base.nome or (len(extra.nome.split()) > len(base.nome.split()) and looks_like_person(extra.nome))
    ):
        base.nome = extra.nome
    if not base.instagram_handle and extra.instagram_handle:
        base.instagram_handle = extra.instagram_handle
        base.instagram_url = extra.instagram_url
    if not base.linkedin_url and extra.linkedin_url:
        base.linkedin_url = extra.linkedin_url
    if not base.site and extra.site:
        base.site = extra.site
    if extra.tema:
        base.set_tema(extra.tema, extra.tema_rank)
    if not base.cidade_uf and extra.cidade_uf:
        base.cidade_uf = extra.cidade_uf
    base.set_followers(extra.followers_num, extra.followers_rounded)
    base.evidence = clean_text(f"{base.evidence} {extra.evidence}")[:4000]
    base.inspected_text = base.inspected_text or extra.inspected_text
    for url in extra.fontes:
        base.add_fonte(url)
    known = {post.url for post in base.posts}
    for post in extra.posts:
        if post.url not in known:
            base.posts.append(post)
            known.add(post.url)
    return base


def same_person(left: Mentor, right: Mentor) -> bool:
    left_handle = left.instagram_handle.lstrip("@").lower()
    right_handle = right.instagram_handle.lstrip("@").lower()
    if left_handle and right_handle:
        return left_handle == right_handle
    if (
        left.linkedin_url
        and right.linkedin_url
        and left.linkedin_url.lower() != right.linkedin_url.lower()
        and not left_handle
        and not right_handle
    ):
        return False
    if left.linkedin_url and right.linkedin_url and left.linkedin_url.lower() == right.linkedin_url.lower():
        return True
    left_name = fold(left.nome)
    right_name = fold(right.nome)
    if left_name and left_name == right_name and (left_name.count(" ") >= 1 or len(left_name) >= 6):
        return True
    shared = left.identity_tokens() & right.identity_tokens()
    return bool(shared)


def dedupe_batch(mentors: list[Mentor]) -> list[Mentor]:
    merged: list[Mentor] = []
    for mentor in mentors:
        for existing in merged:
            if same_person(existing, mentor):
                merge_mentors(existing, mentor)
                break
        else:
            merged.append(mentor)
    return merged


class MasterIndex:
    def __init__(self, rows: list[dict[str, str]]):
        self.handles: set[str] = set()
        self.linkedin: set[str] = set()
        self.names: set[str] = set()
        self.blocked_names: list[str] = []
        self.blocked_handles: list[str] = []
        self.domains: set[str] = set()
        for row in rows:
            handle = (row.get("instagram_handle") or "").lstrip("@").lower()
            if handle:
                self.handles.add(handle)
                self.blocked_handles.append(handle)
            link = linkedin_url_from(row.get("linkedin_url") or "") or (row.get("linkedin_url") or "")
            if "/in/" in link:
                self.linkedin.add(link.lower())
            name = fold(row.get("nome") or "")
            if name:
                self.names.add(name)
                self.blocked_names.append(name)
                if "(" in (row.get("nome") or ""):
                    for extra in re.findall(r"\(([^)]+)\)", row.get("nome") or ""):
                        extra_fold = fold(extra)
                        if extra_fold and not extra_fold.startswith("mentor"):
                            self.blocked_names.append(extra_fold)
            for piece in re.split(r"\s+\|\s+", row.get("site") or ""):
                domain = registrable_domain(piece)
                if domain:
                    self.domains.add(domain)

    def matches(self, mentor: Mentor) -> bool:
        handle = mentor.instagram_handle.lstrip("@").lower()
        if handle and handle in self.handles:
            return True
        if mentor.linkedin_url and mentor.linkedin_url.lower() in self.linkedin:
            return True
        name = fold(mentor.nome)
        if name and name in self.names:
            return True
        if name_is_blocked(mentor.nome, self.blocked_names):
            return True
        if handle_is_blocked(handle, self.blocked_handles):
            return True
        for url in [mentor.site, *mentor.fontes]:
            domain = registrable_domain(url)
            if domain and domain in self.domains:
                return True
        return False


def rejection_reason(mentor: Mentor, index: MasterIndex | None = None) -> str:
    if not mentor.nome or not acceptable_name(mentor.nome, mentor.instagram_handle):
        return "sem_nome"
    if name_is_blocked(mentor.nome) or handle_is_blocked(mentor.instagram_handle):
        return "bloqueado"
    if is_foreign(mentor.evidence + " " + mentor.nome, mentor.site or mentor.linkedin_url or mentor.fonte_url):
        return "fora_do_brasil"
    if mentor.followers_num is not None and mentor.followers_num > MAX_FOLLOWERS:
        return "acima_de_50k"
    contact = mentor.site or mentor.instagram_url or mentor.linkedin_url or " ".join(mentor.fontes)
    if wrong_audience(mentor.evidence) or not passes_offer(mentor.evidence, contact):
        return "fora_do_perfil"
    bio = mentor.evidence
    folded = fold(bio)
    if mentor.inspected_text and "empresari" in folded and not any(
        word in folded for word in ("contador", "escritorio", "contabil")
    ):
        return "fora_do_perfil"
    if index and index.matches(mentor):
        return "ja_no_master"
    if not any([mentor.instagram_url, mentor.linkedin_url, mentor.site]):
        return "sem_contato"
    return ""


def rank_key(mentor: Mentor) -> tuple:
    followers = mentor.followers_num if mentor.followers_num is not None else 10**9
    score = 0
    folded = fold(f"{mentor.nome} {mentor.tema} {mentor.evidence}")
    if any(phrase in folded for phrase in STRONG_PHRASES):
        score += 6
    if mentor.instagram_handle:
        score += 2
    if mentor.site:
        score += 1
    if mentor.linkedin_url:
        score += 1
    if mentor.followers_num is not None:
        if mentor.followers_num <= 10_000:
            score += 3
        elif mentor.followers_num <= 25_000:
            score += 2
        elif mentor.followers_num <= MAX_FOLLOWERS:
            score += 1
    return (-score, followers, fold(mentor.nome))


def attach_posts(mentors: list[Mentor], posts: list[Post]) -> None:
    by_handle: dict[str, list[Post]] = {}
    for post in posts:
        if post.handle:
            by_handle.setdefault(post.handle.lower(), []).append(post)
    for mentor in mentors:
        handle = mentor.instagram_handle.lstrip("@").lower()
        if not handle:
            continue
        incoming = by_handle.get(handle, [])
        known = {post.url for post in mentor.posts}
        for post in incoming:
            if post.url not in known:
                mentor.posts.append(post)
                known.add(post.url)
        if mentor.posts and not mentor.ultimos_posts:
            mentor.ultimos_posts = format_posts(mentor.posts)
