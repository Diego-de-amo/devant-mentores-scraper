import unittest
from datetime import date

from almore_scraper.extracao import (
    bio_de_snippet,
    decodificar_bing,
    eh_anomalia_ddg,
    extrair_programa,
    formatar_posts,
    handle_de_titulo,
    handle_de_url,
    legenda_de_snippet,
    linkedin_de_url,
    nome_de_titulo,
    parse_ddg,
    parse_seguidores,
    pessoa_de_texto,
    post_aproveitavel,
    relevante,
    url_de_post,
)
from almore_scraper.cidades import extrair_cidade


class ExtracaoTeste(unittest.TestCase):
    def test_handle_e_reservados(self):
        self.assertEqual(handle_de_url("https://www.instagram.com/pedroguinle/"), "pedroguinle")
        self.assertEqual(handle_de_url("https://www.instagram.com/p/Cx3MGh2OVbg/"), "")
        self.assertEqual(handle_de_url("https://www.instagram.com/reel/ABCDE12345/"), "")
        self.assertEqual(handle_de_titulo("Pedro Guinle (@pedroguinle) - Instagram"), "pedroguinle")

    def test_seguidores(self):
        self.assertEqual(parse_seguidores("2,629 Followers, 3,712 Following, 664 Posts"), 2629)
        self.assertEqual(parse_seguidores("504K Followers"), 504000)
        self.assertEqual(parse_seguidores("8M Followers"), 8000000)
        self.assertEqual(parse_seguidores("15 mil seguidores"), 15000)
        self.assertEqual(parse_seguidores("1,2 milhão de seguidores"), 1200000)
        self.assertEqual(parse_seguidores("2.629 seguidores"), 2629)
        self.assertIsNone(parse_seguidores("3,712 Following"))
        self.assertIsNone(parse_seguidores(""))

    def test_bing_e_ddg(self):
        import base64

        carga = base64.b64encode(b"https://metodojanga.com.br/").decode()
        url = f"https://www.bing.com/ck/a?!&&p=abc&u=a1{carga}&ntb=1"
        self.assertEqual(decodificar_bing(url), "https://metodojanga.com.br/")
        html = """
        <div class="result results_links">
          <a class="result__a" href="https://metodojanga.com.br/">Método J.A.N.G.A.</a>
          <div class="result__snippet">Mentoria para donos de restaurante.</div>
        </div>
        <div class="result result--ad">
          <a class="result__a" href="https://duckduckgo.com/y.js?ad_domain=ebay.com">Anúncio</a>
          <div class="result__snippet">Compre</div>
        </div>
        <form>
          <input type="hidden" name="vqd" value="4-1">
          <input type="hidden" name="s" value="10">
        </form>
        """
        achados, formulario = parse_ddg(html)
        self.assertEqual(len(achados), 1)
        self.assertEqual(achados[0][1], "https://metodojanga.com.br/")
        self.assertEqual(formulario["vqd"], "4-1")
        self.assertTrue(eh_anomalia_ddg("Unfortunately, bots use DuckDuckGo too."))

    def test_relevancia_descarta_lixo(self):
        bons = [("Mentoria para farmácias", "https://exemplo.com.br", "donos de farmácia")]
        lixo = [("Forum alemão", "https://exemplo.de/forum", "Windows Server")] * 8
        self.assertTrue(relevante(bons, "mentoria para donos de farmácia"))
        self.assertFalse(relevante(lixo, "mentoria para donos de farmácia"))

    def test_nome_programa_pessoa_e_posts(self):
        titulo = "Pedro Guinle | Consultoria e Mentoria em E-commerce"
        self.assertEqual(nome_de_titulo(titulo), "Pedro Guinle")
        self.assertEqual(nome_de_titulo("Método J.A.N.G.A. · Mentoria para donos de restaurante"), "Método J.A.N.G.A.")
        from almore_scraper.extracao import nome_aceitavel

        self.assertTrue(nome_aceitavel("Método J.A.N.G.A."))
        self.assertFalse(nome_aceitavel("Mentoria Empresarial"))
        self.assertTrue(nome_aceitavel("Mentoria Acelerador Autopeças"))
        self.assertEqual(
            pessoa_de_texto("O Acelerador Auto-Peças 100K, criado por Leandro Silva, é o programa."),
            "Leandro Silva",
        )
        programa = extrair_programa("Método J.A.N.G.A. · Mentoria para donos de restaurante")
        self.assertIn("J.A.N.G.A", programa)
        self.assertEqual(
            url_de_post("https://www.instagram.com/p/Cx3MGh2OVbg/"),
            "https://www.instagram.com/p/Cx3MGh2OVbg/",
        )
        self.assertFalse(post_aproveitavel("pedroguinle on April 21, 2023: \"foto\"", date(2026, 11, 10)))
        self.assertTrue(post_aproveitavel("pedroguinle on March 2, 2026: \"aula\"", date(2026, 11, 10)))
        self.assertEqual(
            formatar_posts([("https://www.instagram.com/p/ABCDE/", "aula de margem")]),
            "https://www.instagram.com/p/ABCDE/ | aula de margem",
        )
        self.assertIn("Escale", bio_de_snippet('on Instagram: "Escale seu e-commerce"'))
        self.assertEqual(legenda_de_snippet(': "Back in the days"', "titulo"), "Back in the days")

    def test_linkedin_e_cidade(self):
        self.assertEqual(
            linkedin_de_url("https://br.linkedin.com/in/pedroguinle"),
            "https://www.linkedin.com/in/pedroguinle",
        )
        self.assertEqual(extrair_cidade("Atendo empresários em Campinas e região."), "Campinas/SP")
        self.assertEqual(extrair_cidade("Escritório em São Paulo/SP."), "São Paulo/SP")
        self.assertEqual(extrair_cidade("Unidade São Paulo/RJ"), "")
        self.assertEqual(extrair_cidade("Mentoria/SP para lojistas"), "")
        self.assertEqual(extrair_cidade("Registro CRF/SP do farmacêutico"), "")
        from almore_scraper.extracao import nome_aceitavel, nome_de_titulo as titulo_nome

        self.assertEqual(
            titulo_nome("Mentoria Premium para Donos de Clínicas (@superdoutoresclub"),
            "Mentoria Premium para Donos de Clínicas",
        )
        self.assertFalse(nome_aceitavel("A plataforma para implementar IA no seu marketing"))
        self.assertFalse(nome_aceitavel("MERCADO LIVRE"))
        self.assertFalse(nome_aceitavel("Mentores e Mentoras"))
        self.assertFalse(nome_aceitavel("Mentoria delivery: entenda como turbinar seu negócio"))


if __name__ == "__main__":
    unittest.main()
