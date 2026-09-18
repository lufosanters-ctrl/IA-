"""Conferência de regência: a preposição usada bate com a que o verbo pede?

Até agora o módulo de regência era só consulta — dizia o que o verbo exige e
parava aí. Nenhum erro clássico era detectado. Estes testes fixam o contrato
do conferidor: acusa o desvio real e cala diante da construção correta.
"""

from __future__ import annotations

import pytest

from app.gramatica import analisar_frase
from app.gramatica.regencia import conferir_regencia


@pytest.mark.parametrize("frase, verbo, problema", [
    ("Prefiro café do que chá.", "preferir", "reforco indevido"),
    ("Prefiro muito mais cinema a teatro.", "preferir", "reforco indevido"),
    ("Obedeço as regras da escola.", "obedecer", "preposicao ausente"),
    ("Aludiu o caso durante a aula.", "aludir", "preposicao ausente"),
    ("Respondi a carta ontem.", "responder", "preposicao ausente"),
    ("Cheguei em casa tarde demais.", "chegar", "preposicao trocada"),
    ("Isso depende em você.", "depender", "preposicao trocada"),
    ("Simpatizo dele desde sempre.", "simpatizar", "preposicao trocada"),
    ("Namorei com a Ana por dois anos.", "namorar", "preposicao a mais"),
])
def test_desvio_classico_e_apontado(frase, verbo, problema):
    desvios = conferir_regencia(frase)
    assert desvios, f"nenhum desvio apontado em “{frase}”"
    achado = next((d for d in desvios if d.verbo == verbo), None)
    assert achado is not None, f"o desvio apontado não foi o de “{verbo}”"
    assert achado.problema == problema


@pytest.mark.parametrize("frase", [
    "Prefiro café a chá.",
    "Obedeço às regras da escola.",
    "Cheguei a casa tarde demais.",          # "casa" sem determinante
    "Fomos a Roma no ano passado.",
    "Gosto de estudar à noite.",
    "Moro em São Paulo há dez anos.",
    "Simpatizo com a proposta dele.",
    "O problema consiste em duas partes.",
    "Namorei a Ana por dois anos.",
    "Respondi à carta ontem.",
])
def test_construcao_correta_nao_e_acusada(frase):
    assert conferir_regencia(frase) == [], f"acusou indevidamente “{frase}”"


def test_verbo_polissemico_nunca_e_acusado():
    """Quem decide o sentido é o estudante, não o motor.

    "Assistir" e "visar" mudam de regência com o sentido: acusar um deles
    seria escolher o sentido no lugar de quem escreveu.
    """
    assert conferir_regencia("Assisti o filme ontem.") == []
    assert conferir_regencia("O atirador visou o alvo.") == []


def test_desvio_chega_na_analise_completa():
    """O conferidor tem que alcançar o estudante, não ficar no módulo."""
    analise = analisar_frase("Prefiro café do que chá.")
    assert analise.tem_erro
    assert analise.desvios_de_regencia
    regencias = [a for a in analise.achados if a.topico == "regencia"]
    assert any(a.veredito == "erro" for a in regencias)


def test_rotulo_do_problema_sai_acentuado():
    """O identificador interno é sem acento; o que o estudante lê, não."""
    desvio = conferir_regencia("Obedeço as regras.")[0]
    assert desvio.rotulo == "falta a preposição"
