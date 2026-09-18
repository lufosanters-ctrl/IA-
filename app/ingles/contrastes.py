"""Pares que se confundem: ensinar por contraste, nao isoladamente.

Explicar "present perfect" sozinho nao resolve a duvida de ninguem. A duvida
real e sempre relacional — present perfect OU simple past? — e o que destrava
e o CRITERIO DE DECISAO, nao a definicao de cada um.

Cada contraste aqui traz: o criterio, a pergunta que o estudante deve se
fazer, exemplos minimos e o erro tipico de quem fala portugues.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from ..texto import normalizar


@dataclass(frozen=True, slots=True)
class Contraste:
    """Duas construções que competem, e o critério que decide entre elas."""

    chave: str
    lado_a: str
    lado_b: str
    criterio: str
    pergunta_decisiva: str
    exemplo_a: str
    exemplo_b: str
    erro_tipico: str
    gatilhos: tuple[str, ...] = ()
    lingua: str = "ingles"

    def para_dict(self) -> dict[str, Any]:
        return {
            "chave": self.chave, "lado_a": self.lado_a, "lado_b": self.lado_b,
            "criterio": self.criterio, "pergunta_decisiva": self.pergunta_decisiva,
            "exemplo_a": self.exemplo_a, "exemplo_b": self.exemplo_b,
            "erro_tipico": self.erro_tipico, "lingua": self.lingua,
        }


CONTRASTES: tuple[Contraste, ...] = (
    # ---------------------------- inglês ---------------------------------
    Contraste(
        "perfect_x_past", "present perfect", "simple past",
        "O simple past prende o fato a um momento encerrado; o present perfect "
        "liga o fato ao presente, pelo resultado ou pela continuidade.",
        "O tempo em que isso aconteceu já acabou, ou ainda está correndo?",
        "I have lived here for ten years. (e continuo morando)",
        "I lived there in 2015. (momento fechado)",
        "Usar present perfect com marcador de tempo fechado: “I have seen him "
        "yesterday” é erro — com “yesterday”, só simple past.",
        ("present perfect", "simple past", "have seen", "did you", "already",
         "yet", "since", "for"),
    ),
    Contraste(
        "for_x_since", "for", "since",
        "“for” mede duração; “since” marca o ponto em que começou.",
        "Você está dizendo QUANTO tempo ou DESDE QUANDO?",
        "for three years / for a long time",
        "since 2020 / since I was a child",
        "“since three years” não existe: duração pede “for”.",
        ("for", "since"),
    ),
    Contraste(
        "will_x_going_to", "will", "be going to",
        "“will” para decisão tomada na hora e previsão sem evidência; "
        "“going to” para intenção já formada e previsão com evidência à vista.",
        "A decisão já estava tomada antes de você falar, ou nasceu agora?",
        "The phone is ringing. I'll get it. (decisão agora)",
        "Look at those clouds. It's going to rain. (evidência presente)",
        "Tratar os dois como sinônimos e perder a diferença de intenção.",
        ("will", "going to", "future"),
    ),
    Contraste(
        "used_to_x_would", "used to", "would",
        "Os dois contam hábito passado, mas “used to” também serve para "
        "ESTADOS, e “would” não.",
        "É ação repetida ou estado?",
        "I used to live in Recife. (estado — “would live” seria errado)",
        "Every summer we would go to the beach. (ação repetida)",
        "Usar “would” com verbo de estado: “I would live there” muda o sentido "
        "para condicional.",
        ("used to", "would", "hábito"),
    ),
    Contraste(
        "make_x_do", "make", "do",
        "“make” tende a criar ou produzir algo; “do” tende a executar uma "
        "atividade. As colocações, porém, se aprendem em bloco.",
        "Há um produto resultante, ou é a execução de uma tarefa?",
        "make a decision, make a mistake, make money, make progress",
        "do homework, do the dishes, do business, do research",
        "“Do a mistake” e “make homework” são os deslizes mais comuns.",
        ("make", "do"),
    ),
    Contraste(
        "say_x_tell", "say", "tell",
        "“tell” pede a pessoa como objeto direto; “say” não, e usa “to”.",
        "Você vai mencionar a pessoa logo depois do verbo?",
        "He told me the truth. / He told me to wait.",
        "He said (to me) that he was tired.",
        "“He said me” não existe; “he told that…” sem pessoa também não.",
        ("say", "tell", "said", "told"),
    ),
    Contraste(
        "in_on_at_tempo", "in / on / at (tempo)", "—",
        "Escala decrescente: “in” para períodos longos, “on” para dias e datas, "
        "“at” para horas e pontos exatos.",
        "O recorte é um período, um dia ou um instante?",
        "in 2024, in July, in the morning",
        "on Monday, on July 4th · at 6 p.m., at night",
        "“In the night” em vez de “at night”; “in Monday” em vez de “on Monday”.",
        ("in", "on", "at", "preposition"),
    ),
    Contraste(
        "much_many_alot", "much / many", "a lot of",
        "“much” para incontáveis, “many” para contáveis; “a lot of” serve para "
        "os dois e é o natural em frase afirmativa.",
        "O substantivo é contável? A frase é afirmativa?",
        "How much time? / How many people?",
        "He has a lot of friends. (mais natural que “many friends” aqui)",
        "Usar “much/many” em afirmativa, o que soa formal ou estranho.",
        ("much", "many", "a lot of", "countable"),
    ),
    Contraste(
        "gerund_x_infinitive", "verbo + -ing", "verbo + to",
        "Alguns verbos pedem gerúndio, outros infinitivo, e alguns mudam de "
        "sentido conforme o que vem depois.",
        "Qual verbo vem antes? E ele muda de sentido com a escolha?",
        "enjoy/avoid/finish/mind + -ing · stop smoking (parou de fumar)",
        "want/decide/hope/promise + to · stop to smoke (parou para fumar)",
        "“I enjoy to read” em vez de “I enjoy reading”.",
        ("gerund", "infinitive", "ing", "to + verb", "stop", "remember", "forget"),
    ),
    Contraste(
        "if_conditionals", "second conditional", "first conditional",
        "First conditional trata de possibilidade real; second trata de "
        "hipótese improvável ou contrária ao fato.",
        "Isso pode realmente acontecer, ou é hipótese?",
        "If I win the lottery, I'll travel. (possível)",
        "If I won the lottery, I would travel. (hipotético)",
        "Usar “will” dentro do “if”: “If I will go…” não existe.",
        ("if", "conditional", "would", "were"),
    ),
    # --------------------------- português --------------------------------
    Contraste(
        "od_x_oi", "objeto direto", "objeto indireto",
        "O objeto direto completa o verbo sem preposição obrigatória; o "
        "indireto exige preposição pedida pelo próprio verbo. Se pede, o "
        "complemento é indireto.",
        "O verbo pede preposição NESSE sentido?",
        "Comprei o livro. (od) · Vi o filme. (od)",
        "Assisti ao filme. (oi) · Obedeci às regras. (oi)",
        "Decidir pela preposição visível em vez de pela regência do verbo: "
        "em “gosto de música”, o “de” é exigido, então é indireto.",
        ("objeto direto", "objeto indireto", "transitivo"),
        lingua="portugues",
    ),
    Contraste(
        "adjunto_x_complemento", "adjunto adnominal", "complemento nominal",
        "Se o termo preposicionado é praticante da ação, é adjunto; se é alvo "
        "dela, é complemento nominal.",
        "O termo PRATICA ou SOFRE a ação contida no nome?",
        "A construção dos operários. (eles constroem → adjunto adnominal)",
        "A construção da casa. (a casa é construída → complemento nominal)",
        "Decorar a forma em vez de aplicar o teste agente × paciente.",
        ("adjunto adnominal", "complemento nominal"),
        lingua="portugues",
    ),
    Contraste(
        "permutacao_x_combinacao", "arranjo/permutação", "combinação",
        "Se trocar a ordem gera um caso novo, é arranjo; se não gera, é "
        "combinação.",
        "Mudar a ordem dos escolhidos muda o resultado?",
        "Senhas, pódios, filas → a ordem importa → arranjo.",
        "Comissões, times, conjuntos → a ordem não importa → combinação.",
        "Contar comissão como se fosse pódio e multiplicar por k! sem necessidade.",
        ("arranjo", "combinação", "permutação"),
        lingua="portugues",
    ),
)

CONTRASTES_POR_CHAVE = {c.chave: c for c in CONTRASTES}


def contrastes_relevantes(texto: str, lingua: str = "", limite: int = 3) -> list[Contraste]:
    """Contrastes cujos gatilhos aparecem no texto."""
    alvo = normalizar(texto or "")
    pontuados: list[tuple[int, Contraste]] = []
    for contraste in CONTRASTES:
        if lingua and contraste.lingua != lingua:
            continue
        pontos = sum(
            1 for gatilho in contraste.gatilhos
            if re.search(rf"(?<![a-z]){re.escape(normalizar(gatilho))}(?![a-z])", alvo)
        )
        if pontos:
            pontuados.append((pontos, contraste))
    pontuados.sort(key=lambda par: par[0], reverse=True)
    return [contraste for _, contraste in pontuados[:limite]]
