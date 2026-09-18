"""Gramatica inglesa avaliada em cinco dimensoes, nao apenas 'certo ou errado'."""

from .dimensoes import DIMENSOES, Avaliacao, avaliar_estrutura
from .contrastes import CONTRASTES, Contraste, contrastes_relevantes

__all__ = [
    "Avaliacao",
    "CONTRASTES",
    "Contraste",
    "DIMENSOES",
    "avaliar_estrutura",
    "contrastes_relevantes",
]
