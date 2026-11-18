"""Orquestra a busca do dia: descoberta, filtro, dedupe e gravação."""

from __future__ import annotations

import os
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo

from scraper.config import (
    MAX_IG_PROFILES,
    MAX_NOVOS,
    MAX_PAGE_FETCHES,
    MAX_QUERIES,
    MIN_QUERIES,
    QUERIES,
    SEARCH_PAUSE_SECONDS,
    STOP_AFTER_NOVOS,
)
from scraper.enrich import enrich_instagram, enrich_pages
from scraper.model import (
    Hit,
    MasterIndex,
    Mentor,
    attach_posts,
    dedupe_batch,
    extract_post,
    format_posts,
    mentor_from_hit,
    rank_key,
    rejection_reason,
)
from scraper.search import SearchBlocked, search_duckduckgo, search_with_pause, search_yahoo
from scraper.store import load_csv, write_csv, write_json

Engine = tuple[str, Callable[[str], list[Hit]]]


def _today() -> str:
    return datetime.now(ZoneInfo("America/Sao_Paulo")).date().isoformat()


def _note(reasons: Counter, examples: list[dict[str, str]], reason: str, nome: str, url: str) -> None:
    reasons[reason] += 1
    if reason == "url_ignorada" or len(examples) >= 20:
        return
    examples.append({"motivo": reason, "nome": nome[:80], "url": url[:180]})


def collect_mentors(hits: list[Hit], index: MasterIndex) -> tuple[list[Mentor], Counter, list[dict[str, str]]]:
    parsed: list[Mentor] = []
    reasons: Counter = Counter()
    examples: list[dict[str, str]] = []
    for hit in hits:
        mentor, reason = mentor_from_hit(hit)
        if mentor is None:
            _note(reasons, examples, reason or "fora_do_perfil", hit.title, hit.url)
            continue
        reason = rejection_reason(mentor, index)
        if reason:
            _note(reasons, examples, reason, mentor.nome, hit.url)
            continue
        parsed.append(mentor)
    return _keep(dedupe_batch(parsed), index, reasons, examples)


def _keep(
    mentors: list[Mentor],
    index: MasterIndex,
    reasons: Counter | None = None,
    examples: list[dict[str, str]] | None = None,
) -> tuple[list[Mentor], Counter, list[dict[str, str]]]:
    reasons = reasons if reasons is not None else Counter()
    examples = examples if examples is not None else []
    kept: list[Mentor] = []
    for mentor in dedupe_batch(mentors):
        reason = rejection_reason(mentor, index)
        if reason:
            _note(reasons, examples, reason, mentor.nome, mentor.instagram_url or mentor.site or mentor.linkedin_url)
            continue
        kept.append(mentor)
    return kept, reasons, examples


def backfill_posts(mentors: list[Mentor], searcher: Callable[[str], list[Hit]], pause: float, limit: int = 8) -> int:
    """Busca posts indexados dos handles que ainda não têm duas URLs."""
    filled = 0
    for mentor in mentors:
        handle = mentor.instagram_handle.lstrip("@")
        if not handle or len(mentor.posts) >= 2 or filled >= limit:
            continue
        try:
            hits = searcher(f"{handle} instagram")
        except (SearchBlocked, Exception):
            break
        for hit in hits:
            post = extract_post(hit)
            if post is None:
                continue
            if post.handle and post.handle != handle.lower() and handle.lower() not in hit.url.lower():
                continue
            post.handle = handle.lower()
            if all(post.url != existing.url for existing in mentor.posts):
                mentor.posts.append(post)
        filled += 1
        if pause:
            import time

            time.sleep(pause)
    return filled


