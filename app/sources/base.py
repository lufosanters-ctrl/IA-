"""Contrato comum a todos os conectores de bases de dados."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

import httpx

from ..texto import limpar_html, truncar


@dataclass(slots=True)
class Documento:
    """Registro normalizado, independente da base de origem."""

    id: str
    titulo: str
    url: str
    fonte: str
    resumo: str = ""
    conteudo: str = ""
    autores: list[str] = field(default_factory=list)
    ano: int | None = None
    identificador: str = ""          # DOI, ISBN, PMID...
    tipo: str = "documento"          # artigo, enciclopedia, livro, discussao
    idioma: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def para_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "titulo": self.titulo,
            "url": self.url,
            "fonte": self.fonte,
            "resumo": truncar(self.resumo, 420),
            "autores": self.autores[:6],
            "ano": self.ano,
            "identificador": self.identificador,
            "tipo": self.tipo,
            "idioma": self.idioma,
            "extra": self.extra,
        }


@dataclass(slots=True)
class ResultadoFonte:
    """Resultado da consulta a uma fonte, incluindo diagnostico de falha."""

    fonte: str
    documentos: list[Documento] = field(default_factory=list)
    erro: str = ""
    duracao_ms: int = 0


class FonteBase:
    """Classe base dos conectores.

    Subclasses implementam `buscar`. A classe cuida de tratamento de erro,
    normalizacao e limites de tamanho.
    """

    id: str = "base"
    nome: str = "Base"
    descricao: str = ""
    dominio: str = ""
    tipo: str = "documento"
    idiomas: tuple[str, ...] = ("pt", "en")
    # Areas em que a fonte costuma ser util (usado pelo roteador de consulta).
    areas: tuple[str, ...] = ()

    async def buscar(
        self,
        cliente: httpx.AsyncClient,
        consulta: str,
        limite: int,
        idioma: str,
    ) -> list[Documento]:
        raise NotImplementedError

    async def executar(
        self,
        cliente: httpx.AsyncClient,
        consulta: str,
        limite: int,
        idioma: str = "pt",
    ) -> ResultadoFonte:
        """Executa a busca capturando qualquer falha da rede ou do parser."""
        inicio = asyncio.get_running_loop().time()
        try:
            documentos = await self.buscar(cliente, consulta, limite, idioma)
            for doc in documentos:
                doc.resumo = limpar_html(doc.resumo)
                doc.conteudo = limpar_html(doc.conteudo) or doc.resumo
            documentos = [d for d in documentos if d.titulo and (d.conteudo or d.resumo)]
            erro = ""
        except httpx.TimeoutException:
            documentos, erro = [], "tempo limite excedido"
        except httpx.HTTPStatusError as exc:
            documentos, erro = [], f"HTTP {exc.response.status_code}"
        except httpx.HTTPError as exc:
            documentos, erro = [], f"falha de rede: {type(exc).__name__}"
        except Exception as exc:  # parser quebrado nao pode derrubar a busca
            documentos, erro = [], f"erro ao interpretar a resposta: {type(exc).__name__}"

        duracao = int((asyncio.get_running_loop().time() - inicio) * 1000)
        return ResultadoFonte(
            fonte=self.id,
            documentos=documentos[:limite],
            erro=erro,
            duracao_ms=duracao,
        )

    def para_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "nome": self.nome,
            "descricao": self.descricao,
            "dominio": self.dominio,
            "tipo": self.tipo,
            "areas": list(self.areas),
        }
