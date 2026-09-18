"""Conector do OpenAlex: catalogo aberto com mais de 250 milhoes de trabalhos."""

from __future__ import annotations

import httpx

from ..texto import truncar
from .base import Documento, FonteBase


def reconstruir_resumo(indice_invertido: dict[str, list[int]] | None) -> str:
    """O OpenAlex guarda o abstract como indice invertido; aqui remontamos."""
    if not indice_invertido:
        return ""
    posicoes: list[tuple[int, str]] = []
    for palavra, indices in indice_invertido.items():
        for indice in indices:
            posicoes.append((indice, palavra))
    posicoes.sort(key=lambda item: item[0])
    return " ".join(palavra for _, palavra in posicoes)


class FonteOpenAlex(FonteBase):
    id = "openalex"
    nome = "OpenAlex"
    descricao = "Índice acadêmico aberto com metadados, citações e resumos."
    dominio = "openalex.org"
    tipo = "artigo"
    areas = ("ciencia", "academico", "medicina", "humanas", "engenharia")

    async def buscar(
        self,
        cliente: httpx.AsyncClient,
        consulta: str,
        limite: int,
        idioma: str,
    ) -> list[Documento]:
        resposta = await cliente.get(
            "https://api.openalex.org/works",
            params={
                "search": consulta,
                "per-page": limite,
                "sort": "relevance_score:desc",
                "select": (
                    "id,doi,title,publication_year,authorships,"
                    "abstract_inverted_index,cited_by_count,primary_location,language"
                ),
            },
        )
        resposta.raise_for_status()
        itens = resposta.json().get("results", [])

        documentos: list[Documento] = []
        for item in itens:
            resumo = reconstruir_resumo(item.get("abstract_inverted_index"))
            autores = [
                (a.get("author") or {}).get("display_name", "")
                for a in item.get("authorships", [])
            ]
            local = item.get("primary_location") or {}
            revista = (local.get("source") or {}).get("display_name", "")
            url = local.get("landing_page_url") or item.get("doi") or item.get("id", "")
            documentos.append(
                Documento(
                    id=f"openalex:{(item.get('id') or '').rsplit('/', 1)[-1]}",
                    titulo=item.get("title") or "(sem título)",
                    url=url,
                    fonte=self.id,
                    resumo=truncar(resumo, 400),
                    conteudo=resumo,
                    autores=[a for a in autores if a],
                    ano=item.get("publication_year"),
                    identificador=(item.get("doi") or "").replace("https://doi.org/", ""),
                    tipo="artigo",
                    idioma=item.get("language") or "",
                    extra={
                        "citacoes": item.get("cited_by_count", 0),
                        "revista": revista,
                    },
                )
            )
        return documentos
