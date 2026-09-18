"""Testes do pipeline de pesquisa de ponta a ponta (sem rede real)."""

import pytest

from app.ai import pesquisa
from app.ai.estudo import flashcards_extrativos, gerar_flashcards, gerar_quiz, gerar_plano

pytestmark = pytest.mark.asyncio


async def test_pesquisa_devolve_resposta_com_citacoes():
    resultado = await pesquisa.pesquisar("mecanismo de atencao", fontes=["wikipedia", "arxiv"])

    assert resultado.resposta
    assert resultado.citacoes
    assert resultado.modo == "extrativo"          # sem chave de API nos testes
    assert all(c.numero > 0 and c.titulo for c in resultado.citacoes)
    assert {c.numero for c in resultado.citacoes} == set(range(1, len(resultado.citacoes) + 1))


async def test_resposta_extrativa_cita_apenas_fontes_existentes():
    resultado = await pesquisa.pesquisar("mecanismo de atencao", fontes=["wikipedia"])
    maximo = len(resultado.citacoes)
    import re
    numeros = {int(n) for n in re.findall(r"\[(\d+)\]", resultado.resposta)}
    assert numeros, "a resposta extrativa precisa citar as fontes"
    assert all(1 <= n <= maximo for n in numeros)


async def test_diagnostico_lista_todas_as_fontes_pedidas():
    resultado = await pesquisa.pesquisar("atencao", fontes=["wikipedia", "openalex", "arxiv"])
    consultadas = {d["fonte"] for d in resultado.fontes_consultadas}
    assert consultadas == {"wikipedia", "openalex", "arxiv"}


async def test_cache_evita_segunda_chamada_a_rede():
    pesquisa.limpar_cache()
    await pesquisa.pesquisar("atencao neural", fontes=["wikipedia"])
    segundo = await pesquisa.pesquisar("atencao neural", fontes=["wikipedia"])
    assert any(d["cache"] for d in segundo.fontes_consultadas)


async def test_pesquisa_sem_resultado_nao_quebra():
    resultado = await pesquisa.pesquisar("atencao", fontes=["fonte-que-nao-existe"])
    assert resultado.resposta
    assert isinstance(resultado.citacoes, list)


async def test_fluxo_emite_os_eventos_na_ordem_esperada():
    tipos = []
    async for evento in pesquisa.pesquisar_em_fluxo("atencao", ["wikipedia"]):
        tipos.append(evento["tipo"])

    assert tipos[0] == "etapa"
    assert "fontes" in tipos
    assert "citacoes" in tipos
    assert "texto" in tipos
    assert tipos[-1] == "fim"


async def test_recuperar_resultado_reaproveita_o_material():
    primeiro = await pesquisa.pesquisar("atencao neural", fontes=["wikipedia"])
    pesquisa.registrar_resultado(primeiro, ["wikipedia"])
    reaproveitado = await pesquisa.recuperar_resultado("atencao neural", ["wikipedia"])
    assert reaproveitado is primeiro


async def test_flashcards_extrativos_saem_do_material():
    resultado = await pesquisa.pesquisar("mecanismo de atencao", fontes=["wikipedia"])
    dados = await gerar_flashcards(resultado, quantidade=4)
    assert dados["modo"] == "extrativo"
    assert 1 <= len(dados["cartoes"]) <= 4
    for cartao in dados["cartoes"]:
        assert cartao["frente"] and cartao["verso"]
        assert 0 <= cartao["citacao"] <= len(resultado.citacoes)


async def test_quiz_extrativo_tem_alternativa_correta_valida():
    resultado = await pesquisa.pesquisar("mecanismo de atencao", fontes=["wikipedia", "arxiv"])
    dados = await gerar_quiz(resultado, quantidade=3)
    for questao in dados["questoes"]:
        assert len(questao["alternativas"]) == 4
        assert 0 <= questao["correta"] < 4
        assert len(set(questao["alternativas"])) == 4, "alternativas nao podem repetir"


async def test_plano_extrativo_sequencia_as_sessoes():
    resultado = await pesquisa.pesquisar("atencao neural", fontes=["wikipedia"])
    plano = await gerar_plano("atencao neural", semanas=2, horas_semana=4, resultado=resultado)
    assert plano["sessoes"]
    numeros = [s["numero"] for s in plano["sessoes"]]
    assert numeros == sorted(numeros)
    assert all(s["objetivo"] and s["atividade"] for s in plano["sessoes"])
