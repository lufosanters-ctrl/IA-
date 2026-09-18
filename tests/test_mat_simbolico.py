"""Testes da camada simbólica: leitura segura, resolução e verificação."""

import pytest
import sympy as sp

from app.matematica import simbolico as s


# --------------------------------------------------------------------------
# Segurança da leitura
# --------------------------------------------------------------------------

@pytest.mark.parametrize("perigosa", [
    '__import__("os").system("ls")',
    "x.__class__.__bases__",
    "lambda: 1",
    'open("/etc/passwd").read()',
    'exec("a=1")',
    "eval('2+2')",
    "globals()",
    "x; import os",
])
def test_entrada_perigosa_e_recusada(perigosa):
    """A expressão do usuário nunca pode virar execução de código."""
    with pytest.raises(s.ErroSimbolico):
        s.ler(perigosa)


def test_builtins_nao_existem_na_avaliacao():
    """Mesmo um nome que passe pelo filtro não encontra builtins."""
    assert "__builtins__" in s._ESPACO_GLOBAL
    assert s._ESPACO_GLOBAL["__builtins__"] == {}


@pytest.mark.parametrize("pesada,motivo", [
    ("factorial(999999)", "fatorial"),
    ("99999999999999*x", "grande"),
    ("2^2^2^2", "potências"),
])
def test_entrada_que_travaria_o_processo(pesada, motivo):
    with pytest.raises(s.ErroSimbolico, match=motivo):
        s.ler(pesada)


def test_expressao_longa_demais():
    with pytest.raises(s.ErroSimbolico, match="longa"):
        s.ler("x + " * 300 + "1")


# --------------------------------------------------------------------------
# Leitura de notação de caderno
# --------------------------------------------------------------------------

@pytest.mark.parametrize("entrada,esperado", [
    ("2x^2 - 3x + 1", "2*x**2 - 3*x + 1"),
    ("2x", "2*x"),
    ("x²", "x**2"),
    ("sen(x)", "sin(x)"),
    ("raiz(x)", "sqrt(x)"),
    ("√9", "3"),
])
def test_notacao_escrita_a_mao(entrada, esperado):
    assert s._texto(s.ler(entrada)) == esperado


def test_equacao_precisa_de_um_igual():
    with pytest.raises(s.ErroSimbolico):
        s.ler_equacao("x + 1")
    with pytest.raises(s.ErroSimbolico):
        s.ler_equacao("x = 1 = 2")


# --------------------------------------------------------------------------
# Extração de equações da prosa
# --------------------------------------------------------------------------

def test_extrai_equacao_sem_engolir_palavras():
    """Regressão: o 'o' de 'equação' virava variável e corrompia a leitura."""
    equacoes = s.extrair_equacoes("Resolva a equação x^2 - 5x + 6 = 0 no conjunto dos reais.")
    assert len(equacoes) == 1
    assert s._texto(equacoes[0]) == "Eq(x**2 - 5*x + 6, 0)"
    assert {v.name for v in equacoes[0].free_symbols} == {"x"}


def test_extrai_duas_equacoes_ligadas_por_e():
    equacoes = s.extrair_equacoes("Sabendo que x + y = 10 e x - y = 4, determine x.")
    assert len(equacoes) == 2


def test_extrai_equacao_entre_cifroes():
    equacoes = s.extrair_equacoes("Seja $f(x) = 2x + 1$ uma função afim.")
    assert equacoes and "f(x)" in s._texto(equacoes[0])


def test_prosa_sem_matematica_nao_gera_equacao():
    assert s.extrair_equacoes("Numa cidade, 40% das pessoas gostam de futebol.") == []


def test_igualdade_sem_incognita_e_descartada():
    assert s.extrair_equacoes("Sabemos que 2 + 2 = 4 desde sempre.") == []


def test_funcao_aplicada_nao_vira_multiplicacao():
    assert s._texto(s.ler_equacao("f(x) = 2x + 1")) == "Eq(f(x), 2*x + 1)"


def test_variavel_entre_parenteses_continua_produto():
    assert s._texto(s.ler_equacao("x(x+1) = 6")) == "Eq(x*(x + 1), 6)"


