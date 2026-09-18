"""Biblioteca local: indexa os livros do estudante e os torna pesquisaveis.

Os livros ficam em `biblioteca/` e o indice em `data/biblioteca.db`, um SQLite
com FTS5 (busca textual nativa, com ranqueamento BM25 proprio do SQLite e
tokenizador que ignora acentos — essencial para portugues).

Nada e enviado para fora: o livro e seu, o indice tambem.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .config import obter_config
from .livros import ErroExtracao, extrair, impressao_digital
from .texto import dividir_em_trechos, normalizar, tokenizar, truncar
from .console import conferir_journal

log = logging.getLogger("nucleo.biblioteca")

ESQUEMA = """
CREATE TABLE IF NOT EXISTS livros (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    titulo       TEXT    NOT NULL,
    autores      TEXT    NOT NULL DEFAULT '',
    area         TEXT    NOT NULL DEFAULT '',
    idioma       TEXT    NOT NULL DEFAULT '',
    arquivo      TEXT    NOT NULL,
    impressao    TEXT    NOT NULL UNIQUE,
    formato      TEXT    NOT NULL DEFAULT '',
    paginas      INTEGER NOT NULL DEFAULT 0,
    palavras     INTEGER NOT NULL DEFAULT 0,
    origem       TEXT    NOT NULL DEFAULT 'local',
    licenca      TEXT    NOT NULL DEFAULT '',
    url          TEXT    NOT NULL DEFAULT '',
    adicionado_em TEXT   NOT NULL
);

CREATE TABLE IF NOT EXISTS trechos (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    livro_id  INTEGER NOT NULL REFERENCES livros(id) ON DELETE CASCADE,
    ordem     INTEGER NOT NULL,
    pagina    INTEGER NOT NULL DEFAULT 0,
    capitulo  TEXT    NOT NULL DEFAULT '',
    texto     TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_trechos_livro ON trechos(livro_id);

CREATE VIRTUAL TABLE IF NOT EXISTS trechos_fts USING fts5(
    texto,
    capitulo,
    content='trechos',
    content_rowid='id',
    tokenize="unicode61 remove_diacritics 2"
);

CREATE TRIGGER IF NOT EXISTS trechos_ai AFTER INSERT ON trechos BEGIN
    INSERT INTO trechos_fts(rowid, texto, capitulo)
    VALUES (new.id, new.texto, new.capitulo);
END;

CREATE TRIGGER IF NOT EXISTS trechos_ad AFTER DELETE ON trechos BEGIN
    INSERT INTO trechos_fts(trechos_fts, rowid, texto, capitulo)
    VALUES ('delete', old.id, old.texto, old.capitulo);
END;
"""

_esquema_pronto = False


def caminho_indice() -> Path:
    return obter_config().caminho_banco.with_name("biblioteca.db")


def diretorio_livros() -> Path:
    """Pasta onde os livros ficam guardados (configurável)."""
    destino = obter_config().diretorio_biblioteca
    destino.mkdir(parents=True, exist_ok=True)
    return destino


@contextmanager
def conectar() -> Iterator[sqlite3.Connection]:
    """Conexao com o indice, criando o esquema quando necessario."""
    global _esquema_pronto
    caminho = caminho_indice()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    if not caminho.exists():
        _esquema_pronto = False

    conexao = sqlite3.connect(caminho, timeout=20)
    conexao.row_factory = sqlite3.Row
    conexao.execute("PRAGMA foreign_keys = ON")
    # O WAL precisa de um arquivo -shm mapeado em memória na mesma pasta.
    # Em pasta de rede, ou sincronizada pelo OneDrive — que no Windows 11 é o
    # destino padrão de "Documentos" —, o SQLite não consegue e cai para
    # outro modo SEM levantar erro: ele devolve o modo que conseguiu aplicar.
    # Ler o retorno é a única forma de saber, e vale avisar, porque é a
    # explicação de um "database is locked" que aparece do nada.
    conferir_journal(conexao, caminho)
    try:
        if not _esquema_pronto:
            conexao.executescript(ESQUEMA)
            _esquema_pronto = True
        yield conexao
        conexao.commit()
    except Exception:
        conexao.rollback()
        raise
    finally:
        conexao.close()


def iniciar() -> None:
    global _esquema_pronto
    _esquema_pronto = False
    with conectar():
        pass


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --------------------------------------------------------------------------
# Indexacao
# --------------------------------------------------------------------------

@dataclass(slots=True)
class ResultadoIngestao:
    """O que aconteceu ao tentar indexar um arquivo."""

    arquivo: str
    titulo: str = ""
    livro_id: int | None = None
    trechos: int = 0
    estado: str = "indexado"   # indexado | duplicado | erro
    detalhe: str = ""

    def para_dict(self) -> dict[str, Any]:
        return {
            "arquivo": self.arquivo,
            "titulo": self.titulo,
            "livro_id": self.livro_id,
            "trechos": self.trechos,
            "estado": self.estado,
            "detalhe": self.detalhe,
        }


def indexar(
    caminho: Path,
    area: str = "",
    origem: str = "local",
    licenca: str = "",
    url: str = "",
) -> ResultadoIngestao:
    """Extrai, fragmenta e indexa um livro. Reindexar o mesmo arquivo e no-op."""
    caminho = Path(caminho)
    resultado = ResultadoIngestao(arquivo=caminho.name)

    try:
        digital = impressao_digital(caminho)
    except OSError as exc:
        resultado.estado, resultado.detalhe = "erro", f"nao consegui ler: {exc.strerror}"
        return resultado

    with conectar() as conexao:
        ja_existe = conexao.execute(
            "SELECT id, titulo FROM livros WHERE impressao = ?", (digital,)
        ).fetchone()
    if ja_existe:
        resultado.estado = "duplicado"
        resultado.livro_id = int(ja_existe["id"])
        resultado.titulo = ja_existe["titulo"]
        resultado.detalhe = "este livro ja esta na biblioteca"
        return resultado

    try:
        livro = extrair(caminho)
    except ErroExtracao as exc:
        resultado.estado, resultado.detalhe = "erro", str(exc)
        return resultado

    cfg = obter_config()
    resultado.titulo = livro.titulo

    with conectar() as conexao:
        cursor = conexao.execute(
            """
            INSERT INTO livros (titulo, autores, area, idioma, arquivo, impressao,
                                formato, paginas, palavras, origem, licenca, url,
                                adicionado_em)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                livro.titulo,
                ", ".join(livro.autores[:6]),
                area,
                livro.idioma,
                str(caminho),
                digital,
                livro.formato,
                len(livro.paginas),
                livro.palavras,
                origem,
                licenca,
                url,
                _agora(),
            ),
        )
        livro_id = int(cursor.lastrowid)

        ordem = 0
        lote: list[tuple[Any, ...]] = []
        for pagina in livro.paginas:
            for bloco in dividir_em_trechos(
                pagina.texto, cfg.tamanho_trecho, cfg.sobreposicao_trecho
            ):
                ordem += 1
                lote.append((livro_id, ordem, pagina.numero, pagina.capitulo, bloco))
        conexao.executemany(
            "INSERT INTO trechos (livro_id, ordem, pagina, capitulo, texto) "
            "VALUES (?, ?, ?, ?, ?)",
            lote,
        )

    resultado.livro_id = livro_id
    resultado.trechos = ordem
    if ordem == 0:
        remover_livro(livro_id)
        resultado.estado, resultado.detalhe = "erro", "nenhum trecho indexavel"
    return resultado


