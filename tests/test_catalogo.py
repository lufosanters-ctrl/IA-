"""Testes do catalogo de livros didaticos abertos."""

import httpx
import pytest

from app import biblioteca
from app.catalogo import (
    CATALOGO,
    CATALOGO_POR_CHAVE,
    ErroDownload,
    _nome_seguro,
    baixar_catalogo,
    baixar_gutenberg,
    baixar_wikilivro,
    listar_catalogo,
)

from .conftest import manipulador

pytestmark = pytest.mark.asyncio


@pytest.fixture
def cliente():
    return httpx.AsyncClient(transport=httpx.MockTransport(manipulador))


async def test_catalogo_tem_itens_bem_formados():
    assert len(CATALOGO) >= 10
    for item in CATALOGO:
        assert item.chave and item.titulo and item.area
        assert item.origem in {"wikilivros", "gutenberg"}
    chaves = [i.chave for i in CATALOGO]
    assert len(chaves) == len(set(chaves)), "chaves do catálogo precisam ser únicas"


async def test_filtro_por_area():
    matematica = listar_catalogo("matematica")
    assert matematica
    assert all(i["area"] == "matematica" for i in matematica)


async def test_baixar_wikilivro(cliente, tmp_path):
    async with cliente as sessao:
        arquivo, titulo, url = await baixar_wikilivro(sessao, "Cálculo", tmp_path)
    assert arquivo.exists()
    assert titulo == "Cálculo"
    assert "wikibooks.org" in url
    conteudo = arquivo.read_text(encoding="utf-8")
    assert "## Limites" in conteudo
    assert "épsilon" in conteudo


async def test_baixar_gutenberg_remove_cabecalho_de_licenca(cliente, tmp_path):
    async with cliente as sessao:
        arquivo, titulo, url = await baixar_gutenberg(sessao, "Calculus", tmp_path)
    conteudo = arquivo.read_text(encoding="utf-8")
    assert titulo == "Calculus Made Easy"
    assert "PROJECT GUTENBERG" not in conteudo
    assert "rodapé" not in conteudo
    assert "derivada" in conteudo
    assert "gutenberg.org/ebooks/33283" in url


async def test_baixar_catalogo_indexa_na_biblioteca(cliente):
    antes = biblioteca.estatisticas()["livros"]
    async with cliente as sessao:
        resultados = await baixar_catalogo(chaves=["calculo"], cliente=sessao)
    assert len(resultados) == 1
    assert resultados[0].estado == "indexado"
    assert biblioteca.estatisticas()["livros"] == antes + 1
    assert biblioteca.buscar("razão incremental")


async def test_livro_do_catalogo_guarda_licenca_e_origem(cliente):
    async with cliente as sessao:
        await baixar_catalogo(chaves=["calculo"], cliente=sessao)
    livro = next(l for l in biblioteca.listar_livros() if l["origem"].startswith("catalogo"))
    assert "CC BY-SA" in livro["licenca"]
    assert livro["url"].startswith("https://")


async def test_falha_de_rede_vira_resultado_com_erro():
    def cair(pedido: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sem rede")

    async with httpx.AsyncClient(transport=httpx.MockTransport(cair)) as sessao:
        resultados = await baixar_catalogo(chaves=["calculo"], cliente=sessao)
    assert resultados[0].estado == "erro"
    assert "rede" in resultados[0].detalhe


async def test_livro_sem_resultado_na_origem():
    def vazio(pedido: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"query": {"search": []}, "results": []})

    async with httpx.AsyncClient(transport=httpx.MockTransport(vazio)) as sessao:
        with pytest.raises(ErroDownload):
            await baixar_wikilivro(sessao, "livro inexistente")


async def test_chave_desconhecida_e_ignorada(cliente):
    async with cliente as sessao:
        assert await baixar_catalogo(chaves=["nao-existe"], cliente=sessao) == []


async def test_nome_de_arquivo_seguro():
    assert _nome_seguro("Cálculo: Volume 1/2", ".md") == "cálculo-volume-12.md"
    assert "/" not in _nome_seguro("a/b/c", ".txt")
    assert _nome_seguro("***", ".md") == "livro.md"
