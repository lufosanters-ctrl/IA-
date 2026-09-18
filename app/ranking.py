"""Ranqueamento de trechos recuperados das bases publicas.

Implementa BM25 (Okapi) puro em Python, com dois refinamentos praticos:

* bonus de autoridade por fonte (um artigo revisado por pares pesa mais que
  um post de forum para uma duvida academica);
* selecao final com MMR (Maximal Marginal Relevance) para evitar que o
  contexto enviado ao modelo seja composto por cinco copias do mesmo texto.
"""

from __future__ import annotations

import math
from collections import Counter

from .texto import Trecho, tokenizar

# Peso de credibilidade por fonte. Valores maiores => mais confianca.
PESO_FONTE: dict[str, float] = {
    # O livro que o proprio estudante escolheu e curado por ele: e a fonte de
    # maior confianca que a plataforma tem.
    "biblioteca": 1.35,
    "openalex": 1.20,
    "pubmed": 1.20,
    "arxiv": 1.15,
    "crossref": 1.12,
    "semanticscholar": 1.12,
    "wikipedia": 1.05,
    "openlibrary": 1.00,
    "stackexchange": 0.92,
}

K1 = 1.5
B = 0.75


def _idf(n_docs: int, n_com_termo: int) -> float:
    """IDF do BM25 com suavizacao, sempre positivo."""
    return math.log(1 + (n_docs - n_com_termo + 0.5) / (n_com_termo + 0.5))


def pesos_efetivos(ajustes: dict[str, float] | None = None) -> dict[str, float]:
    """Combina o peso base de cada fonte com o ajuste pedido pela intencao."""
    pesos = dict(PESO_FONTE)
    for fonte, fator in (ajustes or {}).items():
        pesos[fonte] = pesos.get(fonte, 1.0) * fator
    return pesos


def pontuar_bm25(
    consulta: str,
    trechos: list[Trecho],
    ajuste_fontes: dict[str, float] | None = None,
) -> list[Trecho]:
    """Atribui score BM25 a cada trecho e devolve a lista ordenada.

    `ajuste_fontes` vem da intencao detectada na pergunta: uma duvida de
    definicao valoriza livro didatico, uma de estado da arte valoriza
    pre-print recente.
    """
    if not trechos:
        return []

    pesos = pesos_efetivos(ajuste_fontes)

    termos = tokenizar(consulta)
    if not termos:
        for trecho in trechos:
            trecho.score = pesos.get(trecho.fonte, 1.0)
        return sorted(trechos, key=lambda t: t.score, reverse=True)

    corpus = [tokenizar(t.texto) for t in trechos]
    n_docs = len(corpus)
    tam_medio = sum(len(d) for d in corpus) / n_docs or 1.0

    frequencia_doc: Counter[str] = Counter()
    for doc in corpus:
        for termo in set(doc):
            frequencia_doc[termo] += 1

    for trecho, doc in zip(trechos, corpus):
        contagem = Counter(doc)
        tamanho = len(doc) or 1
        score = 0.0
        for termo in termos:
            freq = contagem.get(termo, 0)
            if not freq:
                continue
            idf = _idf(n_docs, frequencia_doc[termo])
            numerador = freq * (K1 + 1)
            denominador = freq + K1 * (1 - B + B * tamanho / tam_medio)
            score += idf * numerador / denominador

        # Casamento de frase exata: sinal forte de relevancia.
        if consulta.strip().lower() in trecho.texto.lower():
            score *= 1.25
        # Termos da consulta presentes no titulo do documento. O sinal e
        # multiplicativo (reforca um trecho ja relevante) e tambem aditivo,
        # para que um titulo certeiro conte mesmo quando o corpo do trecho
        # nao repete os termos da pergunta.
        tokens_titulo = set(tokenizar(trecho.titulo))
        if tokens_titulo:
            cobertura = len(set(termos) & tokens_titulo) / len(set(termos))
            score = score * (1.0 + 0.35 * cobertura) + 0.6 * cobertura

        trecho.score = score * pesos.get(trecho.fonte, 1.0)

    return sorted(trechos, key=lambda t: t.score, reverse=True)


def _similaridade(a: set[str], b: set[str]) -> float:
    """Jaccard entre dois conjuntos de tokens."""
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def selecionar_diversos(
    trechos: list[Trecho],
    limite: int,
    lambda_relevancia: float = 0.72,
    max_por_documento: int = 2,
    max_por_fonte: int | None = None,
) -> list[Trecho]:
    """Escolhe os melhores trechos evitando redundancia (MMR).

    `max_por_fonte` impede que uma unica base domine o contexto. Sem esse
    limite, uma biblioteca local grande afogaria as fontes online (e o
    contrario tambem), e a resposta perderia o contraste entre pontos de vista.
    """
    if not trechos:
        return []

    candidatos = list(trechos[: limite * 5])
    tokens = {id(t): set(tokenizar(t.texto)) for t in candidatos}
    melhor_score = max((t.score for t in candidatos), default=1.0) or 1.0

    escolhidos: list[Trecho] = []
    por_documento: Counter[str] = Counter()
    por_fonte: Counter[str] = Counter()

    while candidatos and len(escolhidos) < limite:
        melhor: Trecho | None = None
        melhor_valor = -1e9
        for candidato in candidatos:
            if por_documento[candidato.doc_id] >= max_por_documento:
                continue
            if max_por_fonte and por_fonte[candidato.fonte] >= max_por_fonte:
                continue
            relevancia = candidato.score / melhor_score
            redundancia = max(
                (_similaridade(tokens[id(candidato)], tokens[id(e)]) for e in escolhidos),
                default=0.0,
            )
            valor = lambda_relevancia * relevancia - (1 - lambda_relevancia) * redundancia
            if valor > melhor_valor:
                melhor_valor = valor
                melhor = candidato
        if melhor is None:
            break
        escolhidos.append(melhor)
        por_documento[melhor.doc_id] += 1
        por_fonte[melhor.fonte] += 1
        candidatos.remove(melhor)

    return escolhidos
