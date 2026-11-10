"""Orquestra a descoberta, o enriquecimento e a gravação dos CSVs."""

from __future__ import annotations

import logging
import re
import urllib.parse
from collections import Counter
from datetime import date, datetime
from difflib import SequenceMatcher
from pathlib import Path
from zoneinfo import ZoneInfo

from almore_scraper.armazenamento import (
    caminho_master,
    candidato_de_linha,
    ler_csv,
    salvar_resultados,
    salvar_resumo,
)
from almore_scraper.busca import Buscador
from almore_scraper.config import Config, Nicho, nichos_do_dia
from almore_scraper.extracao import (
    analisar_html,
    artigo_generico,
    bio_de_snippet,
    extrair_programa,
    formatar_posts,
    handle_de_titulo,
    handle_de_url,
    host_de,
    host_e,
    legenda_de_snippet,
    linkedin_de_url,
    nome_aceitavel,
    nome_de_titulo,
    origem_do_site,
    parece_pessoa,
    parse_seguidores,
    pessoa_de_texto,
    plataforma,
    post_aproveitavel,
    post_do_handle,
    preferir_linkedin,
    serve_como_site,
    url_de_post,
    url_e_perfil,
    url_http,
)
from almore_scraper.filtros import (
    Indice,
    classificar_parceiro,
    eh_mentor_de_contabilidade,
    mesmo_mentor,
    mesclar,
    motivo_descarte,
    pontuar,
    selecionar,
    tem_sinal_mentoria,
)
from almore_scraper.cidades import extrair_cidade
from almore_scraper.http_util import ClienteHttp, pausar, url_segura
from almore_scraper.instagram_client import ClienteInstagram
from almore_scraper.modelos import Candidato, ResultadoBusca
from almore_scraper.util_texto import dobrar, tokens_nome

log = logging.getLogger("almore")

_SEM_BAIXAR = {
    "instagram.com", "linkedin.com", "facebook.com", "fb.com", "youtube.com",
    "youtu.be", "tiktok.com", "twitter.com", "x.com", "wa.me", "whatsapp.com",
}


def hoje_brasil() -> date:
    return datetime.now(ZoneInfo("America/Sao_Paulo")).date()


