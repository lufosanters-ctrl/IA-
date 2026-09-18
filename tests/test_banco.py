"""Testes da persistencia e do algoritmo de repeticao espacada."""

import pytest

from app import banco


def test_sm2_primeira_revisao_boa():
    facilidade, intervalo, repeticoes = banco.calcular_sm2(2.5, 0, 0, 5)
    assert (intervalo, repeticoes) == (1, 1)
    assert facilidade > 2.5


def test_sm2_segunda_revisao_vai_para_seis_dias():
    _, intervalo, _ = banco.calcular_sm2(2.6, 1, 1, 4)
    assert intervalo == 6


def test_sm2_terceira_revisao_multiplica_pelo_fator():
    _, intervalo, _ = banco.calcular_sm2(2.5, 6, 2, 4)
    assert intervalo == 15


def test_sm2_erro_reinicia_o_ciclo():
    facilidade, intervalo, repeticoes = banco.calcular_sm2(2.5, 30, 5, 1)
    assert (intervalo, repeticoes) == (1, 0)
    assert facilidade < 2.5


def test_sm2_facilidade_nunca_abaixo_do_piso():
    facilidade = 2.5
    for _ in range(20):
        facilidade, _, _ = banco.calcular_sm2(facilidade, 1, 0, 0)
    assert facilidade >= 1.3


def test_sm2_intervalo_tem_teto():
    _, intervalo, _ = banco.calcular_sm2(2.5, 1000, 10, 5)
    assert intervalo <= 365


def test_salvar_e_recuperar_pesquisa():
    identificador = banco.salvar_pesquisa(
        "o que e atencao", "resposta", "computacao", "neural",
        [{"numero": 1, "titulo": "Fonte"}],
    )
    item = banco.obter_pesquisa(identificador)
    assert item["pergunta"] == "o que e atencao"
    assert item["citacoes"][0]["titulo"] == "Fonte"
    assert banco.apagar_pesquisa(identificador) is True
    assert banco.obter_pesquisa(identificador) is None


def test_cartoes_duplicados_sao_ignorados():
    baralho = banco.criar_baralho("Estudos")
    cartao = {"frente": "O que e atencao?", "verso": "ponderacao de tokens"}
    assert banco.salvar_cartoes(baralho, [cartao]) == 1
    assert banco.salvar_cartoes(baralho, [cartao]) == 0


def test_criar_baralho_e_idempotente():
    primeiro = banco.criar_baralho("Repetido")
    assert banco.criar_baralho("Repetido") == primeiro


def test_revisao_reagenda_o_cartao():
    baralho = banco.criar_baralho("Revisao")
    banco.salvar_cartoes(baralho, [{"frente": "pergunta", "verso": "resposta"}])
    devidos = banco.cartoes_devidos(baralho)
    assert len(devidos) == 1

    dados = banco.revisar_cartao(devidos[0]["id"], 5)
    assert dados["intervalo"] == 1
    assert banco.cartoes_devidos(baralho) == []


def test_revisao_de_cartao_inexistente():
    assert banco.revisar_cartao(99999, 5) is None


def test_estatisticas_refletem_a_atividade():
    baralho = banco.criar_baralho("Metricas")
    banco.salvar_cartoes(baralho, [{"frente": "a", "verso": "b"}])
    banco.salvar_pesquisa("p", "r", "geral", "neural", [])
    dados = banco.estatisticas()
    assert dados["total_cartoes"] == 1
    assert dados["total_pesquisas"] == 1


def test_banco_se_recupera_se_o_arquivo_for_apagado(monkeypatch):
    """Apagar data/nucleo.db com o servidor no ar nao pode derrubar a aplicacao."""
    from app.config import obter_config

    banco.criar_baralho("Antes")
    caminho = obter_config().caminho_banco
    for sufixo in ("", "-wal", "-shm"):
        arquivo = caminho.with_name(caminho.name + sufixo)
        arquivo.unlink(missing_ok=True)

    # A proxima consulta recria o esquema sozinha, em vez de estourar.
    dados = banco.estatisticas()
    assert dados["total_cartoes"] == 0
    assert banco.listar_baralhos()[0]["nome"] == "Geral"
