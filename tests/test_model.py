from scraper.model import (
    MasterIndex,
    Mentor,
    extract_post,
    mentor_from_hit,
    name_is_blocked,
    rejection_reason,
)
from scraper.search import Hit, unwrap_duckduckgo, unwrap_yahoo

JESSICA = Hit(
    url="https://www.instagram.com/jgromualdo/",
    title="Jéssica Romualdo | Mentora de Contadores (@jgromualdo) - Instagram",
    snippet=(
        "17K Followers, 3,186 Following, 712 Posts - "
        "Jéssica Romualdo | Mentora de Contadores (@jgromualdo) on Instagram: "
        '"Direciono contadoras a sair do operacional e terem uma operação que rode de verdade"'
    ),
    query="mentora de contadores instagram",
    engine="yahoo",
)

FLAVIO = Hit(
    url="https://www.instagram.com/flavio_contador_conceito/",
    title="Flávio Borges | Mentor de Contadores (@flavio_contador_conceito) - Instagram",
    snippet="232K Followers, 2,927 Following - Flávio Borges | Mentor de Contadores (@flavio_contador_conceito) on Instagram: \"Contadores\"",
    query="mentor de contadores",
    engine="duckduckgo",
)

ANDERSON = Hit(
    url="https://www.instagram.com/andersonhernandesoficial/",
    title="Anderson Hernandes | AH (@andersonhernandesoficial) - Instagram",
    snippet="175K Followers - Anderson Hernandes (@andersonhernandesoficial) on Instagram: \"Ajudo Contadores a terem resultado\"",
    query="mentor de contadores",
    engine="yahoo",
)

VIVIANE = Hit(
    url="https://www.instagram.com/vivianearaujo.cd/",
    title="Viviane Araújo | Mentora de Contadores (@vivianearaujo.cd) - Instagram",
    snippet="12K Followers - Viviane Araújo | Mentora de Contadores (@vivianearaujo.cd) on Instagram: \"Maestria contábil\"",
    query="mentora",
    engine="yahoo",
)

BLOG = Hit(
    url="https://andersonmaisse.com.br/blog/mentoria-para-contadores",
    title="Mentoria para Contadores: Guia Completo | Anderson Maisse",
    snippet="O que é mentoria para contadores e como escolher um mentor.",
    query="mentoria para contadores",
    engine="duckduckgo",
)

COLOMBIA = Hit(
    url="https://co.linkedin.com/in/fabian-baron",
    title="Fabián Barón - Mentor de Contadores | LinkedIn",
    snippet="Mentor de Contadores na Colômbia. Planeación tributaria Latam.",
    query="mentor de contadores linkedin",
    engine="yahoo",
)

RENATA = Hit(
    url="https://hotmart.com/pt-br/marketplace/produtos/mentoria-para-contadores-3efpr/Q81999125I",
    title="MENTORIA PARA CONTADORES - Renata Rodrigues Oliveira Ribeiro | Hotmart",
    snippet="Você receberá o acesso a MENTORIA PARA CONTADORES por email.",
    query="mentoria para contadores hotmart",
    engine="duckduckgo",
)

PEDRO_GRANDE = Hit(
    url="https://www.instagram.com/pedromcontador/",
    title="Pedro Mendes | Mentor de Contadores (@pedromcontador) - Instagram",
    snippet="54K Followers - Pedro Mendes | Mentor de Contadores (@pedromcontador) on Instagram: \"Escritório\"",
    query="mentor",
    engine="yahoo",
)

PEDRO_NERY = Hit(
    url="https://br.linkedin.com/in/pedrovhnery",
    title="Pedro Nery - Mentor de Contadores e Empreendedores | LinkedIn",
    snippet="Mentor de Contadores e Empreendedores. Mentoria para contadores no Brasil.",
    query="mentor de contadores linkedin",
    engine="yahoo",
)