def executar(
    config: Config,
    diretorio: Path,
    dia: date | None = None,
    *,
    nichos_ids: list[str] | None = None,
    alvo: int | None = None,
    max_buscas: int | None = None,
    sem_instagram: bool = False,
    buscador: Buscador | None = None,
    baixar=None,
    instagram: ClienteInstagram | None = None,
) -> dict:
    dia = dia or hoje_brasil()
    limite = alvo if alvo is not None else config.alvo_por_dia
    teto_buscas = max_buscas if max_buscas is not None else config.max_buscas
    reserva = min(30, config.max_enriquecimentos)
    teto_descoberta = max(8, teto_buscas - reserva)
    cliente = ClienteHttp()
    buscador = buscador or Buscador(cliente, config.pausa_busca)
    if baixar is None:
        baixar = _baixar_padrao(cliente, config.pausa_fetch)
    if instagram is None and not sem_instagram:
        instagram = ClienteInstagram(config.pausa_instagram, config.falhas_instagram_para_desligar)

    existentes = ler_csv(caminho_master(diretorio)) if diretorio else []
    conhecidos = Indice()
    for linha in existentes:
        conhecidos.adicionar(candidato_de_linha(linha))

    ordem = _ordem_nichos(config, dia, nichos_ids)
    pool: list[Candidato] = []
    nichos_usados: list[Nicho] = []
    erros: list[str] = []
    fetches = 0
    cursor = 0
    rodada = max(1, config.nichos_por_rodada)

    while cursor < len(ordem) and buscador.buscas < teto_descoberta:
        lote = ordem[cursor : cursor + rodada]
        cursor += len(lote)
        nichos_usados.extend(lote)
        for nicho in lote:
            for indice, consulta in enumerate(config.consultas(nicho)):
                if buscador.buscas >= teto_descoberta:
                    break
                paginas = config.max_paginas_por_consulta if indice == 0 else 1
                log.info("Busca [%s] %s", nicho.nome, consulta)
                try:
                    resultados = buscador.buscar(consulta, paginas)
                except Exception as erro:
                    erros.append(f"busca: {type(erro).__name__}")
                    log.warning("Consulta falhou (%s): %s", type(erro).__name__, consulta[:120])
                    continue
                log.info("  %s resultados", len(resultados))
                for resultado in resultados:
                    try:
                        candidato = candidato_de_resultado(resultado, nicho, dia)
                    except Exception as erro:
                        erros.append(f"resultado: {type(erro).__name__}")
                        continue
                    if candidato is not None:
                        _fundir(pool, candidato)
        if _promissores(pool) >= limite + 15:
            break

    fetches = _baixar_paginas(pool, baixar, config.max_fetches, dia, erros)
    for candidato in pool:
        candidato.score = pontuar(candidato, config)
    pool.sort(key=lambda candidato: -candidato.score)
    enriquecimentos = _enriquecer_buscas(pool, buscador, teto_buscas, config.max_enriquecimentos, dia, erros)
    if instagram is not None and not sem_instagram:
        _enriquecer_instaloader(pool, instagram, config, erros)

    descartes: Counter[str] = Counter()
    aprovados: list[Candidato] = []
    for candidato in pool:
        _finalizar(candidato, config)
        motivo = motivo_descarte(candidato, config, conhecidos)
        if motivo:
            descartes[motivo] += 1
            continue
        aprovados.append(candidato)

    escolhidos = []
    for candidato in selecionar(aprovados, config, limite):
        if conhecidos.contem(candidato):
            descartes["duplicado"] += 1
            continue
        conhecidos.adicionar(candidato)
        escolhidos.append(candidato)
    for candidato in escolhidos:
        candidato.data_entrada = dia.isoformat()

    diario, _master = salvar_resultados(diretorio, dia, existentes, escolhidos)
    csv_dia = ""
    if diario is not None:
        try:
            csv_dia = str(diario.relative_to(diretorio.parent))
        except ValueError:
            csv_dia = str(diario)
    instagram_info = {
        "tentativas": getattr(instagram, "tentativas", 0) if instagram else 0,
        "sucessos": getattr(instagram, "sucessos", 0) if instagram else 0,
        "desligado": bool(getattr(instagram, "desligado", sem_instagram)),
        "motivo": getattr(instagram, "motivo", "") if instagram else ("desligado" if sem_instagram else ""),
    }
    resumo = {
        "data": dia.isoformat(),
        "nichos": [nicho.nome for nicho in nichos_usados],
        "buscas": buscador.buscas,
        "fetches": fetches,
        "anomalias_duckduckgo": buscador.anomalias,
        "provedores": dict(buscador.provedores),
        "bloqueios": dict(buscador.bloqueios),
        "candidatos": len(pool),
        "enriquecimentos": enriquecimentos,
        "instagram": instagram_info,
        "descartes": dict(descartes),
        "aprovados": len(aprovados),
        "novos": len(escolhidos),
        "csv_dia": csv_dia,
        "erros": erros[:30],
        "mentores": [
            {
                "nome": candidato.nome,
                "nicho": candidato.nicho,
                "instagram_handle": candidato.instagram_handle,
                "seguidores": candidato.seguidores,
                "cidade_uf": candidato.cidade_uf,
                "menciona_contador_parceiro": candidato.menciona_contador_parceiro,
            }
            for candidato in escolhidos
        ],
    }
    salvar_resumo(diretorio, resumo)
    for candidato in escolhidos:
        log.info(
            "Novo: %s | %s | @%s | seguidores=%s",
            candidato.nome,
            candidato.nicho,
            candidato.instagram_handle or "-",
            candidato.seguidores or "-",
        )
    log.info("Mentores novos gravados: %s", len(escolhidos))
    return resumo


