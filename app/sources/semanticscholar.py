"""Conector do Semantic Scholar: busca academica com sinal de influencia."""

from __future__ import annotations

import httpx

from ..texto import truncar
from .base import Documento, FonteBase


class FonteSemanticScholar(FonteBase):
    id = "semanticscholar"
    nome = "Semantic Scholar"
    descricao = "Busca acadêmica com resumos, citações influentes e acesso aberto."
    dominio = "semanticscholar.org"
    tipo = "artigo"
    areas = ("academico", "computacao", "ciencia", "ia")

    async def buscar(
        self,
        cliente: httpx.AsyncClient,
        consulta: str,
        limite: int,
        idioma: str,
    ) -> list[Documento]:
        resposta = await cliente.get(
            "https://api.semanticscholar.org/graph/v1/paper/search",
            params={
                "query": consulta,
                "limit": limite,
                "fields": "title,abstract,year,authors,externalIds,url,"
                          "citationCount,influentialCitationCount,openAccessPdf,venue",
            },
        )
        resposta.raise_for_status()
        itens = resposta.json().get("data", []) or []

        documentos: list[Documento] = []
        for item in itens:
            resumo = item.get("abstract") or ""
            ids = item.get("externalIds") or {}
            autores = [a.get("name", "") for a in (item.get("authors") or [])]
            pdf = (item.get("openAccessPdf") or {}).get("url", "")
            documentos.append(
                Documento(
                    id=f"semanticscholar:{item.get('paperId', '')}",
                    titulo=item.get("title") or "(sem título)",
                    url=item.get("url") or "",
                    fonte=self.id,
                    resumo=truncar(resumo, 400),
                    conteudo=resumo or item.get("title", ""),
                    autores=[a for a in autores if a],
                    ano=item.get("year"),
                    identificador=ids.get("DOI", "") or ids.get("ArXiv", ""),
                    tipo="artigo",
                    idioma="en",
                    extra={
                        "citacoes": item.get("citationCount", 0),
                        "citacoes_influentes": item.get("influentialCitationCount", 0),
                        "pdf": pdf,
                        "revista": item.get("venue", ""),
                    },
                )
            )
        return documentos
