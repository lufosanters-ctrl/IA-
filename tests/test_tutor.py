"""Testes da tutoria: escada de ajuda, sessão, diagnóstico e fading."""

import pytest

from app.tutor import (
    DEGRAUS,
    abrir_sessao,
    degrau,
    listar_sessoes,
    obter_sessao,
    padroes_de_erro,
    proximo_degrau,
    registrar_tentativa,
    subir_degrau,
)
from app.tutor.escada import NIVEL_MAXIMO, detectar_pedido
from app.tutor.sessao import nivel_inicial_para
from app.tutor.tutoria import apurar, avaliar_tentativa, detectar_materia, orientar
from app.tutor.visao import ErroLeitura, detectar_tipo, texto_de_confirmacao
from app.tutor.visao import Leitura, QuestaoLida, validar_imagem


# --------------------------------------------------------------------------
# Escada
# --------------------------------------------------------------------------

def test_escada_tem_sete_degraus_e_so_o_ultimo_revela():
    assert len(DEGRAUS) == 7
    assert [d.nivel for d in DEGRAUS] == list(range(7))
    reveladores = [d for d in DEGRAUS if d.revela_resposta]
    assert len(reveladores) == 1 and reveladores[0].nivel == NIVEL_MAXIMO


def test_degrau_limita_o_intervalo():
    assert degrau(-5).nivel == 0
    assert degrau(99).nivel == NIVEL_MAXIMO


def test_ajuda_sobe_um_degrau_de_cada_vez():
    assert proximo_degrau(0) == 1
    assert proximo_degrau(3) == 4
    assert proximo_degrau(NIVEL_MAXIMO) == NIVEL_MAXIMO


def test_quem_esta_quase_la_recebe_menos_ajuda():
    """O fading do enunciado: acerto parcial RECUA a escada."""
    assert proximo_degrau(3, acertou_algo=True) == 2
    assert proximo_degrau(0, acertou_algo=True) == 0


def test_pedido_de_resolucao_vai_direto_ao_fim():
    assert proximo_degrau(0, pediu_resolucao=True) == NIVEL_MAXIMO


def test_pedido_de_autonomia_nunca_revela():
    assert proximo_degrau(6, pediu_autonomia=True) == NIVEL_MAXIMO - 1
    assert not degrau(proximo_degrau(6, pediu_autonomia=True)).revela_resposta


@pytest.mark.parametrize("texto,esperado", [
    ("não me dê a resposta, quero tentar", "autonomia"),
    ("me dê uma dica só", "autonomia"),
    ("resolva completo por favor", "resolucao"),
    ("qual é a resposta?", "resolucao"),
    ("desisto", "resolucao"),
    ("estou com dúvida aqui", ""),
])
def test_deteccao_do_pedido(texto, esperado):
    assert detectar_pedido(texto) == esperado


# --------------------------------------------------------------------------
# Matéria
# --------------------------------------------------------------------------

@pytest.mark.parametrize("enunciado,materia", [
    ("Resolva a equação x^2 - 5x + 6 = 0.", "matematica"),
    ("Analise a crase em: Vou a praia.", "portugues"),
    ("Choose the correct option: I have seen him yesterday.", "ingles"),
    ("Qual é o objeto indireto da oração?", "portugues"),
    ("Fale sobre a Revolução Francesa.", "geral"),
])
def test_deteccao_de_materia(enunciado, materia):
    assert detectar_materia(enunciado) == materia


# --------------------------------------------------------------------------
# Sessão e persistência
# --------------------------------------------------------------------------

def test_sessao_guarda_tentativas_em_ordem():
    sessao = abrir_sessao("matematica", "Resolva x^2 - 4 = 0", "polinomios", 2)
    registrar_tentativa(sessao.id, "x = 2", "parcial", "faltou a raiz negativa",
                        "incompleto", 1)
    registrar_tentativa(sessao.id, "x = 2 e x = -2", "correto", "", "", 1)

    recarregada = obter_sessao(sessao.id)
    assert recarregada is not None
    assert [t.veredito for t in recarregada.tentativas] == ["parcial", "correto"]
    assert recarregada.resolvida is True


