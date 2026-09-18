"""Estado da tutoria: sessoes, tentativas e padroes de erro.

Sem memoria nao ha tutoria adaptativa. Tres coisas precisam persistir:

* **onde o estudante esta** em cada questao (o degrau da escada);
* **o que ele ja tentou**, para que a correcao ataque o primeiro erro e nao
  reinicie do zero;
* **o padrao dos erros ao longo do tempo**, que e o que permite ensinar uma
  estrategia preventiva em vez de corrigir o mesmo deslize pela decima vez.

O dominio acumulado por topico alimenta o *fading*: quem ja mostra dominio
comeca a escada mais alto, ou seja, recebe menos andaime.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from ..banco import conectar, registrar_esquema

ESQUEMA_TUTOR = """
CREATE TABLE IF NOT EXISTS sessoes_tutor (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    materia      TEXT    NOT NULL,
    enunciado    TEXT    NOT NULL,
    topico       TEXT    NOT NULL DEFAULT '',
    dificuldade  INTEGER NOT NULL DEFAULT 2,
    nivel_atual  INTEGER NOT NULL DEFAULT 0,
    resolvida    INTEGER NOT NULL DEFAULT 0,
    criada_em    TEXT    NOT NULL,
    atualizada_em TEXT   NOT NULL
);