# --------------------------------------------------------------------------
# Resolução
# --------------------------------------------------------------------------

def test_resolve_quadratica_e_verifica():
    analise = s.analisar("Resolva a equação x^2 - 5x + 6 = 0.")
    assert analise.resolveu
    assert sorted(analise.solucoes["x"]) == ["2", "3"]
    assert all(c.passou for c in analise.checagens)


def test_resolve_sistema_linear():
    analise = s.analisar("Sabendo que x + y = 10 e x - y = 4, determine x e y.")
    assert analise.solucoes["x"] == ["7"]
    assert analise.solucoes["y"] == ["3"]
    assert any(c.nome == "substituição no sistema" and c.passou for c in analise.checagens)


def test_equacao_com_radical_descarta_raiz_estranha():
    analise = s.analisar("Resolva a equação sqrt(x + 3) = x - 3.")
    assert analise.solucoes["x"] == ["6"]          # x = 1 é raiz estranha
    assert all(c.passou for c in analise.checagens)


def test_sem_equacao_no_enunciado():
    analise = s.analisar("Quantos anagramas tem a palavra ARARA?")
    assert not analise.resolveu
    assert analise.observacoes


# --------------------------------------------------------------------------
# Protocolo anti-erro
# --------------------------------------------------------------------------

def test_substituicao_reprova_valor_errado():
    equacao = s.ler_equacao("x^2 - 5x + 6 = 0")
    checagem = s.verificar_por_substituicao(equacao, sp.Symbol("x"), [sp.Integer(5)])
    assert not checagem.passou
    assert "resíduo" in checagem.detalhe


def test_dominio_reprova_raiz_que_anula_denominador():
    equacao = s.ler_equacao("1/(x - 2) = 3")
    checagem = s.verificar_dominio(equacao, sp.Symbol("x"), [sp.Integer(2)])
    assert checagem is not None and not checagem.passou


def test_dominio_reprova_logaritmando_negativo():
    equacao = s.ler_equacao("log(x) = 1")
    checagem = s.verificar_dominio(equacao, sp.Symbol("x"), [sp.Integer(-3)])
    assert checagem is not None and not checagem.passou


def test_identidade_verdadeira():
    checagem = s.verificar_identidade("sen(x)^2 + cos(x)^2", "1")
    assert checagem.passou


def test_identidade_falsa():
    checagem = s.verificar_identidade("sen(2*x)", "2*sen(x)")
    assert not checagem.passou


def test_probabilidade_fora_do_intervalo():
    checagem = s.verificar_intervalo_probabilidade([sp.Rational(3, 2)])
    assert checagem is not None and not checagem.passou


def test_probabilidade_dentro_do_intervalo():
    checagem = s.verificar_intervalo_probabilidade([sp.Rational(1, 4)])
    assert checagem is not None and checagem.passou


# --------------------------------------------------------------------------
# Confronto com a resposta apresentada
# --------------------------------------------------------------------------

def test_confronto_aprova_resposta_completa():
    checagens = s.conferir_resposta("Resolva x^2 - 5x + 6 = 0.", "As raízes são x = 2 e x = 3.")
    assert checagens and all(c.passou for c in checagens)


def test_confronto_acusa_raiz_faltando():
    checagens = s.conferir_resposta("Resolva x^2 - 5x + 6 = 0.", "A única raiz é x = 2.")
    assert checagens and not checagens[0].passou
    assert "3" in checagens[0].detalhe


def test_confronto_nao_se_aplica_quando_a_pergunta_nao_pede_as_raizes():
    """Regressão: em 'calcule r1²+r2²' o confronto acusava erro inexistente."""
    checagens = s.conferir_resposta(
        "Sejam r1 e r2 as raízes de x^2 - 2x - 8 = 0. Calcule r1^2 + r2^2.", "20"
    )
    assert checagens == []


@pytest.mark.parametrize("enunciado,espera", [
    ("Resolva a equação x^2 = 4", True),
    ("Determine o conjunto solução de log x = 1", True),
    ("Calcule a soma das raízes de x^2 - 3x + 2 = 0", False),
])
def test_deteccao_de_pergunta_que_pede_raizes(enunciado, espera):
    assert s.pede_resolver_equacao(enunciado) is espera