def test_sessao_inexistente():
    assert obter_sessao(999999) is None
    assert registrar_tentativa(999999, "x", "correto") is None
    assert subir_degrau(999999, 3) is False


def test_subir_degrau_limita_ao_intervalo():
    sessao = abrir_sessao("geral", "Uma questão qualquer para estudar")
    subir_degrau(sessao.id, 99)
    assert obter_sessao(sessao.id).nivel_atual == NIVEL_MAXIMO


def test_padroes_de_erro_trazem_estrategia_preventiva():
    sessao = abrir_sessao("matematica", "Calcule algo", "polinomios", 2)
    for _ in range(3):
        registrar_tentativa(sessao.id, "-2", "incorreto", "trocou o sinal", "sinal", 2)

    padroes = padroes_de_erro(minimo=2)
    recorrente = next(p for p in padroes["recorrentes"] if p["tipo"] == "sinal")
    assert recorrente["ocorrencias"] >= 3
    assert recorrente["estrategia"]
    assert padroes["dominio"]


def test_fading_reduz_o_andaime_de_quem_domina():
    """Depois de acertar seguidas vezes com pouca ajuda, começa mais alto."""
    assert nivel_inicial_para("trigonometria") == 0
    for _ in range(4):
        sessao = abrir_sessao("matematica", "Questão de trigonometria", "trigonometria", 2)
        registrar_tentativa(sessao.id, "resposta certa", "correto", "", "", 1)
    assert nivel_inicial_para("trigonometria") == 1


def test_fading_nao_reduz_para_quem_erra():
    for _ in range(4):
        sessao = abrir_sessao("matematica", "Questão difícil", "matrizes", 3)
        registrar_tentativa(sessao.id, "errado", "incorreto", "erro", "conceitual", 5)
    assert nivel_inicial_para("matrizes") == 0


def test_listagem_de_sessoes():
    abrir_sessao("portugues", "Analise a crase nesta frase longa o bastante")
    sessoes = listar_sessoes(10)
    assert sessoes and "enunciado" in sessoes[0]


# --------------------------------------------------------------------------
# Orientação por degrau
# --------------------------------------------------------------------------

pytestmark_async = pytest.mark.asyncio


@pytest.mark.asyncio
async def test_degrau_zero_nao_revela_a_resposta():
    resposta = await orientar("Vou a praia amanhã. A crase está correta?", nivel=0)
    assert resposta.nivel == 0
    assert not resposta.revela_resposta
    assert resposta.texto


@pytest.mark.asyncio
async def test_degrau_dois_traz_a_propriedade_que_resolve():
    resposta = await orientar("Vou a praia amanhã. A crase está correta?", nivel=2)
    assert resposta.materia == "portugues"
    assert "regência" in resposta.texto or "crase" in resposta.texto.lower()


@pytest.mark.asyncio
async def test_orientacao_em_matematica_usa_o_diagnostico():
    resposta = await orientar("Resolva a equação x^2 - 5x + 6 = 0.", nivel=0)
    assert resposta.materia == "matematica"
    assert resposta.texto


@pytest.mark.asyncio
async def test_contexto_apurado_nao_vaza_solucao_no_resumo_do_degrau():
    """O resumo lembra o modelo de não revelar o que a álgebra já achou."""
    contexto = await apurar("Resolva a equação x^2 - 5x + 6 = 0.")
    assert "NÃO revele" in contexto.resumo


@pytest.mark.asyncio
async def test_diagnostico_deterministico_de_portugues():
    diagnostico = await avaliar_tentativa(
        "A crase está correta?", "Entreguei o livro à ela, porque ela é feminino.",
        materia="portugues",
    )
    assert diagnostico.veredito == "incorreto"
    assert "pronome pessoal" in diagnostico.por_que


@pytest.mark.asyncio
async def test_diagnostico_deterministico_de_ingles():
    diagnostico = await avaliar_tentativa(
        "Is this sentence correct in English?", "I think people is waiting there.",
        materia="ingles",
    )
    assert diagnostico.veredito == "incorreto"
    assert "people are" in diagnostico.resposta


