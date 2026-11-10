"""Registros que entram no CSV e estruturas internas."""

from __future__ import annotations

from dataclasses import dataclass, field

CAMPOS = [
    "nome",
    "nicho",
    "instagram_handle",
    "instagram_url",
    "linkedin_url",
    "site",
    "programa_mentoria",
    "cidade_uf",
    "seguidores",
    "menciona_contador_parceiro",
    "ultimos_posts",
    "fonte_url",
    "data_entrada",
]

ORIGEM_SEGUIDORES = {"snippet": 1, "snippet_perfil": 2, "instaloader": 3}


@dataclass
class ResultadoBusca:
    titulo: str
    url: str
    snippet: str
    provedor: str


@dataclass
class Candidato:
    nome: str = ""
    nicho: str = ""
    instagram_handle: str = ""
    instagram_url: str = ""
    linkedin_url: str = ""
    site: str = ""
    programa_mentoria: str = ""
    cidade_uf: str = ""
    seguidores: str = ""
    menciona_contador_parceiro: str = ""
    ultimos_posts: str = ""
    fonte_url: str = ""
    data_entrada: str = ""
    corpus: str = ""
    titulos: str = ""
    score: int = 0
    seguidores_origem: str = ""
    termos_nicho: list[str] = field(default_factory=list)

    def definir_handle(self, handle: str) -> None:
        handle = (handle or "").strip().lstrip("@")
        if not handle:
            return
        if self.instagram_handle and self.instagram_handle.lower() != handle.lower():
            return
        self.instagram_handle = handle
        self.instagram_url = f"https://www.instagram.com/{handle}/"

    def definir_seguidores(self, valor: int | None, origem: str) -> None:
        if valor is None or valor < 0:
            return
        atual = ORIGEM_SEGUIDORES.get(self.seguidores_origem, 0)
        nova = ORIGEM_SEGUIDORES.get(origem, 0)
        if self.seguidores and nova < atual:
            return
        self.seguidores = str(int(valor))
        self.seguidores_origem = origem

    def adicionar_texto(self, texto: str, *, titulo: bool = False) -> None:
        limpo = (texto or "").strip()
        if not limpo:
            return
        if titulo:
            if limpo.casefold() not in self.titulos.casefold():
                self.titulos = (self.titulos + "\n" + limpo).strip()
        if limpo.casefold() in self.corpus.casefold():
            return
        self.corpus = (self.corpus + "\n" + limpo).strip()
        if len(self.corpus) > 8000:
            self.corpus = self.corpus[:8000]

    def registro(self) -> dict[str, str]:
        from almore_scraper.util_texto import uma_linha

        limites = {
            "nome": 120,
            "nicho": 60,
            "instagram_handle": 40,
            "instagram_url": 120,
            "linkedin_url": 180,
            "site": 180,
            "programa_mentoria": 120,
            "cidade_uf": 60,
            "seguidores": 12,
            "menciona_contador_parceiro": 220,
            "ultimos_posts": 700,
            "fonte_url": 300,
            "data_entrada": 10,
        }
        linha: dict[str, str] = {}
        for campo in CAMPOS:
            valor = getattr(self, campo) or ""
            if campo == "seguidores":
                linha[campo] = valor if str(valor).isdigit() else ""
            else:
                linha[campo] = uma_linha(str(valor), limites[campo])
        if linha["instagram_handle"]:
            linha["instagram_url"] = f"https://www.instagram.com/{linha['instagram_handle']}/"
        return linha
