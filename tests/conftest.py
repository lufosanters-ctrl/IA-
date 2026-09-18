"""Configuracao dos testes: banco temporario e respostas simuladas das bases."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx
import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))


LIVRO_DE_TESTE = """# Fundamentos de Biologia Celular

## Capítulo 4 — Fotossíntese e o mecanismo de atenção metabólica

A fotossíntese é o processo pelo qual organismos convertem energia luminosa em
energia química armazenada em moléculas orgânicas. Ocorre nos cloroplastos,
organelas delimitadas por dupla membrana que contêm clorofila. A fase
fotoquímica acontece nas membranas dos tilacoides, onde a energia do fóton
excita elétrons da clorofila e alimenta a cadeia transportadora de elétrons.

O ciclo de Calvin, também chamado de fase bioquímica, ocorre no estroma do
cloroplasto e utiliza o ATP e o NADPH produzidos na fase fotoquímica para fixar
dióxido de carbono em moléculas de três carbonos. A enzima responsável pela
fixação é a rubisco, considerada a proteína mais abundante da biosfera.

A taxa fotossintética depende da intensidade luminosa, da concentração de gás
carbônico e da temperatura. O ponto de compensação luminoso é a intensidade em
que a fotossíntese iguala a respiração celular, e o ponto de saturação é aquele
a partir do qual aumentar a luz não aumenta mais a taxa.
"""


@pytest.fixture(autouse=True)
def banco_temporario(tmp_path, monkeypatch):
    """Cada teste usa SQLite e biblioteca proprios, isolados dos reais."""
    from app import banco, biblioteca, config

    config.obter_config.cache_clear()
    cfg = config.obter_config()
    monkeypatch.setattr(cfg, "caminho_banco", tmp_path / "teste.db")
    monkeypatch.setattr(cfg, "diretorio_biblioteca", tmp_path / "biblioteca")
    (tmp_path / "biblioteca").mkdir(parents=True, exist_ok=True)

    banco.iniciar_banco()
    biblioteca.iniciar()

    # Um livro didatico sempre presente: a biblioteca local faz parte do
    # caminho normal da busca, entao os testes precisam exercita-la.
    arquivo = tmp_path / "biblioteca" / "biologia-celular.md"
    arquivo.write_text(LIVRO_DE_TESTE, encoding="utf-8")
    biblioteca.indexar(arquivo, area="biologia")

    yield
    config.obter_config.cache_clear()


# --------------------------------------------------------------------------
# Respostas falsas das APIs publicas
# --------------------------------------------------------------------------

ATOM_ARXIV = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/1706.03762v5</id>
    <published>2017-06-12T00:00:00Z</published>
    <title>Attention Is All You Need</title>
    <summary>The dominant sequence transduction models are based on complex recurrent
    or convolutional neural networks. We propose a new simple network architecture,
    the Transformer, based solely on attention mechanisms, dispensing with recurrence
    and convolutions entirely. Experiments show these models to be superior in quality
    while being more parallelizable and requiring significantly less time to train.</summary>
    <author><name>Ashish Vaswani</name></author>
    <author><name>Noam Shazeer</name></author>
  </entry>
</feed>
"""


def _resposta_wikipedia(pedido: httpx.Request) -> httpx.Response:
    acao = pedido.url.params.get("list") or pedido.url.params.get("prop")
    if acao == "search":
        return httpx.Response(200, json={
            "query": {"search": [{"title": "Transformer (modelo)", "pageid": 42}]}
        })
    return httpx.Response(200, json={
        "query": {"pages": {"42": {
            "pageid": 42,
            "title": "Transformer (modelo)",
            "fullurl": "https://pt.wikipedia.org/wiki/Transformer",
            "extract": (
                "O Transformer e uma arquitetura de rede neural baseada em atencao. "
                "O mecanismo de atencao permite que o modelo pondere a relevancia de "
                "cada token da sequencia de entrada. A arquitetura dispensa recorrencia "
                "e usa camadas de atencao multi-cabeca empilhadas. Isso torna o "
                "treinamento altamente paralelizavel em GPUs modernas."
            ),
        }}}
    })


def _resposta_openalex(pedido: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"results": [{
        "id": "https://openalex.org/W123",
        "doi": "https://doi.org/10.1000/xyz",
        "title": "Attention mechanisms in deep learning",
        "publication_year": 2019,
        "language": "en",
        "cited_by_count": 4210,
        "authorships": [{"author": {"display_name": "Jane Roe"}}],
        "primary_location": {
            "landing_page_url": "https://example.org/artigo",
            "source": {"display_name": "Journal of ML"},
        },
        "abstract_inverted_index": {
            "Attention": [0], "mechanisms": [1], "let": [2], "models": [3],
            "focus": [4], "on": [5], "relevant": [6], "parts": [7], "of": [8],
            "the": [9], "input": [10], "sequence": [11], "during": [12],
            "training": [13], "and": [14], "inference": [15],
        },
    }]})


def _resposta_pubmed(pedido: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"resultList": {"result": [{
        "id": "38000001", "pmid": "38000001", "source": "MED",
        "title": "Clinical outcomes of therapy X",
        "authorString": "Silva J, Souza M",
        "pubYear": "2023", "doi": "10.1000/abc",
        "journalTitle": "Journal of Medicine", "citedByCount": 12,
        "isOpenAccess": "Y",
        "abstractText": (
            "This randomized trial evaluated therapy X in 420 patients. "
            "The primary endpoint was reached in 62 percent of the treatment arm "
            "versus 41 percent of controls. Adverse events were comparable."
        ),
    }]}})


