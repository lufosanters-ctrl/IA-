"""Testes das utilidades de texto."""

from app.texto import (
    dividir_em_trechos,
    dividir_frases,
    limpar_html,
    normalizar,
    resumir_extrativo,
    tokenizar,
    truncar,
)


def test_limpar_html_remove_marcacao_e_referencias():
    bruto = "<p>Texto <b>importante</b>[12] &amp; claro</p>"
    assert limpar_html(bruto) == "Texto importante & claro"


def test_normalizar_remove_acentos():
    assert normalizar("Inteligência") == "inteligencia"
    assert normalizar("AÇÃO") == "acao"


def test_tokenizar_descarta_stopwords():
    tokens = tokenizar("O que é uma rede neural convolucional?")
    assert tokens == ["rede", "neural", "convolucional"]


def test_tokenizar_mantem_stopwords_quando_pedido():
    tokens = tokenizar("o que e uma rede", remover_stopwords=False)
    assert "que" in tokens


def test_dividir_frases_separa_por_pontuacao():
    frases = dividir_frases(
        "A atencao pondera tokens da entrada. O modelo dispensa recorrencia total."
    )
    assert len(frases) == 2


def test_dividir_em_trechos_respeita_tamanho():
    texto = "Uma frase razoavelmente longa sobre redes neurais profundas. " * 40
    trechos = dividir_em_trechos(texto, tamanho=300, sobreposicao=50)
    assert len(trechos) > 1
    assert all(len(t) <= 420 for t in trechos)


def test_dividir_em_trechos_texto_curto_nao_quebra():
    assert dividir_em_trechos("curto demais", tamanho=900) == ["curto demais"]


def test_resumir_extrativo_prioriza_frases_da_consulta():
    texto = (
        "O bolo de cenoura leva cobertura de chocolate quente. "
        "As redes neurais convolucionais processam imagens em camadas."
    )
    resumo = resumir_extrativo(texto, "redes neurais convolucionais", max_frases=1)
    assert "convolucionais" in resumo


def test_truncar_preserva_palavra_inteira():
    assert truncar("palavra outra terceira", 12).endswith("...")
    assert truncar("curto", 40) == "curto"


def test_trechos_nao_comecam_no_meio_de_uma_frase():
    """Regressao: a sobreposicao entre trechos cortava a frase ao meio."""
    texto = " ".join(
        f"Esta é a frase número {i} do material de estudo, com tamanho suficiente "
        f"para ocupar espaço no bloco." for i in range(1, 30)
    )
    trechos = dividir_em_trechos(texto, tamanho=400, sobreposicao=120)
    assert len(trechos) > 2
    for trecho in trechos:
        primeiro = trecho.lstrip()[0]
        assert primeiro.isupper() or primeiro.isdigit(), (
            f"trecho começa no meio de uma frase: {trecho[:60]!r}"
        )


def test_trechos_mantem_a_sobreposicao_util():
    texto = " ".join(
        f"Frase {i} explicando um conceito relevante do capítulo estudado agora."
        for i in range(1, 25)
    )
    trechos = dividir_em_trechos(texto, tamanho=300, sobreposicao=120)
    # Pelo menos um trecho repete conteudo do anterior (contexto preservado).
    assert any(
        set(anterior.split()) & set(seguinte.split())
        for anterior, seguinte in zip(trechos, trechos[1:])
    )
