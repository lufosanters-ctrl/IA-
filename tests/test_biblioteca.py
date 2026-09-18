"""Testes do indice da biblioteca local."""

import pytest

from app import biblioteca

LIVRO = """# Álgebra Linear

## Capítulo 2 — Espaços vetoriais

Um espaço vetorial é um conjunto munido de duas operações, soma de vetores e
multiplicação por escalar, que satisfazem oito axiomas de fechamento,
associatividade, comutatividade e existência de elemento neutro e inverso.

Uma base de um espaço vetorial é um conjunto de vetores linearmente
independentes que gera todo o espaço. A dimensão do espaço é o número de
vetores de qualquer uma de suas bases, e esse número não depende da base
escolhida, o que é um dos resultados centrais da teoria.

A transformação linear preserva as operações do espaço: a imagem da soma é a
soma das imagens, e a imagem do múltiplo escalar é o múltiplo da imagem.
"""


@pytest.fixture
def livro(tmp_path):
    arquivo = tmp_path / "algebra.md"
    arquivo.write_text(LIVRO, encoding="utf-8")
    return arquivo


def test_indexar_livro(livro):
    resultado = biblioteca.indexar(livro, area="matematica")
    assert resultado.estado == "indexado"
    assert resultado.trechos >= 1
    assert resultado.titulo == "Álgebra Linear"


def test_indexar_duas_vezes_nao_duplica(livro):
    biblioteca.indexar(livro)
    segunda = biblioteca.indexar(livro)
    assert segunda.estado == "duplicado"
    titulos = [item["titulo"] for item in biblioteca.listar_livros()]
    assert titulos.count("Álgebra Linear") == 1


def test_arquivo_invalido_vira_erro(tmp_path):
    ruim = tmp_path / "imagem.png"
    ruim.write_bytes(b"\x89PNG isto nao e livro")
    resultado = biblioteca.indexar(ruim)
    assert resultado.estado == "erro"
    assert resultado.detalhe


def test_busca_encontra_o_conceito(livro):
    biblioteca.indexar(livro)
    achados = biblioteca.buscar("base de um espaço vetorial", limite=3)
    assert achados
    assert any("base" in a["texto"].lower() for a in achados)
    assert achados[0]["titulo"] == "Álgebra Linear"


def test_busca_ignora_acentos(livro):
    biblioteca.indexar(livro)
    assert biblioteca.buscar("dimensao do espaco", limite=3)


def test_busca_sem_resultado(livro):
    biblioteca.indexar(livro)
    assert biblioteca.buscar("receita de estrogonofe de camarão", limite=3) == []


@pytest.mark.parametrize("perigosa", [
    'espaço" OR "x', "vetor AND NEAR", "*", '"', "NOT base", "a b -- comentário",
    "()", "vetorial*", "^base",
])
def test_busca_nao_quebra_com_sintaxe_do_fts(livro, perigosa):
    """A pergunta do usuario nunca pode virar operador do FTS5."""
    biblioteca.indexar(livro)
    assert isinstance(biblioteca.buscar(perigosa, limite=3), list)


def test_remover_livro_apaga_os_trechos(livro):
    """A remocao precisa levar junto os trechos e o indice de busca."""
    antes = biblioteca.estatisticas()["trechos"]
    resultado = biblioteca.indexar(livro)
    assert biblioteca.estatisticas()["trechos"] > antes

    assert biblioteca.remover_livro(resultado.livro_id) is True
    assert biblioteca.estatisticas()["trechos"] == antes
    assert biblioteca.buscar("espaço vetorial") == []


def test_remover_livro_inexistente():
    assert biblioteca.remover_livro(99999) is False


def test_indexar_pasta(tmp_path):
    pasta = tmp_path / "acervo"
    pasta.mkdir()
    (pasta / "um.md").write_text(LIVRO, encoding="utf-8")
    (pasta / "dois.md").write_text(LIVRO.replace("Álgebra", "Geometria"), encoding="utf-8")
    resultados = biblioteca.indexar_pasta(pasta)
    assert len([r for r in resultados if r.estado == "indexado"]) == 2


def test_contexto_do_trecho_inclui_vizinhos(livro):
    biblioteca.indexar(livro)
    achado = biblioteca.buscar("transformação linear", limite=1)[0]
    contexto = biblioteca.contexto_do_trecho(achado["id"], janela=1)
    assert len(contexto) >= len(achado["texto"])


def test_estatisticas_somam_o_acervo(livro):
    antes = biblioteca.estatisticas()
    biblioteca.indexar(livro)
    depois = biblioteca.estatisticas()
    assert depois["livros"] == antes["livros"] + 1
    assert depois["palavras"] > antes["palavras"]


def test_montar_expressao_escapa_termos():
    expressao = biblioteca.montar_expressao('espaço" vetorial')
    assert expressao.count('"') % 2 == 0
    assert biblioteca.montar_expressao("!!!") == ""
