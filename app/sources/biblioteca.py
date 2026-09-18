"""Conector da biblioteca local: os livros do proprio estudante.

Diferente das outras fontes, esta nao usa rede. Ela consulta o indice FTS5
criado por `app.biblioteca` e devolve trechos com livro, capitulo e pagina —
material didatico costuma responder melhor que um artigo de pesquisa quando
a duvida e conceitual.
"""

from __future__ import annotations

import httpx

from .. import biblioteca
from ..texto import truncar
from .base import Documento, FonteBase


class FonteBiblioteca(FonteBase):
    id = "biblioteca"
    nome = "Sua biblioteca"
    descricao = (
        "Os livros didáticos que você adicionou, indexados e pesquisáveis "
        "por capítulo e página."
    )
    dominio = "local"
    tipo = "livro"
    areas = ("didático", "fundamentos", "geral")

    async def buscar(
        self,
        cliente: httpx.AsyncClient,
        consulta: str,
        limite: int,
        idioma: str,
    ) -> list[Documento]:
        # A busca e local e sincrona, mas rapida (indice FTS5): nao vale a pena
        # jogar numa thread e pagar o custo de troca de contexto.
        achados = biblioteca.buscar(consulta, limite=limite)

        documentos: list[Documento] = []
        for achado in achados:
            partes = [achado["titulo"]]
            if achado.get("capitulo"):
                partes.append(achado["capitulo"])
            # Numero de pagina so e informacao real em livro paginado.
            if achado.get("pagina") and achado.get("formato") == "pdf":
                partes.append(f"p. {achado['pagina']}")
            autores = [a.strip() for a in (achado.get("autores") or "").split(",") if a.strip()]

            documentos.append(
                Documento(
                    # Agrupa por livro e pagina: dois trechos da mesma pagina
                    # viram uma citacao so, em vez de encher a lista de
                    # referencias com o mesmo lugar do mesmo livro.
                    id=f"biblioteca:{achado['livro_id']}:p{achado.get('pagina', 0)}",
                    titulo=" — ".join(partes),
                    url=achado.get("url") or "",
                    fonte=self.id,
                    resumo=truncar(achado["texto"], 400),
                    conteudo=achado["texto"],
                    autores=autores,
                    tipo="livro",
                    identificador=achado.get("licenca", ""),
                    extra={
                        "livro_id": achado["livro_id"],
                        "livro": achado["titulo"],
                        "trecho_id": achado["id"],
                        "pagina": achado.get("pagina", 0),
                        "paginado": achado.get("formato") == "pdf",
                        "capitulo": achado.get("capitulo", ""),
                        "origem": achado.get("origem", "local"),
                        "local": True,
                    },
                )
            )
        return documentos
