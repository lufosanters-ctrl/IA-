"""Treino dirigido: do erro detectado para o exercício que o corrige.

Detectar que o estudante erra sempre a mesma coisa e apenas dizer "cuidado com
isso" não muda nada. O que muda é praticar exatamente aquilo.

Este módulo fecha o laço. Ele lê os padrões acumulados na tutoria, escolhe a
regra ou o assunto em que o estudante mais falha, e monta um treino curto:

* em português e inglês, frases da mesma regra, tiradas do banco de casos de
  referência — o mesmo banco que afere os motores, e que por isso tem gabarito
  confiável;
* em matemática, uma questão do gerador paramétrico cujo distrator corresponde
  ao erro que ele vem cometendo.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from ..afericao import TODOS_OS_CASOS, Caso
from .sessao import ESTRATEGIAS_PREVENTIVAS, TIPOS_DE_ERRO, padroes_de_erro

# De que assunto tratar quando o erro é de determinado tipo. O tipo de erro
# aponta o COMO; o tópico com mais falhas aponta o QUE.
AREAS_POR_MATERIA: dict[str, tuple[str, ...]] = {
    "portugues": ("crase", "colocacao", "concordancia"),
    "ingles": ("ingles",),
    "matematica": ("algebra", "topico"),
}

# Geradores de questão cujo distrator corresponde a cada tipo de erro.
GERADOR_POR_ERRO: dict[str, str] = {
    "sinal": "polinomios",
    "fora_das_condicoes": "logaritmos",
    "incompleto": "trigonometria",
    "confusao_entre_regras": "combinatoria",
    "conceitual": "complexos",
    "algebrico": "sequencias",
}


@dataclass(slots=True)
class ItemDeTreino:
    """Um exercício do treino, com gabarito guardado para depois."""

    enunciado: str
    resposta: str
    regra: str = ""
    area: str = ""
    alternativas: list[str] = field(default_factory=list)
    correta: int = -1
    explicacao: str = ""

    def para_dict(self, com_gabarito: bool = False) -> dict[str, Any]:
        dados: dict[str, Any] = {
            "enunciado": self.enunciado,
            "regra": self.regra,
            "area": self.area,
            "alternativas": self.alternativas,
        }
        if com_gabarito:
            dados["resposta"] = self.resposta
            dados["correta"] = self.correta
            dados["explicacao"] = self.explicacao
        return dados


@dataclass(slots=True)
class Treino:
    """Um treino curto, dirigido ao erro que mais se repete."""

    motivo: str
    tipo_erro: str = ""
    estrategia: str = ""
    itens: list[ItemDeTreino] = field(default_factory=list)
    origem: str = "banco de referência"

    def para_dict(self, com_gabarito: bool = False) -> dict[str, Any]:
        return {
            "motivo": self.motivo,
            "tipo_erro": self.tipo_erro,
            "estrategia": self.estrategia,
            "origem": self.origem,
            "itens": [i.para_dict(com_gabarito) for i in self.itens],
        }


# --------------------------------------------------------------------------
# Banco de prática a partir dos casos de referência
# --------------------------------------------------------------------------

# Como perguntar cada área ao estudante.
PERGUNTA_DA_AREA: dict[str, str] = {
    "crase": "Nesta frase, o sinal de crase é obrigatório, proibido, facultativo "
             "ou depende da regência?",
    "colocacao": "Qual é a colocação que a norma-padrão exige nesta frase?",
    "concordancia": "A concordância desta frase está correta?",
    "ingles": "Esta frase tem algum erro de estrutura?",
    "topico": "De que assunto é esta questão?",
    "algebra": "Qual é o conjunto solução?",
    "regencia": "Este verbo rege a preposição “a” em algum sentido?",
    "materia": "De que matéria é esta questão?",
}

ALTERNATIVAS_DA_AREA: dict[str, list[str]] = {
    "crase": ["obrigatoria", "proibida", "facultativa", "depende_da_regencia"],
    "colocacao": ["próclise", "mesóclise", "ênclise", "nenhum pronome"],
    "concordancia": ["correto", "erro", "nada detectado"],
    "ingles": ["sim, há erro", "não, está correta"],
    "regencia": ["sim, rege “a”", "não rege “a”"],
    "regencia_uso": ["sim, há desvio de regência", "não, está correta"],
    "lexico": [],
}


def _texto_da_resposta(caso: Caso) -> str:
    if isinstance(caso.esperado, bool):
        if caso.area == "ingles":
            return "sim, há erro" if caso.esperado else "não, está correta"
        if caso.area == "regencia_uso":
            return "sim, há desvio de regência" if caso.esperado else "não, está correta"
        if caso.area == "lexico":
            return "sim" if caso.esperado else "não"
        return "sim, rege “a”" if caso.esperado else "não rege “a”"
    if isinstance(caso.esperado, (set, frozenset)):
        return "{" + ", ".join(sorted(str(v) for v in caso.esperado)) + "}"
    return str(caso.esperado)


def _respondivel(caso: Caso) -> bool:
    """O caso vira um exercício que o estudante consegue responder?

    Um item cujo gabarito não está entre as alternativas é impossível de
    acertar — melhor não montá-lo do que apresentar uma pergunta sem saída.
    """
    alternativas = ALTERNATIVAS_DA_AREA.get(caso.area, [])
    if not alternativas:
        # Área sem alternativas: a questão é de resposta aberta, e o estudante
        # escreve o que achar. Isso é legítimo — o que não pode existir é
        # alternativa fechada cujo gabarito não está entre elas.
        return True
    return _texto_da_resposta(caso) in alternativas


def _item_de_caso(caso: Caso) -> ItemDeTreino:
    alternativas = list(ALTERNATIVAS_DA_AREA.get(caso.area, []))
    resposta = _texto_da_resposta(caso)
    correta = alternativas.index(resposta) if resposta in alternativas else -1
    pergunta = PERGUNTA_DA_AREA.get(caso.area, "Qual é a resposta?")
    return ItemDeTreino(
        enunciado=f"{caso.entrada}\n\n{pergunta}",
        resposta=resposta,
        regra=caso.porque,
        area=caso.area,
        alternativas=alternativas,
        correta=correta,
        explicacao=caso.porque,
    )


def treino_de_area(area: str, quantidade: int = 4,
                   semente: int | None = None) -> list[ItemDeTreino]:
    """Exercícios de uma área, tirados do banco de casos com gabarito."""
    casos = [c for c in TODOS_OS_CASOS if c.area == area and _respondivel(c)]
    if not casos:
        return []
    sorteio = random.Random(semente)
    escolhidos = sorteio.sample(casos, min(quantidade, len(casos)))
    return [_item_de_caso(caso) for caso in escolhidos]


def treino_de_regra(area: str, regra: str, quantidade: int = 4) -> list[ItemDeTreino]:
    """Exercícios da MESMA regra em que o estudante falhou."""
    alvo = regra.lower().strip()
    casos = [
        c for c in TODOS_OS_CASOS
        if c.area == area and alvo and alvo in c.porque.lower() and _respondivel(c)
    ]
    return [_item_de_caso(caso) for caso in casos[:quantidade]]


# --------------------------------------------------------------------------
# Montagem do treino a partir dos padroes acumulados
# --------------------------------------------------------------------------

def _questao_de_matematica(tipo_erro: str, semente: int | None) -> ItemDeTreino | None:
    """Questão cujo distrator corresponde ao erro que o estudante comete."""
    from ..matematica.criacao import criar_parametrica

    topico = GERADOR_POR_ERRO.get(tipo_erro, "")
    questao = criar_parametrica(topico, semente=semente)
    return ItemDeTreino(
        enunciado=questao.enunciado,
        resposta=questao.alternativas[questao.correta],
        regra=questao.ideia_central,
        area="matematica",
        alternativas=questao.alternativas,
        correta=questao.correta,
        explicacao=questao.solucao,
    )


def montar_treino(
    materia: str = "",
    tipo_erro: str = "",
    quantidade: int = 4,
    semente: int | None = None,
) -> Treino:
    """Escolhe o que treinar a partir do histórico, ou do que for pedido.

    Sem pedido explícito, o treino é o do erro que mais se repete — que é
    justamente o que o estudante não está corrigindo sozinho.
    """
    # Duas ocorrências, não uma: "você vem cometendo" é uma afirmação sobre
    # um padrão, e uma ocorrência isolada não é padrão nenhum.
    padroes = padroes_de_erro(minimo=2)
    recorrentes = padroes.get("recorrentes", [])

    if not tipo_erro and recorrentes:
        tipo_erro = recorrentes[0]["tipo"]

    estrategia = ESTRATEGIAS_PREVENTIVAS.get(tipo_erro, "")
    descricao = TIPOS_DE_ERRO.get(tipo_erro, "")

    ocorrencias = next(
        (p["ocorrencias"] for p in recorrentes if p["tipo"] == tipo_erro), 0
    )
    if tipo_erro and descricao and ocorrencias >= 2:
        motivo = (
            f"Erro do tipo “{tipo_erro}” ({descricao}) apareceu "
            f"{ocorrencias} vezes nas suas tentativas. Este treino ataca "
            "exatamente isso."
        )
    elif tipo_erro and descricao:
        motivo = (
            f"Treino de reforço em “{tipo_erro}” ({descricao}). Ainda não há "
            "repetição suficiente para chamar de padrão — isto é prática, "
            "não diagnóstico."
        )
    else:
        motivo = "Treino geral, sem padrão de erro acumulado ainda."

    # A matéria vem do pedido, do assunto em que ele mais erra, ou do sorteio.
    if not materia:
        dominio = padroes.get("dominio", [])
        topico_ruim = dominio[0]["topico"] if dominio else ""
        if topico_ruim in {"crase", "colocacao", "concordancia"}:
            materia = "portugues"
        elif topico_ruim:
            materia = "matematica"
        else:
            materia = "portugues"

    treino = Treino(motivo=motivo, tipo_erro=tipo_erro, estrategia=estrategia)

    if materia == "matematica":
        # Uma questão parametrizada por item. O sorteio pode repetir os mesmos
        # coeficientes, então a deduplicação por enunciado é obrigatória: dois
        # exercícios idênticos no mesmo treino não ensinam nada.
        vistos: set[str] = set()
        tentativa = 0
        while len(treino.itens) < quantidade and tentativa < quantidade * 6:
            questao = _questao_de_matematica(
                tipo_erro, None if semente is None else semente + tentativa
            )
            tentativa += 1
            if questao and questao.enunciado not in vistos:
                vistos.add(questao.enunciado)
                treino.itens.append(questao)
        if treino.itens:
            treino.origem = "gerador paramétrico"
        if len(treino.itens) < quantidade:
            treino.itens.extend(
                treino_de_area("algebra", quantidade - len(treino.itens), semente)
            )
        return treino

    areas = AREAS_POR_MATERIA.get(materia, ("crase",))
    por_area = max(1, quantidade // len(areas))
    for area in areas:
        treino.itens.extend(treino_de_area(area, por_area, semente))
    # Completa o treino até a quantidade pedida, varrendo as áreas de novo com
    # outra semente. Entregar dois exercícios quando cinco foram pedidos é
    # entregar menos do que o estudante pediu.
    rodada = 1
    ja_vistos = {i.enunciado for i in treino.itens}
    while len(treino.itens) < quantidade and rodada <= len(areas) * 3:
        area = areas[(rodada - 1) % len(areas)]
        for item in treino_de_area(area, quantidade, (semente or 0) + rodada):
            if item.enunciado not in ja_vistos and len(treino.itens) < quantidade:
                ja_vistos.add(item.enunciado)
                treino.itens.append(item)
        rodada += 1
    return treino
