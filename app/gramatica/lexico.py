"""Lexico minimo de apoio: genero, numero e classes fechadas.

Nao e um dicionario completo do portugues — e o conjunto de informacoes de
que os motores de crase e colocacao precisam para decidir. As heuristicas de
terminacao cobrem a maior parte dos casos; as listas cobrem as excecoes que
derrubariam a heuristica.

Principio de projeto: quando a evidencia nao basta, devolver
``indeterminado`` em vez de chutar. Um chute errado vira um veredito
gramatical errado, que e muito pior do que um "nao sei" honesto.
"""

from __future__ import annotations

from ..texto import normalizar

# Terminam em -a mas sao masculinos: a heuristica erraria em todos.
# So entram aqui palavras de genero masculino FIXO. Palavras comuns de dois
# generos (o/a colega) ficam em COMUNS_DE_DOIS.
MASCULINOS_EM_A = {
    "problema", "sistema", "tema", "poema", "teorema", "esquema", "programa",
    "telefonema", "cinema", "clima", "dia", "mapa", "planeta", "cometa",
    "profeta", "pijama", "sofa", "dilema", "enigma", "fantasma",
    "idioma", "sintoma", "trauma", "drama", "diagrama", "panorama", "aroma",
    "carisma", "magma", "plasma", "prisma", "dogma", "estratagema", "axioma",
    "paradigma", "cromossoma", "eczema", "lema", "dia-a-dia",
    "guarda-roupa", "guarda-chuva", "papa", "patriarca", "fonema", "morfema",
    "lexema", "estigma", "charisma", "aneurisma", "carcinoma", "linfoma",
    "diafragma", "anagrama", "telegrama", "holograma", "pentagrama",
}

# Comuns de dois generos: o artigo decide, nao a palavra. Devolver um genero
# fixo aqui produzia vereditos errados ("o colega" tratado como feminino).
COMUNS_DE_DOIS = {
    "colega", "atleta", "artista", "jornalista", "dentista", "motorista",
    "estudante", "cliente", "gerente", "agente", "monarca", "camarada",
    "imigrante", "emigrante", "interprete", "personagem", "indigena",
    "martir", "selvagem", "jovem", "cientista", "especialista", "pianista",
    "violinista", "protagonista", "antagonista", "suicida", "homicida",
    "guia", "vigia", "herege", "colegial", "doente", "paciente", "parente",
    "adolescente", "estagiario", "recruta", "reporter", "pediatra",
    "psiquiatra", "dermatologista", "fisioterapeuta", "terapeuta",
    # Homografos com generos diferentes: "o grama" (peso) x "a grama" (relva).
    "grama", "cabeca", "capital", "caixa", "guarda", "moral", "radio",
    "policia", "cura", "lente",
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
    "carne", "pele", "prole", "serie", "especie", "barbarie",
    # Terminam em -o mas sao femininas.
    "tribo", "foto", "moto", "libido", "virago", "nau",
    # Terminam em consoante e sao femininas.
    "mulher", "colher", "cor", "pior", "matriz", "raiz", "perdiz", "codorniz",
    "nuvem", "ordem", "margem", "virgem", "imagem", "garagem", "bagagem",
}

# Sufixos que indicam feminino com alta confianca.
SUFIXOS_FEMININOS = (
    "cao", "sao", "dade", "tude", "agem", "ice", "eza", "ez", "gem",
)

# Excecoes masculinas aos sufixos acima: terminam em -cao/-sao/-gem e sao
# masculinas. Sem esta lista, "coracao" e "balcao" viravam femininos.
MASCULINOS_APESAR_DO_SUFIXO = {
    "coracao", "balcao", "calcao", "falcao", "bracao", "portao", "cartao",
    "caldeirao", "personagem", "vendaval",
}

SUFIXOS_MASCULINOS = ("or", "ol", "al", "el", "il", "ul", "um", "im", "om", "ao")

