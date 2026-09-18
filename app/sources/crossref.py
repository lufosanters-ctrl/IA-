"""Conector da Crossref: metadados canonicos de publicacoes com DOI."""

from __future__ import annotations

import httpx

from ..texto import truncar
from .base import Documento, FonteBase


class FonteCrossref(FonteBase):
    id = "crossref"
    nome = "Crossref"
    descricao = "Registro oficial de DOIs: referências exatas para citar em trabalhos."
    dominio = "crossref.org"
    tipo = "artigo"
    areas = ("academico", "referencia", "ciencia")

    async def buscar(
        self,
        cliente: httpx.AsyncClient,
        consulta: str,
        limite: int,
        idioma: str,
    ) -> list[Documento]:
        resposta = await cliente.get(
            "https://api.crossref.org/works",
            params={"query.bibliographic": consulta, "rows": limite, "select":
                    "DOI,title,abstract,author,issued,container-title,URL,is-referenced-by-count,type"},
        )
        resposta.raise_for_status()
        itens = resposta.json().get("message", {}).get("items", [])

        documentos: list[Documento] = []
        for item in itens:
            titulo = " ".join(item.get("title") or []) or "(sem título)"
            resumo = item.get("abstract", "") or ""
            autores = [
                f"{a.get('given', '')} {a.get('family', '')}".strip()
                for a in item.get("author", [])
            ]
            partes = (item.get("issued") or {}).get("date-parts") or [[None]]
            ano = partes[0][0] if partes and partes[0] else None
            revista = " ".join(item.get("container-title") or [])
            doi = item.get("DOI", "")
            documentos.append(
                Documento(
                    id=f"crossref:{doi}",
                    titulo=titulo,
                    url=item.get("URL") or (f"https://doi.org/{doi}" if doi else ""),
                    fonte=self.id,
                    resumo=truncar(resumo, 400),
                    conteudo=resumo or f"{titulo}. {revista}.",
                    autores=[a for a in autores if a],
                    ano=ano if isinstance(ano, int) else None,
                    identificador=doi,
                    tipo=item.get("type", "artigo"),
                    extra={
                        "revista": revista,
                        "citacoes": item.get("is-referenced-by-count", 0),
                    },
                )
            )
        return documentos
