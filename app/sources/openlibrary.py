"""Conector da Open Library: catalogo aberto de livros do Internet Archive."""

from __future__ import annotations

import httpx

from .base import Documento, FonteBase


class FonteOpenLibrary(FonteBase):
    id = "openlibrary"
    nome = "Open Library"
    descricao = "Catálogo de livros: bibliografia para aprofundar um assunto."
    dominio = "openlibrary.org"
    tipo = "livro"
    areas = ("livros", "bibliografia", "geral")

    async def buscar(
        self,
        cliente: httpx.AsyncClient,
        consulta: str,
        limite: int,
        idioma: str,
    ) -> list[Documento]:
        resposta = await cliente.get(
            "https://openlibrary.org/search.json",
            params={
                "q": consulta,
                "limit": limite,
                "fields": "key,title,author_name,first_publish_year,first_sentence,"
                          "subject,language,cover_i,edition_count,ia",
            },
        )
        resposta.raise_for_status()
        itens = resposta.json().get("docs", [])

        documentos: list[Documento] = []
        for item in itens:
            chave = item.get("key", "")
            assuntos = ", ".join((item.get("subject") or [])[:8])
            frase = " ".join(item.get("first_sentence") or [])
            autores = item.get("author_name") or []
            corpo = " ".join(
                parte
                for parte in [
                    f"{item.get('title', '')}, de {', '.join(autores[:3])}."
                    if autores else item.get("title", ""),
                    frase,
                    f"Assuntos: {assuntos}." if assuntos else "",
                ]
                if parte
            )
            capa = item.get("cover_i")
            documentos.append(
                Documento(
                    id=f"openlibrary:{chave.rsplit('/', 1)[-1]}",
                    titulo=item.get("title", "(sem título)"),
                    url=f"https://openlibrary.org{chave}",
                    fonte=self.id,
                    resumo=corpo[:400],
                    conteudo=corpo,
                    autores=autores,
                    ano=item.get("first_publish_year"),
                    tipo="livro",
                    idioma=", ".join((item.get("language") or [])[:3]),
                    extra={
                        "capa": f"https://covers.openlibrary.org/b/id/{capa}-M.jpg"
                        if capa else "",
                        "edicoes": item.get("edition_count", 0),
                    },
                )
            )
        return documentos
