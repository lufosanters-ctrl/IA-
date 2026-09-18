"""A escada de ajuda tem que ser uma escada.

Sete degraus que devolvem o mesmo texto não são sete degraus — são um degrau
repetido sete vezes, e a política de mínima ajuda vira enfeite. Estes testes
exigem que cada degrau acrescente algo e que nenhum dos degraus 0 a 5 entregue
a resposta.
"""

from __future__ import annotations

import asyncio

import pytest

from app.tutor.escada import NIVEL_MAXIMO, degrau
from app.tutor.tutoria import _ajuda_deterministica, apurar

ENUNCIADOS = [
    "Vou a praia.",
    "Não me disseram nada. Está certo?",
    "Haviam muitos alunos na sala. Corrija.",
    "Prefiro café do que chá. Está certo?",
    "I have 20 years old. Is it correct?",
    "Resolva a equação x^2 - 5x + 6 = 0.",
]


def _ajudas(enunciado: str) -> list[str]:
    contexto = asyncio.run(apurar(enunciado))
    return [
        _ajuda_deterministica(degrau(n), contexto, enunciado)
        for n in range(NIVEL_MAXIMO + 1)
    ]


@pytest.mark.parametrize("enunciado", ENUNCIADOS)
def test_cada_degrau_diz_algo_novo(enunciado):
    ajudas = _ajudas(enunciado)
    repetidos = [
        (i, j) for i in range(len(ajudas)) for j in range(i + 1, len(ajudas))
        if ajudas[i].strip() == ajudas[j].strip()
    ]
    assert not repetidos, f"degraus idênticos em “{enunciado}”: {repetidos}"


@pytest.mark.parametrize("enunciado", ENUNCIADOS)
def test_nenhum_degrau_vem_vazio(enunciado):
    for nivel, texto in enumerate(_ajudas(enunciado)):
        assert texto.strip(), f"degrau {nivel} vazio em “{enunciado}”"
        assert len(texto) > 40, f"degrau {nivel} curto demais em “{enunciado}”"


def test_mecanismo_corresponde_ao_topico_perguntado():
    """Quem pergunta sobre colocação não pode receber a regra de regência."""
    colocacao = _ajudas("Não me disseram nada. Está certo?")[2]
    assert "pronome átono" in colocacao

    concordancia = _ajudas("Haviam muitos alunos na sala. Corrija.")[2]
    assert "impessoal" in concordancia

    crase = _ajudas("Vou a praia.")[2]
    assert "DUAS condições" in crase


def test_solucao_simbolica_so_no_ultimo_degrau():
    ajudas = _ajudas("Resolva a equação x^2 - 5x + 6 = 0.")
    for nivel, texto in enumerate(ajudas[:-1]):
        assert "\\in \\left\\{" not in texto, f"degrau {nivel} entregou a solução"
        assert "Resolução simbólica" not in texto
    assert "Resolução simbólica" in ajudas[-1]


def test_correcao_do_ingles_so_no_ultimo_degrau():
    ajudas = _ajudas("I have 20 years old. Is it correct?")
    for nivel, texto in enumerate(ajudas[:-1]):
        assert "years old" not in texto or "I have 20 years old" in texto, nivel
        assert "I am 20" not in texto, f"degrau {nivel} entregou a forma correta"
    assert "be" in ajudas[-1].lower()
