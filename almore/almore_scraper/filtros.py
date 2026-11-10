"""Regras de negócio: contabilidade, parceiro, pontuação e deduplicação."""

from __future__ import annotations

import re
from collections import Counter

from almore_scraper.config import Config, Nicho, nichos_do_dia
from almore_scraper.extracao import (
    artigo_generico,
    dominio_contabil,
    dominio_mega,
    host_de,
    nome_aceitavel,
    nome_e_contabilidade,
    parece_pessoa,
    plataforma,
)
from almore_scraper.modelos import Candidato
from almore_scraper.util_texto import chave_pessoa, dobrar, espacos, frase_no_trecho

_EXCLUSAO_CONTABIL = [
    re.compile(padrao, re.I)
    for padrao in (
        r"mentor(?:ia|ias|es|a)?\s+(?:para|de|em|voltada[s]? a)\s+(?:os\s+|as\s+)?contadores?",
        r"mentor(?:ia|ias|es|a)?\s+(?:para|de|em)\s+escrit[oó]rios?\s+cont[aá]b",
        r"mentor(?:ia|ias)?\s+cont[aá]bil",
        r"comunidade\s+de\s+contadores",
        r"exclusiv[oa]\s+para\s+contadores",
        r"(?:curso|forma[cç][aã]o|treinamento)\s+para\s+contadores",
        r"contadores?\s+e\s+escrit[oó]rios\s+cont[aá]beis",
        r"mentoria\s+para\s+(?:quem\s+)?(?:é|e)\s+contador",
    )
]

_NEGACAO_CONTADOR = re.compile(
    r"n[aã]o\s+(?:sou|somos|é|e|seria)\s+(?:um\s+|uma\s+)?contadora?\b|"
    r"n[aã]o\s+(?:é|e)\s+(?:uma\s+)?mentoria\s+para\s+contadores",
    re.I,
)

_MENTORIA = re.compile(r"\bmentor(?:ia|ias|es|a|ado|ados|ada|adas)?\b", re.I)
_EMPRESARIO = re.compile(
    r"\b(donos?|empres[aá]ri[oa]s?|lojistas?|empreendedores?|franqueados?|"
    r"produtores?\s+rurais|vendedores?|founders?|infoprodutores?|pmes?|meis?|"
    r"neg[oó]cios?|s[oó]cios?)\b",
    re.I,
)
_BASE = re.compile(
    r"\b(comunidade|turma|alunos|mentorados|mentoradas|membros|hotmart|kiwify|imers[aã]o)\b",
    re.I,
)
_PARCEIRO = [
    re.compile(padrao, re.I)
    for padrao in (
        r"contador(?:a|es)?\s+parceir[oa]s?",
        r"parceria\s+com\s+(?:o\s+|a\s+)?(?:escrit[oó]rio\s+de\s+)?contabil",
        r"parceria\s+cont[aá]bil",
        r"contabilidade\s+parceira",
        r"escrit[oó]rio\s+(?:de\s+)?contabilidade\s+parceir[oa]",
        r"contador(?:a)?\s+oficial",
        r"noss[oa]\s+contador(?:a)?",
        r"contador(?:a)?\s+da\s+(?:comunidade|mentoria|rede|turma)",
        r"indicamos\s+(?:o\s+|a\s+)?contador(?:a)?",
        r"contador(?:a)?\s+recomendad[oa]",
        r"parceiro\s+de\s+contabilidade",
        r"contabilidade\s+indicada",
    )
]
_PT_FORTE = {
    "com", "nao", "voce", "donos", "dono", "loja", "lojas", "negocio", "negocios",
    "brasil", "brasileiro", "brasileira", "seu", "sua", "tambem", "isso", "aqui",
    "dos", "das", "uma", "pela", "pelo", "ate", "como", "mais", "empresario",
    "empresarios", "empresaria", "empreendedor", "empreendedores", "lojista",
    "lojistas", "voce", "nao", "mentoria", "mentor", "para",
}


def texto_sem_negacao_contador(texto: str) -> str:
    return _NEGACAO_CONTADOR.sub(" ", texto or "")


def eh_mentor_de_contabilidade(texto: str, nome: str = "", url: str = "") -> bool:
    if url and dominio_contabil(url):
        return True
    if nome_e_contabilidade(nome):
        return True
    limpo = texto_sem_negacao_contador(texto)
    return any(padrao.search(limpo) for padrao in _EXCLUSAO_CONTABIL)


def tem_sinal_mentoria(texto: str) -> bool:
    return bool(_MENTORIA.search(texto or ""))


def tem_sinal_empresario(texto: str) -> bool:
    return bool(_EMPRESARIO.search(texto or ""))


def tem_base_de_mentorados(texto: str) -> bool:
    return bool(_BASE.search(texto or ""))


