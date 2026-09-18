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


@pytest.fixture(autouse=True)
def banco_temporario(tmp_path, monkeypatch):
    """Cada teste usa um SQLite proprio, isolado do banco real."""
    from app import banco, config

    config.obter_config.cache_clear()
    monkeypatch.setenv("NUCLEO_CAMINHO_BANCO", str(tmp_path / "teste.db"))
    cfg = config.obter_config()
    monkeypatch.setattr(cfg, "caminho_banco", tmp_path / "teste.db")
    banco.iniciar_banco()
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


ROTAS = {
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
