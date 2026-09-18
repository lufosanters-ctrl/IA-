"""As cinco dimensoes de uma construcao inglesa.

"Está certo?" é pergunta insuficiente. Uma frase pode ser perfeitamente
gramatical e, ainda assim, ser algo que nenhum falante diria; pode ser natural
na conversa e inadequada num artigo; pode existir e ser raríssima. Reduzir
tudo a certo/errado é o que produz o inglês de livro escolar que soa estranho.

Estas são as dimensões que a avaliação precisa separar:

1. GRAMMATICALITY — as regras permitem?
2. MEANING        — o que a construção significa de fato?
3. NATURALNESS    — um falante diria assim nesta situação?
4. REGISTER       — formal, neutro, informal, acadêmico?
5. FREQUENCY      — é comum ou é construção de canto de gramática?
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

DIMENSOES: tuple[tuple[str, str, str], ...] = (
    ("grammaticality", "Gramaticalidade",
     "As regras da língua permitem esta construção?"),
    ("meaning", "Significado",
     "O que ela comunica exatamente, e em que difere das alternativas?"),
    ("naturalness", "Naturalidade",
     "Um falante nativo diria isso nesta situação, ou soaria traduzido?"),
    ("register", "Registro",
     "Serve para conversa, para e-mail de trabalho, para texto acadêmico?"),
    ("frequency", "Frequência",
     "É construção corrente ou rara o bastante para soar afetada?"),
)

ESCALA = {
    "grammaticality": ("agramatical", "duvidosa", "gramatical"),
    "naturalness": ("soa traduzido", "aceitável", "natural"),
    "frequency": ("rara", "ocasional", "comum"),
}


@dataclass(slots=True)
class Avaliacao:
    """Uma construção avaliada nas cinco dimensões."""

    construcao: str
    grammaticality: str = ""
    meaning: str = ""
    naturalness: str = ""
    register: str = ""
    frequency: str = ""
    alternativa_melhor: str = ""
    erro_tipico: str = ""
    observacao: str = ""
    fonte: str = "análise estrutural"

    def para_dict(self) -> dict[str, Any]:
        return {
            "construcao": self.construcao,
            "grammaticality": self.grammaticality,
            "meaning": self.meaning,
            "naturalness": self.naturalness,
            "register": self.register,
            "frequency": self.frequency,
            "alternativa_melhor": self.alternativa_melhor,
            "erro_tipico": self.erro_tipico,
            "observacao": self.observacao,
            "fonte": self.fonte,
        }


# --------------------------------------------------------------------------
# Erros estruturais que um falante de portugues comete por transferencia
# --------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class PadraoDeTransferencia:
    """Erro que vem de traduzir a estrutura do portugues palavra por palavra."""

    nome: str
    padrao: str                 # regex
    problema: str
    correcao: str
    porque: str
    exemplo_errado: str
    exemplo_certo: str
    # "erro" = a construção é agramatical em qualquer leitura.
    # "suspeita" = o padrão também tem leitura correta, então o motor avisa
    # sem condenar. Falso cognato e preposição ambígua caem aqui.
    severidade: str = "erro"

    def para_dict(self) -> dict[str, Any]:
        return {
            "nome": self.nome, "problema": self.problema,
            "correcao": self.correcao, "porque": self.porque,
            "exemplo_errado": self.exemplo_errado, "exemplo_certo": self.exemplo_certo,
            "severidade": self.severidade,
        }


TRANSFERENCIAS: tuple[PadraoDeTransferencia, ...] = (
    PadraoDeTransferencia(
        "people + verbo no singular",
        r"\bpeople\s+(is|was|has\b(?!\s+been\s+\w+ing))",
        "“people” é plural em inglês",
        "people are / people were / people have",
        "Em português “as pessoas” e “o povo” são coisas diferentes; em inglês "
        "“people” já é o plural de “person”.",
        "People is waiting outside.",
        "People are waiting outside.",
    ),
    PadraoDeTransferencia(
        "informação no plural",
        r"\b(informations|advices|furnitures|equipments|knowledges|researches)\b",
        "substantivo incontável usado no plural",
        "information / advice / furniture / equipment / knowledge / research",
        "São incontáveis em inglês. Para contar, usa-se “a piece of advice”, "
        "“two pieces of information”.",
        "He gave me some good advices.",
        "He gave me some good advice.",
    ),
    PadraoDeTransferencia(
        "explain + objeto indireto sem 'to'",
        r"\bexplain(?:s|ed|ing)?\s+(?:(?:me|us)\b|(?:him|her|them)\s+(?:the|this|that|these|those|a|an|my|your|our|their|everything|something|why|how|what)\b)",
        "“explain” não aceita objeto indireto sem preposição",
        "explain something to someone",
        "Diferente de “tell me”, o verbo explain exige “to”: a estrutura "
        "“explain me this” não existe.",
        "Can you explain me this rule?",
        "Can you explain this rule to me?",
    ),
    PadraoDeTransferencia(
        "depend of",
        r"\bdepends?\s+of\b",
        "preposição errada",
        "depend on",
        "A regência aqui não acompanha o português: é sempre “depend on”.",
        "It depends of the weather.",
        "It depends on the weather.",
    ),
    PadraoDeTransferencia(
        "married with",
        r"\bmarried\s+with\b",
        "preposição errada",
        "married to",
        "“Casado com” em inglês é “married to”. “Married with” só aparece em "
        "“married with children”, que significa outra coisa.",
        "She is married with a doctor.",
        "She is married to a doctor.",
    ),
    PadraoDeTransferencia(
        "have + idade",
        r"\b([A-Za-z']+)\s+(have|has|had)\s+\d+\s+years?\s+old\b",
        "idade não se expressa com “have” em inglês",
        "be + número + years old",
        "Em português “ter 20 anos”, em inglês “be 20 years old”.",
        "I have 20 years old.",
        "I am 20 years old.",
    ),
    PadraoDeTransferencia(
        "double negative",
        r"\b(don't|doesn't|didn't|can't|won't)\s+\w+\s+(nothing|nobody|nowhere|never)\b",
        "dupla negação",
        "don't … anything / anybody / anywhere / ever",
        "O português aceita “não vi nada”; o inglês padrão não empilha negações.",
        "I didn't see nothing.",
        "I didn't see anything.",
    ),
    PadraoDeTransferencia(
        "since + período de tempo",
        r"\bsince\s+(?:\d+|a|an|one|two|three|four|five|six|seven|eight|nine|"
        r"ten|many|several|some|a few)\s+(?:years?|months?|weeks?|days?|hours?)\b(?!\s+ago)",
        "“since” marca ponto de partida, não duração",
        "for + duração / since + momento",
        "“for two years” (duração) × “since 2020” (ponto no tempo).",
        "I live here since three years.",
        "I have lived here for three years.",
    ),
    PadraoDeTransferencia(
        "pretend = fingir",
        r"\bpretend\s+to\s+(get|obtain|apply|study|work)\b",
        "falso cognato",
        "intend to / plan to",
        "“Pretend” significa fingir. “Pretender” é “intend” ou “plan”.",
        "I pretend to study abroad.",
        "I intend to study abroad.",
        "suspeita",
    ),
    PadraoDeTransferencia(
        "actually = na verdade",
        r"\bactually\b\s*,?\s+(?:i|we|he|she|they|you)\s+"
        r"(?:am|is|are|work|works|live|lives|study|studies)\b",
        "falso cognato",
        "currently / nowadays",
        "“Actually” quer dizer “na verdade”, não “atualmente”.",
        "Actually I work in a bank.",
        "Currently I work in a bank.",
        "suspeita",
    ),
)


def avaliar_estrutura(texto: str) -> list[Avaliacao]:
    """Detecta erros de transferência do português e avalia as construções."""
    import re

    if not texto or not texto.strip():
        return []

    avaliacoes: list[Avaliacao] = []
    for padrao in TRANSFERENCIAS:
        achado = re.search(padrao.padrao, texto, re.IGNORECASE)
        if not achado:
            continue
        suspeita = padrao.severidade == "suspeita"
        avaliacoes.append(Avaliacao(
            construcao=achado.group(0),
            grammaticality="ambíguo" if suspeita else "agramatical",
            meaning=padrao.problema + (
                " (esta construção também tem leitura correta — confira o "
                "sentido pretendido)" if suspeita else ""
            ),
            naturalness="depende do sentido" if suspeita else "soa traduzido",
            register="—",
            frequency="erro frequente entre falantes de português",
            alternativa_melhor=padrao.correcao,
            erro_tipico=padrao.porque,
            observacao=f"Errado: “{padrao.exemplo_errado}” · "
                       f"Certo: “{padrao.exemplo_certo}”",
            fonte="padrão de transferência do português",
        ))
    return avaliacoes