CHARLENE = Hit(
    url="https://www.instagram.com/charlene_mentora/",
    title="Charlene Nunes | Mentora Contábil de Empresárias (@charlene_mentora) - Instagram",
    snippet="1,202 Followers - Charlene Nunes | Mentora Contábil de Empresárias (@charlene_mentora) on Instagram: \"Mais organização\"",
    query="mentoria contabil",
    engine="duckduckgo",
)

POST = Hit(
    url="https://www.instagram.com/reel/DfZexample1/",
    title="Jéssica Romualdo",
    snippet='12 likes, 1 comment - jgromualdo on August 27, 2026: "Uma operação que cabe na rotina da contadora"',
    query="jgromualdo",
    engine="duckduckgo",
)


def test_aceita_mentora_pequena_e_rejeita_o_resto():
    jessica, reason = mentor_from_hit(JESSICA)
    assert reason == ""
    assert jessica is not None
    assert jessica.nome == "Jéssica Romualdo"
    assert jessica.instagram_handle == "@jgromualdo"
    assert jessica.followers_num == 17000
    assert jessica.tema.startswith("Direciono contadoras")

    assert mentor_from_hit(FLAVIO)[1] == "acima_de_50k"
    assert mentor_from_hit(ANDERSON)[1] == "bloqueado"
    assert mentor_from_hit(BLOG)[1] == "fora_do_perfil"
    assert mentor_from_hit(COLOMBIA)[1] == "fora_do_brasil"
    assert mentor_from_hit(PEDRO_GRANDE)[1] == "acima_de_50k"
    assert mentor_from_hit(CHARLENE)[1] == "fora_do_perfil"
    mei = Hit(
        url="https://hotmart.com/pt-br/marketplace/produtos/mentoria-contabil-individual-online/B71315931Y",
        title="Mentoria Contábil - Bruno Reis | Hotmart",
        snippet="Criei essa mentoria contábil online para auxiliar os MEI.",
        query="mentoria contabil hotmart",
        engine="yahoo",
    )
    assert mentor_from_hit(mei)[1] == "fora_do_perfil"
    assert mentor_from_hit(POST)[1] == "url_ignorada"

    renata, reason = mentor_from_hit(RENATA)
    assert reason == ""
    assert renata is not None
    assert renata.nome == "Renata Rodrigues Oliveira Ribeiro"
    assert "hotmart.com" in renata.site

    nery, reason = mentor_from_hit(PEDRO_NERY)
    assert reason == ""
    assert nery is not None
    assert nery.nome == "Pedro Nery"
    assert nery.linkedin_url == "https://www.linkedin.com/in/pedrovhnery/"


def test_post_e_bloqueio_de_nomes():
    post = extract_post(POST)
    assert post is not None
    assert post.handle == "jgromualdo"
    assert post.date is not None and post.date.year == 2026
    assert "rotina da contadora" in post.caption
    assert name_is_blocked("Lucas Presa de Lima")
    assert name_is_blocked("Élcio Guioto")
    assert name_is_blocked("Felipe Guerra")
    assert not name_is_blocked("Anderson Maisse")
    assert not name_is_blocked("Fernanda Oliveira")


def test_dedupe_contra_o_master_e_teto_de_seguidores():
    index = MasterIndex(
        [
            {
                "nome": "Viviane Araújo",
                "instagram_handle": "@vivianearaujo.cd",
                "instagram_url": "https://www.instagram.com/vivianearaujo.cd/",
                "linkedin_url": "",
                "site": "",
                "tema": "",
                "cidade_uf": "",
                "seguidores": "",
                "menciona_ia": "",
                "ultimos_posts": "",
                "fonte_url": "",
                "data_entrada": "2026-11-09",
            }
        ]
    )
    viviane, reason = mentor_from_hit(VIVIANE)
    assert viviane is not None
    assert reason == ""
    assert rejection_reason(viviane, index) == "ja_no_master"

    no_limite = Mentor(
        nome="Ana Souza",
        instagram_handle="@anasouza.contabil",
        instagram_url="https://www.instagram.com/anasouza.contabil/",
        evidence="Mentora de contadores em Belo Horizonte/MG",
        followers_num=50000,
    )
    assert rejection_reason(no_limite) == ""
    no_limite.followers_num = 50001
    assert rejection_reason(no_limite) == "acima_de_50k"


