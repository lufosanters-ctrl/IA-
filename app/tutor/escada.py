"""A escada de ajuda: sete degraus entre a duvida e a resolucao completa.

O principio que organiza tudo e o da **minima ajuda necessaria**. Pular direto
para a resolucao destroi o exercicio; recusar ajuda a quem esta travado de
verdade produz frustracao. A escada existe para que a ajuda cresca um degrau
de cada vez, e so quando o degrau anterior nao bastou.

    0  ORIENTACAO        qual e o assunto e o que a questao quer
    1  PERGUNTA GUIA     uma pergunta que obriga a pensar
    2  PISTA CONCEITUAL  qual propriedade resolve
    3  PISTA OPERACIONAL qual e o proximo passo concreto
    4  PRIMEIRO PASSO    faz a primeira transformacao e devolve o problema
    5  RESOLUCAO PARCIAL desenvolve ate antes da etapa decisiva
    6  RESOLUCAO COMPLETA so a pedido, ou quando ocultar ja nao ensina nada
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Palavras com que o estudante pede para NAO receber a resposta.
PEDIDOS_DE_AUTONOMIA = (
    "nao me de a resposta", "não me dê a resposta", "nao me da a resposta",
    "quero tentar", "me ajude a resolver", "me de uma dica", "me dê uma dica",
    "so uma dica", "só uma dica", "nao entrega", "não entrega", "sem spoiler",
    "deixa eu tentar", "me guia", "me guie", "nao resolve", "não resolve",
)

# Palavras com que o estudante pede a resolucao completa.
# Pedidos que valem o salto para o último degrau. Todos são formulações em
# PRIMEIRA PESSOA, dirigidas ao tutor.
#
# "resolva" sozinho ficou de fora de propósito: é a primeira palavra de quase
# todo enunciado de matemática ("Resolva a equação..."), e bastava colar a
# questão no campo de pedido para receber a resolução inteira sem passar por
# nenhum degrau. A escada existe justamente para isso não acontecer.
PEDIDOS_DE_RESOLUCAO = (
    "resolve logo", "resolva pra mim", "resolve pra mim", "resolva para mim",
    "mostre a resolucao", "mostre a resolução", "mostra a resolucao",
    "mostra a resolução", "me de a resposta", "me dê a resposta",
    "me da a resposta", "me dá a resposta", "qual e a resposta",
    "qual é a resposta", "resolucao completa", "resolução completa",
    "desisto", "nao consigo mais", "não consigo mais", "explica tudo",
    "mostra a solucao", "mostra a solução", "mostre a solucao",
    "mostre a solução", "gabarito", "entrega a resposta", "quero a resposta",
    "so a resposta", "só a resposta", "me diz a resposta", "me fala a resposta",
)


@dataclass(frozen=True, slots=True)
class Degrau:
    """Um degrau da escada, com o que pode e o que não pode aparecer."""

    nivel: int
    nome: str
    objetivo: str
    instrucao: str
    revela_resposta: bool = False
    tamanho_maximo: int = 400

    def para_dict(self) -> dict[str, Any]:
        return {
            "nivel": self.nivel, "nome": self.nome, "objetivo": self.objetivo,
            "revela_resposta": self.revela_resposta,
        }


DEGRAUS: tuple[Degrau, ...] = (
    Degrau(
        0, "Orientação",
        "situar o estudante sem revelar o caminho",
        "Diga apenas: qual é o assunto envolvido, o que exatamente a questão "
        "pede, e onde a atenção deve se concentrar. NÃO indique método, "
        "fórmula, propriedade nem primeiro passo. No máximo 3 linhas.",
        tamanho_maximo=300,
    ),
    Degrau(
        1, "Pergunta guia",
        "obrigar o estudante a pensar no ponto certo",
        "Faça UMA pergunta — só uma — que force o raciocínio no ponto que "
        "destrava o problema. A pergunta deve ter resposta objetiva e ser "
        "respondível com o que o estudante já sabe. Nada de explicação antes "
        "nem depois. No máximo 2 linhas.",
        tamanho_maximo=200,
    ),
    Degrau(
        2, "Pista conceitual",
        "nomear a propriedade que resolve, sem aplicá-la",
        "Aponte a propriedade, regra ou estrutura que resolve o problema. "
        "NÃO aplique ao caso, NÃO desenvolva. Ex.: “repare que a expressão é "
        "simétrica em x e y” ou “este verbo muda de regência conforme o "
        "sentido”. No máximo 4 linhas.",
        tamanho_maximo=350,
    ),
    Degrau(
        3, "Pista operacional",
        "indicar o próximo passo concreto",
        "Diga qual é o próximo passo concreto, no imperativo, sem executá-lo. "
        "Ex.: “fatore o numerador antes de expandir” ou “identifique primeiro "
        "o sentido do verbo na frase”. Pare aí. No máximo 4 linhas.",
        tamanho_maximo=350,
    ),
    Degrau(
        4, "Primeiro passo",
        "fazer junto a primeira transformação e devolver o problema",
        "Execute APENAS a primeira transformação, mostrando-a por extenso. "
        "Em seguida devolva o problema ao estudante com uma pergunta sobre o "
        "que vem depois. Não avance para o segundo passo.",
        tamanho_maximo=700,
    ),
    Degrau(
        5, "Resolução parcial",
        "desenvolver até a etapa decisiva e parar",
        "Desenvolva a solução até imediatamente ANTES da etapa decisiva — "
        "aquela que, uma vez dada, entrega o resultado. Pare ali e pergunte "
        "o que o estudante faria em seguida. Não escreva a resposta final nem "
        "deixe que ela se deduza trivialmente do que você escreveu.",
        tamanho_maximo=1200,
    ),
    Degrau(
        6, "Resolução completa",
        "mostrar tudo, com ideia, desenvolvimento e verificação",
        "Agora sim, resolução integral. Estruture em: o que a questão pede; "
        "ideia central; resolução; por que funciona; a pegadinha; regra para "
        "guardar. Explique o raciocínio — nunca despeje contas.",
        revela_resposta=True,
        tamanho_maximo=3000,
    ),
)

DEGRAUS_POR_NIVEL = {d.nivel: d for d in DEGRAUS}
NIVEL_MAXIMO = max(d.nivel for d in DEGRAUS)


def degrau(nivel: int) -> Degrau:
    """Devolve o degrau, limitando ao intervalo válido."""
    return DEGRAUS_POR_NIVEL[max(0, min(NIVEL_MAXIMO, int(nivel)))]


def proximo_degrau(
    nivel_atual: int,
    acertou_algo: bool = False,
    pediu_resolucao: bool = False,
    pediu_autonomia: bool = False,
) -> int:
    """Decide o próximo degrau segundo a política de mínima ajuda.

    O estudante que está quase lá não precisa de mais ajuda — precisa de menos.
    Por isso um acerto parcial RECUA a escada: é o “fading” do enunciado, a
    retirada gradual do andaime.
    """
    if pediu_resolucao:
        return NIVEL_MAXIMO
    if pediu_autonomia:
        # Pedido explícito de autonomia: nunca passa da resolução parcial.
        return min(nivel_atual, NIVEL_MAXIMO - 1)
    if acertou_algo:
        # Quem está quase lá não precisa de mais andaime: precisa de menos.
        return max(0, nivel_atual - 1)
    return min(nivel_atual + 1, NIVEL_MAXIMO)


def detectar_pedido(texto: str) -> str:
    """Lê o que o estudante pediu: 'resolucao', 'autonomia' ou ''."""
    from ..texto import normalizar

    alvo = normalizar(texto or "")
    if any(normalizar(p) in alvo for p in PEDIDOS_DE_AUTONOMIA):
        return "autonomia"
    if any(normalizar(p) in alvo for p in PEDIDOS_DE_RESOLUCAO):
        return "resolucao"
    # "resolva" isolado num pedido curto é um pedido; "Resolva a equação
    # x^2-5x+6=0" é o enunciado colado de volta no campo, e aí a escada não
    # pode ser pulada.
    if "resolva" in alvo and _parece_pedido_e_nao_enunciado(alvo):
        return "resolucao"
    return ""


# Substantivos que denunciam enunciado colado, não pedido ao tutor.
_PALAVRAS_DE_ENUNCIADO = (
    "equacao", "inequacao", "sistema", "expressao", "problema", "questao",
    "funcao", "integral", "limite", "matriz", "triangulo", "polinomio",
)


def _parece_pedido_e_nao_enunciado(alvo: str) -> bool:
    """Texto curto, sem equação, sem número e sem vocabulário de enunciado."""
    return (
        len(alvo) <= 45
        and "=" not in alvo
        and not any(c.isdigit() for c in alvo)
        and not any(p in alvo for p in _PALAVRAS_DE_ENUNCIADO)
    )
