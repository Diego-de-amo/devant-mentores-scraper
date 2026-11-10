"""Cidades usadas só quando o texto traz uma pista explícita."""

from __future__ import annotations

import re

from almore_scraper.util_texto import dobrar

# Capitais e cidades grandes. O par é (nome canônico, UF).
_CIDADES: list[tuple[str, str]] = [
    ("Rio Branco", "AC"),
    ("Maceió", "AL"),
    ("Arapiraca", "AL"),
    ("Macapá", "AP"),
    ("Manaus", "AM"),
    ("Salvador", "BA"),
    ("Feira de Santana", "BA"),
    ("Vitória da Conquista", "BA"),
    ("Lauro de Freitas", "BA"),
    ("Camaçari", "BA"),
    ("Fortaleza", "CE"),
    ("Juazeiro do Norte", "CE"),
    ("Sobral", "CE"),
    ("Brasília", "DF"),
    ("Vitória", "ES"),
    ("Vila Velha", "ES"),
    ("Serra", "ES"),
    ("Cariacica", "ES"),
    ("Goiânia", "GO"),
    ("Aparecida de Goiânia", "GO"),
    ("Anápolis", "GO"),
    ("Rio Verde", "GO"),
    ("São Luís", "MA"),
    ("Imperatriz", "MA"),
    ("Cuiabá", "MT"),
    ("Rondonópolis", "MT"),
    ("Sinop", "MT"),
    ("Campo Grande", "MS"),
    ("Dourados", "MS"),
    ("Belo Horizonte", "MG"),
    ("Uberlândia", "MG"),
    ("Contagem", "MG"),
    ("Juiz de Fora", "MG"),
    ("Betim", "MG"),
    ("Montes Claros", "MG"),
    ("Uberaba", "MG"),
    ("Governador Valadares", "MG"),
    ("Ipatinga", "MG"),
    ("Divinópolis", "MG"),
    ("Sete Lagoas", "MG"),
    ("Poços de Caldas", "MG"),
    ("Pouso Alegre", "MG"),
    ("Varginha", "MG"),
    ("Belém", "PA"),
    ("Ananindeua", "PA"),
    ("Santarém", "PA"),
    ("Marabá", "PA"),
    ("Parauapebas", "PA"),
    ("João Pessoa", "PB"),
    ("Campina Grande", "PB"),
    ("Curitiba", "PR"),
    ("Londrina", "PR"),
    ("Maringá", "PR"),
    ("Ponta Grossa", "PR"),
    ("Cascavel", "PR"),
    ("Foz do Iguaçu", "PR"),
    ("São José dos Pinhais", "PR"),
    ("Colombo", "PR"),
    ("Recife", "PE"),
    ("Jaboatão dos Guararapes", "PE"),
    ("Olinda", "PE"),
    ("Caruaru", "PE"),
    ("Petrolina", "PE"),
    ("Teresina", "PI"),
    ("Parnaíba", "PI"),
    ("Rio de Janeiro", "RJ"),
    ("São Gonçalo", "RJ"),
    ("Duque de Caxias", "RJ"),
    ("Nova Iguaçu", "RJ"),
    ("Niterói", "RJ"),
    ("Belford Roxo", "RJ"),
    ("Campos dos Goytacazes", "RJ"),
    ("Petrópolis", "RJ"),
    ("Volta Redonda", "RJ"),
    ("Macaé", "RJ"),
    ("Cabo Frio", "RJ"),
    ("Nova Friburgo", "RJ"),
    ("Angra dos Reis", "RJ"),
    ("Resende", "RJ"),
    ("Barra Mansa", "RJ"),
    ("Maricá", "RJ"),
    ("Natal", "RN"),
    ("Mossoró", "RN"),
    ("Parnamirim", "RN"),
    ("Porto Alegre", "RS"),
    ("Caxias do Sul", "RS"),
    ("Pelotas", "RS"),
    ("Canoas", "RS"),
    ("Santa Maria", "RS"),
    ("Novo Hamburgo", "RS"),
    ("São Leopoldo", "RS"),
    ("Passo Fundo", "RS"),
    ("Rio Grande", "RS"),
    ("Gravataí", "RS"),
    ("Porto Velho", "RO"),
    ("Boa Vista", "RR"),
    ("Florianópolis", "SC"),
    ("Joinville", "SC"),
    ("Blumenau", "SC"),
    ("Balneário Camboriú", "SC"),
    ("Chapecó", "SC"),
    ("Itajaí", "SC"),
    ("Criciúma", "SC"),
    ("Jaraguá do Sul", "SC"),
    ("São José", "SC"),
    ("Palhoça", "SC"),
    ("São Paulo", "SP"),
    ("Guarulhos", "SP"),
    ("Campinas", "SP"),
    ("São Bernardo do Campo", "SP"),
    ("Santo André", "SP"),
    ("Osasco", "SP"),
    ("Ribeirão Preto", "SP"),
    ("Sorocaba", "SP"),
    ("São José dos Campos", "SP"),
    ("São José do Rio Preto", "SP"),
    ("Santos", "SP"),
    ("Mauá", "SP"),
    ("Diadema", "SP"),
    ("Jundiaí", "SP"),
    ("Piracicaba", "SP"),
    ("Bauru", "SP"),
    ("Itaquaquecetuba", "SP"),
    ("São Vicente", "SP"),
    ("Franca", "SP"),
    ("Guarujá", "SP"),
    ("Taubaté", "SP"),
    ("Praia Grande", "SP"),
    ("Limeira", "SP"),
    ("Suzano", "SP"),
    ("Taboão da Serra", "SP"),
    ("Sumaré", "SP"),
    ("Barueri", "SP"),
    ("Embu das Artes", "SP"),
    ("Indaiatuba", "SP"),
    ("Cotia", "SP"),
    ("Americana", "SP"),
    ("Marília", "SP"),
    ("Araraquara", "SP"),
    ("Presidente Prudente", "SP"),
    ("São Carlos", "SP"),
    ("Hortolândia", "SP"),
    ("Rio Claro", "SP"),
    ("Jacareí", "SP"),
    ("Itu", "SP"),
    ("Atibaia", "SP"),
    ("Aracaju", "SE"),
    ("Palmas", "TO"),
]