# Teto de uma varredura. Sem ele, uma pasta com milhares de arquivos fazia a
# requisicao rodar por minutos sem resposta nem forma de acompanhar.
MAX_ARQUIVOS_POR_VARREDURA = 500


def indexar_pasta(pasta: Path | None = None, area: str = "",
                  maximo: int = MAX_ARQUIVOS_POR_VARREDURA) -> list[ResultadoIngestao]:
    """Indexa os livros de uma pasta (por padrao, `biblioteca/`)."""
    from .livros import FORMATOS

    pasta = Path(pasta) if pasta else diretorio_livros()
    arquivos = sorted(
        caminho for caminho in pasta.rglob("*")
        if caminho.is_file() and caminho.suffix.lower() in FORMATOS
        and not caminho.name.startswith(".")
    )
    resultados = [indexar(caminho, area=area) for caminho in arquivos[:maximo]]
    if len(arquivos) > maximo:
        restantes = len(arquivos) - maximo
        log.info("varredura limitada a %d arquivos; %d ficaram de fora", maximo, restantes)
        resultados.append(ResultadoIngestao(
            arquivo=f"(+{restantes} arquivos)", titulo="", estado="ignorado",
            detalhe=(
                f"a varredura para em {maximo} arquivos por vez. "
                "Rode de novo para continuar de onde parou."
            ),
        ))
    return resultados


def remover_livro(livro_id: int) -> bool:
    with conectar() as conexao:
        cursor = conexao.execute("DELETE FROM livros WHERE id = ?", (livro_id,))
        return cursor.rowcount > 0


def listar_livros() -> list[dict[str, Any]]:
    with conectar() as conexao:
        linhas = conexao.execute(
            """
            SELECT l.*, COUNT(t.id) AS trechos
              FROM livros l LEFT JOIN trechos t ON t.livro_id = l.id
             GROUP BY l.id
             ORDER BY l.adicionado_em DESC
            """
        ).fetchall()
    return [dict(linha) for linha in linhas]