# Terminam em -a tonico (cha, sofa, alvara): quase sempre masculinos. A
# normalizacao remove o acento, entao o teste precisa ver a forma original.
FEMININOS_EM_A_TONICO = {"pa", "la", "ma", "xa", "fa"}

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

# Pronomes de tratamento que rejeitam artigo (Vossa Excelencia, Sua Senhoria).
# "sua" sozinho NAO entra: e possessivo comum ("a sua casa" e correto) e a
# presenca dele aqui bloqueava a regra da crase facultativa.
PRONOMES_TRATAMENTO = {
    "vossa", "vossas", "vossemece", "excelencia", "senhoria",
    "majestade", "eminencia", "santidade", "alteza", "reverendissima",
    "magnificencia", "meritissima",
}

# Sequencias que realmente formam tratamento: "sua" so conta seguido de um
# nucleo de tratamento.
NUCLEOS_DE_TRATAMENTO = {
    "excelencia", "senhoria", "majestade", "eminencia", "santidade",
    "alteza", "reverendissima", "magnificencia", "meritissima", "graca",
}

POSSESSIVOS_FEMININOS = {"minha", "tua", "sua", "nossa", "vossa", "minhas",
                         "tuas", "suas", "nossas", "vossas"}

# Palavras que costumam aparecer repetidas em locuções sem crase.
REPETIVEIS = {
    "cara", "gota", "dia", "face", "frente", "lado", "ponta", "passo", "uma",
    "hora", "bocado", "pouco", "corpo", "olho", "ombro", "peito", "boca",
}

# Substantivos terminados em -ar/-er/-ir que a heuristica de infinitivo
# confundiria com verbos. "Refiro-me a mulher" nao tem verbo depois do "a".
SUBSTANTIVOS_EM_R = {
    "mulher", "colher", "talher", "qualquer", "lugar", "ar", "mar", "altar",
    "bar", "colar", "pomar", "militar", "familiar", "celular", "escolar",
    "popular", "particular", "auxiliar", "similar", "regular", "titular",
    "dolar", "acucar", "nectar", "jaguar", "nuclear", "linear", "palmar",
    "hospitalar", "exemplar", "vulgar", "singular", "circular", "espetacular",
    "elementar", "alimentar", "complementar", "suplementar", "parlamentar",
    "polar", "solar", "lunar", "estelar", "molecular", "muscular", "ocular",
    "peculiar", "secular", "vegetal", "andar", "paladar", "colegial",
    "caractere", "carater", "mister", "poder", "dever", "prazer", "afazer",
    "amanhecer", "anoitecer", "entardecer", "parecer", "haver",
}

# Infinitivos de alta frequencia. A lista existe para decidir -er/-ir/-or,
# onde a terminacao sozinha nao distingue verbo de substantivo.
VERBOS_COMUNS = {
    # -ar (amostra; o padrao -ar e produtivo e tratado por heuristica)
    "estar", "dar", "falar", "olhar", "achar", "ficar", "chamar", "deixar",
    "passar", "levar", "contar", "pensar", "voltar", "tomar", "trabalhar",
    "chegar", "encontrar", "comecar", "usar", "tratar", "mostrar", "acabar",
    "entrar", "continuar", "estudar", "ensinar", "aprender", "explicar",
    "calcular", "somar", "multiplicar", "dividir", "verificar", "analisar",
    "resolver", "demonstrar", "provar", "aplicar", "comparar", "observar",
    "assistir", "aspirar", "visar", "implicar", "obedecer", "perdoar",
    "informar", "avisar", "convidar", "preferir", "namorar", "custar",
    "agradar", "aludir", "proceder", "responder", "esquecer", "lembrar",
    # -er
    "ser", "ter", "fazer", "dizer", "poder", "saber", "querer", "ver",
    "viver", "conhecer", "correr", "beber", "comer", "vender", "perder",
    "escrever", "receber", "trazer", "crescer", "morrer", "nascer", "valer",
    "caber", "doer", "mover", "remover", "promover", "escolher", "recolher",
    "acontecer", "oferecer", "merecer", "estabelecer", "pertencer", "vencer",
    "convencer", "sofrer", "entender", "atender", "pretender", "defender",
    "depender", "surpreender", "aparecer", "desaparecer", "reconhecer",
    "devolver", "envolver", "desenvolver", "percorrer", "socorrer", "ocorrer",
    # -ir
    "ir", "vir", "partir", "abrir", "sentir", "servir", "seguir", "conseguir",
    "pedir", "medir", "ouvir", "dormir", "sair", "cair", "subir", "fugir",
    "dirigir", "exigir", "atingir", "permitir", "admitir", "transmitir",
    "discutir", "produzir", "conduzir", "reduzir", "traduzir", "construir",
    "destruir", "influir", "incluir", "concluir", "substituir", "atribuir",
    "distribuir", "contribuir", "possuir", "insistir", "existir", "resistir",
    "consistir", "persistir", "repetir", "competir", "sugerir", "referir",
    "conferir", "transferir", "ferir", "advertir", "converter", "divertir",
    # -or
    "por", "supor", "compor", "dispor", "propor", "expor", "impor", "repor",
    "opor", "depor", "transpor",
}


