"""Conectores para bases de dados publicas da internet."""

from .base import Documento, FonteBase, ResultadoFonte
from .registro import FONTES, fonte_por_id, listar_fontes

__all__ = [
    "Documento",
    "FonteBase",
    "ResultadoFonte",
    "FONTES",
    "fonte_por_id",
    "listar_fontes",
]