UFS = {
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG",
    "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
}

_BLOQUEIO = {
    "mentoria", "mentor", "programa", "curso", "instagram", "linkedin", "brasil",
    "online", "hotmart", "grupo", "escola", "metodo", "comunidade", "blog",
    "artigo", "loja", "oficial", "crf", "crm", "cro", "coren", "cref", "cnpj",
    "cpf", "mei", "ltda",
}

_POR_DOBRADO: dict[str, tuple[str, str]] = {}
for _nome, _uf in _CIDADES:
    _POR_DOBRADO.setdefault(dobrar(_nome), (_nome, _uf))

_ORDENADAS = sorted(_CIDADES, key=lambda item: len(item[0]), reverse=True)
_ALTERNATIVA = "|".join(re.escape(nome) for nome, _uf in _ORDENADAS)
_LOCALIZADOR = re.compile(rf"\b(?:em|de|na|no|nas|nos)\s+({_ALTERNATIVA})\b", re.IGNORECASE)
_COM_UF = re.compile(rf"\b({_ALTERNATIVA})\s*[/\-–]\s*([A-Za-z]{{2}})\b", re.IGNORECASE)
_LIVRE = re.compile(
    r"\b([A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÁÉÍÓÚÂÊÔÃÕÇáéíóúâêôãõç]+"
    r"(?:\s+(?:de|da|do|dos|das)\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÁÉÍÓÚÂÊÔÃÕÇáéíóúâêôãõç]+"
    r"|\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÁÉÍÓÚÂÊÔÃÕÇáéíóúâêôãõç]+){0,3})"
    r"\s*/\s*(AC|AL|AP|AM|BA|CE|DF|ES|GO|MA|MT|MS|MG|PA|PB|PR|PE|PI|RJ|RN|RS|RO|RR|SC|SP|SE|TO)\b"
)


def _canonico(trecho: str) -> tuple[str, str] | None:
    return _POR_DOBRADO.get(dobrar(trecho))


def extrair_cidade(texto: str) -> str:
    if not texto:
        return ""
    conflito = False
    for match in _COM_UF.finditer(texto):
        par = _canonico(match.group(1))
        uf = match.group(2).upper()
        if par and par[1] == uf:
            return f"{par[0]}/{par[1]}"
        if par and par[1] != uf:
            conflito = True
    match = _LOCALIZADOR.search(texto)
    if match:
        par = _canonico(match.group(1))
        if par:
            return f"{par[0]}/{par[1]}"
    if conflito:
        return ""
    match = _LIVRE.search(texto)
    if match:
        cidade = match.group(1).strip()
        uf = match.group(2).upper()
        tokens = dobrar(cidade).split()
        if uf in UFS and tokens and not any(token in _BLOQUEIO for token in tokens):
            if cidade.isupper() and len(cidade) <= 5:
                return ""
            par = _canonico(cidade)
            if par:
                return f"{par[0]}/{par[1]}" if par[1] == uf else ""
            return f"{cidade}/{uf}"
    return ""
