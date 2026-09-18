"""O sistema só pode afirmar o que realmente verificou.

A pior falha de uma plataforma de estudo não é dizer "não sei" — é dizer
"conferido" sobre uma resposta errada. A checagem por substituição confere a
raiz na equação que o motor LEU, nunca na pergunta que o enunciado FEZ, e
essa diferença produzia resposta errada com selo verde.
"""

from __future__ import annotations

import asyncio

import pytest

from app.matematica.resolucao import Problema, resolver
from app.matematica.simbolico import (
    analisar,
    base_do_logaritmo,
    condicoes_nao_aplicadas,
)


@pytest.mark.parametrize("enunciado, esperado", [
    ("Resolva log(x) + log(x-3) = 1 na base 10.", 10),
    ("Resolva log(x) = 3 na base 2.", 2),
    ("Resolva log_5(x) = 2.", 5),
    ("Resolva x^2 - 5x + 6 = 0.", None),
])
def test_base_declarada_e_respeitada(enunciado, esperado):
    assert base_do_logaritmo(enunciado) == esperado


@pytest.mark.parametrize("enunciado, resposta", [
    ("Resolva log(x) + log(x-3) = 1 na base 10.", "5"),
    ("Resolva log(x) = 3 na base 2.", "8"),
    ("Resolva log(x) = 2.", "100"),
])
def test_log_sem_base_e_decimal_nao_natural(enunciado, resposta):
    """“log x” no ensino brasileiro é base 10; o SymPy usa `log` para ln."""
    analise = analisar(enunciado)
    assert analise.solucoes.get("x") == [resposta]


@pytest.mark.parametrize("enunciado", [
    "Resolva x^2 = 9 sabendo que x < 0.",
    "Resolva sen(x) = 1/2 com x em graus, 0 <= x <= 360.",
    "Resolva cos(x) = 1/2 no intervalo [0, 4pi].",
    "Determine n natural tal que n^2 = 16.",
])
def test_condicao_em_prosa_vira_ressalva(enunciado):
    """Condição que a álgebra não aplica não pode passar em silêncio."""
    assert condicoes_nao_aplicadas(enunciado)
    assert not analisar(enunciado).confiavel


def test_pergunta_diferente_das_raizes_nao_e_apresentada_como_resposta():
    enunciado = "Sejam a e b as raizes de x^2-7x+10=0. Calcule a^2+b^2."
    analise = analisar(enunciado)
    assert analise.solucoes                      # a álgebra leu a equação
    assert not analise.responde_a_pergunta       # mas não é o que se pediu
    assert not analise.confiavel


@pytest.mark.parametrize("enunciado, verificado", [
    ("Resolva a equacao x^2 - 5x + 6 = 0.", True),
    ("Resolva log(x) + log(x-3) = 1 na base 10.", True),
    ("Resolva x^2 = 9 sabendo que x < 0.", False),
    ("Sejam a e b as raizes de x^2-7x+10=0. Calcule a^2+b^2.", False),
])
def test_selo_de_verificado_so_quando_merecido(enunciado, verificado):
    resultado = asyncio.run(resolver(Problema(enunciado=enunciado)))
    assert resultado.verificado is verificado
    if not verificado:
        assert resultado.ressalvas, "sem selo é preciso dizer o que faltou"
        assert "não é a resposta do problema" in resultado.texto


def test_leitura_parcial_nao_usa_o_titulo_resposta():
    resultado = asyncio.run(
        resolver(Problema(enunciado="Resolva x^2 = 9 sabendo que x < 0."))
    )
    assert "## O que a álgebra leu" in resultado.texto
    assert "## Resposta" not in resultado.texto
