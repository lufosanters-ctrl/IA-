"""Analise gramatical de uma frase: reune os motores num veredito unico."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .colocacao import analisar_colocacao
from .concordancia import analisar_concordancia
from .crase import DEPENDE, FACULTATIVA, OBRIGATORIA, PROIBIDA, analisar_crase
from .regencia import nomes_na_frase, verbos_na_frase


@dataclass(slots=True)
class Achado:
    """Um ponto da frase que merece atenção, com regra e teste."""

    topico: str              # crase | regencia | colocacao | concordancia
    trecho: str
    veredito: str            # erro | atencao | correto | depende
    regra: str
    explicacao: str
    teste: str = ""
    pergunta_guia: str = ""

    def para_dict(self) -> dict[str, Any]:
        return {
            "topico": rotular_topico(self.topico),
            "trecho": self.trecho,
            "veredito": self.veredito,
            "regra": self.regra,
            "explicacao": self.explicacao,
            "teste": self.teste,
            "pergunta_guia": self.pergunta_guia,
        }


@dataclass(slots=True)
class AnaliseGramatical:
    """O que os motores determinísticos apuraram sobre a frase."""

    frase: str
    achados: list[Achado] = field(default_factory=list)
    crase: list[dict[str, Any]] = field(default_factory=list)
    colocacao: list[dict[str, Any]] = field(default_factory=list)
    concordancia: list[dict[str, Any]] = field(default_factory=list)
    regencia: list[dict[str, Any]] = field(default_factory=list)

    @property
    def tem_erro(self) -> bool:
        return any(a.veredito == "erro" for a in self.achados)

    @property
    def topicos_envolvidos(self) -> list[str]:
        """Tópicos na ordem de relevância: erro primeiro, depois o resto."""
        ordem = {"erro": 0, "depende": 1, "atencao": 2, "correto": 3}
        vistos: dict[str, int] = {}
        for achado in self.achados:
            peso = ordem.get(achado.veredito, 4)
            if achado.topico not in vistos or peso < vistos[achado.topico]:
                vistos[achado.topico] = peso
        return [t for t, _ in sorted(vistos.items(), key=lambda par: par[1])]

    def para_dict(self) -> dict[str, Any]:
        return {
            "frase": self.frase,
            "achados": [a.para_dict() for a in self.achados],
            "crase": self.crase,
            "colocacao": self.colocacao,
            "concordancia": self.concordancia,
            "regencia": self.regencia,
            "tem_erro": self.tem_erro,
            "topicos_envolvidos": [
                rotular_topico(t) for t in self.topicos_envolvidos
            ],
        }


ROTULOS_TOPICO = {
    "crase": "crase",
    "regencia": "regência",
    "colocacao": "colocação pronominal",
    "concordancia": "concordância",
}


def rotular_topico(topico: str) -> str:
    return ROTULOS_TOPICO.get(topico, topico)


_VEREDITO_CRASE = {
    OBRIGATORIA: "erro",
    PROIBIDA: "erro",
    FACULTATIVA: "correto",
    DEPENDE: "depende",
}


def analisar_frase(frase: str) -> AnaliseGramatical:
    """Passa a frase por todos os motores e reúne os achados."""
    analise = AnaliseGramatical(frase=frase)
    if not frase or not frase.strip():
        return analise

    # --- crase -------------------------------------------------------------
    for ocorrencia in analisar_crase(frase):
        analise.crase.append(ocorrencia.para_dict())
        if ocorrencia.correto is True:
            veredito = "correto"
        elif ocorrencia.correto is False:
            veredito = "erro"
        else:
            veredito = "depende"
        analise.achados.append(Achado(
            topico="crase",
            trecho=ocorrencia.contexto,
            veredito=veredito,
            regra=ocorrencia.regra,
            explicacao=ocorrencia.explicacao,
            teste=(
                "Troque o termo feminino por um masculino equivalente: se "
                "aparecer “ao”, a preposição existe."
            ),
            pergunta_guia=ocorrencia.pergunta_guia,
        ))

    # --- colocação pronominal ---------------------------------------------
    for ocorrencia in analisar_colocacao(frase):
        analise.colocacao.append(ocorrencia.para_dict())
        analise.achados.append(Achado(
            topico="colocacao",
            trecho=f"{ocorrencia.verbo} / {ocorrencia.pronome}",
            veredito="correto" if ocorrencia.correto else "erro",
            regra=ocorrencia.regra,
            explicacao=(
                f"Usou {ocorrencia.posicao_usada}; a norma-padrão pede "
                f"{ocorrencia.posicao_correta}. {ocorrencia.explicacao}"
                if not ocorrencia.correto else ocorrencia.explicacao
            ),
            teste="Procure palavra atrativa antes do verbo; se houver, o pronome "
                  "vai para antes.",
        ))

    # --- concordância ------------------------------------------------------
    for achado in analisar_concordancia(frase):
        analise.concordancia.append(achado.para_dict())
        analise.achados.append(Achado(
            topico="concordancia",
            trecho=achado.trecho,
            veredito=achado.veredito,
            regra=achado.configuracao,
            explicacao=achado.regra + (
                f" Correção: {achado.correcao}." if achado.correcao else ""
            ),
            teste=achado.teste,
        ))

    # --- regência ----------------------------------------------------------
    for verbo, sentidos in verbos_na_frase(frase):
        entrada = {
            "verbo": verbo,
            "sentidos": [s.para_dict() for s in sentidos],
        }
        analise.regencia.append(entrada)
        if len(sentidos) > 1:
            resumo = "; ".join(
                f"{s.sentido} → {s.transitividade}"
                + (f" ({', '.join(s.preposicoes)})" if s.preposicoes else "")
                for s in sentidos
            )
            analise.achados.append(Achado(
                topico="regencia",
                trecho=verbo,
                veredito="depende",
                regra=f"“{verbo}” muda de regência conforme o sentido",
                explicacao=f"Sentidos registrados: {resumo}.",
                teste="Determine primeiro o SENTIDO na frase; só depois decida a "
                      "preposição.",
                pergunta_guia=f"Em que sentido “{verbo}” está empregado aqui?",
            ))

    for nome, preposicoes in nomes_na_frase(frase):
        analise.regencia.append({"nome": nome, "preposicoes": list(preposicoes)})

    return analise
