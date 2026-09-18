"""Lexico minimo de apoio: genero, numero e classes fechadas.

Nao e um dicionario completo do portugues — e o conjunto de informacoes de
que os motores de crase e colocacao precisam para decidir. As heuristicas de
terminacao cobrem a maior parte dos casos; as listas cobrem as excecoes que
derrubariam a heuristica.
"""

from __future__ import annotations

from ..texto import normalizar

# Terminam em -a mas sao masculinos: a heuristica erraria em todos.
MASCULINOS_EM_A = {
    "problema", "sistema", "tema", "poema", "teorema", "esquema", "programa",
    "telefonema", "cinema", "clima", "dia", "mapa", "planeta", "cometa",
    "profeta", "atleta", "pijama", "sofa", "dilema", "enigma", "fantasma",
    "idioma", "sintoma", "trauma", "drama", "diagrama", "panorama", "aroma",
    "carisma", "magma", "plasma", "prisma", "dogma", "estratagema", "axioma",
    "paradigma", "cromossoma", "eczema", "grama", "lema", "dia-a-dia",
    "guarda-roupa", "guarda-chuva", "papa", "monarca", "patriarca", "colega",
}

# Nao terminam em -a mas sao femininos.
FEMININOS_FORA_DO_PADRAO = {
    "mao", "razao", "questao", "solucao", "acao", "opcao", "decisao", "visao",
    "sessao", "missao", "paixao", "tradicao", "condicao", "excecao", "regiao",
    "uniao", "reuniao", "eleicao", "estacao", "informacao", "educacao",
    "producao", "nacao", "ocasiao", "pressao", "impressao", "expressao",
    "lei", "fe", "foz", "cruz", "luz", "paz", "voz", "vez", "flor", "cor",
    "dor", "tarde", "noite", "arte", "parte", "morte", "sorte", "gente",
    "ponte", "fonte", "frente", "mente", "corrente", "classe", "base", "fase",
    "crase", "analise", "sintese", "tese", "chave", "nave", "ave", "nuvem",
    "viagem", "imagem", "garagem", "coragem", "origem", "margem", "vantagem",
    "linguagem", "mensagem", "paisagem", "homenagem", "vertigem", "virtude",
    "universidade", "cidade", "verdade", "liberdade", "saude", "juventude",
    "multidao", "prisao", "televisao", "diversao", "tensao", "extensao",
    "sede", "rede", "parede", "hepatite", "bronquite", "febre", "torre",
    "carne", "chave", "pele", "prole", "serie", "especie", "barbarie",
}

# Sufixos que indicam feminino com alta confianca.
SUFIXOS_FEMININOS = (
    "cao", "sao", "dade", "tude", "agem", "ice", "eza", "ez", "gem", "tude",
)

SUFIXOS_MASCULINOS = ("or", "ol", "al", "el", "il", "ul", "um", "im", "om", "ao")

PRONOMES_PESSOAIS = {
    "eu", "tu", "ele", "ela", "nos", "vos", "eles", "elas", "mim", "ti", "si",
    "voce", "voces", "comigo", "contigo", "consigo", "conosco", "convosco",
    "me", "te", "se", "lhe", "lhes", "nos", "vos", "o", "a", "os", "as",
}

PRONOMES_DEMONSTRATIVOS_SEM_CRASE = {
    "esta", "estas", "essa", "essas", "isto", "isso", "este", "estes",
    "esse", "esses",
}

PRONOMES_INDEFINIDOS = {
    "alguma", "algumas", "nenhuma", "nenhumas", "qualquer", "quaisquer",
    "cada", "tal", "tais", "certa", "certas", "outra", "outras", "toda",
    "todas", "muita", "muitas", "pouca", "poucas", "varias", "algum",
    "nenhum", "todo", "todos", "outro", "outros",
}

PRONOMES_TRATAMENTO = {
    "vossa", "vossas", "sua", "vossemece", "excelencia", "senhoria",
    "majestade", "eminencia", "santidade", "alteza", "reverendissima",
    "magnificencia", "meritissima",
}

POSSESSIVOS_FEMININOS = {"minha", "tua", "sua", "nossa", "vossa", "minhas",
                         "tuas", "suas", "nossas", "vossas"}

# Palavras que costumam aparecer repetidas em locuções sem crase.
REPETIVEIS = {
    "cara", "gota", "dia", "face", "frente", "lado", "ponta", "passo", "uma",
    "hora", "bocado", "pouco", "corpo", "olho", "ombro", "peito", "boca",
}


def normalizado(palavra: str) -> str:
    return normalizar(palavra).strip(" .,;:!?()[]\"'")


def e_plural(palavra: str) -> bool:
    alvo = normalizado(palavra)
    if len(alvo) < 3:
        return False
    return alvo.endswith(("s", "ns", "es", "is")) and not alvo.endswith(("as vezes",))


def genero(palavra: str) -> str:
    """Devolve 'feminino', 'masculino' ou 'indeterminado'."""
    alvo = normalizado(palavra)
    if not alvo:
        return "indeterminado"

    singular = alvo[:-1] if alvo.endswith("s") and len(alvo) > 3 else alvo

    if singular in MASCULINOS_EM_A or alvo in MASCULINOS_EM_A:
        return "masculino"
    if singular in FEMININOS_FORA_DO_PADRAO or alvo in FEMININOS_FORA_DO_PADRAO:
        return "feminino"
    if singular.endswith(SUFIXOS_FEMININOS):
        return "feminino"
    if singular.endswith("a"):
        return "feminino"
    if singular.endswith(SUFIXOS_MASCULINOS) or singular.endswith("o"):
        return "masculino"
    return "indeterminado"


def e_verbo_no_infinitivo(palavra: str) -> bool:
    alvo = normalizado(palavra)
    return len(alvo) > 3 and alvo.endswith(("ar", "er", "ir", "or"))


def e_numeral_cardinal(palavra: str) -> bool:
    alvo = normalizado(palavra).replace(".", "").replace(",", "")
    if alvo.isdigit():
        return True
    return alvo in {
        "um", "dois", "tres", "quatro", "cinco", "seis", "sete", "oito",
        "nove", "dez", "onze", "doze", "vinte", "trinta", "cem", "mil",
    }
