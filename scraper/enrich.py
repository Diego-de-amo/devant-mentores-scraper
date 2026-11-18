"""Enriquecimento opcional: páginas públicas e Instaloader.

O Instagram anônimo em IP de datacenter costuma responder 429. Nesse caso
o enriquecimento para e a linha fica com o que a busca já tinha mostrado.
"""

from __future__ import annotations

import os
import re
import time
from pathlib import Path
from urllib.parse import urlsplit

import requests
from bs4 import BeautifulSoup

from scraper.config import IG_PAUSE_SECONDS, PAGE_PAUSE_SECONDS, USER_AGENT
from scraper.model import (
    Mentor,
    Post,
    format_posts,
    instagram_handle_from_url,
    linkedin_url_from,
    looks_like_person,
)
from scraper.textutil import clean_text, find_city_uf

_PRIVATE_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}


def public_http_url(url: str) -> bool:
    parts = urlsplit(url if "://" in url else "")
    host = (parts.hostname or "").lower()
    if parts.scheme not in {"http", "https"} or not host:
        return False
    if host in _PRIVATE_HOSTS or host.endswith(".local") or host.endswith(".internal"):
        return False
    return True


def fetch_page(url: str, session: requests.Session | None = None) -> dict[str, str | list[str]]:
    if not public_http_url(url):
        return {"ok": "", "error": "url_recusada", "title": "", "text": "", "description": "", "handles": [], "linkedin": ""}
    session = session or requests.Session()
    try:
        response = session.get(
            url,
            timeout=(8, 20),
            headers={"User-Agent": USER_AGENT, "Accept-Language": "pt-BR,pt;q=0.9"},
            allow_redirects=True,
        )
    except requests.RequestException as exc:
        return {"ok": "", "error": type(exc).__name__, "title": "", "text": "", "description": "", "handles": [], "linkedin": ""}
    if response.status_code >= 400:
        return {
            "ok": "",
            "error": f"HTTP {response.status_code}",
            "title": "",
            "text": "",
            "description": "",
            "handles": [],
            "linkedin": "",
        }
    raw = response.content[:1_000_000]
    try:
        html = raw.decode("utf-8")
    except UnicodeDecodeError:
        html = raw.decode("latin-1", "replace")
    sample = html[:2500].casefold()
    if "cf-chl" in sample or "just a moment" in sample or "attention required" in sample:
        return {
            "ok": "",
            "error": "challenge",
            "title": "",
            "text": "",
            "description": "",
            "handles": [],
            "linkedin": "",
        }
    soup = BeautifulSoup(html, "html.parser")
    description = ""
    meta = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
    if meta and meta.get("content"):
        description = clean_text(meta["content"])
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    title = clean_text(soup.title.get_text(" ", strip=True) if soup.title else "")
    text = clean_text(soup.get_text(" ", strip=True))[:6000]
    handles: list[str] = []
    for handle in re.findall(r"instagram\.com/([A-Za-z0-9._]{2,30})", html):
        token = instagram_handle_from_url(f"https://www.instagram.com/{handle}/")
        if token and token not in handles:
            handles.append(token)
    linkedin = ""
    for anchor in soup.find_all("a", href=True):
        if "linkedin.com/in/" in anchor["href"]:
            linkedin = linkedin_url_from(anchor["href"])
            if linkedin:
                break
    if not linkedin and "linkedin.com/in/" in html:
        linkedin = linkedin_url_from(html)
    return {
        "ok": "1",
        "error": "",
        "title": title,
        "text": text,
        "description": description,
        "handles": handles,
        "linkedin": linkedin,
    }


