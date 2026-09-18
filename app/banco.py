"""Persistencia local em SQLite: historico, biblioteca e revisao espacada.

Nada sai da maquina do estudante: o arquivo fica em data/nucleo.db.
A revisao espacada usa o algoritmo SM-2 (o mesmo do Anki/SuperMemo).
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterator

from .config import obter_config

ESQUEMA = """
CREATE TABLE IF NOT EXISTS pesquisas (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    pergunta    TEXT    NOT NULL,
    resposta    TEXT    NOT NULL,
    area        TEXT    NOT NULL DEFAULT '',
    modo        TEXT    NOT NULL DEFAULT '',
    citacoes    TEXT    NOT NULL DEFAULT '[]',
    criada_em   TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS baralhos (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    nome        TEXT    NOT NULL UNIQUE,
    descricao   TEXT    NOT NULL DEFAULT '',
    criado_em   TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS cartoes (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    baralho_id    INTEGER NOT NULL REFERENCES baralhos(id) ON DELETE CASCADE,
    frente        TEXT    NOT NULL,
    verso         TEXT    NOT NULL,
    fonte_url     TEXT    NOT NULL DEFAULT '',
    fonte_titulo  TEXT    NOT NULL DEFAULT '',
    dificuldade   TEXT    NOT NULL DEFAULT 'media',
    facilidade    REAL    NOT NULL DEFAULT 2.5,
    intervalo     INTEGER NOT NULL DEFAULT 0,
    repeticoes    INTEGER NOT NULL DEFAULT 0,
    revisar_em    TEXT    NOT NULL,
    acertos       INTEGER NOT NULL DEFAULT 0,
    erros         INTEGER NOT NULL DEFAULT 0,
    criado_em     TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS revisoes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    cartao_id   INTEGER NOT NULL REFERENCES cartoes(id) ON DELETE CASCADE,
    nota        INTEGER NOT NULL,
    revisado_em TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cartoes_revisar ON cartoes(revisar_em);
CREATE INDEX IF NOT EXISTS idx_cartoes_baralho ON cartoes(baralho_id);
CREATE INDEX IF NOT EXISTS idx_pesquisas_data  ON pesquisas(criada_em DESC);
"""


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# O esquema so precisa ser aplicado uma vez por processo, mas a flag e
# reavaliada quando o arquivo do banco desaparece (apagado a mao, volume
# reiniciado): sem isso, qualquer consulta seguinte falharia ate o servidor
# ser reiniciado.
_esquema_pronto = False


def _preparar(conexao: sqlite3.Connection) -> None:
    """Garante tabelas, indices e o baralho padrao."""
    conexao.executescript(ESQUEMA)
    if not conexao.execute("SELECT 1 FROM baralhos LIMIT 1").fetchone():
        conexao.execute(
            "INSERT INTO baralhos (nome, descricao, criado_em) VALUES (?, ?, ?)",
            ("Geral", "Cartões salvos das suas pesquisas", _agora()),
        )


@contextmanager
def conectar() -> Iterator[sqlite3.Connection]:
    """Conexao com chaves estrangeiras ativas, esquema garantido e commit."""
    global _esquema_pronto

    cfg = obter_config()
    cfg.caminho_banco.parent.mkdir(parents=True, exist_ok=True)
    if not cfg.caminho_banco.exists():
        _esquema_pronto = False

    conexao = sqlite3.connect(cfg.caminho_banco, timeout=15)
    conexao.row_factory = sqlite3.Row
    conexao.execute("PRAGMA foreign_keys = ON")
    conexao.execute("PRAGMA journal_mode = WAL")
    try:
        if not _esquema_pronto:
            _preparar(conexao)
            _esquema_pronto = True
        yield conexao
        conexao.commit()
    except Exception:
        conexao.rollback()
        raise
    finally:
        conexao.close()


def iniciar_banco() -> None:
    """Cria as tabelas e o baralho padrao no arranque da aplicacao."""
    global _esquema_pronto
    _esquema_pronto = False
    with conectar():
        pass


# --------------------------------------------------------------------------
# Historico de pesquisas
# --------------------------------------------------------------------------

def salvar_pesquisa(
    pergunta: str,
    resposta: str,
    area: str,
    modo: str,
    citacoes: list[dict[str, Any]],
) -> int:
    with conectar() as conexao:
        cursor = conexao.execute(
            "INSERT INTO pesquisas (pergunta, resposta, area, modo, citacoes, criada_em) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (pergunta, resposta, area, modo, json.dumps(citacoes, ensure_ascii=False), _agora()),
        )
        return int(cursor.lastrowid)


def listar_pesquisas(limite: int = 30) -> list[dict[str, Any]]:
    with conectar() as conexao:
        linhas = conexao.execute(
            "SELECT id, pergunta, area, modo, criada_em FROM pesquisas "
            "ORDER BY id DESC LIMIT ?",
            (limite,),
        ).fetchall()
    return [dict(linha) for linha in linhas]


def obter_pesquisa(pesquisa_id: int) -> dict[str, Any] | None:
    with conectar() as conexao:
        linha = conexao.execute(
            "SELECT * FROM pesquisas WHERE id = ?", (pesquisa_id,)
        ).fetchone()
    if linha is None:
        return None
    dados = dict(linha)
    dados["citacoes"] = json.loads(dados.get("citacoes") or "[]")
    return dados


def apagar_pesquisa(pesquisa_id: int) -> bool:
    with conectar() as conexao:
        cursor = conexao.execute("DELETE FROM pesquisas WHERE id = ?", (pesquisa_id,))
        return cursor.rowcount > 0


# --------------------------------------------------------------------------
# Baralhos e cartoes
# --------------------------------------------------------------------------

def criar_baralho(nome: str, descricao: str = "") -> int:
    with conectar() as conexao:
        linha = conexao.execute(
            "SELECT id FROM baralhos WHERE nome = ?", (nome,)
        ).fetchone()
        if linha:
            return int(linha["id"])
        cursor = conexao.execute(
            "INSERT INTO baralhos (nome, descricao, criado_em) VALUES (?, ?, ?)",
            (nome, descricao, _agora()),
        )
        return int(cursor.lastrowid)


def listar_baralhos() -> list[dict[str, Any]]:
    hoje = date.today().isoformat()
    with conectar() as conexao:
        linhas = conexao.execute(
            """
            SELECT b.id, b.nome, b.descricao, b.criado_em,
                   COUNT(c.id) AS total,
                   SUM(CASE WHEN date(c.revisar_em) <= date(?) THEN 1 ELSE 0 END) AS devidos
            FROM baralhos b
            LEFT JOIN cartoes c ON c.baralho_id = b.id
            GROUP BY b.id
            ORDER BY b.nome
            """,
            (hoje,),
        ).fetchall()
    return [
        {**dict(linha), "devidos": int(linha["devidos"] or 0), "total": int(linha["total"] or 0)}
        for linha in linhas
    ]


def apagar_baralho(baralho_id: int) -> bool:
    with conectar() as conexao:
        cursor = conexao.execute("DELETE FROM baralhos WHERE id = ?", (baralho_id,))
        return cursor.rowcount > 0


def salvar_cartoes(baralho_id: int, cartoes: list[dict[str, Any]]) -> int:
    """Insere cartoes novos, ignorando duplicatas exatas de frente no baralho."""
    if not cartoes:
        return 0
    agora = _agora()
    hoje = date.today().isoformat()
    inseridos = 0
    with conectar() as conexao:
        existentes = {
            linha["frente"]
            for linha in conexao.execute(
                "SELECT frente FROM cartoes WHERE baralho_id = ?", (baralho_id,)
            ).fetchall()
        }
        for cartao in cartoes:
            frente = str(cartao.get("frente", "")).strip()
            verso = str(cartao.get("verso", "")).strip()
            if not frente or not verso or frente in existentes:
                continue
            existentes.add(frente)
            conexao.execute(
                """
                INSERT INTO cartoes
                    (baralho_id, frente, verso, fonte_url, fonte_titulo,
                     dificuldade, revisar_em, criado_em)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    baralho_id,
                    frente,
                    verso,
                    str(cartao.get("fonte_url", "")),
                    str(cartao.get("fonte_titulo", "")),
                    str(cartao.get("dificuldade", "media")),
                    hoje,
                    agora,
                ),
            )
            inseridos += 1
    return inseridos


def cartoes_do_baralho(baralho_id: int, limite: int = 200) -> list[dict[str, Any]]:
    with conectar() as conexao:
        linhas = conexao.execute(
            "SELECT * FROM cartoes WHERE baralho_id = ? ORDER BY id DESC LIMIT ?",
            (baralho_id, limite),
        ).fetchall()
    return [dict(linha) for linha in linhas]


def cartoes_devidos(baralho_id: int | None = None, limite: int = 30) -> list[dict[str, Any]]:
    """Cartoes cuja data de revisao ja chegou."""
    hoje = date.today().isoformat()
    consulta = (
        "SELECT * FROM cartoes WHERE date(revisar_em) <= date(?) "
        + ("AND baralho_id = ? " if baralho_id else "")
        + "ORDER BY date(revisar_em) ASC, repeticoes ASC LIMIT ?"
    )
    parametros: tuple[Any, ...] = (
        (hoje, baralho_id, limite) if baralho_id else (hoje, limite)
    )
    with conectar() as conexao:
        linhas = conexao.execute(consulta, parametros).fetchall()
    return [dict(linha) for linha in linhas]


def apagar_cartao(cartao_id: int) -> bool:
    with conectar() as conexao:
        cursor = conexao.execute("DELETE FROM cartoes WHERE id = ?", (cartao_id,))
        return cursor.rowcount > 0


# --------------------------------------------------------------------------
# Repeticao espacada (SM-2)
# --------------------------------------------------------------------------

def calcular_sm2(
    facilidade: float,
    intervalo: int,
    repeticoes: int,
    nota: int,
) -> tuple[float, int, int]:
    """Aplica o SM-2.

    `nota` vai de 0 (esqueci completamente) a 5 (lembrei na hora).
    Devolve (nova_facilidade, novo_intervalo_em_dias, novas_repeticoes).
    """
    nota = max(0, min(5, int(nota)))

    if nota < 3:
        # Erro: volta para o inicio, mas a facilidade acumulada e preservada.
        nova_facilidade = max(1.3, facilidade - 0.20)
        return nova_facilidade, 1, 0

    nova_facilidade = facilidade + (0.1 - (5 - nota) * (0.08 + (5 - nota) * 0.02))
    nova_facilidade = max(1.3, round(nova_facilidade, 3))
    novas_repeticoes = repeticoes + 1

    if novas_repeticoes == 1:
        novo_intervalo = 1
    elif novas_repeticoes == 2:
        novo_intervalo = 6
    else:
        novo_intervalo = max(1, round(intervalo * nova_facilidade))

    return nova_facilidade, min(novo_intervalo, 365), novas_repeticoes


def revisar_cartao(cartao_id: int, nota: int) -> dict[str, Any] | None:
    """Registra uma revisao e reagenda o cartao."""
    with conectar() as conexao:
        linha = conexao.execute(
            "SELECT * FROM cartoes WHERE id = ?", (cartao_id,)
        ).fetchone()
        if linha is None:
            return None

        facilidade, intervalo, repeticoes = calcular_sm2(
            float(linha["facilidade"]),
            int(linha["intervalo"]),
            int(linha["repeticoes"]),
            nota,
        )
        proxima = (date.today() + timedelta(days=intervalo)).isoformat()
        acertou = 1 if nota >= 3 else 0

        conexao.execute(
            """
            UPDATE cartoes
               SET facilidade = ?, intervalo = ?, repeticoes = ?, revisar_em = ?,
                   acertos = acertos + ?, erros = erros + ?
             WHERE id = ?
            """,
            (facilidade, intervalo, repeticoes, proxima, acertou, 1 - acertou, cartao_id),
        )
        conexao.execute(
            "INSERT INTO revisoes (cartao_id, nota, revisado_em) VALUES (?, ?, ?)",
            (cartao_id, nota, _agora()),
        )
    return {
        "id": cartao_id,
        "facilidade": facilidade,
        "intervalo": intervalo,
        "repeticoes": repeticoes,
        "revisar_em": proxima,
    }


def estatisticas() -> dict[str, Any]:
    """Painel de progresso do estudante."""
    hoje = date.today().isoformat()
    inicio_semana = (date.today() - timedelta(days=7)).isoformat()
    with conectar() as conexao:
        total_cartoes = conexao.execute("SELECT COUNT(*) AS n FROM cartoes").fetchone()["n"]
        devidos = conexao.execute(
            "SELECT COUNT(*) AS n FROM cartoes WHERE date(revisar_em) <= date(?)", (hoje,)
        ).fetchone()["n"]
        total_pesquisas = conexao.execute(
            "SELECT COUNT(*) AS n FROM pesquisas"
        ).fetchone()["n"]
        revisoes_semana = conexao.execute(
            "SELECT COUNT(*) AS n FROM revisoes WHERE date(revisado_em) >= date(?)",
            (inicio_semana,),
        ).fetchone()["n"]
        desempenho = conexao.execute(
            "SELECT AVG(CASE WHEN nota >= 3 THEN 1.0 ELSE 0.0 END) AS taxa FROM revisoes"
        ).fetchone()["taxa"]
        dominados = conexao.execute(
            "SELECT COUNT(*) AS n FROM cartoes WHERE intervalo >= 21"
        ).fetchone()["n"]
        por_area = conexao.execute(
            "SELECT area, COUNT(*) AS n FROM pesquisas GROUP BY area ORDER BY n DESC LIMIT 6"
        ).fetchall()

    return {
        "total_cartoes": total_cartoes,
        "cartoes_devidos": devidos,
        "cartoes_dominados": dominados,
        "total_pesquisas": total_pesquisas,
        "revisoes_7_dias": revisoes_semana,
        "taxa_acerto": round((desempenho or 0.0) * 100, 1),
        "por_area": [dict(linha) for linha in por_area],
    }
