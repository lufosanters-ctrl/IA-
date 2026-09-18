"""Saida de terminal que funciona no Windows tambem.

Tres coisas quebram um programa em linha de comando no Windows e em nenhum
outro lugar:

1. **A pagina de codigo.** O console do Windows nao usa UTF-8 por padrao. Em
   portugues ele costuma vir em cp850 ou cp1252, onde `—`, `“`, `…`, `✓` e `✗`
   simplesmente nao existem. Imprimir um deles derruba o programa com
   `UnicodeEncodeError` — nao e erro de logica, e o console recusando o
   caractere.
2. **As cores.** As sequencias ANSI so funcionam com o processamento de
   terminal virtual ligado. Sem ele, em vez de texto verde aparece `←[32m`
   grudado no meio da frase.
3. **Saida redirecionada.** `python -m app.afericao > saida.txt` troca o
   console por um arquivo, e a codificacao muda junto.

Este modulo resolve os tres de uma vez: tenta subir o console para UTF-8,
descobre o que ele aceita e, para o que nao aceita, troca o simbolo por um
equivalente que qualquer terminal imprime.
"""

from __future__ import annotations

import os
import sys
from typing import Any, TextIO

# Equivalentes ASCII dos simbolos que a interface de linha de comando usa.
# A troca so acontece quando o console nao aceita o original.
EQUIVALENTES: dict[str, str] = {
    "—": "-", "–": "-", "―": "-",
    "“": '"', "”": '"', "‘": "'", "’": "'",
    "…": "...",
    "✓": "OK", "✗": "X", "✔": "OK", "✘": "X",
    "→": "->", "←": "<-", "↑": "^", "↓": "v",
    "█": "#", "▓": "#", "▒": "=", "░": "-", "·": ".",
    "•": "*", "≥": ">=", "≤": "<=", "≠": "!=",
    "∈": "em", "∩": "inter", "∪": "uniao", "∞": "inf",
    "π": "pi", "Δ": "Delta", "√": "raiz",
}


def _tentar_utf8(fluxo: TextIO) -> None:
    """Sobe o fluxo para UTF-8; nao dando, ao menos impede que ele estoure.

    `reconfigure` existe a partir do 3.7 e resolve o caso comum: o console do
    Windows ate aceita UTF-8, mas o Python so descobre isso se mandarmos.

    Quando nem isso da certo, o segundo passo importa tanto quanto: trocar o
    tratamento de erro para `replace` na propria codificacao do console. Sem
    isso, qualquer texto que NAO passe por `escrever` — a ajuda do argparse,
    um traceback, uma mensagem de biblioteca — ainda derrubaria o programa.
    Um acento perdido e melhor que um programa que nao abre.
    """
    reconfigurar = getattr(fluxo, "reconfigure", None)
    if reconfigurar is None:
        return
    try:
        reconfigurar(encoding="utf-8", errors="replace")
        return
    except (ValueError, OSError):
        pass
    try:
        reconfigurar(errors="replace")
    except (ValueError, OSError):
        # Fluxo que nao aceita troca nenhuma. O `suportado` detecta e a troca
        # por equivalentes cobre o que passa por `escrever`.
        pass


def preparar_saida() -> None:
    """Prepara stdout e stderr para texto em portugues."""
    for fluxo in (sys.stdout, sys.stderr):
        if fluxo is not None:
            _tentar_utf8(fluxo)


def codificacao_da_saida() -> str:
    return (getattr(sys.stdout, "encoding", None) or "ascii").lower()


def suportado(texto: str) -> bool:
    """O console consegue imprimir este texto sem estourar?"""
    codificacao = codificacao_da_saida()
    if codificacao.replace("-", "") in {"utf8", "utf8mb4"}:
        return True
    try:
        texto.encode(codificacao, errors="strict")
    except (UnicodeEncodeError, LookupError):
        return False
    return True


def adaptar(texto: str) -> str:
    """Troca o que o console nao aceita por um equivalente que ele aceita.

    Devolve o texto intacto quando tudo cabe — que e o caso no Windows
    Terminal, no PowerShell moderno e em qualquer terminal de Linux ou macOS.
    """
    if suportado(texto):
        return texto
    saida = texto
    for original, equivalente in EQUIVALENTES.items():
        if original in saida and not suportado(original):
            saida = saida.replace(original, equivalente)
    if suportado(saida):
        return saida
    # Sobrou algo fora do mapa: troca caractere a caractere, sem derrubar nada.
    codificacao = codificacao_da_saida()
    return saida.encode(codificacao, errors="replace").decode(codificacao, errors="replace")