def test_rejeita_titulo_de_produto_e_dominio_ja_no_funil():
    firma = Hit(
        url="https://www.instagram.com/contabilidadeconsultiva/",
        title="Contabilidade Consultiva (@contabilidadeconsultiva) - Instagram",
        snippet="Contabilidade Consultiva (@contabilidadeconsultiva) mentoria para contadores",
        query="mentoria",
        engine="yahoo",
    )
    assert mentor_from_hit(firma)[1] == "sem_nome"
    painel = Hit(
        url="https://contab.tutory.com.br/login.php",
        title="Entrar no Painel do Aluno",
        snippet="Cadastro Inicial. Mentoria para contadores.",
        query="mentoria",
        engine="yahoo",
    )
    assert mentor_from_hit(painel)[1] == "url_ignorada"
    marca = Hit(
        url="https://melhorprocesso.com.br/imersao2/",
        title="Melhor Processo",
        snippet="Imersão para estruturar seu escritório contábil.",
        query="mentoria",
        engine="yahoo",
    )
    assert mentor_from_hit(marca)[1] == "sem_nome"
    pedro = Hit(
        url="https://br.linkedin.com/in/pedrovhnery",
        title="Pedro Nery - Mentor de Contadores e Empreendedores | LinkedIn",
        snippet="Veja o perfil de Pedro Nery no LinkedIn, uma comunidade profissional de 1 bilhão de usuários.",
        query="mentor de contadores linkedin",
        engine="yahoo",
    )
    pedro_mentor, pedro_reason = mentor_from_hit(pedro)
    assert pedro_reason == ""
    assert pedro_mentor is not None
    assert "bilhão" not in pedro_mentor.tema
    assert "Mentor de Contadores" in pedro_mentor.tema
    helo = Hit(
        url="https://helodecastro.com.br/mentoria-contabil/",
        title="Programa Mentoria Contábil – Helô de Castro",
        snippet="Programa de mentoria contábil.",
        query="mentoria contábil",
        engine="yahoo",
    )
    mentor, reason = mentor_from_hit(helo)
    assert reason == ""
    assert mentor is not None
    assert mentor.nome == "Helô de Castro"

    index = MasterIndex(
        [
            {
                "nome": "Viviane Araújo",
                "instagram_handle": "@vivianearaujo.cd",
                "instagram_url": "",
                "linkedin_url": "",
                "site": "https://contadoresvisionarios.com.br/maestria-contabil/",
                "tema": "",
                "cidade_uf": "",
                "seguidores": "",
                "menciona_ia": "",
                "ultimos_posts": "",
                "fonte_url": "",
                "data_entrada": "2026-11-09",
            }
        ]
    )
    mesma_marca = Mentor(
        nome="Ana Paula Souza",
        instagram_handle="@ana.outra",
        instagram_url="https://www.instagram.com/ana.outra/",
        site="https://contadoresvisionarios.com.br/imersao-ia/",
        evidence="Mentoria para contadores",
    )
    assert index.matches(mesma_marca)


def test_espelho_de_instagram_nao_entra():
    from scraper.model import url_kind

    assert url_kind("https://imginn.com/p/DexaJUfRXP0/") == "skip"
    assert url_kind("https://www.instagram.com/fernandakzoficial/") == "instagram_profile"


def test_unwrap_buscadores():
    assert unwrap_duckduckgo(
        "//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.instagram.com%2Fjgromualdo%2F&rut=abc"
    ) == "https://www.instagram.com/jgromualdo/"
    assert unwrap_yahoo(
        "https://r.search.yahoo.com/RU=https%3a%2f%2fwww.instagram.com%2fjgromualdo%2f/RK=2/RS=abc"
    ) == "https://www.instagram.com/jgromualdo/"
