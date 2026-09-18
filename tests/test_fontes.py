"""Testes dos conectores, com respostas simuladas das APIs publicas."""

import httpx
import pytest

from app.sources.openalex import reconstruir_resumo
from app.sources.registro import FONTES, detectar_area, escolher_fontes

from .conftest import manipulador

pytestmark = pytest.mark.asyncio


@pytest.mark.parametrize("identificador", sorted(FONTES))
async def test_cada_fonte_devolve_documentos_normalizados(identificador, cliente_falso):
    async with cliente_falso as cliente:
        resultado = await FONTES[identificador].executar(cliente, "atencao neural", 5, "pt")

    assert resultado.erro == "", f"{identificador} falhou: {resultado.erro}"
    assert resultado.documentos, f"{identificador} nao devolveu documentos"
    for documento in resultado.documentos:
        assert documento.titulo
        assert documento.fonte == identificador
        assert documento.conteudo or documento.resumo
        assert "<" not in documento.conteudo  # HTML precisa vir limpo


async def test_falha_de_rede_nao_derruba_a_busca():
    def quebrar(pedido: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sem rede")

    async with httpx.AsyncClient(transport=httpx.MockTransport(quebrar)) as cliente:
        resultado = await FONTES["wikipedia"].executar(cliente, "teste", 3, "pt")

    assert resultado.documentos == []
    assert "falha de rede" in resultado.erro


async def test_resposta_malformada_vira_erro_tratado():
    def lixo(pedido: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="isto nao e json nem xml")

    async with httpx.AsyncClient(transport=httpx.MockTransport(lixo)) as cliente:
        resultado = await FONTES["openalex"].executar(cliente, "teste", 3, "pt")

    assert resultado.documentos == []
    assert resultado.erro


async def test_status_http_de_erro_e_reportado():
    def negar(pedido: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"erro": "muitas requisicoes"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(negar)) as cliente:
        resultado = await FONTES["arxiv"].executar(cliente, "teste", 3, "pt")

    assert resultado.erro == "HTTP 429"


async def test_wikipedia_respeita_o_idioma(cliente_falso):
    fonte = FONTES["wikipedia"]
    assert fonte._endpoint("pt").startswith("https://pt.")
    assert fonte._endpoint("en").startswith("https://en.")


async def test_limite_de_resultados_e_respeitado(cliente_falso):
    async with cliente_falso as cliente:
        resultado = await FONTES["openalex"].executar(cliente, "teste", 1, "pt")
    assert len(resultado.documentos) <= 1
