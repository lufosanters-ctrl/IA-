"""Conector do Stack Exchange: respostas praticas de programacao, matematica e mais."""

from __future__ import annotations

import httpx

from ..texto import limpar_html, truncar
from .base import Documento, FonteBase

SITES_POR_AREA = {
    "programacao": "stackoverflow",
    "matematica": "math",
    "estatistica": "stats",
    "fisica": "physics",
    "biologia": "biology",
    "ingles": "english",
}


class FonteStackExchange(FonteBase):
    id = "stackexchange"
    nome = "Stack Exchange"
    descricao = "Perguntas e respostas revisadas pela comunidade, com exemplos práticos."
    dominio = "stackexchange.com"
    tipo = "discussao"
    areas = ("programacao", "matematica", "estatistica", "pratica")

    def __init__(self, site: str = "stackoverflow") -> None:
        self.site = site

    async def buscar(
        self,
        cliente: httpx.AsyncClient,
        consulta: str,
        limite: int,
        idioma: str,
    ) -> list[Documento]:
        resposta = await cliente.get(
            "https://api.stackexchange.com/2.3/search/advanced",
            params={
                "order": "desc",
                "sort": "relevance",
                "q": consulta,
                "site": self.site,
                "pagesize": limite,
                "filter": "!nNPvSNdWme",  # inclui o corpo das perguntas
                "answers": 1,
            },
        )
        resposta.raise_for_status()
        itens = resposta.json().get("items", [])

        documentos: list[Documento] = []
        for item in itens:
            corpo = limpar_html(item.get("body") or item.get("body_markdown") or "")
            titulo = limpar_html(item.get("title", ""))
            tags = item.get("tags") or []
            documentos.append(
                Documento(
                    id=f"stackexchange:{item.get('question_id')}",
                    titulo=titulo,
                    url=item.get("link", ""),
                    fonte=self.id,
                    resumo=truncar(corpo, 400),
                    conteudo=f"{titulo}. {corpo}",
                    tipo="discussao",
                    extra={
                        "pontuacao": item.get("score", 0),
                        "respondida": bool(item.get("is_answered")),
                        "tags": tags[:6],
                        "site": self.site,
                    },
                )
            )
        # Perguntas ja respondidas e bem votadas primeiro.
        documentos.sort(
            key=lambda d: (
                d.extra.get("respondida", False),
                d.extra.get("pontuacao", 0),
            ),
            reverse=True,
        )
        return documentos