CREATE TABLE IF NOT EXISTS tentativas_tutor (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    sessao_id     INTEGER NOT NULL REFERENCES sessoes_tutor(id) ON DELETE CASCADE,
    texto         TEXT    NOT NULL,
    veredito      TEXT    NOT NULL DEFAULT '',
    primeiro_erro TEXT    NOT NULL DEFAULT '',
    tipo_erro     TEXT    NOT NULL DEFAULT '',
    nivel_ajuda   INTEGER NOT NULL DEFAULT 0,
    criada_em     TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS dominio_tutor (
    topico        TEXT PRIMARY KEY,
    acertos       INTEGER NOT NULL DEFAULT 0,
    erros         INTEGER NOT NULL DEFAULT 0,
    soma_ajuda    INTEGER NOT NULL DEFAULT 0,
    sessoes       INTEGER NOT NULL DEFAULT 0,
    atualizado_em TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tentativas_sessao ON tentativas_tutor(sessao_id);
CREATE INDEX IF NOT EXISTS idx_sessoes_data ON sessoes_tutor(criada_em DESC);
"""

# Tipos de erro reconhecidos. Corrigir "erro de sinal" e corrigir "erro
# conceitual" sao intervencoes diferentes; misturar os dois nao ensina nada.
TIPOS_DE_ERRO: dict[str, str] = {
    "conceitual": "não domina a regra ou o conceito envolvido",
    "interpretacao": "leu o enunciado de outro jeito",
    "algebrico": "a ideia estava certa, a manipulação escorregou",
    "sinal": "troca de sinal no meio da conta",
    "distracao": "sabia fazer, mas pulou ou copiou errado um passo",
    "fora_das_condicoes": "aplicou uma regra fora da hipótese em que ela vale",
    "confusao_entre_regras": "usou uma regra no lugar de outra parecida",
    "incompleto": "parou antes de responder o que foi pedido",
}

ESTRATEGIAS_PREVENTIVAS: dict[str, str] = {
    "sinal": "Antes de fechar a conta, refaça só os sinais, de trás para a "
             "frente. É o tipo de erro que some com uma conferência de 10 segundos.",
    "interpretacao": "Releia o enunciado e sublinhe o que é DADO e o que é "
                     "PEDIDO antes de escrever a primeira linha.",
    "fora_das_condicoes": "Toda vez que usar uma fórmula, escreva ao lado a "
                          "condição em que ela vale. Se a condição não está "
                          "verificada, a fórmula não se aplica.",
    "confusao_entre_regras": "Monte um par de exemplos mínimos que separem as "
                             "duas regras. O contraste fixa melhor que a definição.",
    "algebrico": "Substitua um valor numérico simples no início e no fim da "
                 "manipulação: se o resultado muda, o erro está no meio.",
    "incompleto": "Ao terminar, releia a pergunta e confira se respondeu "
                  "exatamente aquilo, na forma pedida.",
    "distracao": "Copie o enunciado uma vez à mão antes de resolver. Parece "
                 "perda de tempo e corta a maioria desses erros.",
    "conceitual": "Antes da próxima questão do mesmo assunto, reescreva a regra "
                  "com suas palavras e crie um exemplo próprio.",
}


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# As tabelas da tutoria nascem junto com as do banco principal.
registrar_esquema(ESQUEMA_TUTOR)


def iniciar_banco_tutor() -> None:
    """Garante as tabelas da tutoria (idempotente)."""
    with conectar():
        pass


def _garantir() -> None:
    """A conexão já cria o esquema quando necessário; nada a fazer aqui."""


@dataclass(slots=True)
class Tentativa:
    """Uma tentativa do estudante, já diagnosticada."""

    id: int
    texto: str
    veredito: str
    primeiro_erro: str
    tipo_erro: str
    nivel_ajuda: int
    criada_em: str

    def para_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "texto": self.texto, "veredito": self.veredito,
            "primeiro_erro": self.primeiro_erro, "tipo_erro": self.tipo_erro,
            "nivel_ajuda": self.nivel_ajuda, "criada_em": self.criada_em,
        }


@dataclass(slots=True)
class Sessao:
    """Uma questão em estudo, com o histórico do que já foi tentado."""

    id: int
    materia: str
    enunciado: str
    topico: str
    dificuldade: int
    nivel_atual: int
    resolvida: bool
    criada_em: str
    tentativas: list[Tentativa] = field(default_factory=list)

    def para_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "materia": self.materia, "enunciado": self.enunciado,
            "topico": self.topico, "dificuldade": self.dificuldade,
            "nivel_atual": self.nivel_atual, "resolvida": self.resolvida,
            "criada_em": self.criada_em,
            "tentativas": [t.para_dict() for t in self.tentativas],
        }


def nivel_inicial_para(topico: str) -> int:
    """Fading: quem já mostra domínio começa a escada com menos andaime.

    Domínio alto não significa pular a tutoria — significa que a primeira
    intervenção pode ser uma pergunta em vez de uma orientação completa.
    """
    _garantir()
    if not topico:
        return 0
    with conectar() as conexao:
        linha = conexao.execute(
            "SELECT acertos, erros, soma_ajuda, sessoes FROM dominio_tutor "
            "WHERE topico = ?", (topico,)
        ).fetchone()
    if linha is None or linha["sessoes"] < 3:
        return 0

    total = linha["acertos"] + linha["erros"]
    taxa = linha["acertos"] / total if total else 0.0
    ajuda_media = linha["soma_ajuda"] / linha["sessoes"]
    # Acerta muito e com pouca ajuda: entra direto na pergunta guia.
    if taxa >= 0.75 and ajuda_media <= 2.0:
        return 1
    return 0


def abrir_sessao(
    materia: str,
    enunciado: str,
    topico: str = "",
    dificuldade: int = 2,
) -> Sessao:
    """Abre uma sessão de estudo para uma questão."""
    _garantir()
    agora = _agora()
    nivel = nivel_inicial_para(topico)
    with conectar() as conexao:
        cursor = conexao.execute(
            "INSERT INTO sessoes_tutor (materia, enunciado, topico, dificuldade, "
            "nivel_atual, criada_em, atualizada_em) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (materia, enunciado, topico, dificuldade, nivel, agora, agora),
        )
        identificador = int(cursor.lastrowid)
    return Sessao(
        id=identificador, materia=materia, enunciado=enunciado, topico=topico,
        dificuldade=dificuldade, nivel_atual=nivel, resolvida=False,
        criada_em=agora,
    )


def obter_sessao(sessao_id: int) -> Sessao | None:
    """Carrega a sessão com todas as tentativas, em ordem."""
    _garantir()
    with conectar() as conexao:
        linha = conexao.execute(
            "SELECT * FROM sessoes_tutor WHERE id = ?", (sessao_id,)
        ).fetchone()
        if linha is None:
            return None
        tentativas = conexao.execute(
            "SELECT * FROM tentativas_tutor WHERE sessao_id = ? ORDER BY id",
            (sessao_id,),
        ).fetchall()

    return Sessao(
        id=linha["id"], materia=linha["materia"], enunciado=linha["enunciado"],
        topico=linha["topico"], dificuldade=linha["dificuldade"],
        nivel_atual=linha["nivel_atual"], resolvida=bool(linha["resolvida"]),
        criada_em=linha["criada_em"],
        tentativas=[
            Tentativa(
                id=t["id"], texto=t["texto"], veredito=t["veredito"],
                primeiro_erro=t["primeiro_erro"], tipo_erro=t["tipo_erro"],
                nivel_ajuda=t["nivel_ajuda"], criada_em=t["criada_em"],
            )
            for t in tentativas
        ],
    )


def registrar_tentativa(
    sessao_id: int,
    texto: str,
    veredito: str,
    primeiro_erro: str = "",
    tipo_erro: str = "",
    nivel_ajuda: int = 0,
) -> Tentativa | None:
    """Guarda a tentativa e atualiza o domínio acumulado do tópico."""
    _garantir()
    agora = _agora()
    with conectar() as conexao:
        sessao = conexao.execute(
            "SELECT topico FROM sessoes_tutor WHERE id = ?", (sessao_id,)
        ).fetchone()
        if sessao is None:
            return None

        cursor = conexao.execute(
            "INSERT INTO tentativas_tutor (sessao_id, texto, veredito, "
            "primeiro_erro, tipo_erro, nivel_ajuda, criada_em) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (sessao_id, texto, veredito, primeiro_erro, tipo_erro, nivel_ajuda, agora),
        )
        identificador = int(cursor.lastrowid)
        conexao.execute(
            "UPDATE sessoes_tutor SET atualizada_em = ?, resolvida = ? WHERE id = ?",
            (agora, 1 if veredito == "correto" else 0, sessao_id),
        )

        topico = sessao["topico"] or "geral"
        acerto = 1 if veredito == "correto" else 0
        conexao.execute(
            """
            INSERT INTO dominio_tutor (topico, acertos, erros, soma_ajuda,
                                       sessoes, atualizado_em)
            VALUES (?, ?, ?, ?, 1, ?)
            ON CONFLICT(topico) DO UPDATE SET
                acertos = acertos + excluded.acertos,
                erros = erros + excluded.erros,
                soma_ajuda = soma_ajuda + excluded.soma_ajuda,
                sessoes = sessoes + 1,
                atualizado_em = excluded.atualizado_em
            """,
            (topico, acerto, 1 - acerto, nivel_ajuda, agora),
        )

    return Tentativa(
        id=identificador, texto=texto, veredito=veredito,
        primeiro_erro=primeiro_erro, tipo_erro=tipo_erro,
        nivel_ajuda=nivel_ajuda, criada_em=agora,
    )


def subir_degrau(sessao_id: int, novo_nivel: int) -> bool:
    """Move a sessão para outro degrau da escada."""
    _garantir()
    with conectar() as conexao:
        cursor = conexao.execute(
            "UPDATE sessoes_tutor SET nivel_atual = ?, atualizada_em = ? WHERE id = ?",
            (max(0, min(6, int(novo_nivel))), _agora(), sessao_id),
        )
        return cursor.rowcount > 0


def listar_sessoes(limite: int = 20) -> list[dict[str, Any]]:
    _garantir()
    with conectar() as conexao:
        linhas = conexao.execute(
            """
            SELECT s.id, s.materia, s.topico, s.dificuldade, s.nivel_atual,
                   s.resolvida, s.criada_em, s.enunciado,
                   COUNT(t.id) AS tentativas
              FROM sessoes_tutor s
              LEFT JOIN tentativas_tutor t ON t.sessao_id = s.id
             GROUP BY s.id ORDER BY s.id DESC LIMIT ?
            """,
            (limite,),
        ).fetchall()
    return [
        {**dict(linha), "resolvida": bool(linha["resolvida"]),
         "enunciado": (linha["enunciado"] or "")[:180]}
        for linha in linhas
    ]


def padroes_de_erro(minimo: int = 2) -> dict[str, Any]:
    """Erros que se repetem, com a estratégia preventiva de cada um.

    Corrigir o mesmo deslize pela décima vez não ensina. Nomear o padrão e
    oferecer uma rotina que o previne, sim.
    """
    _garantir()
    with conectar() as conexao:
        por_tipo = conexao.execute(
            "SELECT tipo_erro, COUNT(*) AS n FROM tentativas_tutor "
            "WHERE tipo_erro <> '' GROUP BY tipo_erro ORDER BY n DESC"
        ).fetchall()
        por_topico = conexao.execute(
            """
            SELECT topico, acertos, erros, sessoes, soma_ajuda
              FROM dominio_tutor ORDER BY erros DESC LIMIT 10
            """
        ).fetchall()

    recorrentes = [
        {
            "tipo": linha["tipo_erro"],
            "ocorrencias": linha["n"],
            "descricao": TIPOS_DE_ERRO.get(linha["tipo_erro"], ""),
            "estrategia": ESTRATEGIAS_PREVENTIVAS.get(linha["tipo_erro"], ""),
        }
        for linha in por_tipo if linha["n"] >= minimo
    ]
    dominio = []
    for linha in por_topico:
        total = linha["acertos"] + linha["erros"]
        dominio.append({
            "topico": linha["topico"],
            "acertos": linha["acertos"],
            "erros": linha["erros"],
            "taxa": round(linha["acertos"] / total * 100, 1) if total else 0.0,
            "ajuda_media": round(linha["soma_ajuda"] / linha["sessoes"], 2)
            if linha["sessoes"] else 0.0,
        })
    return {"recorrentes": recorrentes, "dominio": dominio}
