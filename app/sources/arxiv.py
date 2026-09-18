"""Conector do arXiv (pre-prints de exatas, computacao e engenharia)."""

from __future__ import annotations

import xml.etree.ElementTree as ET

import httpx

from ..texto import truncar
from .base import Documento, FonteBase

NS = {"atom": "http://www.w3.org/2005/Atom"}


class FonteArxiv(FonteBase):
    id = "arxiv"
    nome = "arXiv"
    descricao = "Pré-prints de física, matemática, computação, estatística e biologia."
    dominio = "arxiv.org"
    tipo = "artigo"
    idiomas = ("en",)
    areas = ("computacao", "matematica", "fisica", "estatistica", "ia")

    async def buscar(
        self,
        cliente: httpx.AsyncClient,
        consulta: str,
        limite: int,
        idioma: str,
    ) -> list[Documento]:
        resposta = await cliente.get(
            "https://export.arxiv.org/api/query",
            params={
                "search_query": f"all:{consulta}",
                "start": 0,
                "max_results": limite,
                "sortBy": "relevance",
            },
        )
        resposta.raise_for_status()
        raiz = ET.fromstring(resposta.text)

        documentos: list[Documento] = []
        for entrada in raiz.findall("atom:entry", NS):
            titulo = (entrada.findtext("atom:title", "", NS) or "").strip()
            resumo = " ".join((entrada.findtext("atom:summary", "", NS) or "").split())
            link = (entrada.findtext("atom:id", "", NS) or "").strip()
            publicado = entrada.findtext("atom:published", "", NS) or ""
            autores = [
                (a.findtext("atom:name", "", NS) or "").strip()
                for a in entrada.findall("atom:author", NS)
            ]
            doi = entrada.findtext("{http://arxiv.org/schemas/atom}doi", "", NS) or ""
            ano = int(publicado[:4]) if publicado[:4].isdigit() else None
            documentos.append(
                Documento(
                    id=f"arxiv:{link.rsplit('/', 1)[-1]}",
                    titulo=titulo,
                    url=link,
                    fonte=self.id,
                    resumo=truncar(resumo, 400),
                    conteudo=resumo,
                    autores=[a for a in autores if a],
                    ano=ano,
                    identificador=doi,
                    tipo="artigo",
                    idioma="en",
                )
            )
        return documentos