def apply_page(mentor: Mentor, page: dict) -> None:
    if not page.get("ok"):
        return
    handles = page.get("handles") or []
    if isinstance(handles, list) and len(handles) == 1 and not mentor.instagram_handle:
        handle = handles[0]
        mentor.instagram_handle = f"@{handle}"
        mentor.instagram_url = f"https://www.instagram.com/{handle}/"
    linkedin = str(page.get("linkedin") or "")
    if linkedin and not mentor.linkedin_url:
        mentor.linkedin_url = linkedin
    description = str(page.get("description") or "")
    text = str(page.get("text") or "")
    if description and mentor.tema_rank < 2:
        mentor.set_tema(description, rank=2)
    blob = clean_text(f"{page.get('title') or ''} {description} {text}")
    mentor.evidence = clean_text(f"{mentor.evidence} {blob}")[:5000]
    if len(text) >= 400:
        mentor.inspected_text = True
    if not mentor.cidade_uf:
        mentor.cidade_uf = find_city_uf(blob)


def enrich_pages(mentors: list[Mentor], fetcher=fetch_page, limit: int = 10, pause: float = PAGE_PAUSE_SECONDS) -> dict:
    report = {"lidas": 0, "erros": 0, "detalhes": []}
    fetched = 0
    for mentor in mentors:
        if fetched >= limit:
            break
        target = mentor.site or ""
        if not target or not public_http_url(target):
            continue
        host = urlsplit(target).netloc.lower()
        if any(name in host for name in ("instagram.com", "linkedin.com", "facebook.com", "youtube.com", "yahoo.com")):
            continue
        page = fetcher(target)
        fetched += 1
        if page.get("ok"):
            apply_page(mentor, page)
            report["lidas"] += 1
        else:
            report["erros"] += 1
            report["detalhes"].append({"url": target, "erro": page.get("error") or "falha"})
        if pause:
            time.sleep(pause)
    return report


def _instaloader():
    import instaloader
    from instaloader.exceptions import TooManyRequestsException
    from instaloader.instaloadercontext import RateController

    class FailFastRateController(RateController):
        def sleep(self, secs: float) -> None:
            if secs > 5:
                raise TooManyRequestsException(f"espera de {secs:.0f}s; interrompendo Instagram")
            time.sleep(secs)

        def handle_429(self, query_type: str) -> None:
            raise TooManyRequestsException("HTTP 429 do Instagram; interrompendo enriquecimento")

    return instaloader.Instaloader(
        sleep=False,
        quiet=True,
        download_pictures=False,
        download_videos=False,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        max_connection_attempts=1,
        request_timeout=20,
        fatal_status_codes=[429],
        rate_controller=lambda ctx: FailFastRateController(ctx),
    )