def candidato_de_resultado(resultado: ResultadoBusca, nicho: Nicho, dia: date) -> Candidato | None:
    if not url_http(resultado.url):
        return None
    if url_de_post(resultado.url):
        return None
    if host_e(host_de(resultado.url), {"reddit.com", "pinterest.com", "wikipedia.org", "amazon.com", "ebay.com"}):
        return None
    texto = f"{resultado.titulo}\n{resultado.snippet}"
    perfil = False
    handle = handle_de_url(resultado.url) or handle_de_titulo(resultado.titulo)
    if handle and url_e_perfil(resultado.url, handle):
        perfil = True
    if not perfil and not tem_sinal_mentoria(texto):
        return None
    if eh_mentor_de_contabilidade(texto, nome_de_titulo(resultado.titulo), resultado.url):
        return None
    nome = pessoa_de_texto(resultado.snippet) or pessoa_de_texto(resultado.titulo) or nome_de_titulo(resultado.titulo)
    if not nome_aceitavel(nome):
        return None
    linkedin = linkedin_de_url(resultado.url)
    if linkedin and not _linkedin_bate_com_nome(nome, linkedin):
        return None
    candidato = Candidato(
        nome=nome,
        nicho=nicho.nome,
        termos_nicho=list(nicho.termos),
        data_entrada=dia.isoformat(),
        fonte_url=resultado.url,
    )
    candidato.adicionar_texto(resultado.titulo, titulo=True)
    candidato.adicionar_texto(resultado.snippet)
    if perfil and handle:
        candidato.definir_handle(handle)
        candidato.definir_seguidores(parse_seguidores(resultado.snippet), "snippet_perfil")
        candidato.adicionar_texto(bio_de_snippet(resultado.snippet))
    if linkedin:
        candidato.linkedin_url = linkedin
    site = origem_do_site(resultado.url)
    if site:
        candidato.site = site
    programa = extrair_programa(resultado.titulo)
    if programa:
        candidato.programa_mentoria = programa
    return candidato


def _fundir(pool: list[Candidato], candidato: Candidato) -> None:
    for existente in pool:
        if mesmo_mentor(existente, candidato):
            mesclar(existente, candidato)
            return
    pool.append(candidato)


def _promissores(pool: list[Candidato]) -> int:
    total = 0
    for candidato in pool:
        texto = f"{candidato.titulos}\n{candidato.corpus}"
        if nome_aceitavel(candidato.nome) and tem_sinal_mentoria(texto):
            if not eh_mentor_de_contabilidade(texto, candidato.nome, candidato.fonte_url):
                total += 1
    return total


def _baixar_padrao(cliente: ClienteHttp, pausa: tuple[float, float]):
    def baixar(url: str) -> str | None:
        if not url_segura(url):
            return None
        pausar(pausa)
        resposta = cliente.solicitar(url, timeout=12, tentativas=1)
        if resposta is None or resposta.status >= 400:
            return None
        if "\x00" in resposta.corpo[:200]:
            return None
        return resposta.corpo

    return baixar


def _pode_baixar(url: str) -> bool:
    return url_http(url) and url_segura(url) and not host_e(host_de(url), _SEM_BAIXAR)


def _baixar_paginas(pool: list[Candidato], baixar, limite: int, dia: date, erros: list[str]) -> int:
    feitos = 0
    ordenados = sorted(pool, key=lambda candidato: (bool(candidato.instagram_handle), bool(candidato.site)))
    for candidato in list(ordenados):
        if feitos >= limite:
            break
        if not _pode_baixar(candidato.fonte_url):
            continue
        try:
            html = baixar(candidato.fonte_url)
        except Exception as erro:
            erros.append(f"fetch: {type(erro).__name__}")
            continue
        feitos += 1
        if not html:
            continue
        try:
            pagina = analisar_html(html, candidato.fonte_url)
        except Exception as erro:
            erros.append(f"html: {type(erro).__name__}")
            continue
        extras = _aplicar_pagina(candidato, pagina, dia)
        if extras:
            if candidato in pool:
                pool.remove(candidato)
            for extra in extras:
                _fundir(pool, extra)
    return feitos


def _aplicar_pagina(candidato: Candidato, pagina, dia: date) -> list[Candidato]:
    candidato.adicionar_texto(pagina.titulo, titulo=True)
    candidato.adicionar_texto(pagina.descricao)
    candidato.adicionar_texto(pagina.texto[:2000])
    if pagina.cidade_uf and not candidato.cidade_uf:
        candidato.cidade_uf = pagina.cidade_uf
    if pagina.linkedins:
        candidato.linkedin_url = preferir_linkedin(candidato.linkedin_url, pagina.linkedins[0])
    if not candidato.site:
        candidato.site = pagina.site_json or origem_do_site(candidato.fonte_url)
    if pagina.nome_json and parece_pessoa(pagina.nome_json) and nome_aceitavel(pagina.nome_json):
        if not parece_pessoa(candidato.nome):
            if candidato.nome and not candidato.programa_mentoria:
                candidato.programa_mentoria = candidato.nome
            candidato.nome = pagina.nome_json
    if _parece_lista(pagina):
        extras = _candidatos_de_lista(candidato, pagina, dia)
        if extras:
            return extras
    if pagina.handles and not candidato.instagram_handle:
        escolhido = _escolher_handle(candidato, pagina.handles)
        if escolhido:
            candidato.definir_handle(escolhido)
    return []


