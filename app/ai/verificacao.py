"""Checagem de fundamentacao: a resposta esta mesmo apoiada nas fontes?

Citar `[3]` no fim da frase nao prova nada — o modelo pode citar a fonte
errada, ou afirmar um numero que nao esta la. Este modulo confere, afirmacao
por afirmacao, se o texto citado sustenta o que foi dito.

A checagem e lexical, nao semantica: mede sobreposicao de palavras de conteudo
e confere se os numeros citados aparecem na fonte. Isso nao pega paráfrase
distante, mas pega com seguranca os dois erros que mais importam — citar a
fonte errada e inventar numero.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from ..texto import dividir_frases, normalizar, tokenizar

_RE_CITACAO = re.compile(r"\[(\d+)\]")
_RE_NUMERO = re.compile(r"\b\d+(?:[.,]\d+)?\s*%?")
_RE_MARCACAO = re.compile(r"[*_`#>]+")

# Frases que nao sao afirmacoes factuais e portanto nao precisam de citacao.
_ABERTURAS_NAO_FACTUAIS = (
    "para fixar", "atencao", "em resumo", "resumindo", "vale lembrar",
    "pergunta", "teste voce mesmo", "como funciona", "observacao",
    "modo extrativo", "compare as fontes", "abra as referencias",
)

APOIO_FORTE = 0.34
APOIO_PARCIAL = 0.16


@dataclass(slots=True)
class Afirmacao:
    """Uma frase da resposta e o quanto as fontes citadas a sustentam."""

    frase: str
    citacoes: list[int] = field(default_factory=list)
    apoio: float = 0.0
    estado: str = "sem_citacao"      # apoiada | parcial | fraca | sem_citacao
    numeros_ausentes: list[str] = field(default_factory=list)

    def para_dict(self) -> dict[str, Any]:
        return {
            "frase": self.frase,
            "citacoes": self.citacoes,
            "apoio": round(self.apoio, 3),
            "estado": self.estado,
            "numeros_ausentes": self.numeros_ausentes,
        }


@dataclass(slots=True)
class Relatorio:
    """Resultado da checagem, exibido ao lado da resposta."""

    afirmacoes: list[Afirmacao] = field(default_factory=list)
    citacoes_invalidas: list[int] = field(default_factory=list)
    cobertura: float = 0.0           # fracao de afirmacoes factuais com citacao
    solidez: float = 0.0             # fracao das citadas que ficaram apoiadas
    alertas: list[str] = field(default_factory=list)

    @property
    def confiavel(self) -> bool:
        return not self.citacoes_invalidas and self.cobertura >= 0.6 and self.solidez >= 0.6

    def para_dict(self) -> dict[str, Any]:
        return {
            "afirmacoes": [a.para_dict() for a in self.afirmacoes],
            "citacoes_invalidas": self.citacoes_invalidas,
            "cobertura": round(self.cobertura, 3),
            "solidez": round(self.solidez, 3),
            "alertas": self.alertas,
            "confiavel": self.confiavel,
        }


def _limpar_frase(frase: str) -> str:
    return _RE_MARCACAO.sub("", _RE_CITACAO.sub("", frase)).strip(" -–—•\t")


def _e_factual(frase: str) -> bool:
    """Descarta titulos de secao e frases de conversa."""
    limpa = _limpar_frase(frase)
    if len(limpa) < 40:
        return False
    minuscula = normalizar(limpa)
    if any(minuscula.startswith(normalizar(a)) for a in _ABERTURAS_NAO_FACTUAIS):
        return False
    return len(tokenizar(limpa)) >= 4


def _numeros(texto: str) -> list[str]:
    achados = []
    for bruto in _RE_NUMERO.findall(texto):
        limpo = bruto.strip().replace(" ", "")
        # Ignora numeracao de lista e anos genericos isolados curtos.
        if limpo.rstrip("%") in {"1", "2", "3", "4", "5"}:
            continue
        achados.append(limpo)
    return achados


def _numero_presente(numero: str, fonte: str) -> bool:
    """Confere o numero na fonte, tolerando virgula/ponto e o sinal de porcento."""
    base = numero.rstrip("%").replace(",", ".")
    variantes = {base, base.replace(".", ","), numero, numero.rstrip("%")}
    if base.endswith(".0"):
        variantes.add(base[:-2])
    return any(v and v in fonte for v in variantes)


def verificar_fundamentacao(
    resposta: str,
    citacoes: list[Any],
) -> Relatorio:
    """Confere cada afirmacao da resposta contra o texto que ela cita."""
    relatorio = Relatorio()
    if not resposta.strip():
        # Nada a checar: cobertura e solidez plenas por vacuidade.
        relatorio.cobertura = relatorio.solidez = 1.0
        return relatorio

    textos: dict[int, str] = {}
    for citacao in citacoes:
        numero = getattr(citacao, "numero", None)
        trecho = getattr(citacao, "trecho", "")
        if numero is None and isinstance(citacao, dict):
            numero, trecho = citacao.get("numero"), citacao.get("trecho", "")
        if numero is not None:
            textos[int(numero)] = trecho or ""

    factuais = 0
    citadas = 0
    apoiadas = 0

    for linha in resposta.split("\n"):
        for frase in dividir_frases(linha) or ([linha] if linha.strip() else []):
            numeros_citados = [int(n) for n in _RE_CITACAO.findall(frase)]
            invalidos = [n for n in numeros_citados if n not in textos]
            for numero in invalidos:
                if numero not in relatorio.citacoes_invalidas:
                    relatorio.citacoes_invalidas.append(numero)

            if not _e_factual(frase):
                continue
            factuais += 1

            afirmacao = Afirmacao(frase=_limpar_frase(frase)[:300],
                                  citacoes=numeros_citados)
            validos = [n for n in numeros_citados if n in textos]
            if not validos:
                relatorio.afirmacoes.append(afirmacao)
                continue

            citadas += 1
            fonte = " ".join(textos[n] for n in validos)
            tokens_frase = set(tokenizar(afirmacao.frase))
            tokens_fonte = set(tokenizar(fonte))
            afirmacao.apoio = (
                len(tokens_frase & tokens_fonte) / len(tokens_frase)
                if tokens_frase else 0.0
            )
            afirmacao.numeros_ausentes = [
                n for n in _numeros(afirmacao.frase) if not _numero_presente(n, fonte)
            ]

            if afirmacao.apoio >= APOIO_FORTE and not afirmacao.numeros_ausentes:
                afirmacao.estado = "apoiada"
                apoiadas += 1
            elif afirmacao.apoio >= APOIO_PARCIAL and not afirmacao.numeros_ausentes:
                afirmacao.estado = "parcial"
                apoiadas += 0.5
            else:
                afirmacao.estado = "fraca"
            relatorio.afirmacoes.append(afirmacao)

    relatorio.cobertura = citadas / factuais if factuais else 1.0
    relatorio.solidez = apoiadas / citadas if citadas else 1.0

    if relatorio.citacoes_invalidas:
        numeros = ", ".join(f"[{n}]" for n in sorted(relatorio.citacoes_invalidas))
        relatorio.alertas.append(
            f"A resposta cita {numeros}, que não existe na lista de referências."
        )
    sem_citacao = [a for a in relatorio.afirmacoes if a.estado == "sem_citacao"]
    if factuais and len(sem_citacao) / factuais > 0.4:
        relatorio.alertas.append(
            f"{len(sem_citacao)} de {factuais} afirmações estão sem citação. "
            "Confira essas partes nas fontes antes de estudar por elas."
        )
    fracas = [a for a in relatorio.afirmacoes if a.estado == "fraca"]
    if fracas:
        relatorio.alertas.append(
            f"{len(fracas)} afirmação(ões) citam uma fonte que não parece "
            "sustentá-las. Abra a referência e confira."
        )
    com_numero = [a for a in relatorio.afirmacoes if a.numeros_ausentes]
    if com_numero:
        exemplos = ", ".join(sorted({n for a in com_numero for n in a.numeros_ausentes})[:4])
        relatorio.alertas.append(
            f"Números citados que não aparecem na fonte indicada: {exemplos}."
        )
    return relatorio