def termo_no_texto(texto: str, termos: list[str]) -> bool:
    blob = dobrar(texto)
    for termo in termos:
        pedaco = dobrar(termo)
        if pedaco and pedaco in blob:
            return True
        if pedaco.replace(" ", "") and pedaco.replace(" ", "") in blob.replace(" ", ""):
            return True
    return False


def parece_portugues(texto: str, site: str = "", cidade: str = "") -> bool:
    if cidade:
        return True
    if site and (".com.br" in site.lower() or site.lower().rstrip("/").endswith(".br")):
        return True
    tokens = set(re.sub(r"[^a-z0-9]+", " ", dobrar(texto)).split())
    fortes = tokens & (_PT_FORTE - {"mentoria", "mentor", "para"})
    return len(fortes) >= 1 and len(tokens & _PT_FORTE) >= 2


def classificar_parceiro(texto: str) -> str:
    bruto = texto or ""
    if len(espacos(bruto)) < 80:
        return ""
    for padrao in _PARCEIRO:
        for match in padrao.finditer(bruto):
            janela = bruto[max(0, match.start() - 40) : match.start()]
            if re.search(r"\b(n[aã]o|sem|nenhum|jamais)\b", janela, re.I):
                continue
            evidencia = frase_no_trecho(bruto, match.start(), match.end())
            return f"yes | {evidencia}" if evidencia else "yes"
    return "no"


def pontuar(candidato: Candidato, config: Config) -> int:
    texto = f"{candidato.titulos}\n{candidato.corpus}"
    pontos = 0
    if tem_sinal_mentoria(texto):
        pontos += 5
    if tem_sinal_empresario(texto):
        pontos += 5
    if tem_base_de_mentorados(texto):
        pontos += 3
    if candidato.instagram_handle:
        pontos += 3
    if candidato.linkedin_url:
        pontos += 2
    if candidato.site:
        pontos += 2
    if candidato.programa_mentoria:
        pontos += 2
    if candidato.cidade_uf:
        pontos += 1
    if candidato.seguidores.isdigit():
        quantidade = int(candidato.seguidores)
        if quantidade <= 30_000:
            pontos += 5
        elif quantidade <= config.preferencia_seguidores:
            pontos += 3
        elif quantidade <= config.teto_seguidores:
            pontos += 1
    if candidato.menciona_contador_parceiro.startswith("yes"):
        pontos -= 4
    return pontos


def motivo_descarte(candidato: Candidato, config: Config, conhecidos: "Indice") -> str:
    if not nome_aceitavel(candidato.nome):
        return "sem_nome" if not candidato.nome else "nome_generico"
    if dominio_mega(candidato.site) or dominio_mega(candidato.fonte_url) or dominio_mega(getattr(candidato, "fonte_url", "")):
        return "instituicao"
    texto = f"{candidato.titulos}\n{candidato.corpus}\n{candidato.nome}"
    if eh_mentor_de_contabilidade(texto, candidato.nome, candidato.site or candidato.fonte_url):
        return "contabilidade"
    if not tem_sinal_mentoria(texto):
        return "sem_mentoria"
    if not (tem_sinal_empresario(texto) or termo_no_texto(texto, candidato.termos_nicho + [candidato.nicho])):
        return "sem_publico"
    if artigo_generico(candidato.nome) or artigo_generico(candidato.titulos.split("\n")[0] if candidato.titulos else ""):
        if not candidato.instagram_handle and not parece_pessoa(candidato.nome):
            return "artigo"
    if candidato.instagram_handle.lower() in config.ignorar_handles:
        return "celebridade"
    if candidato.seguidores.isdigit() and int(candidato.seguidores) > config.teto_seguidores:
        return "seguidores"
    if not (candidato.instagram_handle or candidato.linkedin_url or candidato.site):
        return "sem_contato"
    if not parece_portugues(texto, candidato.site, candidato.cidade_uf):
        return "idioma"
    if conhecidos.contem(candidato):
        return "duplicado"
    return ""


def ordem_seguidores(candidato: Candidato, config: Config) -> tuple[int, int]:
    if not candidato.seguidores.isdigit():
        return (1, 0)
    quantidade = int(candidato.seguidores)
    if quantidade <= config.preferencia_seguidores:
        return (0, quantidade)
    return (2, quantidade)


def selecionar(candidatos: list[Candidato], config: Config, alvo: int | None = None) -> list[Candidato]:
    limite = config.alvo_por_dia if alvo is None else alvo
    ordenados = sorted(
        candidatos,
        key=lambda candidato: (
            -candidato.score,
            ordem_seguidores(candidato, config),
            dobrar(candidato.nome),
        ),
    )
    escolhidos: list[Candidato] = []
    contagem: Counter[str] = Counter()
    adiados: list[Candidato] = []
    for candidato in ordenados:
        if contagem[candidato.nicho] >= config.max_por_nicho:
            adiados.append(candidato)
            continue
        escolhidos.append(candidato)
        contagem[candidato.nicho] += 1
        if len(escolhidos) >= limite:
            return escolhidos
    for candidato in adiados:
        if len(escolhidos) >= limite:
            break
        escolhidos.append(candidato)
    return escolhidos


