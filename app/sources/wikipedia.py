"""Conector da Wikipedia (API MediaWiki, sem chave)."""

from __future__ import annotations

import httpx

from ..texto import truncar
from .base import Documento, FonteBase


class FonteWikipedia(FonteBase):
    id = "wikipedia"
    nome = "Wikipedia"
    descricao = "Enciclopédia colaborativa: visão geral e definições de qualquer tema."
    dominio = "wikipedia.org"
    tipo = "enciclopedia"
    areas = ("geral", "historia", "ciencia", "cultura", "biografia")

    def _endpoint(self, idioma: str) -> str:
        lang = "pt" if idioma.startswith("pt") else "en"
        return f"https://{lang}.wikipedia.org/w/api.php"

    async def buscar(
        self,
        cliente: httpx.AsyncClient,
        consulta: str,
        limite: int,
        idioma: str,
    ) -> list[Documento]:
        url = self._endpoint(idioma)
        resposta = await cliente.get(
            url,
            params={
                "action": "query",
                "list": "search",
                "srsearch": consulta,
                "srlimit": limite,
                "srprop": "snippet",
                "format": "json",
            },
        )
        resposta.raise_for_status()
        achados = resposta.json().get("query", {}).get("search", [])
        if not achados:
            return []

        titulos = [item["title"] for item in achados]
        detalhes = await cliente.get(
            url,
            params={
                "action": "query",
                "prop": "extracts|info",
                "exintro": 0,
                "explaintext": 1,
                "exsectionformat": "plain",
                "inprop": "url",
                "titles": "|".join(titulos),
                "format": "json",
            },
        )
        detalhes.raise_for_status()
        paginas = detalhes.json().get("query", {}).get("pages", {})

        documentos: list[Documento] = []
        for pagina in paginas.values():
            if "missing" in pagina:
                continue
            extrato = pagina.get("extract", "") or ""
            documentos.append(
                Documento(
                    id=f"wikipedia:{pagina.get('pageid')}",
                    titulo=pagina.get("title", ""),
                    url=pagina.get("fullurl", ""),
                    fonte=self.id,
                    resumo=truncar(extrato, 400),
                    conteudo=extrato[:20000],
                    tipo="enciclopedia",
                    idioma="pt" if idioma.startswith("pt") else "en",
                )
            )
        ordem = {t: i for i, t in enumerate(titulos)}
        documentos.sort(key=lambda d: ordem.get(d.titulo, 99))
        return documentos