def cores_disponiveis(fluxo: Any = None) -> bool:
    """Vale usar cor ANSI nesta saida?

    Nao vale quando a saida foi redirecionada para arquivo, quando a variavel
    NO_COLOR esta definida (convencao respeitada por toda ferramenta moderna),
    nem no console antigo do Windows, onde a sequencia de escape aparece como
    lixo no meio do texto.
    """
    fluxo = fluxo if fluxo is not None else sys.stdout
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    if not hasattr(fluxo, "isatty") or not fluxo.isatty():
        return False
    if os.name != "nt":
        return True
    # No Windows, a cor depende do terminal virtual. O Windows Terminal e o
    # PowerShell 7 anunciam-se; o console legado, nao.
    return bool(
        os.environ.get("WT_SESSION")
        or os.environ.get("TERM_PROGRAM")
        or os.environ.get("ANSICON")
        or "xterm" in os.environ.get("TERM", "")
        or _ligar_terminal_virtual()
    )


def _ligar_terminal_virtual() -> bool:
    """Liga o processamento ANSI no console do Windows, se der.

    O Windows 10 em diante sabe interpretar as sequencias de escape, mas o
    modo vem desligado para programas antigos. Ligar e uma chamada so.
    """
    if os.name != "nt":
        return False
    try:
        import ctypes

        kernel = ctypes.windll.kernel32                      # type: ignore[attr-defined]
        manipulador = kernel.GetStdHandle(-11)               # STD_OUTPUT_HANDLE
        modo = ctypes.c_uint32()
        if not kernel.GetConsoleMode(manipulador, ctypes.byref(modo)):
            return False
        # ENABLE_VIRTUAL_TERMINAL_PROCESSING
        return bool(kernel.SetConsoleMode(manipulador, modo.value | 0x0004))
    except Exception:
        return False


def escrever(texto: str = "", fluxo: TextIO | None = None) -> None:
    """`print` que nunca derruba o programa por causa da codificacao."""
    destino = fluxo if fluxo is not None else sys.stdout
    try:
        print(adaptar(texto), file=destino)
    except UnicodeEncodeError:
        # Ultimo recurso: ASCII puro. Melhor um acento perdido que um traceback.
        print(texto.encode("ascii", errors="replace").decode("ascii"), file=destino)


# --------------------------------------------------------------------------
# SQLite em pasta sincronizada
# --------------------------------------------------------------------------

_JA_AVISADO: set[str] = set()


def conferir_journal(conexao: Any, caminho: Any) -> str:
    """Aplica o WAL e avisa, uma vez, quando a pasta nao o permite.

    O `PRAGMA journal_mode` nao levanta erro quando falha: ele devolve o modo
    que conseguiu aplicar. Em pasta de rede ou sincronizada pelo OneDrive —
    que no Windows 11 e o destino padrao de "Documentos" — o WAL depende de um
    arquivo mapeado em memoria que o sincronizador atrapalha, e a aplicacao
    passa a rodar em modo DELETE sem ninguem saber. Saber disso e a explicacao
    de um "database is locked" que aparece do nada.
    """
    import logging

    linha = conexao.execute("PRAGMA journal_mode = WAL").fetchone()
    modo = str(linha[0] if linha else "").lower()
    chave = str(caminho)
    if modo != "wal" and chave not in _JA_AVISADO:
        _JA_AVISADO.add(chave)
        logging.getLogger("nucleo").warning(
            "o banco %s está em modo %s, não WAL. Isso costuma acontecer em "
            "pasta de rede ou sincronizada (OneDrive, Dropbox, Google Drive). "
            "Funciona, mas fica mais lento e mais sujeito a travas. Para "
            "evitar, guarde o projeto numa pasta local, por exemplo "
            "C:\\dev\\IA-, ou aponte CAMINHO_BANCO para fora da pasta "
            "sincronizada.",
            chave, modo or "desconhecido",
        )
    return modo
