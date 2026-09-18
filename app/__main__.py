"""Ponto de entrada: python -m app"""

from __future__ import annotations

import uvicorn

from .config import obter_config


def main() -> None:
    cfg = obter_config()
    print(f"\n  {cfg.nome_app} — http://{cfg.host}:{cfg.porta}\n")
    uvicorn.run(
        "app.main:app",
        host=cfg.host,
        port=cfg.porta,
        reload=cfg.recarregar,
        log_level="info",
    )


if __name__ == "__main__":
    main()
