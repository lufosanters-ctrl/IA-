"""Testes da avaliação em cinco dimensões e dos contrastes."""

import pytest

from app.ingles import CONTRASTES, DIMENSOES, avaliar_estrutura, contrastes_relevantes
from app.ingles.dimensoes import TRANSFERENCIAS


def test_as_cinco_dimensoes_estao_definidas():
    chaves = {c for c, _, _ in DIMENSOES}
    assert chaves == {"grammaticality", "meaning", "naturalness", "register", "frequency"}


@pytest.mark.parametrize("frase,correcao", [
    ("People is waiting outside.", "people are"),
    ("Can you explain me this rule?", "explain something to someone"),
    ("It depends of the weather.", "depend on"),
    ("She is married with a doctor.", "married to"),
    ("I have 20 years old.", "be + número"),
    ("I didn't see nothing there.", "anything"),
    ("I live here since three years.", "for + duração"),
    ("He gave me some good advices.", "advice"),
])
def test_erros_de_transferencia_do_portugues(frase, correcao):
    avaliacoes = avaliar_estrutura(frase)
    assert avaliacoes, f"não detectou o erro em: {frase}"
    assert any(correcao in a.alternativa_melhor for a in avaliacoes)
    assert all(a.grammaticality == "agramatical" for a in avaliacoes)


@pytest.mark.parametrize("frase", [
    "I have been here since 2020.",
    "She told me the truth.",
    "It depends on you.",
    "I waited for two hours.",
])
def test_frases_corretas_nao_geram_alerta(frase):
    assert avaliar_estrutura(frase) == []


def test_toda_transferencia_traz_exemplo_certo_e_errado():
    for padrao in TRANSFERENCIAS:
        assert padrao.exemplo_errado and padrao.exemplo_certo
        assert padrao.exemplo_errado != padrao.exemplo_certo
        assert padrao.porque


def test_avaliacao_vazia_para_texto_vazio():
    assert avaliar_estrutura("") == []


# --------------------------------------------------------------------------
# Contrastes
# --------------------------------------------------------------------------

def test_todo_contraste_tem_criterio_de_decisao():
    for contraste in CONTRASTES:
        assert contraste.criterio
        assert contraste.pergunta_decisiva.endswith("?")
        assert contraste.exemplo_a and contraste.exemplo_b
        assert contraste.erro_tipico


def test_contraste_de_tempo_verbal_e_encontrado():
    achados = contrastes_relevantes("I have seen him yesterday")
    assert any(c.chave == "perfect_x_past" for c in achados)


def test_contraste_for_since():
    achados = contrastes_relevantes("I have lived here since 2019")
    assert any(c.chave in {"for_x_since", "perfect_x_past"} for c in achados)


def test_filtro_por_lingua():
    portugueses = contrastes_relevantes("objeto direto e objeto indireto",
                                        lingua="portugues")
    assert portugueses and all(c.lingua == "portugues" for c in portugueses)


def test_texto_sem_gatilho_nao_traz_contraste():
    assert contrastes_relevantes("xyz abc qwerty") == []


def test_contrastes_cobrem_as_duas_linguas():
    linguas = {c.lingua for c in CONTRASTES}
    assert linguas == {"ingles", "portugues"}