def mesclar(destino: Candidato, origem: Candidato) -> None:
    if origem.nome and (not destino.nome or (parece_pessoa(origem.nome) and not parece_pessoa(destino.nome))):
        if destino.nome and not destino.programa_mentoria and not parece_pessoa(destino.nome):
            destino.programa_mentoria = destino.nome
        destino.nome = origem.nome
    if not destino.nicho:
        destino.nicho = origem.nicho
    if origem.instagram_handle:
        destino.definir_handle(origem.instagram_handle)
    destino.linkedin_url = destino.linkedin_url or origem.linkedin_url
    if "/company/" in destino.linkedin_url and "/in/" in origem.linkedin_url:
        destino.linkedin_url = origem.linkedin_url
    if not destino.site:
        destino.site = origem.site
    if not destino.programa_mentoria:
        destino.programa_mentoria = origem.programa_mentoria
    elif origem.programa_mentoria and len(origem.programa_mentoria) > len(destino.programa_mentoria):
        destino.programa_mentoria = origem.programa_mentoria
    if not destino.cidade_uf:
        destino.cidade_uf = origem.cidade_uf
    if origem.seguidores:
        try:
            destino.definir_seguidores(int(origem.seguidores), origem.seguidores_origem or "snippet")
        except ValueError:
            pass
    if not destino.ultimos_posts:
        destino.ultimos_posts = origem.ultimos_posts
    if not destino.fonte_url or _fonte_melhor(origem.fonte_url, destino.fonte_url):
        if origem.fonte_url:
            destino.fonte_url = origem.fonte_url
    destino.adicionar_texto(origem.titulos, titulo=True)
    destino.adicionar_texto(origem.corpus)
    for termo in origem.termos_nicho:
        if termo not in destino.termos_nicho:
            destino.termos_nicho.append(termo)


def _fonte_melhor(nova: str, atual: str) -> bool:
    if not nova:
        return False
    if not atual:
        return True
    return (not plataforma(nova) and not dominio_contabil(nova)) and (plataforma(atual) or dominio_contabil(atual))


def mesmo_mentor(esquerda: Candidato, direita: Candidato) -> bool:
    if esquerda.instagram_handle and direita.instagram_handle:
        return esquerda.instagram_handle.lower() == direita.instagram_handle.lower()
    if esquerda.linkedin_url and esquerda.linkedin_url == direita.linkedin_url:
        return True
    if esquerda.site and direita.site and not plataforma(esquerda.site):
        if host_de(esquerda.site) and host_de(esquerda.site) == host_de(direita.site):
            return True
    chave_esq = chave_pessoa(esquerda.nome)
    chave_dir = chave_pessoa(direita.nome)
    if chave_esq and chave_esq == chave_dir and dobrar(esquerda.nicho) == dobrar(direita.nicho):
        return True
    if esquerda.fonte_url and esquerda.fonte_url == direita.fonte_url and plataforma(esquerda.fonte_url):
        return True
    return False


class Indice:
    def __init__(self) -> None:
        self.handles: set[str] = set()
        self.linkedins: set[str] = set()
        self.hosts: set[str] = set()
        self.pessoas: set[tuple[str, str]] = set()
        self.fontes: set[str] = set()

    def adicionar(self, candidato: Candidato) -> None:
        if candidato.instagram_handle:
            self.handles.add(candidato.instagram_handle.lower())
        if candidato.linkedin_url:
            self.linkedins.add(candidato.linkedin_url.lower())
        if candidato.site and not plataforma(candidato.site):
            host = host_de(candidato.site)
            if host:
                self.hosts.add(host)
        chave = chave_pessoa(candidato.nome)
        if chave and candidato.nicho:
            self.pessoas.add((chave, dobrar(candidato.nicho)))
        if candidato.fonte_url and plataforma(candidato.fonte_url):
            self.fontes.add(candidato.fonte_url.split("?")[0].rstrip("/").lower())

    def contem(self, candidato: Candidato) -> bool:
        if candidato.instagram_handle and candidato.instagram_handle.lower() in self.handles:
            return True
        if candidato.linkedin_url and candidato.linkedin_url.lower() in self.linkedins:
            return True
        if candidato.site and not plataforma(candidato.site):
            host = host_de(candidato.site)
            if host and host in self.hosts:
                return True
        chave = chave_pessoa(candidato.nome)
        if chave and (chave, dobrar(candidato.nicho)) in self.pessoas:
            return True
        if candidato.fonte_url and plataforma(candidato.fonte_url):
            if candidato.fonte_url.split("?")[0].rstrip("/").lower() in self.fontes:
                return True
        return False


def rotacao(nichos: list[Nicho], dia, quantidade: int) -> list[Nicho]:
    return nichos_do_dia(nichos, dia, quantidade)