def _parece_lista(pagina) -> bool:
    if len(pagina.handles) < 2:
        return False
    if artigo_generico(pagina.titulo):
        return True
    return bool(re.search(r"\b(melhores|lista|ranking|\d+\s+mentores)\b", dobrar(pagina.titulo)))


def _candidatos_de_lista(origem: Candidato, pagina, dia: date) -> list[Candidato]:
    extras: list[Candidato] = []
    for handle, contexto in pagina.handles:
        nome = pessoa_de_texto(contexto) or nome_de_titulo(contexto)
        if not nome_aceitavel(nome):
            continue
        candidato = Candidato(
            nome=nome,
            nicho=origem.nicho,
            termos_nicho=list(origem.termos_nicho),
            data_entrada=dia.isoformat(),
            fonte_url=origem.fonte_url,
        )
        candidato.definir_handle(handle)
        candidato.adicionar_texto(pagina.titulo, titulo=True)
        candidato.adicionar_texto(contexto)
        candidato.adicionar_texto(pagina.descricao)
        extras.append(candidato)
    return extras


def _escolher_handle(candidato: Candidato, handles: list[tuple[str, str]]) -> str:
    melhor = ""
    melhor_nota = 0.0
    referencia = dobrar(candidato.nome).replace(" ", "")
    dominio = host_de(candidato.site or candidato.fonte_url).split(".")[0]
    for handle, _contexto in handles:
        nota = max(
            SequenceMatcher(None, referencia, handle.lower()).ratio(),
            SequenceMatcher(None, dominio, handle.lower()).ratio() if dominio else 0.0,
        )
        if nota > melhor_nota:
            melhor_nota = nota
            melhor = handle
    if melhor_nota >= 0.45:
        return melhor
    return ""


def _linkedin_bate_com_nome(nome: str, url: str) -> bool:
    slug = dobrar(url.rstrip("/").rsplit("/", 1)[-1]).replace("-", "")
    tokens = [token for token in tokens_nome(nome) if len(token) >= 4]
    if not tokens:
        return False
    return any(token in slug for token in tokens)


def _enriquecer_buscas(pool, buscador, teto_buscas: int, limite: int, dia: date, erros: list[str]) -> int:
    feitos = 0
    for candidato in list(pool):
        if feitos >= limite or buscador.buscas >= teto_buscas:
            break
        texto = f"{candidato.titulos}\n{candidato.corpus}"
        if not nome_aceitavel(candidato.nome) or not tem_sinal_mentoria(texto):
            continue
        if not candidato.instagram_handle:
            continue
        if candidato.seguidores and candidato.ultimos_posts:
            continue
        consulta = f"instagram.com/{candidato.instagram_handle}"
        try:
            resultados = buscador.buscar(consulta, 1)
        except Exception as erro:
            erros.append(f"enriquecimento: {type(erro).__name__}")
            continue
        feitos += 1
        _aplicar_enriquecimento(candidato, resultados, dia)
    return feitos


