"""Testes da inteligencia de consulta: intencao, traducao e realimentacao."""

import httpx
import pytest

from app.consulta import (
    INTENCOES,
    classificar_intencao,
    consulta_expandida,
    termos_de_realimentacao,
    traduzir_pela_wikipedia,
    traduzir_pelo_glossario,
    versao_em_ingles,
)
from app.texto import Trecho


@pytest.mark.parametrize("pergunta,esperado", [
    ("O que é entropia?", "definicao"),
    ("Defina função exponencial", "definicao"),
    ("Como calcular a derivada de um produto?", "procedimento"),
    ("Passo a passo para montar um experimento", "procedimento"),
    ("Qual a diferença entre mitose e meiose?", "comparacao"),
    ("RNA versus DNA", "comparacao"),
    ("Por que a água ferve mais rápido na montanha?", "causa"),
    ("Quais os avanços recentes em supercondutores?", "estado_da_arte"),
    ("Estado da arte em modelos de linguagem", "estado_da_arte"),
    ("Calcule a integral definida de x ao quadrado", "exercicio"),
    ("me fale da lua", "geral"),
])
def test_classificacao_de_intencao(pergunta, esperado):
    assert classificar_intencao(pergunta).tipo == esperado


def test_ano_recente_sugere_estado_da_arte():
    assert classificar_intencao("terapias genicas em 2025").tipo == "estado_da_arte"


def test_intencao_de_definicao_valoriza_livro():
    pesos = INTENCOES["definicao"].pesos
    assert pesos["biblioteca"] > 1.0
    assert pesos["arxiv"] < 1.0


def test_intencao_de_estado_da_arte_valoriza_preprint():
    pesos = INTENCOES["estado_da_arte"].pesos
    assert pesos["arxiv"] > pesos["biblioteca"]
    assert pesos["openlibrary"] < 1.0


def test_glossario_traduz_expressao_longa_primeiro():
    assert traduzir_pelo_glossario("mecanismo de atenção") == "attention mechanism"


def test_glossario_junta_varios_conceitos():
    traducao = traduzir_pelo_glossario("relação entre diabetes e hipertensão")
    assert "diabetes mellitus" in traducao
    assert "hypertension" in traducao


def test_glossario_sem_termo_conhecido():
    assert traduzir_pelo_glossario("qual o nome do cachorro do vizinho") == ""


@pytest.mark.asyncio
async def test_traducao_pela_wikipedia():
    def responder(pedido: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"query": {"pages": {"1": {
            "title": "Fotossíntese",
            "langlinks": [{"lang": "en", "*": "Photosynthesis"}],
        }}}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(responder)) as cliente:
        assert await traduzir_pela_wikipedia(cliente, "fotossíntese") == "Photosynthesis"


@pytest.mark.asyncio
async def test_traducao_cai_no_glossario_sem_rede():
    def falhar(pedido: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sem rede")

    async with httpx.AsyncClient(transport=httpx.MockTransport(falhar)) as cliente:
        traducao, origem = await versao_em_ingles(cliente, "mecanismo de atenção")
    assert traducao == "attention mechanism"
    assert origem == "glossario"


@pytest.mark.asyncio
async def test_pergunta_em_ingles_nao_e_traduzida():
    traducao, origem = await versao_em_ingles(None, "what is attention mechanism")
    assert origem == "original"
    assert traducao == "what is attention mechanism"


def _trecho(texto: str, doc: str) -> Trecho:
    return Trecho(texto=texto, doc_id=doc, titulo="t", url="", fonte="wikipedia")


def test_realimentacao_aprende_o_jargao_dos_melhores_trechos():
    bons = [
        _trecho("o cloroplasto contém tilacoides e realiza fotofosforilação "
                "durante a etapa luminosa da via metabólica", f"b{i}")
        for i in range(3)
    ]
    ruins = [
        _trecho("assunto completamente diferente sobre economia e mercado "
                "financeiro internacional", f"r{i}")
        for i in range(6)
    ]
    termos = termos_de_realimentacao(bons + ruins, "fotossíntese", quantidade=4,
                                     trechos_considerados=3)
    assert "cloroplasto" in termos or "tilacoides" in termos
    assert "economia" not in termos


def test_realimentacao_ignora_termos_da_propria_pergunta():
    trechos = [_trecho("entropia entropia entropia sistema termodinamico isolado", f"d{i}")
               for i in range(5)]
    assert "entropia" not in termos_de_realimentacao(trechos, "entropia")


def test_realimentacao_com_poucos_trechos():
    assert termos_de_realimentacao([_trecho("texto", "d1")], "x") == []


def test_consulta_expandida():
    assert consulta_expandida("entropia", ["isolado"]) == "entropia isolado"
    assert consulta_expandida("entropia", []) == "entropia"
