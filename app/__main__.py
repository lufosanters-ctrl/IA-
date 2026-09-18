"""Ponto de entrada: python -m app"""

from __future__ import annotations

import uvicorn

from .config import obter_config
from .console import escrever, preparar_saida


def main() -> None:
    preparar_saida()
    cfg = obter_config()
    escrever(f"\n  {cfg.nome_app} — http://{cfg.host}:{cfg.porta}\n")
    uvicorn.run(
        "app.main:app",
        host=cfg.host,
        port=cfg.porta,
        reload=cfg.recarregar,
        log_level="info",
    )


if __name__ == "__main__":
    main()
