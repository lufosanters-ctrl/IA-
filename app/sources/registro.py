"""Registro das fontes disponiveis e roteamento por area de conhecimento."""

from __future__ import annotations

from ..texto import normalizar
from .arxiv import FonteArxiv
from .base import FonteBase
from .crossref import FonteCrossref
from .openalex import FonteOpenAlex
from .openlibrary import FonteOpenLibrary
from .pubmed import FontePubMed
from .semanticscholar import FonteSemanticScholar
from .stackexchange import FonteStackExchange
from .wikipedia import FonteWikipedia

FONTES: dict[str, FonteBase] = {
    fonte.id: fonte
    for fonte in (
        FonteWikipedia(),
        FonteOpenAlex(),
        FonteArxiv(),
        FontePubMed(),
        FonteSemanticScholar(),
        FonteCrossref(),
        FonteOpenLibrary(),
        FonteStackExchange(),
    )
}

# Conjunto padrao: cobertura ampla sem estourar o tempo de resposta.
FONTES_PADRAO = ("wikipedia", "openalex", "arxiv", "pubmed", "semanticscholar")

# Palavras que sugerem a area da pergunta -> fontes prioritarias.
PISTAS_AREA: dict[str, tuple[str, ...]] = {
    "medicina": (
        "doenca", "doencas", "sintoma", "sintomas", "tratamento", "clinico", "paciente",
        "farmaco", "medicamento", "diagnostico", "cancer", "virus", "vacina", "terapia",
        "anatomia", "fisiologia", "enfermagem", "saude", "epidemiologia", "neuronio",
    ),
    "computacao": (
        "algoritmo", "programacao", "python", "javascript", "codigo", "software",
        "compilador", "banco de dados", "api", "rede neural", "machine learning",
        "aprendizado de maquina", "criptografia", "estrutura de dados", "docker",
        "kubernetes", "framework", "typescript", "compilacao", "front-end", "back-end",
    ),
    "matematica": (
        "integral", "derivada", "teorema", "equacao", "matriz", "algebra", "calculo",
        "geometria", "probabilidade", "estatistica", "limite", "funcao quadratica",
        "logaritmo", "trigonometria", "vetor", "demonstracao",
    ),
    "fisica": (
        "quantica", "relatividade", "termodinamica", "particula", "eletromagnetismo",
        "optica", "mecanica", "energia", "forca", "gravidade", "onda",
    ),
    "humanas": (
        "historia", "filosofia", "sociologia", "guerra", "revolucao", "literatura",
        "politica", "economia", "direito", "constituicao", "cultura", "antropologia",
    ),
}

FONTES_POR_AREA: dict[str, tuple[str, ...]] = {
    "medicina": ("pubmed", "wikipedia", "openalex", "semanticscholar"),
    "computacao": ("arxiv", "stackexchange", "wikipedia", "semanticscholar"),
    "matematica": ("wikipedia", "arxiv", "stackexchange", "openalex"),
    "fisica": ("arxiv", "wikipedia", "openalex", "semanticscholar"),
    "humanas": ("wikipedia", "openalex", "openlibrary", "crossref"),
}


# Rotulos acentuados das areas, so para exibicao. As chaves internas ficam
# sem acento porque sao comparadas com texto normalizado.
ROTULOS_AREA: dict[str, str] = {
    "computacao": "computação",
    "matematica": "matemática",
    "fisica": "física",
    "estatistica": "estatística",
    "medicina": "medicina",
    "biologia": "biologia",
    "saude": "saúde",
    "neurociencia": "neurociência",
    "academico": "acadêmico",
    "ciencia": "ciência",
    "historia": "história",
    "referencia": "referência",
    "engenharia": "engenharia",
    "programacao": "programação",
    "pratica": "prática",
    "ia": "IA",
}


def rotular_area(area: str) -> str:
    """Nome da area como deve aparecer na interface."""
    return ROTULOS_AREA.get(area, area)


def listar_fontes() -> list[dict]:
    """Descricao das fontes para exibir na interface."""
    fontes = []
    for fonte in FONTES.values():
        dados = fonte.para_dict()
        dados["areas"] = [rotular_area(a) for a in dados["areas"]]
        fontes.append(dados)
    return fontes


def fonte_por_id(identificador: str) -> FonteBase | None:
    return FONTES.get(identificador)


def detectar_area(consulta: str) -> str:
    """Deduz a area do conhecimento a partir das palavras da pergunta."""
    texto = f" {normalizar(consulta)} "
    melhor_area, melhor_pontos = "geral", 0.0
    for area, pistas in PISTAS_AREA.items():
        pontos = 0.0
        for pista in pistas:
            alvo = normalizar(pista)
            # Expressoes com mais de uma palavra sao um sinal mais forte.
            peso = 1.0 + 0.8 * alvo.count(" ")
            if f" {alvo} " in texto or f" {alvo}s " in texto:
                pontos += peso
        if pontos > melhor_pontos:
            melhor_area, melhor_pontos = area, pontos
    return melhor_area


def escolher_fontes(consulta: str, pedidas: list[str] | None = None) -> list[str]:
    """Decide quais bases consultar: escolha do usuario ou roteamento automatico."""
    if pedidas:
        validas = [f for f in pedidas if f in FONTES]
        if validas:
            return validas
    area = detectar_area(consulta)
    return list(FONTES_POR_AREA.get(area, FONTES_PADRAO))