def _aplicar_enriquecimento(candidato: Candidato, resultados: list[ResultadoBusca], dia: date) -> None:
    handle = candidato.instagram_handle
    if not handle:
        return
    perfil = None
    for resultado in resultados:
        encontrado = handle_de_url(resultado.url) or handle_de_titulo(resultado.titulo)
        if not encontrado or encontrado.lower() != handle.lower():
            continue
        if not url_e_perfil(resultado.url, encontrado):
            continue
        caminho = urllib.parse.urlparse(resultado.url).path.strip("/").lower()
        if caminho == handle.lower():
            perfil = resultado
            break
        perfil = perfil or resultado
    if perfil is not None:
        candidato.definir_seguidores(parse_seguidores(perfil.snippet), "snippet_perfil")
        candidato.adicionar_texto(bio_de_snippet(perfil.snippet))
        candidato.adicionar_texto(perfil.titulo, titulo=True)
        pessoa = nome_de_titulo(perfil.titulo)
        if pessoa and parece_pessoa(pessoa) and nome_aceitavel(pessoa) and not parece_pessoa(candidato.nome):
            if candidato.nome and not candidato.programa_mentoria:
                candidato.programa_mentoria = candidato.nome
            candidato.nome = pessoa
        linkedin = linkedin_de_url(perfil.url)
        if linkedin:
            candidato.linkedin_url = preferir_linkedin(candidato.linkedin_url, linkedin)
    posts: list[tuple[str, str]] = []
    for resultado in resultados:
        combinado = f"{resultado.titulo} {resultado.snippet}"
        if not post_do_handle(resultado.url, combinado, handle):
            continue
        if not post_aproveitavel(combinado, dia):
            continue
        url = url_de_post(resultado.url)
        if not url or any(url == existente for existente, _legenda in posts):
            continue
        posts.append((url, legenda_de_snippet(resultado.snippet, resultado.titulo)))
        if len(posts) >= 3:
            break
    if posts and not candidato.ultimos_posts:
        candidato.ultimos_posts = formatar_posts(posts)


def _enriquecer_instaloader(pool: list[Candidato], instagram: ClienteInstagram, config: Config, erros: list[str]) -> None:
    from almore_scraper.instagram_client import RespostaInstagram

    interessantes = [candidato for candidato in pool if candidato.instagram_handle and nome_aceitavel(candidato.nome)]
    for candidato in interessantes:
        if instagram.desligado:
            break
        if instagram.tentativas:
            pausar(config.pausa_instagram)
        try:
            resposta: RespostaInstagram = instagram.obter(candidato.instagram_handle)
        except Exception as erro:
            erros.append(f"instagram: {type(erro).__name__}")
            continue
        perfil = resposta.perfil
        if resposta.status != "ok" or perfil is None:
            continue
        candidato.definir_seguidores(perfil.seguidores, "instaloader")
        candidato.adicionar_texto(perfil.bio)
        if perfil.posts:
            candidato.ultimos_posts = formatar_posts([(url, legenda) for url, legenda in perfil.posts])
        if perfil.site and not candidato.site and serve_como_site(perfil.site):
            candidato.site = origem_do_site(perfil.site)
        if perfil.nome and parece_pessoa(perfil.nome) and nome_aceitavel(perfil.nome) and not parece_pessoa(candidato.nome):
            if candidato.nome and not candidato.programa_mentoria:
                candidato.programa_mentoria = candidato.nome
            candidato.nome = perfil.nome
        if not candidato.cidade_uf and perfil.bio:
            candidato.cidade_uf = extrair_cidade(perfil.bio)


def _finalizar(candidato: Candidato, config: Config) -> None:
    if not candidato.programa_mentoria:
        candidato.programa_mentoria = extrair_programa(candidato.titulos) or extrair_programa(candidato.corpus[:700])
    if candidato.programa_mentoria and dobrar(candidato.programa_mentoria) == dobrar(candidato.nome) and parece_pessoa(candidato.nome):
        candidato.programa_mentoria = ""
    if not candidato.cidade_uf:
        candidato.cidade_uf = extrair_cidade(f"{candidato.titulos}\n{candidato.corpus[:1500]}")
    candidato.menciona_contador_parceiro = classificar_parceiro(f"{candidato.titulos}\n{candidato.corpus}")
    if candidato.instagram_handle:
        candidato.instagram_url = f"https://www.instagram.com/{candidato.instagram_handle}/"
    if candidato.site and (plataforma(candidato.site) or not serve_como_site(candidato.site)):
        candidato.site = ""
    candidato.score = pontuar(candidato, config)


def _ordem_nichos(config: Config, dia: date, nichos_ids: list[str] | None) -> list[Nicho]:
    if nichos_ids:
        queridos = {item.strip() for item in nichos_ids if item.strip()}
        escolhidos = [nicho for nicho in config.nichos if nicho.id in queridos]
        if not escolhidos:
            raise ValueError("Nenhum nicho informado existe na configuração")
        return escolhidos
    quantidade = len(config.nichos)
    return nichos_do_dia(config.nichos, dia, quantidade)