def estatisticas() -> dict[str, Any]:
    with conectar() as conexao:
        livros = conexao.execute("SELECT COUNT(*) AS n FROM livros").fetchone()["n"]
        trechos = conexao.execute("SELECT COUNT(*) AS n FROM trechos").fetchone()["n"]
        palavras = conexao.execute(
            "SELECT COALESCE(SUM(palavras), 0) AS n FROM livros"
        ).fetchone()["n"]
    return {"livros": livros, "trechos": trechos, "palavras": palavras}


# --------------------------------------------------------------------------
# Busca
# --------------------------------------------------------------------------

_RE_SEGURO = re.compile(r"[^0-9a-zA-ZÀ-ÿ]+")


def montar_expressao(consulta: str) -> str:
    """Traduz a pergunta do usuario para a sintaxe do FTS5, com seguranca.

    Toda pontuacao vira separador, cada termo e citado (impede que `AND`,
    `NEAR` ou aspas soltas do usuario virem operador) e o conjunto e unido
    por OR, para que uma pergunta longa ainda encontre algo.
    """
    termos = [t for t in _RE_SEGURO.split(consulta) if len(t) > 1]
    # Calcular o conjunto UMA vez: dentro da comprehension, `tokenizar` rodava
    # de novo para cada termo e a montagem virava O(n2).
    significativos = {normalizar(x) for x in tokenizar(consulta)}
    uteis = [t for t in termos if normalizar(t) in significativos]
    escolhidos = uteis or termos
    if not escolhidos:
        return ""
    partes = [f'"{t}"' for t in escolhidos[:12]]
    expressao = " OR ".join(partes)
    if len(escolhidos) > 1:
        # A frase inteira, quando aparece, e o sinal mais forte.
        frase = " ".join(escolhidos[:8])
        expressao = f'"{frase}" OR {expressao}'
    return expressao


def buscar(consulta: str, limite: int = 8, livro_id: int | None = None) -> list[dict[str, Any]]:
    """Busca trechos nos livros indexados, ordenados pelo BM25 do FTS5."""
    expressao = montar_expressao(consulta)
    if not expressao:
        return []

    sql = """
        SELECT t.id, t.pagina, t.capitulo, t.texto, t.ordem,
               l.id AS livro_id, l.titulo, l.autores, l.arquivo, l.area,
               l.origem, l.url, l.licenca, l.formato,
               bm25(trechos_fts, 4.0, 1.0) AS pontuacao
          FROM trechos_fts
          JOIN trechos t ON t.id = trechos_fts.rowid
          JOIN livros  l ON l.id = t.livro_id
         WHERE trechos_fts MATCH ?
    """
    parametros: list[Any] = [expressao]
    if livro_id is not None:
        sql += " AND l.id = ?"
        parametros.append(livro_id)
    sql += " ORDER BY pontuacao LIMIT ?"
    parametros.append(limite)

    try:
        with conectar() as conexao:
            linhas = conexao.execute(sql, parametros).fetchall()
    except sqlite3.OperationalError as erro:
        # Expressao que o FTS5 recusou: devolver vazio e melhor que quebrar a
        # busca. Mas "database is locked" e "no such table" tambem caem aqui,
        # e engolir isso em silencio faz a biblioteca do estudante parecer
        # vazia sem nenhum sinal do que houve.
        motivo = str(erro).lower()
        if "syntax error" in motivo or "fts5" in motivo or "malformed match" in motivo:
            log.debug("busca recusada pelo FTS5: %s", erro)
        else:
            log.error("falha operacional na busca da biblioteca: %s", erro)
        return []
    return [dict(linha) for linha in linhas]


def contexto_do_trecho(trecho_id: int, janela: int = 1) -> str:
    """Texto do trecho junto com os vizinhos, para leitura em contexto."""
    with conectar() as conexao:
        alvo = conexao.execute(
            "SELECT livro_id, ordem FROM trechos WHERE id = ?", (trecho_id,)
        ).fetchone()
        if alvo is None:
            return ""
        linhas = conexao.execute(
            "SELECT texto FROM trechos WHERE livro_id = ? AND ordem BETWEEN ? AND ? "
            "ORDER BY ordem",
            (alvo["livro_id"], alvo["ordem"] - janela, alvo["ordem"] + janela),
        ).fetchall()
    return " ".join(linha["texto"] for linha in linhas)


def resumo_do_livro(livro_id: int, limite: int = 600) -> str:
    """Primeiras linhas do livro, usadas como descricao na interface."""
    with conectar() as conexao:
        linha = conexao.execute(
            "SELECT texto FROM trechos WHERE livro_id = ? ORDER BY ordem LIMIT 1",
            (livro_id,),
        ).fetchone()
    return truncar(linha["texto"], limite) if linha else ""
