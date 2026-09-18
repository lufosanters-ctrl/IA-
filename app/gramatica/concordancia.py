"""Concordancia verbal: as armadilhas que caem em prova.

Analise sintatica completa exige um parser que nao cabe aqui. O que cabe — e
o que resolve a maior parte das questoes — e reconhecer as CONFIGURACOES
classicas e enunciar a regra que vale para cada uma:

* "haver" no sentido de existir e impessoal e nao vai ao plural;
* "fazer" indicando tempo decorrido tambem e impessoal;
* "existir" concorda normalmente, e por isso e o contraste util;
* a particula "se" apassivadora leva o verbo ao plural, a de indeterminacao
  do sujeito nao.

Cada achado vem com o teste que o estudante pode aplicar sozinho.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

PLURAIS_DE_HAVER = (
    "haviam", "houveram", "hao de haver", "havia de haver", "haverao",
    "houveram", "haveriam",
)

_RE_HAVER_PLURAL = re.compile(
    r"\b(haviam|houveram|haver[ãa]o|haveriam)\b", re.IGNORECASE
)
_RE_HAVER_SINGULAR = re.compile(r"\b(h[áa]|havia|houve|haver[áa])\b", re.IGNORECASE)
_RE_FAZER_TEMPO = re.compile(
    r"\b(fazem|faziam|fizeram|far[ãa]o)\s+(?:mais de\s+|cerca de\s+)?"
    r"(?:\w+\s+)?(anos?|meses|m[êe]s|dias?|semanas?|horas?|s[ée]culos?)\b",
    re.IGNORECASE,
)
_RE_SE_APASSIVADORA = re.compile(
    r"\b(\w+)-se\s+((?:os|as|uns|umas|muitos|muitas|v[áa]rios|v[áa]rias|dois|duas|"
    r"tr[êe]s)\s+)?([A-Za-zÀ-ÿ]+s)\b", re.IGNORECASE
)
_RE_SE_INDETERMINACAO = re.compile(
    r"\b(\w+)-se\s+(de|a|em|com|para|por)\b", re.IGNORECASE
)
_RE_UM_DOS_QUE = re.compile(r"\bum[a]? d[oa]s que\b", re.IGNORECASE)


@dataclass(slots=True)
class AchadoConcordancia:
    """Uma configuração de concordância detectada, com a regra e o teste."""

    configuracao: str
    trecho: str
    veredito: str          # erro | atencao | correto
    regra: str
    teste: str
    correcao: str = ""

    def para_dict(self) -> dict[str, Any]:
        return {
            "configuracao": self.configuracao,
            "trecho": self.trecho,
            "veredito": self.veredito,
            "regra": self.regra,
            "teste": self.teste,
            "correcao": self.correcao,
        }


def _trecho(frase: str, achado: re.Match[str], margem: int = 30) -> str:
    inicio = max(0, achado.start() - margem)
    fim = min(len(frase), achado.end() + margem)
    return ("…" if inicio else "") + frase[inicio:fim].strip() + ("…" if fim < len(frase) else "")


def analisar_concordancia(frase: str) -> list[AchadoConcordancia]:
    """Detecta as configurações de concordância que costumam ser cobradas."""
    if not frase or not frase.strip():
        return []
    achados: list[AchadoConcordancia] = []

    # --- haver impessoal ---------------------------------------------------
    for achado in _RE_HAVER_PLURAL.finditer(frase):
        forma = achado.group(1)
        achados.append(AchadoConcordancia(
            configuracao="“haver” no plural",
            trecho=_trecho(frase, achado),
            veredito="erro",
            regra=(
                "No sentido de “existir” ou “acontecer”, o verbo haver é "
                "impessoal: não tem sujeito e fica sempre na 3ª pessoa do "
                "singular."
            ),
            teste=(
                "Troque por “existir”. Se “existiam” fica bem, o sujeito existe "
                "e o certo com haver é o singular: “havia”."
            ),
            correcao=f"“{forma}” → “{'havia' if forma.lower().startswith('hav') else 'houve'}”",
        ))

    for achado in _RE_HAVER_SINGULAR.finditer(frase):
        achados.append(AchadoConcordancia(
            configuracao="“haver” no singular",
            trecho=_trecho(frase, achado),
            veredito="correto",
            regra="Haver impessoal permanece no singular, qualquer que seja o "
                  "número do complemento.",
            teste="Confira se o sentido é mesmo “existir”; se for “ter posse”, "
                  "a análise muda.",
        ))

    # --- fazer indicando tempo --------------------------------------------
    for achado in _RE_FAZER_TEMPO.finditer(frase):
        achados.append(AchadoConcordancia(
            configuracao="“fazer” indicando tempo decorrido",
            trecho=_trecho(frase, achado),
            veredito="erro",
            regra=(
                "Indicando tempo decorrido, o verbo fazer é impessoal e fica no "
                "singular: “faz dois anos”, “fazia dez dias”."
            ),
            teste="Pergunte “quem faz?”. Se não há resposta, o verbo é impessoal.",
            correcao=f"“{achado.group(1)}” → singular",
        ))

    # --- partícula "se" ----------------------------------------------------
    for achado in _RE_SE_INDETERMINACAO.finditer(frase):
        achados.append(AchadoConcordancia(
            configuracao="“se” índice de indeterminação do sujeito",
            trecho=_trecho(frase, achado),
            veredito="correto",
            regra=(
                "Com verbo transitivo indireto ou intransitivo, o “se” indetermina "
                "o sujeito e o verbo fica obrigatoriamente no singular: "
                "“precisa-se de professores”."
            ),
            teste="Existe preposição depois do verbo? Então o “se” não é "
                  "apassivador, e o verbo não vai ao plural.",
        ))

    for achado in _RE_SE_APASSIVADORA.finditer(frase):
        if _RE_SE_INDETERMINACAO.search(achado.group(0)):
            continue
        verbo = achado.group(1)
        sujeito = achado.group(3)
        no_plural = verbo.lower().endswith(("m", "ram", "rao"))
        achados.append(AchadoConcordancia(
            configuracao="“se” apassivador (voz passiva sintética)",
            trecho=_trecho(frase, achado),
            veredito="correto" if no_plural else "erro",
            regra=(
                "Com verbo transitivo direto, o “se” é apassivador e o termo "
                "seguinte é o SUJEITO: o verbo concorda com ele."
            ),
            teste=(
                f"Passe para a passiva analítica: “{sujeito} são "
                f"{verbo.lower()}dos/as”. Se a frase faz sentido assim, o verbo "
                "precisa ir ao plural."
            ),
            correcao="" if no_plural else f"“{verbo}-se” → verbo no plural",
        ))

    # --- "um dos que" ------------------------------------------------------
    for achado in _RE_UM_DOS_QUE.finditer(frase):
        achados.append(AchadoConcordancia(
            configuracao="“um dos que”",
            trecho=_trecho(frase, achado),
            veredito="atencao",
            regra=(
                "Em “um dos que”, o sujeito do verbo seguinte é o pronome "
                "relativo “que”, cujo antecedente é plural — daí o verbo no "
                "plural: “foi um dos que chegaram”."
            ),
            teste="Reordene: “dos que chegaram, ele foi um”. O plural fica claro.",
        ))

    return achados