def _resposta_semanticscholar(pedido: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"data": [{
        "paperId": "abc123", "title": "A survey of transformers",
        "abstract": "Transformers have become the dominant architecture in NLP. "
                    "This survey reviews variants, efficiency techniques and applications.",
        "year": 2021, "url": "https://semanticscholar.org/paper/abc123",
        "authors": [{"name": "Tianyang Lin"}], "externalIds": {"DOI": "10.1000/survey"},
        "citationCount": 900, "influentialCitationCount": 80,
        "openAccessPdf": {"url": "https://example.org/pdf"}, "venue": "AI Open",
    }]})


def _resposta_crossref(pedido: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"message": {"items": [{
        "DOI": "10.1000/cr1", "title": ["Deep learning review"],
        "abstract": "<jats:p>A broad review of deep learning methods and results.</jats:p>",
        "author": [{"given": "Yann", "family": "Doe"}],
        "issued": {"date-parts": [[2015]]},
        "container-title": ["Nature"], "URL": "https://doi.org/10.1000/cr1",
        "is-referenced-by-count": 55000, "type": "journal-article",
    }]}})


def _resposta_openlibrary(pedido: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"docs": [{
        "key": "/works/OL1W", "title": "Deep Learning",
        "author_name": ["Ian Goodfellow", "Yoshua Bengio"],
        "first_publish_year": 2016,
        "first_sentence": ["An introduction to the mathematics of deep learning."],
        "subject": ["Machine learning", "Neural networks"],
        "language": ["eng"], "cover_i": 999, "edition_count": 4,
    }]})


def _resposta_stackexchange(pedido: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"items": [{
        "question_id": 777, "title": "How does self-attention work?",
        "body": "<p>I am trying to understand how self-attention computes weights "
                "between tokens in a sequence. Could someone explain the math?</p>",
        "link": "https://stackoverflow.com/q/777", "score": 42, "is_answered": True,
        "tags": ["nlp", "transformers"],
    }]})


def _resposta_wikilivros(pedido: httpx.Request) -> httpx.Response:
    lista = pedido.url.params.get("list")
    if lista == "search":
        return httpx.Response(200, json={"query": {"search": [
            {"title": "Cálculo/Capítulo 1"}, {"title": "Cálculo"},
        ]}})
    if lista == "allpages":
        return httpx.Response(200, json={"query": {"allpages": [
            {"title": "Cálculo/Limites"}, {"title": "Cálculo/Derivadas"},
        ]}})
    corpo = (
        "O limite de uma função descreve o comportamento dela quando a variável "
        "se aproxima de um valor. A definição formal usa épsilon e delta para "
        "tornar precisa a ideia intuitiva de aproximação. A derivada é o limite "
        "da razão incremental e mede a taxa de variação instantânea da função. "
    ) * 4
    return httpx.Response(200, json={"query": {"pages": {
        "1": {"title": "Cálculo", "extract": corpo},
        "2": {"title": "Cálculo/Limites", "extract": corpo},
        "3": {"title": "Cálculo/Derivadas", "extract": corpo},
    }}})


def _resposta_gutendex(pedido: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"results": [{
        "id": 33283, "title": "Calculus Made Easy",
        "authors": [{"name": "Thompson, Silvanus P."}],
        "formats": {"text/plain; charset=utf-8":
                    "https://www.gutenberg.org/files/33283/33283-0.txt"},
    }]})


def _resposta_gutenberg_arquivo(pedido: httpx.Request) -> httpx.Response:
    miolo = (
        "Considerando que a derivada mede a taxa de variação de uma grandeza, "
        "o cálculo diferencial se torna uma ferramenta simples de usar. "
    ) * 60
    inicio = "cabeçalho\n*** START OF THIS PROJECT GUTENBERG EBOOK ***\n"
    fim = "\n*** END OF THIS PROJECT GUTENBERG EBOOK ***\nrodapé"
    return httpx.Response(200, text=inicio + miolo + fim)


ROTAS = {
    "pt.wikibooks.org": _resposta_wikilivros,
    "gutendex.com": _resposta_gutendex,
    "www.gutenberg.org": _resposta_gutenberg_arquivo,
    "wikipedia.org": _resposta_wikipedia,
    "api.openalex.org": _resposta_openalex,
    "export.arxiv.org": lambda p: httpx.Response(200, text=ATOM_ARXIV),
    "www.ebi.ac.uk": _resposta_pubmed,
    "api.semanticscholar.org": _resposta_semanticscholar,
    "api.crossref.org": _resposta_crossref,
    "openlibrary.org": _resposta_openlibrary,
    "api.stackexchange.com": _resposta_stackexchange,
}


def manipulador(pedido: httpx.Request) -> httpx.Response:
    """Roteia cada chamada simulada para a resposta falsa correspondente."""
    host = pedido.url.host
    for chave, funcao in ROTAS.items():
        if host.endswith(chave) or chave in host:
            return funcao(pedido)
    return httpx.Response(404, json={"erro": f"host nao simulado: {host}"})


@pytest.fixture
def cliente_falso() -> httpx.AsyncClient:
    """Cliente httpx que responde localmente, sem tocar a internet."""
    return httpx.AsyncClient(transport=httpx.MockTransport(manipulador))


@pytest.fixture(autouse=True)
def sem_rede(monkeypatch):
    """Garante que o pipeline use o transporte simulado."""
    from app.ai import pesquisa

    def criar_cliente_falso():
        return httpx.AsyncClient(transport=httpx.MockTransport(manipulador))

    monkeypatch.setattr(pesquisa, "criar_cliente", criar_cliente_falso)
    pesquisa.limpar_cache()
    yield
    pesquisa.limpar_cache()
