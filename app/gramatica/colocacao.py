"""Colocacao pronominal: proclise, mesoclise e enclise.

Este e um dos poucos topicos de sintaxe que se resolvem por um algoritmo quase
fechado:

    ha palavra atrativa antes do verbo?  -> PROCLISE (obrigatoria)
    nao ha, e o verbo esta no futuro?    -> MESOCLISE
    nao ha, e o verbo nao esta no futuro -> ENCLISE

O trabalho real e reconhecer as palavras atrativas, que sao de classes
fechadas: negacao, adverbio, pronome relativo, indefinido, demonstrativo e
conjuncao subordinativa.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from ..texto import normalizar

PRONOMES_ATONOS = {
    "me", "te", "se", "o", "a", "lhe", "nos", "vos", "os", "as", "lhes",
    "lo", "la", "los", "las", "no", "na", "nos", "nas",
}

# --------------------------------------------------------------------------
# Palavras atrativas: exigem proclise
# --------------------------------------------------------------------------

NEGACOES = {"nao", "nunca", "jamais", "nada", "ninguem", "nenhum", "nenhuma",
            "nem", "nadinha"}

ADVERBIOS = {
    "sempre", "talvez", "agora", "ja", "ainda", "aqui", "ali", "la", "ca",
    "bem", "mal", "muito", "pouco", "so", "somente", "apenas", "tambem",
    "antes", "depois", "logo", "hoje", "ontem", "amanha", "certamente",
    "possivelmente", "provavelmente", "quica", "porventura",
}

RELATIVOS = {"que", "quem", "qual", "quais", "cujo", "cuja", "cujos", "cujas",
             "onde", "quanto", "quanta", "quantos", "quantas"}

INDEFINIDOS = {"alguem", "ninguem", "tudo", "nada", "algo", "todos", "todas",
               "alguns", "algumas", "outro", "outra", "qualquer", "poucos",
               "muitos", "varios", "ambos"}

DEMONSTRATIVOS = {"isto", "isso", "aquilo", "este", "esta", "esse", "essa",
                  "aquele", "aquela", "estes", "estas", "esses", "essas",
                  "aqueles", "aquelas"}

CONJUNCOES_SUBORDINATIVAS = {
    "que", "quando", "se", "porque", "pois", "embora", "conforme", "caso",
    "como", "enquanto", "segundo", "salvo", "conquanto", "ainda", "posto",
    "mesmo", "desde", "assim", "portanto", "porquanto",
}

ATRATIVAS = (NEGACOES | ADVERBIOS | RELATIVOS | INDEFINIDOS
             | DEMONSTRATIVOS | CONJUNCOES_SUBORDINATIVAS)

_TERMINACOES_FUTURO_PRESENTE = ("ei", "as", "a", "emos", "eis", "ao")
_TERMINACOES_FUTURO_PRETERITO = ("ia", "ias", "iamos", "ieis", "iam")

_RE_MESOCLISE = re.compile(
    r"\b([A-Za-zÀ-ÿ]+)-(me|te|se|o|a|lhe|nos|vos|os|as|lhes|lo|la|los|las)"
    r"-([a-zà-ÿ]{1,6})\b", re.IGNORECASE
)
_RE_ENCLISE = re.compile(
    r"\b([A-Za-zÀ-ÿ]+)-(me|te|se|o|a|lhe|nos|vos|os|as|lhes|lo|la|los|las|"
    r"no|na|nos|nas)\b", re.IGNORECASE
)
# Sem o hífen: "disseram-me" precisa virar dois tokens, senão a busca pela
# palavra atrativa não encontra o verbo e a análise cai no caso errado.
_RE_PALAVRA = re.compile(r"[A-Za-zÀ-ÿ]+")

PROCLISE, MESOCLISE, ENCLISE = "próclise", "mesóclise", "ênclise"

# Se a palavra seguinte é determinante ou preposição, o suposto pronome átono
# não está antes de um verbo — é conjunção ou artigo. "Assinale se a crase…"
# não tem próclise nenhuma.
_NAO_SAO_VERBO = {
    "o", "a", "os", "as", "um", "uma", "uns", "umas", "de", "do", "da", "dos",
    "das", "em", "no", "na", "nos", "nas", "por", "para", "com", "sem", "sob",
    "sobre", "entre", "que", "qual", "quais", "este", "esta", "esse", "essa",
    "aquele", "aquela", "isto", "isso", "aquilo", "seu", "sua", "meu", "minha",
    "muito", "pouco", "todo", "toda", "mais", "menos", "e", "ou", "mas",
}


@dataclass(slots=True)
class OcorrenciaColocacao:
    """Um pronome átono posicionado na frase, com o veredito da regra."""

    pronome: str
    verbo: str
    posicao_usada: str
    posicao_correta: str
    correto: bool
    regra: str
    explicacao: str
    atrativa: str = ""

    def para_dict(self) -> dict[str, Any]:
        return {
            "pronome": self.pronome,
            "verbo": self.verbo,
            "posicao_usada": self.posicao_usada,
            "posicao_correta": self.posicao_correta,
            "correto": self.correto,
            "regra": self.regra,
            "explicacao": self.explicacao,
            "atrativa": self.atrativa,
        }


def _e_futuro(verbo: str) -> bool:
    """O verbo está no futuro do presente ou do pretérito?"""
    alvo = normalizar(verbo)
    if len(alvo) < 4:
        return False
    if alvo.endswith(_TERMINACOES_FUTURO_PRETERITO) and alvo[:-2].endswith(("ar", "er", "ir")):
        return True
    for terminacao in _TERMINACOES_FUTURO_PRESENTE:
        if alvo.endswith(terminacao):
            radical = alvo[: -len(terminacao)] if terminacao else alvo
            if radical.endswith(("ar", "er", "ir")):
                return True
    return False


def _atrativa_antes(palavras: list[str], indice_verbo: int) -> str:
    """Devolve a palavra atrativa que antecede o verbo, se houver."""
    for passo in range(1, 4):
        posicao = indice_verbo - passo
        if posicao < 0:
            break
        candidata = normalizar(palavras[posicao])
        if candidata in ATRATIVAS:
            return palavras[posicao]
    return ""


def _posicao_exigida(atrativa: str, verbo: str, inicio_de_frase: bool) -> tuple[str, str, str]:
    """Aplica o algoritmo e devolve (posição, regra, explicação)."""
    if atrativa:
        return (
            PROCLISE,
            "palavra atrativa antes do verbo",
            f"“{atrativa}” é palavra atrativa (negação, advérbio, pronome "
            "relativo/indefinido/demonstrativo ou conjunção subordinativa) e "
            "puxa o pronome para antes do verbo.",
        )
    if _e_futuro(verbo):
        return (
            MESOCLISE,
            "futuro sem palavra atrativa",
            f"“{verbo}” está no futuro e não há palavra atrativa, então o pronome "
            "vai para o meio do verbo. Ênclise com futuro é proibida na "
            "norma-padrão.",
        )
    if inicio_de_frase:
        return (
            ENCLISE,
            "início de período",
            "Na norma-padrão não se inicia período com pronome átono, então o "
            "pronome fica depois do verbo.",
        )
    return (
        ENCLISE,
        "ausência de fator de próclise",
        "Sem palavra atrativa e sem verbo no futuro, a colocação natural na "
        "norma-padrão é depois do verbo.",
    )


def analisar_colocacao(frase: str) -> list[OcorrenciaColocacao]:
    """Analisa a posição de cada pronome átono da frase."""
    if not frase or not frase.strip():
        return []

    palavras = _RE_PALAVRA.findall(frase)
    if not palavras:
        return []
    ocorrencias: list[OcorrenciaColocacao] = []
    ja_visto: set[str] = set()

    # --- mesóclise: verbo-pronome-desinência --------------------------------
    for achado in _RE_MESOCLISE.finditer(frase):
        radical, pronome, desinencia = achado.groups()
        verbo = f"{radical}{desinencia}"
        indice = next((i for i, p in enumerate(palavras)
                       if normalizar(p).startswith(normalizar(radical))), 0)
        atrativa = _atrativa_antes(palavras, indice)
        correta, regra, explicacao = _posicao_exigida(atrativa, verbo, indice == 0)
        ja_visto.add(achado.group(0).lower())
        ocorrencias.append(OcorrenciaColocacao(
            pronome=pronome, verbo=verbo, posicao_usada=MESOCLISE,
            posicao_correta=correta, correto=correta == MESOCLISE,
            regra=regra, explicacao=explicacao, atrativa=atrativa,
        ))

    # --- ênclise: verbo-pronome --------------------------------------------
    for achado in _RE_ENCLISE.finditer(frase):
        if any(achado.group(0).lower() in visto for visto in ja_visto):
            continue
        verbo, pronome = achado.groups()
        indice = next((i for i, p in enumerate(palavras)
                       if normalizar(p) == normalizar(verbo)), 0)
        atrativa = _atrativa_antes(palavras, indice)
        correta, regra, explicacao = _posicao_exigida(atrativa, verbo, indice == 0)
        ocorrencias.append(OcorrenciaColocacao(
            pronome=pronome, verbo=verbo, posicao_usada=ENCLISE,
            posicao_correta=correta, correto=correta == ENCLISE,
            regra=regra, explicacao=explicacao, atrativa=atrativa,
        ))

    # --- próclise: pronome antes do verbo ----------------------------------
    for indice, palavra in enumerate(palavras[:-1]):
        alvo = normalizar(palavra)
        if alvo not in PRONOMES_ATONOS or alvo in {"o", "a", "os", "as"}:
            # Artigos e pronomes homônimos exigiriam análise sintática completa.
            continue
        if f"-{alvo}" in frase.lower():
            continue  # já contabilizado como ênclise ou mesóclise
        verbo = palavras[indice + 1]
        if normalizar(verbo) in _NAO_SAO_VERBO:
            continue  # o que vem depois não é verbo: não há próclise aqui
        atrativa = _atrativa_antes(palavras, indice)
        correta, regra, explicacao = _posicao_exigida(atrativa, verbo, indice == 0)
        ocorrencias.append(OcorrenciaColocacao(
            pronome=palavra, verbo=verbo, posicao_usada=PROCLISE,
            posicao_correta=correta, correto=correta == PROCLISE,
            regra=regra, explicacao=explicacao, atrativa=atrativa,
        ))

    return ocorrencias
