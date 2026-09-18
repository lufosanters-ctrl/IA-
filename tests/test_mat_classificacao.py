"""Testes do diagnóstico: assunto, dificuldade e profundidade adaptativa."""

import pytest

from app.matematica.classificacao import NIVEIS, TOPICOS, classificar


@pytest.mark.parametrize("enunciado,topico", [
    ("Determine as raízes do polinômio p(x) = x^3 - 6x^2 + 11x - 6.", "polinomios"),
    ("Seja z um número complexo de módulo 2 e argumento pi/3. Calcule z^6.", "complexos"),
    ("Resolva a equação sen(2x) = cos(x) no intervalo dado.", "trigonometria"),
    ("Num triângulo, a bissetriz interna divide o lado oposto. Calcule a área do triângulo.",
     "geometria_plana"),
    ("Determine a equação da elipse de focos F1 e F2 e excentricidade 1/2.",
     "geometria_analitica"),
    ("Calcule o volume de um tronco de cone de raios 3 e 5.", "geometria_espacial"),
    ("Calcule o determinante da matriz A e discuta o sistema linear associado.", "matrizes"),
    ("De quantos modos podemos formar comissões de 3 pessoas?", "combinatoria"),
    ("Qual a probabilidade de sair soma 7 no lançamento de dois dados?", "probabilidade"),
    ("Calcule o limite de (sen x)/x quando x tende a zero.", "calculo"),
    ("Numa progressão aritmética de razão 3, calcule a soma dos termos.", "sequencias"),
    ("Resolva a equação exponencial 2^(x+1) = 8 usando logaritmo.", "logaritmos"),
    ("Mostre que n^3 - n é divisível por 6 para todo inteiro n.", "teoria_numeros"),
])
def test_deteccao_de_assunto(enunciado, topico):
    assert classificar(enunciado).topico == topico


def test_soma_de_cubos_nao_vai_para_geometria_espacial():
    """Regressão: 'cubos' de potência caía em geometria espacial."""
    diagnostico = classificar(
        "Demonstre que a soma dos n primeiros cubos é o quadrado da soma dos "
        "n primeiros naturais."
    )
    assert diagnostico.topico != "geometria_espacial"


@pytest.mark.parametrize("enunciado,nivel_minimo", [
    ("Calcule 2 + 2.", 1),
    ("Resolva x^2 - 4 = 0.", 1),
    ("De quantos modos 5 casais podem sentar-se de modo que cada casal fique junto?", 2),
    ("Demonstre que existe um inteiro n tal que a propriedade vale para todo m.", 4),
    ("Determine todos os valores reais de m para que a equação tenha duas raízes "
     "distintas e positivas.", 3),
])
def test_escala_de_dificuldade(enunciado, nivel_minimo):
    assert classificar(enunciado).dificuldade >= nivel_minimo


def test_problema_direto_nao_e_superestimado():
    assert classificar("Calcule a derivada de x^2.").dificuldade <= 2


def test_pedido_de_demonstracao_e_detectado():
    assert classificar("Prove que a soma de dois ímpares é par.").pede_demonstracao
    assert not classificar("Calcule a soma de 3 com 5.").pede_demonstracao


def test_profundidade_e_adaptativa():
    facil = classificar("Calcule 2 + 2.")
    dificil = classificar(
        "Demonstre que, para todo n, existe uma configuração em que a "
        "propriedade falha, e discuta o caso limite conforme o parâmetro k."
    )
    assert facil.orcamento_tokens < dificil.orcamento_tokens
    assert not facil.usar_critico
    assert dificil.usar_critico
    assert dificil.usar_estrategias_multiplas


def test_cada_topico_traz_estrategias_e_verificacoes():
    for topico in TOPICOS:
        assert topico.estrategias, f"{topico.chave} sem estratégias"
        assert topico.verificacoes, f"{topico.chave} sem protocolo de verificação"


def test_diagnostico_sempre_preenchido():
    diagnostico = classificar("uma frase qualquer sem matemática nenhuma")
    assert diagnostico.topico_nome
    assert diagnostico.estrategias
    assert diagnostico.verificacoes
    assert diagnostico.dificuldade in NIVEIS