# --------------------------------------------------------------------------
# Leitura de imagem
# --------------------------------------------------------------------------

def _png_minimo() -> bytes:
    import struct
    import zlib

    def bloco(tipo: bytes, dados: bytes) -> bytes:
        corpo = tipo + dados
        return struct.pack(">I", len(dados)) + corpo + struct.pack(">I", zlib.crc32(corpo))

    return (b"\x89PNG\r\n\x1a\n"
            + bloco(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
            + bloco(b"IEND", b""))


@pytest.mark.parametrize("assinatura,tipo", [
    (b"\xff\xd8\xff\xe0", "jpeg"),
    (b"RIFF\x00\x00\x00\x00WEBP", "webp"),
    (b"GIF89a", "gif"),
    (b"%PDF-1.4", ""),
    (b"qualquer coisa", ""),
])
def test_deteccao_de_formato_por_assinatura(assinatura, tipo):
    assert detectar_tipo(assinatura) == tipo


def test_png_valido_passa():
    assert validar_imagem(_png_minimo()) == "png"


@pytest.mark.parametrize("conteudo,motivo", [
    (b"", "vazio"),
    (b"isto nao e imagem", "formato"),
    (b"x" * (9 * 1024 * 1024), "maior"),
])
def test_imagem_invalida_e_recusada(conteudo, motivo):
    with pytest.raises(ErroLeitura, match=motivo):
        validar_imagem(conteudo)


def test_confirmacao_mostra_o_que_foi_lido_e_o_que_nao_foi():
    leitura = Leitura(
        questoes=[QuestaoLida(
            numero="12", enunciado="Calcule o valor de x.",
            alternativas=[{"letra": "A", "texto": "2"}, {"letra": "B", "texto": "3"}],
        )],
        anotacoes_do_estudante="x = 2x + 1",
        alternativa_marcada="B",
        ilegivel=["o expoente no canto direito"],
    )
    texto = texto_de_confirmacao(leitura)
    assert "Calcule o valor de x." in texto
    assert "**A)** 2" in texto
    assert "x = 2x + 1" in texto
    assert "expoente no canto direito" in texto
    assert not leitura.confiavel        # há trecho ilegível


def test_leitura_sem_ilegivel_e_confiavel():
    leitura = Leitura(questoes=[QuestaoLida(enunciado="Enunciado completo.")])
    assert leitura.confiavel


# --------------------------------------------------------------------------
# A escada não pode vazar a resposta antes da hora
# --------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("nivel", [0, 1, 2, 3, 4, 5])
async def test_degraus_intermediarios_nao_dao_o_veredito(nivel):
    """Regressão: o degrau 2 entregava a conclusão sobre a frase."""
    resposta = await orientar(
        "Assinale se a crase está correta: Vou a praia amanhã.", nivel=nivel
    )
    texto = resposta.texto.lower()
    assert "as duas condições da crase estão satisfeitas" not in texto
    assert not resposta.revela_resposta


@pytest.mark.asyncio
async def test_degrau_seis_entrega_o_veredito():
    resposta = await orientar(
        "Assinale se a crase está correta: Vou a praia amanhã.", nivel=6
    )
    assert resposta.revela_resposta
    assert "regência" in resposta.texto or "crase" in resposta.texto.lower()


@pytest.mark.asyncio
async def test_matematica_so_mostra_a_solucao_no_ultimo_degrau():
    enunciado = "Resolva a equação x^2 - 5x + 6 = 0."
    for nivel in range(6):
        resposta = await orientar(enunciado, nivel=nivel)
        assert "Resolução simbólica" not in resposta.texto

    final = await orientar(enunciado, nivel=6)
    assert "Resolução simbólica" in final.texto
    assert "2" in final.texto and "3" in final.texto


@pytest.mark.asyncio
async def test_ingles_so_corrige_no_ultimo_degrau():
    enunciado = "Is this correct? People is waiting outside since three years."
    intermediario = await orientar(enunciado, nivel=2)
    assert "people are" not in intermediario.texto.lower()

    final = await orientar(enunciado, nivel=6)
    assert "people are" in final.texto.lower()