def normalizado(palavra: str) -> str:
    return normalizar(palavra).strip(" .,;:!?()[]\"'")


def e_plural(palavra: str) -> bool:
    alvo = normalizado(palavra)
    if len(alvo) < 3:
        return False
    return alvo.endswith(("s", "ns", "es", "is")) and not alvo.endswith(("as vezes",))


def e_comum_de_dois(palavra: str) -> bool:
    """Palavra cujo genero depende do artigo, nao da terminacao."""
    alvo = normalizado(palavra)
    singular = alvo[:-1] if alvo.endswith("s") and len(alvo) > 3 else alvo
    return alvo in COMUNS_DE_DOIS or singular in COMUNS_DE_DOIS


def _termina_em_a_tonico(palavra: str) -> bool:
    """`cha`, `sofa`, `alvara`: o -a final e tonico e a palavra e masculina."""
    bruto = palavra.strip(" .,;:!?()[]\"'").lower()
    return len(bruto) > 2 and bruto.endswith(("á", "ã"))


def genero(palavra: str) -> str:
    """Devolve 'feminino', 'masculino' ou 'indeterminado'."""
    alvo = normalizado(palavra)
    if not alvo:
        return "indeterminado"

    singular = alvo[:-1] if alvo.endswith("s") and len(alvo) > 3 else alvo

    # Comum de dois generos: nenhuma terminacao decide.
    if alvo in COMUNS_DE_DOIS or singular in COMUNS_DE_DOIS:
        return "indeterminado"
    if singular in MASCULINOS_EM_A or alvo in MASCULINOS_EM_A:
        return "masculino"
    if singular in MASCULINOS_APESAR_DO_SUFIXO or alvo in MASCULINOS_APESAR_DO_SUFIXO:
        return "masculino"
    if singular in FEMININOS_FORA_DO_PADRAO or alvo in FEMININOS_FORA_DO_PADRAO:
        return "feminino"
    # "cha", "sofa", "alvara": -a tonico e marca de masculino.
    if _termina_em_a_tonico(palavra) and singular not in FEMININOS_EM_A_TONICO:
        return "masculino"
    if singular.endswith(SUFIXOS_FEMININOS):
        return "feminino"
    if singular.endswith("a"):
        return "feminino"
    if singular.endswith(SUFIXOS_MASCULINOS) or singular.endswith("o"):
        return "masculino"
    return "indeterminado"


# Um substantivo comum de dois generos nao diz o proprio genero, mas a frase
# em volta costuma dizer. Estas terminacoes marcam o adjetivo que concorda.
_FEM_ADJETIVO = ("a", "as", "ora", "oras", "esa", "esas", "ina", "inas")
_MASC_ADJETIVO = ("o", "os", "or", "ores", "es", "ao", "aos")

