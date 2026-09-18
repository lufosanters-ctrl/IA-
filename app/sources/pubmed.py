"""Conector do PubMed via Europe PMC (resumos completos, sem chave de API)."""

from __future__ import annotations

import httpx

from ..texto import truncar
from .base import Documento, FonteBase


class FontePubMed(FonteBase):
    id = "pubmed"
    nome = "PubMed / Europe PMC"
    descricao = "Literatura biomédica e das ciências da vida, com resumos completos."
    dominio = "europepmc.org"
    tipo = "artigo"
    areas = ("medicina", "biologia", "saude", "farmacologia", "neurociencia")

    async def buscar(
        self,
        cliente: httpx.AsyncClient,
        consulta: str,
        limite: int,
        idioma: str,
    ) -> list[Documento]:
        resposta = await cliente.get(
            "https://www.ebi.ac.uk/europepmc/webservices/rest/search",
            params={
                "query": consulta,
                "format": "json",
                "pageSize": limite,
                "resultType": "core",
            },
        )
        resposta.raise_for_status()
        itens = resposta.json().get("resultList", {}).get("result", [])

        documentos: list[Documento] = []
        for item in itens:
            resumo = item.get("abstractText") or ""
            pmid = item.get("pmid") or item.get("id") or ""
            doi = item.get("doi") or ""
            if pmid and item.get("source") == "MED":
                url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
            elif doi:
                url = f"https://doi.org/{doi}"
            else:
                url = f"https://europepmc.org/article/{item.get('source', 'MED')}/{item.get('id', '')}"
            autores = [
                a.strip()
                for a in (item.get("authorString") or "").split(",")
                if a.strip()
            ]
            ano = item.get("pubYear")
            documentos.append(
                Documento(
                    id=f"pubmed:{item.get('id', pmid)}",
                    titulo=item.get("title") or "(sem título)",
                    url=url,
                    fonte=self.id,
                    resumo=truncar(resumo, 400),
                    conteudo=resumo,
                    autores=autores,
                    ano=int(ano) if str(ano).isdigit() else None,
                    identificador=doi or pmid,
                    tipo="artigo",
                    idioma="en",
                    extra={
                        "revista": item.get("journalTitle", ""),
                        "citacoes": item.get("citedByCount", 0),
                        "acesso_aberto": item.get("isOpenAccess") == "Y",
                    },
                )
            )
        return documentos
