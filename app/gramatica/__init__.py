"""Motores deterministicos de gramatica da lingua portuguesa.

A ideia e a mesma do motor matematico: o que torna a resposta confiavel nao e
o texto afirmar que conferiu, e um verificador independente conferir. Aqui o
verificador e um conjunto de regras codificadas — regencia, crase, colocacao
pronominal e as armadilhas classicas de concordancia — que funciona sem
nenhum modelo de linguagem.
"""

from .analise import Achado, analisar_frase
from .colocacao import analisar_colocacao
from .concordancia import analisar_concordancia
from .crase import OcorrenciaCrase, analisar_crase
from .regencia import (
    REGENCIA_NOMINAL,
    REGENCIA_VERBAL,
    Sentido,
    consultar_nome,
    consultar_verbo,
    verbos_na_frase,
)

__all__ = [
    "Achado",
    "OcorrenciaCrase",
    "REGENCIA_NOMINAL",
    "REGENCIA_VERBAL",
    "Sentido",
    "analisar_colocacao",
    "analisar_concordancia",
    "analisar_crase",
    "analisar_frase",
    "consultar_nome",
    "consultar_verbo",
    "verbos_na_frase",
]
