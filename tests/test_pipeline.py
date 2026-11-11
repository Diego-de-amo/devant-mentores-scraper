from scraper.model import Post
from scraper.pipeline import run
from scraper.search import Hit
from scraper.store import load_csv, rows_from_funnel
from tests.test_model import (
    ANDERSON,
    BLOG,
    CHARLENE,
    COLOMBIA,
    FLAVIO,
    JESSICA,
    PEDRO_GRANDE,
    PEDRO_NERY,
    POST,
    RENATA,
    VIVIANE,
)

HITS = [
    JESSICA,
    FLAVIO,
    ANDERSON,
    VIVIANE,
    BLOG,
    COLOMBIA,
    RENATA,
    PEDRO_GRANDE,
    PEDRO_NERY,
    CHARLENE,
    POST,
]


def test_funil_tem_os_vinte_do_arquivo_anexo():
    rows = rows_from_funnel("data/seed/funil_mentores.csv")
    assert len(rows) == 20
    handles = {row["instagram_handle"].lstrip("@").lower() for row in rows}
    assert "contadorevoltado" in handles
    assert "andersonhernandesoficial" in handles
    assert "prof.fellipeguerra" in handles
    assert rows[0]["data_entrada"] == "2026-11-09"
    assert all(row["ultimos_posts"] == "" for row in rows)


def test_pipeline_offline_grava_so_mentores_novos(tmp_path):
    master = [
        {
            "nome": "Viviane Araújo",
            "instagram_handle": "@vivianearaujo.cd",
            "instagram_url": "https://www.instagram.com/vivianearaujo.cd/",
            "linkedin_url": "",
            "site": "https://contadoresvisionarios.com.br/maestria-contabil/",
            "tema": "Gestão de escritório",
            "cidade_uf": "",
            "seguidores": "~98500",
            "menciona_ia": "",
            "ultimos_posts": "",
            "fonte_url": "https://contadoresvisionarios.com.br/maestria-contabil/",
            "data_entrada": "2026-11-09",
        }
    ]
    from scraper.store import write_csv

    write_csv(tmp_path / "mentores_master.csv", master)

    def engine(query: str):
        if "mentor" not in query:
            return []
        return [Hit(**{**hit.__dict__, "query": query, "engine": "teste"}) for hit in HITS]

    def page(url: str):
        if "hotmart.com" in url:
            return {
                "ok": "1",
                "error": "",
                "title": "Mentoria para contadores",
                "description": "Mentoria para contadores com inteligência artificial aplicada ao tributário.",
                "text": "Página de vendas da mentoria para contadores. " * 30,
                "handles": [],
                "linkedin": "https://www.linkedin.com/in/renata-rodrigues-oliveira/",
            }
        return {"ok": "", "error": "HTTP 403", "title": "", "text": "", "description": "", "handles": [], "linkedin": ""}

    def instagram(mentors):
        for mentor in mentors:
            if mentor.instagram_handle.lower() == "@jgromualdo":
                mentor.set_followers(16940, False)
                mentor.inspected_text = True
                mentor.evidence += " Mentora de contadores. Operação do escritório."
                mentor.posts = [
                    Post(
                        url="https://www.instagram.com/p/AAA111bbb22/",
                        caption="Rotina da contadora dona de escritório",
                        date=None,
                        handle="jgromualdo",
                    )
                ]
        return {"modo": "anonimo", "status": "ok", "perfis_enriquecidos": 1, "detalhe": "teste"}

    report = run(
        data_dir=tmp_path,
        max_novos=20,
        engines=[("teste", engine)],
        page_fetcher=page,
        ig_enricher=instagram,
        pause=0,
        today="2026-11-10",
        search_posts=False,
    )
    assert report["novos"] >= 3
    nomes = set(report["mentores"])
    assert "Jéssica Romualdo" in nomes
    assert "Renata Rodrigues Oliveira Ribeiro" in nomes
    assert "Pedro Nery" in nomes
    assert "Viviane Araújo" not in nomes
    assert "Flávio Borges" not in nomes
    assert "Anderson Hernandes" not in nomes
    assert "Charlene Nunes" not in nomes

    daily = load_csv(tmp_path / "mentores_2026-11-10.csv")
    jessica = next(row for row in daily if row["nome"] == "Jéssica Romualdo")
    assert jessica["seguidores"] == "16940"
    assert jessica["menciona_ia"].startswith("não:")
    assert "https://www.instagram.com/p/AAA111bbb22/" in jessica["ultimos_posts"]
    assert jessica["data_entrada"] == "2026-11-10"
    renata = next(row for row in daily if "Renata" in row["nome"])
    assert renata["menciona_ia"].startswith("sim:")
    assert "inteligência artificial" in renata["menciona_ia"]
    assert "/in/renata-rodrigues-oliveira/" in renata["linkedin_url"]

    master_rows = load_csv(tmp_path / "mentores_master.csv")
    assert master_rows[0]["nome"] == "Viviane Araújo"
    assert len(master_rows) == 1 + len(daily)

    second = run(
        data_dir=tmp_path,
        max_novos=20,
        engines=[("teste", engine)],
        page_fetcher=page,
        ig_enricher=instagram,
        pause=0,
        today="2026-11-10",
        search_posts=False,
    )
    assert second["novos"] == 0
