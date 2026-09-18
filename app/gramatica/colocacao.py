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
    "que", "quando", "se", "porque", "embora", "conforme", "caso",
    "como", "enquanto", "segundo", "conquanto", "posto", "porquanto",
    "consoante", "conquanto", "malgrado", "contanto",
}

# Locucoes conjuntivas: a atracao esta na locucao inteira, nao na primeira
# palavra. "Portanto" e "pois" coordenam e NAO atraem o pronome.
LOCUCOES_ATRATIVAS = {
    ("assim", "que"), ("mesmo", "que"), ("desde", "que"), ("ainda", "que"),
    ("salvo", "se"), ("posto", "que"), ("ja", "que"), ("visto", "que"),
    ("por", "mais", "que"), ("sem", "que"), ("apesar", "de"),
    ("a", "medida", "que"), ("logo", "que"), ("depois", "que"),
    ("antes", "que"), ("cada", "vez", "que"), ("toda", "vez", "que"),
}

ATRATIVAS = (NEGACOES | ADVERBIOS | RELATIVOS | INDEFINIDOS
             | DEMONSTRATIVOS | CONJUNCOES_SUBORDINATIVAS)

# Futuro do presente e do pretérito: a desinência vem colada ao infinitivo
# inteiro (amar+ei, vender+ia), então o teste precisa ver as duas partes.
# Testar só "termina em -a com radical em -er" dava "considera" como futuro.
_FUTURO_ACENTUADO = (
    "arei", "erei", "irei", "arás", "erás", "irás", "ará", "erá", "irá",
    "aremos", "eremos", "iremos", "areis", "ereis", "ireis",
    "arão", "erão", "irão",
    "aria", "eria", "iria", "arias", "erias", "irias",
    "aríamos", "eríamos", "iríamos", "aríeis", "eríeis", "iríeis",
    "ariam", "eriam", "iriam",
)
# As mesmas formas sem acento, restritas às que continuam inequívocas.
_FUTURO_SEM_ACENTO = (
    "arei", "erei", "irei", "aremos", "eremos", "iremos",
    "arao", "erao", "irao", "aria", "eria", "iria",
    "ariam", "eriam", "iriam", "ariamos", "eriamos", "iriamos",
    "arias", "erias", "irias",
)
# Futuros irregulares: o infinitivo não aparece inteiro na forma conjugada.
_FUTUROS_IRREGULARES = {
    "farei", "farás", "fará", "faremos", "farão", "faria", "fariam",
    "direi", "dirás", "dirá", "diremos", "dirão", "diria", "diriam",
    "trarei", "trarás", "trará", "traremos", "trarão", "traria", "trariam",
    "porei", "porás", "porá", "poremos", "porão", "poria", "poriam",
    "serei", "será", "seremos", "serão", "seria", "seriam",
    "terei", "terá", "teremos", "terão", "teria", "teriam",
    "verei", "verá", "veremos", "verão", "veria", "veriam",
    "virei", "virá", "viremos", "virão", "viria", "viriam",
}

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

# Formas que só existem depois do verbo (alomorfes) ou que são homônimas de
# artigo/contração. Varrê-las como próclise produzia falso positivo em
# qualquer frase com "no", "na" ou "a".
SO_DEPOIS_DO_VERBO = {
    "o", "a", "os", "as", "lo", "la", "los", "las", "no", "na", "nas",
}

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
    bruto = (verbo or "").lower().strip(" .,;:!?")
    alvo = normalizar(bruto)
    if len(alvo) < 4:
        return False
    if bruto in _FUTUROS_IRREGULARES:
        return True
    if alvo in {normalizar(f) for f in _FUTUROS_IRREGULARES}:
        return True
    if bruto.endswith(_FUTURO_ACENTUADO):
        return True
    return alvo.endswith(_FUTURO_SEM_ACENTO)


_RE_FRONTEIRA = re.compile(r"[,;:.!?()\u2014\u2013]")


def _atrativa_antes(palavras: list[str], indice_verbo: int,
                    marcas: list[Any] | None = None,
                    frase: str = "") -> str:
    """A palavra atrativa que antecede o verbo, dentro da MESMA oração.

    A busca para em vírgula, ponto-e-vírgula ou travessão: em “Quando cheguei,
    sentei-me à mesa”, o “Quando” pertence à oração anterior e não atrai o
    pronome da seguinte.
    """
    for passo in range(1, 4):
        posicao = indice_verbo - passo
        if posicao < 0:
            break
        if marcas and frase:
            fim = marcas[posicao].end()
            inicio = marcas[posicao + 1].start() if posicao + 1 < len(marcas) else fim
            if _RE_FRONTEIRA.search(frase[fim:inicio]):
                break
        candidata = normalizar(palavras[posicao])
        # Locução conjuntiva: a atração está no conjunto, não na primeira
        # palavra. "Assim" sozinho não atrai; "assim que" atrai.
        for tamanho in (3, 2):
            trecho = tuple(normalizar(p) for p in palavras[posicao: posicao + tamanho])
            if trecho in LOCUCOES_ATRATIVAS and posicao + tamanho <= indice_verbo:
                return " ".join(palavras[posicao: posicao + tamanho])
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

    marcas = list(_RE_PALAVRA.finditer(frase))
    palavras = [m.group(0) for m in marcas]
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
        atrativa = _atrativa_antes(palavras, indice, marcas, frase)
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
        atrativa = _atrativa_antes(palavras, indice, marcas, frase)
        correta, regra, explicacao = _posicao_exigida(atrativa, verbo, indice == 0)
        ocorrencias.append(OcorrenciaColocacao(
            pronome=pronome, verbo=verbo, posicao_usada=ENCLISE,
            posicao_correta=correta, correto=correta == ENCLISE,
            regra=regra, explicacao=explicacao, atrativa=atrativa,
        ))

    # --- próclise: pronome antes do verbo ----------------------------------
    for indice, palavra in enumerate(palavras[:-1]):
        alvo = normalizar(palavra)
        if alvo not in PRONOMES_ATONOS or alvo in SO_DEPOIS_DO_VERBO:
            # Artigos, contrações e alomorfes enclíticos: "no", "la" e "o"
            # só são pronome átono colados DEPOIS do verbo ("põe-no",
            # "fazê-la"). Soltos na frase são artigo ou preposição.
            continue
        if f"-{alvo}" in frase.lower():
            continue  # já contabilizado como ênclise ou mesóclise
        verbo = palavras[indice + 1]
        if normalizar(verbo) in _NAO_SAO_VERBO:
            continue  # o que vem depois não é verbo: não há próclise aqui
        atrativa = _atrativa_antes(palavras, indice, marcas, frase)
        correta, regra, explicacao = _posicao_exigida(atrativa, verbo, indice == 0)
        ocorrencias.append(OcorrenciaColocacao(
            pronome=palavra, verbo=verbo, posicao_usada=PROCLISE,
            posicao_correta=correta, correto=correta == PROCLISE,
            regra=regra, explicacao=explicacao, atrativa=atrativa,
        ))

    return ocorrencias
