"""Testes sincronos do roteamento por area e da remontagem de resumos."""

from app.sources.openalex import reconstruir_resumo
from app.sources.registro import detectar_area, escolher_fontes


def test_reconstruir_resumo_do_openalex():
    indice = {"redes": [0], "neurais": [1], "profundas": [2]}
    assert reconstruir_resumo(indice) == "redes neurais profundas"
    assert reconstruir_resumo(None) == ""


def test_roteamento_por_area():
    assert detectar_area("sintomas e tratamento do cancer") == "medicina"
    assert detectar_area("algoritmo em python para ordenar") == "computacao"
    assert detectar_area("derivada e integral de uma funcao") == "matematica"
    assert detectar_area("quem pintou a mona lisa") == "geral"


def test_escolha_de_fontes_respeita_o_pedido_do_usuario():
    assert escolher_fontes("qualquer coisa", ["arxiv"]) == ["arxiv"]
    assert escolher_fontes("qualquer coisa", ["inexistente"]) != ["inexistente"]
    assert "pubmed" in escolher_fontes("tratamento clinico do paciente")
