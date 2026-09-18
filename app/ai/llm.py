"""Acesso ao modelo de linguagem, com degradacao elegante.

Se houver ANTHROPIC_API_KEY, a plataforma usa o modelo para sintetizar
respostas, gerar flashcards e montar planos de estudo. Sem chave, tudo
continua funcionando em "modo extrativo": as respostas sao construidas a
partir dos trechos recuperados das bases, sem invencao de conteudo.
"""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from typing import Any

from ..config import obter_config

_RE_JSON = re.compile(r"(\{.*\}|\[.*\])", re.DOTALL)


class ErroModelo(RuntimeError):
    """Falha ao consultar o modelo de linguagem."""


class MotorIA:
    """Fachada fina sobre a API da Anthropic."""

    def __init__(self) -> None:
        self._cfg = obter_config()
        self._cliente: Any | None = None

    @property
    def disponivel(self) -> bool:
        return self._cfg.tem_llm

    @property
    def modelo(self) -> str:
        return self._cfg.modelo

    def _obter_cliente(self) -> Any:
        if self._cliente is None:
            try:
                from anthropic import AsyncAnthropic
            except ImportError as exc:  # pragma: no cover
                raise ErroModelo("pacote 'anthropic' nao instalado") from exc
            self._cliente = AsyncAnthropic(api_key=self._cfg.anthropic_api_key)
        return self._cliente

    async def responder(
        self,
        sistema: str,
        prompt: str,
        max_tokens: int | None = None,
        temperatura: float | None = None,
    ) -> str:
        """Pede uma resposta completa ao modelo."""
        if not self.disponivel:
            raise ErroModelo("nenhuma chave de API configurada")
        cliente = self._obter_cliente()
        try:
            resposta = await cliente.messages.create(
                model=self._cfg.modelo,
                max_tokens=max_tokens or self._cfg.modelo_max_tokens,
                temperature=(
                    self._cfg.modelo_temperatura if temperatura is None else temperatura
                ),
                system=sistema,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as exc:  # rede, cota, autenticacao
            raise ErroModelo(str(exc)) from exc
        return "".join(
            bloco.text for bloco in resposta.content if getattr(bloco, "type", "") == "text"
        ).strip()

    async def transmitir(
        self,
        sistema: str,
        prompt: str,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        """Gera a resposta em pedacos, para exibicao progressiva na interface."""
        if not self.disponivel:
            raise ErroModelo("nenhuma chave de API configurada")
        cliente = self._obter_cliente()
        try:
            async with cliente.messages.stream(
                model=self._cfg.modelo,
                max_tokens=max_tokens or self._cfg.modelo_max_tokens,
                temperature=self._cfg.modelo_temperatura,
                system=sistema,
                messages=[{"role": "user", "content": prompt}],
            ) as fluxo:
                async for texto in fluxo.text_stream:
                    yield texto
        except Exception as exc:
            raise ErroModelo(str(exc)) from exc

    async def responder_json(
        self,
        sistema: str,
        prompt: str,
        max_tokens: int | None = None,
    ) -> Any:
        """Resposta do modelo interpretada como JSON, tolerante a texto extra."""
        bruto = await self.responder(
            sistema + "\n\nResponda SOMENTE com JSON valido, sem cercas de codigo.",
            prompt,
            max_tokens=max_tokens,
        )
        return extrair_json(bruto)


def extrair_json(bruto: str) -> Any:
    """Extrai o primeiro objeto/array JSON de um texto."""
    texto = (bruto or "").strip()
    if texto.startswith("```"):
        texto = re.sub(r"^```[a-zA-Z]*\n?", "", texto)
        texto = re.sub(r"\n?```$", "", texto).strip()
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        pass
    achado = _RE_JSON.search(texto)
    if not achado:
        raise ErroModelo("o modelo nao devolveu JSON interpretavel")
    try:
        return json.loads(achado.group(1))
    except json.JSONDecodeError as exc:
        raise ErroModelo("JSON malformado na resposta do modelo") from exc


_motor: MotorIA | None = None


def obter_motor() -> MotorIA:
    """Instancia unica do motor de IA."""
    global _motor
    if _motor is None:
        _motor = MotorIA()
    return _motor
