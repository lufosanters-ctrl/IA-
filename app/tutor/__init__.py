"""Tutoria adaptativa: escada de ajuda, diagnostico do primeiro erro e fading."""

from .escada import DEGRAUS, Degrau, degrau, proximo_degrau
from .sessao import (
    Sessao,
    Tentativa,
    abrir_sessao,
    iniciar_banco_tutor,
    listar_sessoes,
    obter_sessao,
    padroes_de_erro,
    registrar_tentativa,
    subir_degrau,
)

__all__ = [
    "DEGRAUS",
    "Degrau",
    "Sessao",
    "Tentativa",
    "abrir_sessao",
    "degrau",
    "iniciar_banco_tutor",
    "listar_sessoes",
    "obter_sessao",
    "padroes_de_erro",
    "proximo_degrau",
    "registrar_tentativa",
    "subir_degrau",
]
