import unittest
from datetime import date

from almore_scraper.config import Nicho, carregar_config, nichos_do_dia
from almore_scraper.filtros import (
    Indice,
    classificar_parceiro,
    eh_mentor_de_contabilidade,
    motivo_descarte,
    pontuar,
    selecionar,
)
from almore_scraper.modelos import Candidato


def _config():
    return carregar_config()


def _mentor(**kwargs):
    base = dict(
        nome="Leandro Silva",
        nicho="Autopeças",
        instagram_handle="leandrosilva",
        instagram_url="https://www.instagram.com/leandrosilva/",
        site="https://conexao.example.com.br/",
        fonte_url="https://conexao.example.com.br/",
        corpus="Mentoria para donos de autopeças. Turma de lojistas no Brasil.",
        titulos="Mentoria para donos de autopeças",
        termos_nicho=["autopeças"],
        data_entrada="2026-11-10",
    )
    base.update(kwargs)
    return Candidato(**base)


class FiltrosTeste(unittest.TestCase):
    def test_config_sem_contabilidade_e_rotacao(self):
        config = _config()
        self.assertGreaterEqual(len(config.nichos), 30)
        self.assertTrue(all("contab" not in nicho.id for nicho in config.nichos))
        dia_a = nichos_do_dia(config.nichos, date(2026, 11, 10), 8)
        dia_b = nichos_do_dia(config.nichos, date(2026, 11, 11), 8)
        self.assertEqual(len(dia_a), 8)
        self.assertNotEqual([nicho.id for nicho in dia_a], [nicho.id for nicho in dia_b])
        consultas = config.consultas(config.nichos[0])
        self.assertGreaterEqual(len(consultas), 3)
        self.assertTrue(all("contadores" not in consulta for consulta in consultas))

    def test_contabilidade_e_parceiro(self):
        self.assertTrue(eh_mentor_de_contabilidade("Mentoria para contadores que querem captar clientes"))
        self.assertTrue(eh_mentor_de_contabilidade("Programa", "Brasct Contabilidade", "https://brasct.com.br/"))
        self.assertTrue(eh_mentor_de_contabilidade("", "", "https://chattarcontabilidade.com.br/artigo"))
        self.assertFalse(
            eh_mentor_de_contabilidade(
                "Mentor de e-commerce. Nosso contador parceiro atende a comunidade.",
                "Pedro Guinle",
                "https://www.pedroguinle.com/",
            )
        )
        self.assertFalse(eh_mentor_de_contabilidade("Não sou contador, sou mentor de oficinas mecânicas."))
        texto = "Mentor de oficinas para donos de negócio. " + ("operação lucrativa. " * 8)
        self.assertEqual(classificar_parceiro(texto), "no")
        texto_sim = texto + " O contador parceiro da turma é o escritório local."
        self.assertTrue(classificar_parceiro(texto_sim).startswith("yes |"))
        negado = texto + " Ainda não temos contador parceiro."
        self.assertEqual(classificar_parceiro(negado), "no")
        self.assertEqual(classificar_parceiro("Mentoria curta."), "")

    def test_descarte_pontuacao_e_selecao(self):
        config = _config()
        indice = Indice()
        bom = _mentor()
        self.assertEqual(motivo_descarte(bom, config, indice), "")
        mega = _mentor(seguidores="8000000")
        self.assertEqual(motivo_descarte(mega, config, indice), "seguidores")
        famoso = _mentor(instagram_handle="anitta")
        self.assertEqual(motivo_descarte(famoso, config, indice), "celebridade")
        contabil = _mentor(corpus="Mentoria para contadores e escritórios contábeis no Brasil, com turma.")
        self.assertEqual(motivo_descarte(contabil, config, indice), "contabilidade")
        indice.adicionar(bom)
        self.assertEqual(motivo_descarte(bom, config, indice), "duplicado")

        pequeno = _mentor(seguidores="12000", seguidores_origem="snippet_perfil")
        grande = _mentor(nome="Ana Souza", instagram_handle="anasouza", seguidores="140000", seguidores_origem="snippet_perfil")
        pequeno.menciona_contador_parceiro = "no"
        grande.menciona_contador_parceiro = "yes | contador parceiro"
        pequeno.score = pontuar(pequeno, config)
        grande.score = pontuar(grande, config)
        self.assertGreater(pequeno.score, grande.score)

        nichos = []
        for indice_nicho in range(3):
            for numero in range(13):
                item = _mentor(
                    nome=f"Pessoa {indice_nicho}{numero} Silva",
                    nicho=f"Nicho {indice_nicho}",
                    instagram_handle=f"pessoa{indice_nicho}{numero}",
                    site=f"https://pessoa{indice_nicho}{numero}.com.br/",
                )
                item.score = 10
                nichos.append(item)
        config.max_por_nicho = 12
        escolhidos = selecionar(nichos, config, 30)
        self.assertEqual(len(escolhidos), 30)
        self.assertLessEqual(sum(item.nicho == "Nicho 0" for item in escolhidos[:24]), 12)


if __name__ == "__main__":
    unittest.main()
