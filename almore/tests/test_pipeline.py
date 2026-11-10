import json
import unittest
from collections import Counter
from datetime import date
from pathlib import Path

from almore_scraper.armazenamento import ler_csv
from almore_scraper.config import Config, Nicho
from almore_scraper.modelos import CAMPOS, ResultadoBusca
from almore_scraper.pipeline import executar


class _Busca:
    def __init__(self, mapa):
        self.mapa = mapa
        self.buscas = 0
        self.anomalias = 0
        self.provedores = Counter()
        self.bloqueios = Counter()

    def buscar(self, consulta, paginas=1):
        self.buscas += 1
        self.provedores["fake"] += 1
        for chave, valor in self.mapa.items():
            if chave in consulta:
                return valor
        return []


def _config():
    nicho = Nicho("restaurantes", "Food service", ["restaurantes"], [])
    return Config(
        alvo_por_dia=5,
        nichos_por_rodada=1,
        max_por_nicho=5,
        max_buscas=10,
        max_paginas_por_consulta=1,
        max_fetches=5,
        max_enriquecimentos=5,
        pausa_busca=(0, 0),
        pausa_fetch=(0, 0),
        pausa_instagram=(0, 0),
        templates=["mentoria para donos de {termo}"],
        ignorar_handles={"anitta"},
        nichos=[nicho],
    )


HTML = """
<html><head>
<title>Ezequiel Aguiar | Mentoria para donos de restaurante</title>
<meta name="description" content="Mentoria para donos de restaurante em Campinas. Turma de empresários.">
<script type="application/ld+json">
{"name": "Ezequiel Aguiar", "sameAs": ["https://www.instagram.com/ezequielaguiar/"]}
</script>
</head><body>
<p>Programa de mentoria para donos de restaurante. Não temos contador parceiro.</p>
</body></html>
"""


class PipelineTeste(unittest.TestCase):
    def test_grava_so_mentor_real_e_nao_inventa(self):
        resultado = ResultadoBusca(
            "Ezequiel Aguiar | Mentoria para donos de restaurante",
            "https://jornada.example.com.br/",
            "Mentoria para donos de restaurante que querem sair do operacional.",
            "fake",
        )
        contabil = ResultadoBusca(
            "Mentoria para contadores - Escritório Contábil",
            "https://chattarcontabilidade.com.br/mentoria",
            "Mentoria para contadores e escritórios contábeis.",
            "fake",
        )
        perfil = ResultadoBusca(
            "Ezequiel Aguiar (@ezequielaguiar) - Instagram",
            "https://www.instagram.com/ezequielaguiar/",
            '1,200 Followers, 300 Following, 40 Posts - Ezequiel Aguiar (@ezequielaguiar) on Instagram: "Mentoria para donos de restaurante em Campinas"',
            "fake",
        )
        post_velho = ResultadoBusca(
            "Ezequiel Aguiar - Instagram",
            "https://www.instagram.com/p/AAAAA11111/",
            '10 likes - ezequielaguiar on April 21, 2023: "foto antiga"',
            "fake",
        )
        buscador = _Busca(
            {
                "donos de restaurantes": [resultado, contabil],
                "instagram.com/ezequielaguiar": [perfil, post_velho],
            }
        )

        def baixar(url):
            if "jornada.example.com.br" in url:
                return HTML
            return None

        diretorio = Path(self.id().replace(".", "_"))
        # isolated temp via unittest
        import tempfile

        with tempfile.TemporaryDirectory() as pasta:
            diretorio = Path(pasta)
            resumo = executar(
                _config(),
                diretorio,
                date(2026, 11, 10),
                buscador=buscador,
                baixar=baixar,
                sem_instagram=True,
            )
            self.assertEqual(resumo["novos"], 1)
            linhas = ler_csv(diretorio / "mentores_master.csv")
            self.assertEqual(len(linhas), 1)
            linha = linhas[0]
            self.assertEqual(list(linha), CAMPOS)
            self.assertEqual(linha["nome"], "Ezequiel Aguiar")
            self.assertEqual(linha["nicho"], "Food service")
            self.assertEqual(linha["instagram_handle"], "ezequielaguiar")
            self.assertEqual(linha["seguidores"], "1200")
            self.assertEqual(linha["cidade_uf"], "Campinas/SP")
            self.assertEqual(linha["data_entrada"], "2026-11-10")
            self.assertEqual(linha["ultimos_posts"], "")
            self.assertTrue(linha["menciona_contador_parceiro"].startswith("no"))
            self.assertNotIn("chattar", json.dumps(linhas).lower())
            dia = ler_csv(diretorio / "mentores_2026-11-10.csv")
            self.assertEqual(dia, linhas)

            resumo2 = executar(
                _config(),
                diretorio,
                date(2026, 11, 10),
                buscador=buscador,
                baixar=baixar,
                sem_instagram=True,
            )
            self.assertEqual(resumo2["novos"], 0)
            self.assertEqual(len(ler_csv(diretorio / "mentores_master.csv")), 1)


if __name__ == "__main__":
    unittest.main()
