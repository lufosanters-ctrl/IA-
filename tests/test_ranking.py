"""Testes do ranqueamento BM25 e da selecao diversa."""

from app.ranking import pontuar_bm25, selecionar_diversos
from app.texto import Trecho


def criar(texto: str, doc_id: str, fonte: str = "wikipedia", titulo: str = "t") -> Trecho:
    return Trecho(texto=texto, doc_id=doc_id, titulo=titulo, url="", fonte=fonte)


def test_bm25_ordena_por_relevancia():
    trechos = [
        criar("receita de bolo de cenoura com cobertura", "d1"),
        criar("o mecanismo de atencao pondera tokens da sequencia", "d2"),
    ]
    ordenado = pontuar_bm25("mecanismo de atencao", trechos)
    assert ordenado[0].doc_id == "d2"
    assert ordenado[0].score > ordenado[1].score


def test_bm25_usa_peso_da_fonte_para_desempatar():
    texto = "o mecanismo de atencao pondera tokens"
    trechos = [criar(texto, "d1", "stackexchange"), criar(texto, "d2", "openalex")]
    ordenado = pontuar_bm25("mecanismo de atencao", trechos)
    assert ordenado[0].fonte == "openalex"


def test_bm25_bonifica_termo_no_titulo():
    sem = criar("texto qualquer sobre computacao", "d1", titulo="Assunto diverso")
    com = criar("texto qualquer sobre computacao", "d2", titulo="Atencao neural")
    ordenado = pontuar_bm25("atencao", [sem, com])
    assert ordenado[0].doc_id == "d2"


def test_bm25_sem_termos_uteis_nao_quebra():
    trechos = [criar("qualquer coisa", "d1")]
    assert pontuar_bm25("de o a", trechos)[0].score > 0


def test_selecao_limita_trechos_por_documento():
    trechos = [criar(f"atencao neural variante {i}", "mesmo-doc") for i in range(6)]
    escolhidos = selecionar_diversos(pontuar_bm25("atencao", trechos), limite=5,
                                     max_por_documento=2)
    assert len(escolhidos) == 2


def test_selecao_prefere_conteudo_diverso():
    trechos = [
        criar("atencao neural pondera tokens", "d1"),
        criar("atencao neural pondera tokens", "d2"),
        criar("atencao em modelos de visao computacional com convolucoes", "d3"),
    ]
    escolhidos = selecionar_diversos(pontuar_bm25("atencao", trechos), limite=2)
    assert {t.doc_id for t in escolhidos} == {"d1", "d3"}


def test_selecao_vazia():
    assert selecionar_diversos([], limite=5) == []
