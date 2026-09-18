"""Cache em memoria com expiracao, usado para as chamadas as bases externas."""

from __future__ import annotations

import time
from collections import OrderedDict
from threading import Lock
from typing import Any


class CacheTTL:
    """Cache LRU simples com tempo de vida por item."""

    def __init__(self, ttl_segundos: int = 3600, max_itens: int = 512) -> None:
        self._ttl = ttl_segundos
        self._max = max_itens
        self._dados: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._trava = Lock()
        self.acertos = 0
        self.erros = 0

    def obter(self, chave: str) -> Any | None:
        with self._trava:
            item = self._dados.get(chave)
            if item is None:
                self.erros += 1
                return None
            expira_em, valor = item
            if expira_em < time.time():
                del self._dados[chave]
                self.erros += 1
                return None
            self._dados.move_to_end(chave)
            self.acertos += 1
            return valor

    def guardar(self, chave: str, valor: Any) -> None:
        with self._trava:
            self._dados[chave] = (time.time() + self._ttl, valor)
            self._dados.move_to_end(chave)
            while len(self._dados) > self._max:
                self._dados.popitem(last=False)

    def limpar(self) -> None:
        with self._trava:
            self._dados.clear()

    @property
    def estatisticas(self) -> dict[str, int]:
        return {"itens": len(self._dados), "acertos": self.acertos, "erros": self.erros}
