"""Os geradores paramétricos: gabarito certo, variedade suficiente.

Um gerador de questão erra em silêncio. A questão sai bonita, o estudante
responde, o sistema diz que ele errou — e o errado era o gabarito. Estes
testes varrem todo o espaço de sementes e conferem cada gabarito por um
caminho independente.
"""

from __future__ import annotations

import collections
import math
import random
import re

import pytest
import sympy as sp

from app.matematica.criacao import (
    GERADORES,
    _anagramas,
    conferir_questao,
    criar_parametrica,
)

# 150 sementes cobrem o espaço de parâmetros de todos os moldes sem tornar
# a suíte lenta. A varredura completa (800) roda à mão quando um gerador muda.
SEMENTES = 150


@pytest.mark.parametrize("topico", sorted(GERADORES))
def test_toda_questao_passa_na_propria_conferencia(topico):
    invalidas = []
    for semente in range(SEMENTES):
        valida, motivo = conferir_questao(criar_parametrica(topico, semente=semente))
        if not valida:
            invalidas.append((semente, motivo))
    assert not invalidas, f"{len(invalidas)} inválidas, ex.: {invalidas[0]}"


@pytest.mark.parametrize("topico", sorted(GERADORES))
def test_alternativas_nunca_se_repetem(topico):
    for semente in range(SEMENTES):
        questao = criar_parametrica(topico, semente=semente)
        alternativas = [a.strip().lower() for a in questao.alternativas]
        assert len(set(alternativas)) == len(alternativas), (
            f"{topico} semente {semente}: {questao.alternativas}"
        )


@pytest.mark.parametrize("topico, minimo", [
    ("polinomios", 20),
    ("complexos", 8),
    ("sequencias", 8),
    ("combinatoria", 12),
    ("trigonometria", 8),
    ("logaritmos", 8),
])
def test_repertorio_nao_se_esgota_numa_sessao(topico, minimo):
    """Três enunciados no total acabam no primeiro treino de quatro itens."""
    distintos = {criar_parametrica(topico, semente=s).enunciado
                 for s in range(SEMENTES)}
    assert len(distintos) >= minimo, f"{topico}: só {len(distintos)} enunciados"


def test_selo_de_conferencia_e_ganho_nao_declarado():
    """O selo dizia "calculado simbolicamente" sem rodar conferência alguma."""
    questao = criar_parametrica("polinomios", semente=7)
    assert questao.observacao_da_conferencia
    assert questao.observacao_da_conferencia != "gabarito calculado simbolicamente"
    valida, motivo = conferir_questao(questao)
    assert questao.conferida is valida
    assert questao.observacao_da_conferencia == motivo


def test_anagramas_conferidos_contra_a_formula():
    """n! dividido pelos fatoriais das repetições, contado por fora."""
    for semente in range(SEMENTES):
        bruta = _anagramas(random.Random(semente))
        palavra = re.search(r"\*\*([A-Z]+)\*\*", bruta["enunciado"]).group(1)
        esperado = math.factorial(len(palavra))
        for n in collections.Counter(palavra).values():
            esperado //= math.factorial(n)
        obtido = bruta["alternativas"][bruta["correta"]].strip("$").replace(" ", "")
        assert obtido == str(esperado), f"{palavra}: {obtido} ≠ {esperado}"


def test_trigonometria_usa_o_arco_principal_de_cada_funcao():
    """sen(π/6)=1/2, mas cos(π/3)=1/2: usar o arco do seno no cosseno erra."""
    x = sp.Symbol("x", real=True)
    for semente in range(SEMENTES):
        questao = criar_parametrica("trigonometria", semente=semente)
        achado = re.search(r"\$(.+?) = (-?\\frac\{.+?\}\{.+?\})\$", questao.enunciado)
        if not achado:
            continue
        funcao = sp.sin if "sen" in achado.group(1) else sp.cos
        valor = sp.sympify(
            achado.group(2)
            .replace(r"\frac{1}{2}", "1/2")
            .replace(r"\frac{\sqrt{2}}{2}", "sqrt(2)/2")
            .replace(r"\frac{\sqrt{3}}{2}", "sqrt(3)/2")
        )
        esperadas = sorted(
            sp.solveset(sp.Eq(funcao(x), valor), x, sp.Interval(0, 2 * sp.pi)),
            key=float,
        )
        gabarito = questao.alternativas[questao.correta]
        for raiz in esperadas:
            assert sp.latex(raiz) in gabarito, (
                f"semente {semente}: {sp.latex(raiz)} fora de {gabarito}"
            )
