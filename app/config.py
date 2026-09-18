"""Configuracao central da aplicacao.

Todas as opcoes podem ser definidas por variaveis de ambiente ou por um
arquivo .env na raiz do projeto (veja .env.example).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

RAIZ = Path(__file__).resolve().parent.parent


class Configuracao(BaseSettings):
    """Parametros de execucao da plataforma."""

    model_config = SettingsConfigDict(
        env_file=str(RAIZ / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Identidade -----------------------------------------------------
    nome_app: str = "Nucleo"
    descricao_app: str = "IA de estudo que pesquisa bases de dados publicas da internet"

    # --- Servidor -------------------------------------------------------
    host: str = "127.0.0.1"
    porta: int = 8000
    recarregar: bool = False

    # --- Modelo de linguagem -------------------------------------------
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    modelo: str = Field(default="claude-sonnet-5", alias="NUCLEO_MODELO")
    modelo_max_tokens: int = 2600
    modelo_temperatura: float = 0.2

    # --- Pesquisa -------------------------------------------------------
    timeout_http: float = 20.0
    max_resultados_por_fonte: int = 6
    max_trechos_contexto: int = 14
    tamanho_trecho: int = 900
    sobreposicao_trecho: int = 150
    user_agent: str = (
        "Nucleo/1.0 (plataforma educacional; https://github.com/lufosanters-ctrl/IA-)"
    )

    # --- Cache e banco --------------------------------------------------
    cache_ttl_segundos: int = 60 * 60 * 6
    cache_max_itens: int = 512
    caminho_banco: Path = RAIZ / "data" / "nucleo.db"

    # --- Biblioteca local -----------------------------------------------
    # Pasta onde o estudante deixa os livros a serem indexados.
    diretorio_biblioteca: Path = RAIZ / "biblioteca"
    max_mb_por_livro: int = 200

    @property
    def tem_llm(self) -> bool:
        """Indica se ha chave de API configurada para sintese neural."""
        return bool(self.anthropic_api_key.strip())

    @property
    def diretorio_web(self) -> Path:
        return RAIZ / "web"


class ErroDeConfiguracao(RuntimeError):
    """Algo no .env impede a plataforma de subir."""


def _conferir_caminho(rotulo: str, variavel: str, caminho: Path) -> None:
    """Recusa caminho corrompido, dizendo onde arrumar.

    O caso real é do Windows. Um caminho tem barra invertida e espaços, e
    escrever `DIRETORIO_BIBLIOTECA="C:\\Users\\nome\\livros"` entre aspas
    duplas é o reflexo natural. Só que o leitor de .env interpreta sequências
    de escape dentro de aspas: `\n` de "\nome" vira uma QUEBRA DE LINHA, e o
    caminho chega aqui partido ao meio. O `mkdir` seguinte falha com um erro
    do sistema que não menciona o .env, e o servidor não sobe.
    """
    texto = str(caminho)
    if any(ord(c) < 32 for c in texto):
        raise ErroDeConfiguracao(
            f"{rotulo} tem caractere de controle: {texto!r}.\n\n"
            f"No arquivo .env, escreva {variavel} SEM aspas duplas:\n"
            f"    {variavel}=C:\\Users\\seu-nome\\livros\n"
            "ou com barras normais, que o Windows também aceita:\n"
            f"    {variavel}=C:/Users/seu-nome/livros\n\n"
            "Entre aspas duplas, o \\n de uma pasta como \\nome vira quebra "
            "de linha."
        )


@lru_cache(maxsize=1)
def obter_config() -> Configuracao:
    """Retorna a configuracao (carregada uma unica vez)."""
    cfg = Configuracao()
    _conferir_caminho("o caminho do banco", "CAMINHO_BANCO", cfg.caminho_banco)
    _conferir_caminho(
        "o diretório da biblioteca", "DIRETORIO_BIBLIOTECA", cfg.diretorio_biblioteca
    )
    cfg.caminho_banco.parent.mkdir(parents=True, exist_ok=True)
    cfg.diretorio_biblioteca.mkdir(parents=True, exist_ok=True)
    return cfg