def run(
    data_dir: str | Path = "data",
    max_novos: int | None = None,
    engines: list[Engine] | None = None,
    page_fetcher=None,
    ig_enricher=None,
    pause: float | None = None,
    today: str | None = None,
    search_posts: Callable[[str], list[Hit]] | None | bool = True,
) -> dict:
    data_path = Path(data_dir)
    master_path = data_path / "mentores_master.csv"
    today = today or _today()
    max_novos = MAX_NOVOS if max_novos is None else max_novos
    pause = SEARCH_PAUSE_SECONDS if pause is None else pause
    engines = engines or [("duckduckgo", search_duckduckgo), ("yahoo", search_yahoo)]

    master_rows = load_csv(master_path)
    index = MasterIndex(master_rows)
    hits: list[Hit] = []
    blocked: set[str] = set()
    strikes: dict[str, int] = {}
    engine_stats = {name: {"consultas": 0, "resultados": 0, "erro": ""} for name, _engine in engines}
    queries_ran: list[str] = []

    for query_index, query in enumerate(QUERIES):
        if query_index >= MAX_QUERIES:
            break
        usable = [(name, engine) for name, engine in engines if name not in blocked]
        if not usable:
            break
        found, errors = search_with_pause(usable, query, pause=pause)
        queries_ran.append(query)
        for name, _engine in usable:
            engine_stats[name]["consultas"] += 1
        for hit in found:
            engine_stats[hit.engine]["resultados"] += 1
        for name, message in errors.items():
            engine_stats[name]["erro"] = message
            lowered = message.lower()
            hard_block = any(token in lowered for token in ("429", "403", "consent"))
            soft_block = any(token in lowered for token in ("202", "anomalia", "500", "bloque"))
            if hard_block:
                blocked.add(name)
            elif soft_block:
                strikes[name] = strikes.get(name, 0) + 1
                if strikes[name] >= 2:
                    blocked.add(name)
        hits.extend(found)
        if query_index + 1 >= MIN_QUERIES:
            accepted, _reasons, _examples = collect_mentors(hits, index)
            if len(accepted) >= max(STOP_AFTER_NOVOS, max_novos):
                break

    mentors, reasons, examples = collect_mentors(hits, index)
    mentors.sort(key=rank_key)

    if page_fetcher is None:
        page_report = enrich_pages(
            mentors[: max_novos + 5],
            limit=MAX_PAGE_FETCHES,
            pause=1.2 if pause else 0,
        )
    else:
        page_report = enrich_pages(mentors[: max_novos + 5], fetcher=page_fetcher, limit=MAX_PAGE_FETCHES, pause=0)

    mentors, page_reasons, page_examples = _keep(mentors, index)
    reasons.update(page_reasons)
    examples.extend(page_examples)
    mentors.sort(key=rank_key)

    shortlist = mentors[: max(max_novos + 8, MAX_IG_PROFILES)]
    if ig_enricher is None:
        ig_report = enrich_instagram(shortlist, pause=12 if pause else 0, max_profiles=MAX_IG_PROFILES)
    else:
        ig_report = ig_enricher(shortlist)

    kept_short, ig_reasons, ig_examples = _keep(shortlist, index)
    reasons.update(ig_reasons)
    examples.extend(ig_examples)
    if len(kept_short) < max_novos:
        rest = [mentor for mentor in mentors if mentor not in shortlist]
        extra, extra_reasons, extra_examples = _keep(rest, index)
        kept_short.extend(extra)
        reasons.update(extra_reasons)
        examples.extend(extra_examples)

    attach_posts(kept_short, [post for hit in hits if (post := extract_post(hit))])
    kept_short.sort(key=rank_key)
    chosen = kept_short[:max_novos]
    post_searcher = search_yahoo if search_posts is True else search_posts if search_posts else None
    posts_buscados = 0
    if post_searcher is not None:
        posts_buscados = backfill_posts(chosen, post_searcher, pause=pause or 0)
    for mentor in chosen:
        mentor.data_entrada = today
        mentor.menciona_ia = ""
        if mentor.posts:
            mentor.ultimos_posts = format_posts(mentor.posts)

    new_rows = [mentor.to_row() for mentor in chosen]
    daily_path = data_path / f"mentores_{today}.csv"
    write_csv(daily_path, new_rows)
    write_csv(master_path, master_rows + new_rows)

    report = {
        "data": today,
        "horario_brasilia": datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat(timespec="seconds"),
        "alvo": max_novos,
        "novos": len(new_rows),
        "consultas": queries_ran,
        "busca": engine_stats,
        "motores_bloqueados": sorted(blocked),
        "resultados_brutos": len(hits),
        "paginas": page_report,
        "instagram": ig_report,
        "posts_buscados": posts_buscados,
        "descartes": dict(reasons),
        "descartes_exemplos": examples[:20],
        "arquivo_diario": daily_path.as_posix(),
        "mentores": [row["nome"] for row in new_rows],
    }
    write_json(data_path / "ultimo_run.json", report)
    return report


def main_max() -> int:
    raw = os.environ.get("MAX_NOVOS", "").strip()
    if not raw:
        return MAX_NOVOS
    return max(1, int(raw))
