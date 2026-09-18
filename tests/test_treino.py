"""Treino dirigido: praticar exatamente o ponto em que se erra.

Um treino só serve se cada exercício for respondível e se o conjunto não
repetir a mesma conta. Estes testes guardam as duas coisas.
"""

from __future__ import annotations

import pytest

from app.tutor import treino


@pytest.mark.parametrize("materia", ["portugues", "ingles", "matematica"])
@pytest.mark.parametrize("quantidade", [3, 5])
def test_treino_entrega_a_quantidade_pedida(materia, quantidade):
    montado = treino.montar_treino(materia, "", quantidade, semente=7)
    assert len(montado.itens) == quantidade


@pytest.mark.parametrize("materia", ["portugues", "ingles", "matematica"])
def test_nenhum_exercicio_e_impossivel_de_acertar(materia):
    """Item com alternativas fechadas precisa ter o gabarito entre elas."""
    montado = treino.montar_treino(materia, "", 5, semente=3)
    for item in montado.itens:
        if item.alternativas:
            assert 0 <= item.correta < len(item.alternativas), item.enunciado
            assert item.alternativas[item.correta] == item.resposta


@pytest.mark.parametrize("materia", ["portugues", "ingles", "matematica"])
def test_treino_nao_repete_exercicio(materia):
    montado = treino.montar_treino(materia, "", 5, semente=11)
    enunciados = [i.enunciado for i in montado.itens]
    assert len(set(enunciados)) == len(enunciados)


def test_gabarito_so_sai_quando_pedido():
    """Entregar a resposta junto com a pergunta é entregar o peixe."""
    montado = treino.montar_treino("portugues", "", 3, semente=5)
    sem = montado.para_dict(com_gabarito=False)
    com = montado.para_dict(com_gabarito=True)
    assert all("resposta" not in i for i in sem["itens"])
    assert all("resposta" in i for i in com["itens"])


def test_treino_de_area_so_monta_casos_respondiveis():
    itens = treino.treino_de_area("colocacao", 8, semente=2)
    for item in itens:
        assert item.resposta in item.alternativas