def enrich_instagram(mentors: list[Mentor], pause: float = IG_PAUSE_SECONDS, max_profiles: int = 12) -> dict:
    report = {
        "modo": "anonimo",
        "status": "sem_perfil",
        "perfis_enriquecidos": 0,
        "detalhe": "",
    }
    targets = [mentor for mentor in mentors if mentor.instagram_handle][:max_profiles]
    if not targets:
        return report
    try:
        loader = _instaloader()
    except Exception as exc:  # pragma: no cover - ambiente sem a lib
        report["status"] = "instaloader_indisponivel"
        report["detalhe"] = f"{type(exc).__name__}: {exc}"
        return report

    import instaloader
    from instaloader.exceptions import (
        ConnectionException,
        LoginRequiredException,
        PrivateProfileNotFollowedException,
        ProfileNotExistsException,
        QueryReturnedNotFoundException,
        TooManyRequestsException,
    )

    username = os.environ.get("IG_USERNAME", "").strip()
    session_file = os.environ.get("IG_SESSIONFILE", "").strip()
    if username and session_file and Path(session_file).is_file():
        try:
            loader.load_session_from_file(username, session_file)
            logged = loader.test_login()
            if logged:
                report["modo"] = "sessao"
                report["detalhe"] = f"sessão autenticada como {logged}"
            else:
                report["detalhe"] = "arquivo de sessão não autenticou; tentativa anônima"
                loader = _instaloader()
        except (TooManyRequestsException, instaloader.exceptions.AbortDownloadException, ConnectionException) as exc:
            report["modo"] = "sessao"
            report["status"] = "bloqueado_429" if "429" in str(exc) else "sessao_falhou"
            report["detalhe"] = f"{type(exc).__name__}: {exc}"
            return report
        except Exception as exc:
            report["detalhe"] = f"sessão inválida ({type(exc).__name__}); tentativa anônima"
            loader = _instaloader()

    enriched = 0
    for index, mentor in enumerate(targets):
        handle = mentor.instagram_handle.lstrip("@")
        try:
            profile = instaloader.Profile.from_username(loader.context, handle)
        except (TooManyRequestsException, instaloader.exceptions.AbortDownloadException) as exc:
            report["status"] = "bloqueado_429"
            report["detalhe"] = (report["detalhe"] + " " + f"{type(exc).__name__}: {exc}").strip()
            break
        except LoginRequiredException as exc:
            report["status"] = "login_exigido"
            report["detalhe"] = str(exc)
            break
        except ConnectionException as exc:
            message = str(exc)
            if "429" in message or "login" in message.lower():
                report["status"] = "bloqueado_429" if "429" in message else "login_exigido"
                report["detalhe"] = message
                break
            report["detalhe"] = (report["detalhe"] + f" {handle}: {type(exc).__name__}").strip()
            continue
        except (ProfileNotExistsException, QueryReturnedNotFoundException, PrivateProfileNotFollowedException):
            continue
        except Exception as exc:
            if "429" in str(exc):
                report["status"] = "bloqueado_429"
                report["detalhe"] = str(exc)
                break
            report["detalhe"] = (report["detalhe"] + f" {handle}: {type(exc).__name__}").strip()
            continue

        full_name = clean_text(getattr(profile, "full_name", "") or "")
        if full_name and (looks_like_person(full_name) or not mentor.nome):
            mentor.nome = full_name
        biography = clean_text(getattr(profile, "biography", "") or "")
        if biography:
            mentor.set_tema(biography, rank=3)
            mentor.evidence = clean_text(f"{mentor.evidence} {biography}")[:5000]
            mentor.inspected_text = True
        followers = getattr(profile, "followers", None)
        if isinstance(followers, int):
            mentor.set_followers(followers, rounded=False)
        external = clean_text(getattr(profile, "external_url", "") or "")
        if external.startswith("http") and not mentor.site and "instagram.com" not in external:
            mentor.site = external
        live_posts = []
        try:
            for post in profile.get_posts():
                caption = clean_text(getattr(post, "caption", "") or "")
                caption = caption.split("\n", 1)[0]
                if len(caption) > 140:
                    caption = caption[:139].rstrip() + "…"
                live_posts.append(
                    Post(
                        url=f"https://www.instagram.com/p/{post.shortcode}/",
                        caption=caption,
                        date=getattr(post, "date_utc", None),
                        handle=handle.lower(),
                    )
                )
                if len(live_posts) >= 3:
                    break
        except (
            TooManyRequestsException,
            instaloader.exceptions.AbortDownloadException,
            ConnectionException,
            LoginRequiredException,
        ) as exc:
            if live_posts:
                mentor.posts = live_posts
                mentor.ultimos_posts = format_posts(live_posts)
            if isinstance(exc, LoginRequiredException):
                report["status"] = "login_exigido"
            elif "429" in str(exc):
                report["status"] = "bloqueado_429"
            else:
                report["status"] = "parcial"
            report["detalhe"] = (report["detalhe"] + f" posts de {handle}: {type(exc).__name__}").strip()
            enriched += 1
            break
        except Exception:
            pass
        if live_posts:
            mentor.posts = live_posts
            mentor.ultimos_posts = format_posts(live_posts)
        enriched += 1
        report["perfis_enriquecidos"] = enriched
        if index < len(targets) - 1 and pause:
            time.sleep(pause)

    report["perfis_enriquecidos"] = enriched
    if report["status"] == "sem_perfil":
        report["status"] = "ok" if enriched else "sem_dados"
    elif report["status"] == "bloqueado_429" and enriched:
        report["status"] = "parcial_429"
    return report