# Adverbios de intensidade ficam ENTRE o substantivo e o adjetivo ("colega
# muito nova"): passar por cima deles preserva a concordancia.
_INTENSIFICADORES = {
    "muito", "pouco", "bem", "bastante", "tao", "mais", "menos", "meio",
    "demasiado", "extremamente", "particularmente", "especialmente",
}


def genero_no_contexto(palavras: list[str], indice: int) -> str:
    """Genero da palavra na posicao `indice`, usando a frase para desempatar.

    Para comum de dois generos ("colega", "atleta", "jornalista"), a palavra
    sozinha nao decide — mas o adjetivo que a acompanha decide: "a colega
    nova", "a atleta vencedora". Sem esse apoio, devolve ``comum``, que e
    diferente de ``indeterminado``: aqui sabemos que a palavra ACEITA artigo
    feminino, so nao sabemos se e esse o caso.
    """
    if not 0 <= indice < len(palavras):
        return "indeterminado"
    palavra = palavras[indice]
    direto = genero(palavra)
    if not e_comum_de_dois(palavra):
        return direto

    for passo in (1, 2):
        if indice + passo >= len(palavras):
            break
        vizinha = normalizado(palavras[indice + passo])
        if not vizinha:
            break
        if vizinha in _INTENSIFICADORES:
            continue
        # Preposicao, conjuncao ou relativo fecham o sintagma: o que vem
        # depois e outro nucleo, nao um adjetivo que concorda com este.
        # Sem isso, "a colega de turma" concordava com "turma".
        if len(vizinha) < 3 or e_verbo_no_infinitivo(vizinha):
            break
        if vizinha.endswith(_FEM_ADJETIVO):
            return "feminino"
        if vizinha.endswith(_MASC_ADJETIVO):
            return "masculino"
        break
    return "comum"


def e_verbo_no_infinitivo(palavra: str) -> bool:
    """Reconhece infinitivos sem confundir substantivos como `mulher`.

    Conservador de proposito: um verbo nao reconhecido faz a analise cair no
    ramo de regencia (seguro); um substantivo tomado por verbo produz um
    veredito `proibida` sem recurso.
    """
    alvo = normalizado(palavra)
    if len(alvo) <= 3:
        return alvo in VERBOS_COMUNS
    if alvo in SUBSTANTIVOS_EM_R:
        return False
    if alvo in VERBOS_COMUNS:
        return True
    # -ar e a conjugacao produtiva do portugues: fora da lista de
    # substantivos conhecidos, uma palavra longa em -ar e quase sempre verbo.
    if alvo.endswith("ar") and len(alvo) > 4:
        return True
    return False


def e_numeral_cardinal(palavra: str) -> bool:
    alvo = normalizado(palavra).replace(".", "").replace(",", "")
    if alvo.isdigit():
        return True
    return alvo in {
        "um", "dois", "tres", "quatro", "cinco", "seis", "sete", "oito",
        "nove", "dez", "onze", "doze", "treze", "catorze", "quatorze",
        "quinze", "dezesseis", "dezessete", "dezoito", "dezenove",
        "vinte", "trinta", "quarenta", "cinquenta", "sessenta", "setenta",
        "oitenta", "noventa", "cem", "mil",
    }


def e_tratamento(palavras: list[str], indice: int) -> bool:
    """`Vossa Excelencia` conta; `sua casa` nao."""
    atual = normalizado(palavras[indice]) if 0 <= indice < len(palavras) else ""
    if atual in PRONOMES_TRATAMENTO and atual not in {"sua", "suas"}:
        return True
    if atual in {"sua", "suas", "vossa", "vossas"}:
        seguinte = normalizado(palavras[indice + 1]) if indice + 1 < len(palavras) else ""
        return seguinte in NUCLEOS_DE_TRATAMENTO
    return False
