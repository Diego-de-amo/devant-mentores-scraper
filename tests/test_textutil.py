from datetime import datetime

from scraper.textutil import (
    excel_safe,
    find_city_uf,
    followers_label,
    ia_evidence,
    menciona_ia_field,
    parse_followers,
    parse_post_date,
    quoted_snippet,
)


def test_parse_followers_formats():
    assert parse_followers("17K Followers, 3,186 Following") == (17000, True)
    assert parse_followers("1,075 seguidores, A seguir 12") == (1075, False)
    assert parse_followers("1.075 seguidores") == (1075, False)
    assert parse_followers("232K Followers") == (232000, True)
    assert parse_followers("54K Followers") == (54000, True)
    assert parse_followers("~6,5 mil seguidores") == (6500, True)
    assert parse_followers("118,3 mil seguidores") == (118300, True)
    assert parse_followers("3,186 Following, 712 Posts") == (None, False)
    assert followers_label(17000, True) == "~17000"
    assert followers_label(1075, False) == "1075"
    assert followers_label(None, False) == ""


def test_ia_nao_confunde_com_verbo_ou_nome():
    assert ia_evidence("Maria foi ao escritório e ele ia para o curso") == ""
    assert ia_evidence("DIA DE CAMPO no escritório") == ""
    assert "inteligência artificial" in ia_evidence("fala de inteligência artificial no tributário").lower() or "artificial" in ia_evidence("fala de inteligência artificial no tributário")
    assert menciona_ia_field("uso de IA para fechar o balanço", inspected=False).startswith("sim:")
    assert menciona_ia_field("mentoria de gestão", inspected=False) == ""
    assert menciona_ia_field("mentoria de gestão do escritório contábil " * 5, inspected=True).startswith("não:")


def test_cidade_e_data_e_excel():
    assert find_city_uf("Atende em Maceió/AL e online") == "Maceió/AL"
    assert find_city_uf("Instagram/SP não é cidade") == ""
    assert find_city_uf("mora em São Paulo") == ""
    assert parse_post_date("jgromualdo on August 27, 2026: ok") == datetime(2026, 8, 27)
    assert parse_post_date("em 3 de março de 2026") == datetime(2026, 3, 3)
    assert excel_safe("=cmd") == "'=cmd"
    assert excel_safe("@jgromualdo") == "@jgromualdo"
    assert excel_safe("https://exemplo.com") == "https://exemplo.com"
    snippet = '17K Followers - Ana (@ana) on Instagram: "Direciono contadoras a sair do operacional"'
    assert quoted_snippet(snippet).startswith("Direciono contadoras")
