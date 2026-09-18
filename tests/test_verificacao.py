"""Testes da checagem de fundamentacao das respostas."""

from app.ai.pesquisa import Citacao
from app.ai.verificacao import verificar_fundamentacao

FONTES = [
    Citacao(numero=1, titulo="Livro", url="", fonte="biblioteca",
            trecho="A fotossíntese converte energia luminosa em energia química "
                   "dentro dos cloroplastos, organelas que contêm clorofila."),
    Citacao(numero=2, titulo="Artigo", url="", fonte="openalex",
            trecho="O ciclo de Calvin ocorre no estroma e fixa dióxido de carbono. "
                   "A eficiência típica medida foi de 4,5 por cento."),
]


def test_resposta_bem_fundamentada():
    texto = (
        "A fotossíntese converte energia luminosa em energia química dentro dos "
        "cloroplastos, que contêm clorofila [1]. O ciclo de Calvin fixa dióxido de "
        "carbono no estroma do cloroplasto [2]."
    )
    relatorio = verificar_fundamentacao(texto, FONTES)
    assert relatorio.confiavel
    assert relatorio.cobertura == 1.0
    assert all(a.estado == "apoiada" for a in relatorio.afirmacoes)
    assert relatorio.alertas == []


def test_citacao_para_fonte_inexistente():
    texto = "A fotossíntese ocorre nos cloroplastos das células vegetais [7]."
    relatorio = verificar_fundamentacao(texto, FONTES)
    assert relatorio.citacoes_invalidas == [7]
    assert not relatorio.confiavel
    assert any("[7]" in alerta for alerta in relatorio.alertas)


def test_numero_inventado_e_apontado():
    texto = (
        "A eficiência da fotossíntese medida no experimento foi de 87,4 por cento "
        "nas plantas tropicais analisadas [2]."
    )
    relatorio = verificar_fundamentacao(texto, FONTES)
    afirmacao = relatorio.afirmacoes[0]
    assert "87,4" in afirmacao.numeros_ausentes
    assert afirmacao.estado == "fraca"


def test_numero_presente_na_fonte_passa():
    texto = ("A eficiência do ciclo de Calvin medida no estroma foi de 4,5 por "
             "cento nas condições do experimento [2].")
    relatorio = verificar_fundamentacao(texto, FONTES)
    assert relatorio.afirmacoes[0].numeros_ausentes == []


def test_afirmacao_que_cita_a_fonte_errada():
    texto = ("Napoleão Bonaparte foi derrotado na batalha de Waterloo no ano de "
             "mil oitocentos e quinze [1].")
    relatorio = verificar_fundamentacao(texto, FONTES)
    assert relatorio.afirmacoes[0].estado == "fraca"
    assert relatorio.solidez < 0.5


def test_afirmacao_sem_citacao_entra_na_cobertura():
    texto = ("A fotossíntese converte energia luminosa em energia química nos "
             "cloroplastos das células vegetais analisadas.")
    relatorio = verificar_fundamentacao(texto, FONTES)
    assert relatorio.afirmacoes[0].estado == "sem_citacao"
    assert relatorio.cobertura == 0.0


def test_titulo_de_secao_nao_conta_como_afirmacao():
    texto = "## Para fixar\n\n- Ponto curto"
    relatorio = verificar_fundamentacao(texto, FONTES)
    assert relatorio.afirmacoes == []
    assert relatorio.cobertura == 1.0


def test_resposta_vazia():
    relatorio = verificar_fundamentacao("", FONTES)
    assert relatorio.afirmacoes == []
    assert relatorio.confiavel


def test_aceita_citacoes_como_dicionario():
    fontes = [{"numero": 1, "trecho": "A mitocôndria produz ATP pela respiração celular."}]
    texto = "A mitocôndria produz ATP por meio da respiração celular aeróbica [1]."
    assert verificar_fundamentacao(texto, fontes).afirmacoes[0].estado == "apoiada"
