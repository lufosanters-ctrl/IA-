"""Regencia verbal e nominal: o verbo sozinho nao decide nada.

O erro mais comum em questao de regencia e consultar o verbo e parar por ai.
"Assistir" nao tem UMA regencia: tem uma por sentido. O caminho correto e

    VERBO → SENTIDO → TRANSITIVIDADE → PREPOSICAO → COMPLEMENTO

e e exatamente essa cadeia que esta codificada aqui. Cada verbo guarda seus
sentidos, e cada sentido guarda a sua propria regencia, com exemplo.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from ..texto import normalizar


@dataclass(frozen=True, slots=True)
class Sentido:
    """Um sentido do verbo e a regencia que ele exige NESSE sentido."""

    sentido: str
    transitividade: str          # direto | indireto | direto e indireto | intransitivo
    preposicoes: tuple[str, ...]
    exemplo: str
    observacao: str = ""

    @property
    def exige_a(self) -> bool:
        """Este sentido rege a preposicao 'a'? (condicao necessaria da crase)"""
        return "a" in self.preposicoes

    def para_dict(self) -> dict[str, Any]:
        return {
            "sentido": self.sentido,
            "transitividade": self.transitividade,
            "preposicoes": list(self.preposicoes),
            "exemplo": self.exemplo,
            "observacao": self.observacao,
            "exige_a": self.exige_a,
        }


def _s(sentido: str, transitividade: str, preposicoes: str, exemplo: str,
       observacao: str = "") -> Sentido:
    preps = tuple(p.strip() for p in preposicoes.split("/") if p.strip())
    return Sentido(sentido, transitividade, preps, exemplo, observacao)


# --------------------------------------------------------------------------
# Regencia verbal
# --------------------------------------------------------------------------

REGENCIA_VERBAL: dict[str, tuple[Sentido, ...]] = {
    "assistir": (
        _s("ver, presenciar", "indireto", "a", "Assisti ao filme ontem.",
           "É o sentido cobrado na maioria das provas: exige a preposição 'a'."),
        _s("prestar assistência, socorrer", "direto", "",
           "O médico assistiu o paciente."),
        _s("caber, pertencer (direito)", "indireto", "a",
           "Assiste ao réu o direito de defesa."),
        _s("morar, residir", "indireto", "em", "Assisto em Belo Horizonte.",
           "Uso hoje raro e de registro formal."),
    ),
    "aspirar": (
        _s("desejar, almejar", "indireto", "a", "Aspirava ao cargo de diretor.",
           "Neste sentido não se usa pronome oblíquo 'o/a': diz-se 'aspirava a ele'."),
        _s("sorver, inalar", "direto", "", "Aspirou o perfume das flores."),
    ),
    "visar": (
        _s("ter em vista, objetivar", "indireto", "a",
           "A medida visa ao controle da inflação.",
           "Com infinitivo, a preposição é facultativa: 'visa (a) reduzir custos'."),
        _s("mirar, apontar", "direto", "", "O atirador visou o alvo."),
        _s("dar visto, autenticar", "direto", "", "O gerente visou o cheque."),
    ),
    "implicar": (
        _s("acarretar, ter como consequência", "direto", "",
           "O atraso implicou prejuízo.",
           "Na norma-padrão não leva 'em': 'implicou prejuízo', não 'implicou em prejuízo'."),
        _s("envolver, comprometer", "direto e indireto", "em",
           "Implicaram o funcionário no desvio."),
        _s("ter implicância", "indireto", "com", "Vive implicando com o irmão."),
    ),
    "proceder": (
        _s("ter fundamento", "intransitivo", "", "A denúncia não procede."),
        _s("originar-se, provir", "indireto", "de", "O trem procede de Salvador."),
        _s("dar início, realizar", "indireto", "a",
           "A comissão procedeu à leitura dos nomes."),
        _s("comportar-se", "intransitivo", "", "Procedeu bem durante a prova."),
    ),
    "obedecer": (
        _s("acatar", "indireto", "a", "Obedeça aos sinais de trânsito.",
           "Apesar de indireto, admite voz passiva: 'as ordens foram obedecidas'."),
    ),
    "desobedecer": (
        _s("não acatar", "indireto", "a", "Desobedeceu às normas da escola."),
    ),
    "pagar": (
        _s("quitar (a coisa)", "direto", "", "Paguei a conta."),
        _s("remunerar (a pessoa)", "indireto", "a", "Paguei ao garçom.",
           "Coisa: objeto direto. Pessoa: objeto indireto. Pode reunir os dois: "
           "'paguei a conta ao garçom'."),
    ),
    "perdoar": (
        _s("desculpar (a falta)", "direto", "", "Perdoou a ofensa."),
        _s("desculpar (a pessoa)", "indireto", "a", "Perdoou ao amigo."),
    ),
    "preferir": (
        _s("escolher entre dois", "direto e indireto", "a",
           "Prefiro cinema a teatro.",
           "Na norma-padrão não se usa 'do que', nem reforço como 'muito', "
           "'mais' ou 'antes': basta 'prefiro X a Y'."),
    ),
    "esquecer": (
        _s("não lembrar (sem pronome)", "direto", "", "Esqueci o compromisso."),
        _s("não lembrar (pronominal)", "indireto", "de",
           "Esqueci-me do compromisso.",
           "Com o pronome, exige 'de'; sem o pronome, é direto."),
    ),
    "lembrar": (
        _s("trazer à memória (sem pronome)", "direto", "", "Lembrei o compromisso."),
        _s("trazer à memória (pronominal)", "indireto", "de",
           "Lembrei-me do compromisso."),
        _s("avisar, fazer recordar", "direto e indireto", "a",
           "Lembrei ao chefe o prazo."),
    ),
    "custar": (
        _s("ser difícil, demorar", "indireto", "a",
           "Custou-me acreditar naquilo.",
           "Sujeito é a oração ('acreditar naquilo'); a pessoa é objeto indireto. "
           "Portanto não se diz 'eu custei a acreditar' na norma-padrão."),
        _s("ter determinado preço", "direto", "", "O livro custou quarenta reais."),
        _s("acarretar, causar", "direto e indireto", "a",
           "A imprudência custou-lhe o emprego."),
    ),
    "namorar": (
        _s("manter namoro", "direto", "", "Namora uma colega de turma.",
           "Na norma-padrão não leva 'com': 'namora uma colega'."),
    ),
    "chamar": (
        _s("convocar, fazer vir", "direto", "", "Chamei o técnico."),
        _s("dar nome, apelidar", "direto e indireto", "a",
           "Chamaram-no de herói. / Chamaram-lhe herói.",
           "Quatro construções são aceitas: 'chamaram-no herói', 'chamaram-no de "
           "herói', 'chamaram-lhe herói', 'chamaram-lhe de herói'."),
        _s("invocar", "indireto", "por", "Chamava por socorro."),
    ),
    "agradar": (
        _s("fazer carinho, acariciar", "direto", "", "Agradou o gato."),
        _s("satisfazer, ser agradável a", "indireto", "a",
           "O resultado não agradou aos torcedores."),
    ),
    "querer": (
        _s("desejar", "direto", "", "Quero um café."),
        _s("estimar, ter afeto", "indireto", "a", "Quero muito aos meus pais."),
    ),
    "simpatizar": (
        _s("ter simpatia", "indireto", "com", "Simpatizo com a proposta.",
           "Não é pronominal: não existe 'simpatizar-se com'."),
    ),
    "antipatizar": (
        _s("não ter simpatia", "indireto", "com", "Antipatizo com aquele discurso.",
           "Também não é pronominal."),
    ),
    "responder": (
        _s("dar resposta", "indireto", "a", "Respondeu ao questionário.",
           "Admite voz passiva analítica: 'o questionário foi respondido'."),
    ),
    "atender": (
        _s("dar atenção a, acolher pedido", "indireto", "a", "Atendeu ao pedido."),
        _s("receber, servir (pessoa)", "direto", "", "O médico atendeu o paciente."),
    ),
    "presidir": (
        _s("dirigir", "direto e indireto", "a", "Presidiu a sessão. / Presidiu à sessão.",
           "Ambas as construções são registradas pelos gramáticos."),
    ),
    "informar": (
        _s("dar conhecimento", "direto e indireto", "a/de",
           "Informou o resultado aos alunos. / Informou os alunos do resultado.",
           "Bitransitivo: a coisa e a pessoa trocam de função conforme a construção."),
    ),
    "avisar": (
        _s("dar aviso", "direto e indireto", "a/de",
           "Avisei o professor da mudança. / Avisei a mudança ao professor."),
    ),
    "aludir": (
        _s("fazer alusão, referir-se", "indireto", "a", "Aludiu ao episódio anterior."),
    ),
    "referir": (
        _s("fazer referência (pronominal)", "indireto", "a",
           "Referiu-se ao artigo publicado."),
    ),
    "consistir": (
        _s("ser constituído", "indireto", "em", "O prêmio consiste em uma bolsa.",
           "Na norma-padrão, 'em' — não 'de'."),
    ),
    "constar": (
        _s("ser composto", "indireto", "de", "O livro consta de dez capítulos."),
        _s("estar registrado", "indireto", "em", "Consta em ata."),
    ),
    "depender": (_s("estar condicionado", "indireto", "de", "Depende de você."),),
    "gostar": (_s("apreciar", "indireto", "de", "Gosta de música clássica."),),
    "precisar": (
        _s("ter necessidade", "indireto", "de", "Preciso de ajuda."),
        _s("determinar com exatidão", "direto", "", "O laudo precisou a hora do fato."),
    ),
    "confiar": (
        _s("ter confiança", "indireto", "em", "Confio em você."),
        _s("entregar aos cuidados", "direto e indireto", "a",
           "Confiou o segredo ao amigo."),
    ),
    "deparar": (
        _s("encontrar por acaso", "indireto", "com", "Deparou com um obstáculo.",
           "Também se registra 'deparou-se com'."),
    ),
    "versar": (_s("tratar de", "indireto", "sobre", "A prova versou sobre sintaxe."),),
    "interceder": (
        _s("pedir em favor de", "indireto", "por", "Intercedeu por seu aluno."),
    ),
    "incidir": (_s("recair", "indireto", "em/sobre", "O imposto incide sobre a renda."),),
    "ir": (
        _s("deslocar-se para", "indireto", "a/para", "Fui ao mercado.",
           "'a' para permanência breve, 'para' para permanência definitiva. "
           "Na norma-padrão não se usa 'em': 'fui ao médico', não 'fui no médico'."),
    ),
    "chegar": (
        _s("atingir um lugar", "indireto", "a", "Cheguei ao aeroporto.",
           "Também não admite 'em' na norma-padrão."),
    ),
    "morar": (_s("residir", "indireto", "em", "Moro em Recife."),),
    "residir": (_s("ter residência", "indireto", "em", "Reside em Curitiba."),),
    "assistir_nota": (),
    "sobressair": (
        _s("destacar-se", "intransitivo", "", "Sobressaiu entre os candidatos.",
           "A forma pronominal 'sobressair-se' é condenada pela norma-padrão."),
    ),
    "obstar": (_s("impedir", "indireto", "a", "Nada obsta ao seguimento do processo."),),
    "anuir": (_s("concordar", "indireto", "a", "Anuiu ao pedido."),),
    "assentir": (_s("consentir", "indireto", "a/em", "Assentiu ao convite."),),
    "convidar": (
        _s("chamar para participar", "direto e indireto", "para/a",
           "Convidou os amigos para a festa."),
    ),
    "esquivar": (_s("evitar (pronominal)", "indireto", "de", "Esquivou-se da pergunta."),),
    "imbuir": (_s("impregnar", "direto e indireto", "de", "Imbuiu-se de coragem."),),
    "vigiar": (_s("observar, guardar", "direto", "", "Vigiava a entrada."),),
    "suceder": (
        _s("vir depois", "indireto", "a", "A calmaria sucedeu à tempestade."),
        _s("acontecer", "intransitivo", "", "Sucedeu um imprevisto."),
    ),
    "sobrevir": (_s("acontecer depois", "indireto", "a", "Sobreveio-lhe uma crise."),),
}

# --------------------------------------------------------------------------
# Regencia nominal
# --------------------------------------------------------------------------

REGENCIA_NOMINAL: dict[str, tuple[str, ...]] = {
    "acessível": ("a",),
    "acostumado": ("a", "com"),
    "afável": ("com", "para com"),
    "aflito": ("com", "por"),
    "alheio": ("a",),
    "análogo": ("a",),
    "ansioso": ("por", "de"),
    "apto": ("a", "para"),
    "ávido": ("de", "por"),
    "benéfico": ("a",),
    "capaz": ("de", "para"),
    "compatível": ("com",),
    "contrário": ("a",),
    "curioso": ("de", "por"),
    "desejoso": ("de",),
    "diferente": ("de",),
    "dúvida": ("em", "sobre", "acerca de"),
    "essencial": ("a", "para"),
    "favorável": ("a",),
    "fiel": ("a",),
    "generoso": ("com", "para com"),
    "grato": ("a", "por"),
    "hábil": ("em",),
    "horror": ("a",),
    "imune": ("a", "de"),
    "inerente": ("a",),
    "insensível": ("a",),
    "leal": ("a",),
    "necessário": ("a", "para"),
    "nocivo": ("a",),
    "obediência": ("a",),
    "ojeriza": ("a", "por"),
    "paralelo": ("a",),
    "passível": ("de",),
    "preferência": ("a", "por"),
    "preferível": ("a",),
    "prejudicial": ("a",),
    "próximo": ("a", "de"),
    "propenso": ("a",),
    "próprio": ("de", "para"),
    "respeito": ("a", "com", "para com", "por"),
    "sensível": ("a",),
    "situado": ("em", "entre"),
    "suscetível": ("de", "a"),
    "útil": ("a", "para"),
    "versado": ("em",),
}


# --------------------------------------------------------------------------
# Consulta
# --------------------------------------------------------------------------

def consultar_verbo(verbo: str) -> tuple[Sentido, ...]:
    """Todos os sentidos registrados para um verbo, pelo infinitivo."""
    return REGENCIA_VERBAL.get(normalizar(verbo).strip(), ())


def consultar_nome(nome: str) -> tuple[str, ...]:
    """Preposicoes que um nome (substantivo ou adjetivo) costuma reger."""
    alvo = normalizar(nome).strip()
    for chave, preposicoes in REGENCIA_NOMINAL.items():
        if normalizar(chave) == alvo:
            return preposicoes
    return ()


# Terminações que os verbos assumem ao serem conjugados. A lista é ampla de
# propósito: aqui o objetivo é DETECTAR que o verbo aparece na frase, não
# fazer análise morfológica completa.
_TERMINACOES = (
    "ar", "er", "ir", "or", "o", "a", "e", "as", "es", "am", "em", "ou", "eu", "iu",
    "amos", "emos", "imos", "aram", "eram", "iram", "ava", "avam", "ia", "iam",
    "ei", "i", "ando", "endo", "indo", "ado", "ido", "ara", "era", "ira",
    "aria", "eria", "iria", "asse", "esse", "isse", "assem", "essem", "issem",
    "ará", "erá", "irá", "arão", "erão", "irão", "arem", "erem", "irem",
    "ou-se", "am-se", "a-se", "e-se",
)


# Verbos irregulares nao se deixam achar pelo radical: "ir" nao aparece em
# "vou", "foi" nem "vá". Para esses, as formas vao listadas.
FORMAS_IRREGULARES: dict[str, tuple[str, ...]] = {
    "ir": ("vou", "vais", "vai", "vamos", "ides", "vao", "ia", "ias", "iamos",
           "iam", "fui", "foste", "foi", "fomos", "foram", "irei", "iras",
           "ira", "iremos", "irao", "iria", "iriam", "va", "vas", "vamos",
           "indo", "ido", "fosse", "fossem", "for", "forem"),
    "querer": ("quero", "queres", "quer", "queremos", "querem", "queria",
               "queriam", "quis", "quiseste", "quisemos", "quiseram",
               "quererei", "querera", "quereria", "queira", "queiram",
               "quisesse", "quisessem", "querendo", "querido"),
    "referir": ("refiro", "referes", "refere", "referimos", "referem",
                "referia", "referiam", "referi", "referiu", "referiram",
                "refira", "refiram", "referindo", "referido"),
    "preferir": ("prefiro", "preferes", "prefere", "preferimos", "preferem",
                 "preferia", "preferiam", "preferi", "preferiu", "preferiram",
                 "prefira", "prefiram", "preferindo", "preferido"),
    "ver": ("vejo", "ves", "ve", "vemos", "veem", "via", "viam", "vi", "viu",
            "vimos", "viram", "verei", "vera", "veria", "veja", "vejam",
            "visse", "vissem", "vendo", "visto"),
    "vir": ("venho", "vens", "vem", "vimos", "vindes", "veem", "vinha",
            "vinham", "vim", "veio", "viemos", "vieram", "virei", "vira",
            "viria", "venha", "venham", "viesse", "viessem", "vindo"),
    "ter": ("tenho", "tens", "tem", "temos", "tendes", "tem", "tinha",
            "tinham", "tive", "teve", "tivemos", "tiveram", "terei", "tera",
            "teria", "tenha", "tenham", "tivesse", "tivessem", "tendo", "tido"),
    "poder": ("posso", "podes", "pode", "podemos", "podem", "podia", "podiam",
              "pude", "pode", "pudemos", "puderam", "poderei", "podera",
              "poderia", "possa", "possam", "pudesse", "pudessem", "podendo"),
}

def _variantes_do_radical(radical: str) -> set[str]:
    """Variantes ortográficas que o radical assume ao ser conjugado.

    A ortografia muda para preservar o som: cheg- vira chegu- em "cheguei",
    fic- vira fiqu- em "fiquei", obedec- vira obedeç- em "obedeço". Sem essas
    variantes, a detecção perde justamente as formas mais usadas.
    """
    variantes = {radical}
    if radical.endswith("c"):
        variantes.add(radical[:-1] + "ç")
        variantes.add(radical[:-1] + "qu")
    if radical.endswith("g"):
        variantes.add(radical + "u")
        variantes.add(radical[:-1] + "j")
    if radical.endswith("ç"):
        variantes.add(radical[:-1] + "c")
    return variantes


@lru_cache(maxsize=256)
def _padrao_do_verbo(infinitivo: str) -> re.Pattern[str]:
    """Regex que casa o verbo pelo radical, pelas variantes e pelas irregulares."""
    radical = infinitivo[:-2] if len(infinitivo) > 3 else infinitivo
    terminacoes = "|".join(
        sorted(map(re.escape, _TERMINACOES), key=len, reverse=True)
    )
    alternativas = [
        rf"{re.escape(variante)}(?:{terminacoes})?"
        for variante in sorted(_variantes_do_radical(radical), key=len, reverse=True)
    ]
    alternativas += [
        re.escape(forma) for forma in FORMAS_IRREGULARES.get(infinitivo, ())
    ]
    return re.compile(rf"\b(?:{'|'.join(alternativas)})\b", re.IGNORECASE)


def verbos_na_frase(frase: str) -> list[tuple[str, tuple[Sentido, ...]]]:
    """Verbos de regência problemática presentes na frase.

    A detecção é por radical, então é generosa: prefere apontar um verbo que
    talvez não esteja ali a deixar passar um que está. Quem decide o sentido é
    o estudante — e é justamente essa a pergunta que o tutor precisa fazer.
    """
    texto = normalizar(frase)
    achados: list[tuple[str, tuple[Sentido, ...]]] = []
    for infinitivo, sentidos in REGENCIA_VERBAL.items():
        if not sentidos:
            continue
        if _padrao_do_verbo(infinitivo).search(texto):
            achados.append((infinitivo, sentidos))
    return achados


def nomes_na_frase(frase: str) -> list[tuple[str, tuple[str, ...]]]:
    """Nomes de regência cobrada em prova presentes na frase."""
    texto = normalizar(frase)
    achados: list[tuple[str, tuple[str, ...]]] = []
    for nome, preposicoes in REGENCIA_NOMINAL.items():
        alvo = normalizar(nome)
        if re.search(rf"\b{re.escape(alvo)}(?:s|es|a|as)?\b", texto):
            achados.append((nome, preposicoes))
    return achados


# --------------------------------------------------------------------------
# Conferencia: o dicionario acima diz o que o verbo PEDE; esta parte compara
# com o que a frase REALMENTE usou.
# --------------------------------------------------------------------------

# Como cada preposicao aparece de fato no texto, ja contraida com artigo.
CONTRACOES: dict[str, str] = {
    "a": "a", "ao": "a", "aos": "a", "à": "a", "às": "a", "a": "a",
    "de": "de", "do": "de", "da": "de", "dos": "de", "das": "de",
    "dele": "de", "dela": "de", "deste": "de", "desta": "de", "desse": "de",
    "dessa": "de", "daquele": "de", "daquela": "de", "disso": "de", "disto": "de",
    "em": "em", "no": "em", "na": "em", "nos": "em", "nas": "em",
    "num": "em", "numa": "em", "nele": "em", "nela": "em", "neste": "em",
    "nesta": "em", "nesse": "em", "nessa": "em", "naquele": "em", "nisso": "em",
    "com": "com", "comigo": "com", "contigo": "com", "conosco": "com",
    "por": "por", "pelo": "por", "pela": "por", "pelos": "por", "pelas": "por",
    "para": "para", "pra": "para", "pro": "para", "pras": "para",
    "sobre": "sobre", "sob": "sob", "ante": "ante", "apos": "apos",
    "ate": "ate", "contra": "contra", "desde": "desde", "entre": "entre",
    "perante": "perante", "sem": "sem", "tras": "tras",
}

# Artigos e demonstrativos SEM preposicao embutida: a presenca de um deles
# logo depois do verbo indica objeto direto — e portanto preposicao ausente.
# Substantivos que dispensam artigo por natureza: depois deles o "a" sem
# acento pode ser a preposicao sozinha. "Cheguei a casa" esta correto.
SEM_ARTIGO_POR_NATURAL = {
    "casa", "terra", "bordo", "missa", "palacio", "domicilio", "bordo",
    "roma", "portugal", "israel", "paris", "belem", "salvador", "recife",
}

ARTIGOS_NUS = {
    "o", "a", "os", "as", "um", "uma", "uns", "umas",
    "este", "esta", "estes", "estas", "esse", "essa", "esses", "essas",
    "aquele", "aquela", "aqueles", "aquelas", "meu", "minha", "seu", "sua",
    "nosso", "nossa", "teu", "tua",
}

# Verbos curtos demais para a deteccao por radical ser confiavel.
_CURTOS_DEMAIS = {"ir", "ver", "ter", "vir", "por"}

_RE_TOKEN = re.compile(r"[0-9A-Za-zÀ-ÿ][0-9A-Za-zÀ-ÿ'-]*")


# Como cada problema aparece para o estudante. O identificador interno fica
# sem acento por conveniencia de codigo; o rotulo, nao.
ROTULOS_DE_PROBLEMA = {
    "preposicao ausente": "falta a preposição",
    "preposicao trocada": "preposição trocada",
    "preposicao a mais": "preposição a mais",
    "reforco indevido": "reforço indevido",
}


@dataclass(frozen=True, slots=True)
class DesvioRegencia:
    """Uma regencia que a frase usou de forma diferente da registrada."""

    verbo: str
    forma_usada: str
    preposicao_usada: str
    preposicoes_esperadas: tuple[str, ...]
    problema: str
    explicacao: str
    sugestao: str
    exemplo: str

    @property
    def rotulo(self) -> str:
        return ROTULOS_DE_PROBLEMA.get(self.problema, self.problema)

    def para_dict(self) -> dict[str, Any]:
        return {
            "verbo": self.verbo,
            "rotulo": self.rotulo,
            "forma_usada": self.forma_usada,
            "preposicao_usada": self.preposicao_usada,
            "preposicoes_esperadas": list(self.preposicoes_esperadas),
            "problema": self.problema,
            "explicacao": self.explicacao,
            "sugestao": self.sugestao,
            "exemplo": self.exemplo,
        }


def _preposicao_do_token(bruto: str) -> str:
    """A preposicao que este token carrega, ja desfeita a contracao."""
    limpo = bruto.lower().strip(" .,;:!?()[]\"'")
    # "à/às" so existem com preposicao dentro; "a/as" sem acento sao artigo.
    if limpo in {"à", "às", "àquele", "àquela", "àqueles", "àquelas", "àquilo"}:
        return "a"
    chave = normalizar(limpo)
    if chave in ARTIGOS_NUS:
        return ""
    return CONTRACOES.get(chave, "")


def conferir_regencia(frase: str) -> list[DesvioRegencia]:
    """Compara a preposicao usada na frase com a que o verbo exige.

    Conservador de proposito: so acusa desvio em verbo de sentido unico no
    dicionario. Verbo polissemico ("assistir", "visar") muda de regencia com
    o sentido, e quem decide o sentido e o estudante, nao o motor.
    """
    marcas = list(_RE_TOKEN.finditer(frase or ""))
    if not marcas:
        return []
    brutos = [m.group(0) for m in marcas]
    normais = [normalizar(b) for b in brutos]

    desvios: list[DesvioRegencia] = []
    for infinitivo, sentidos in REGENCIA_VERBAL.items():
        if len(sentidos) != 1 or infinitivo in _CURTOS_DEMAIS:
            continue
        sentido = sentidos[0]
        if sentido.transitividade == "intransitivo":
            continue
        padrao = _padrao_do_verbo(infinitivo)
        for indice, normal in enumerate(normais):
            if not padrao.fullmatch(normal):
                continue
            seguinte = brutos[indice + 1] if indice + 1 < len(brutos) else ""
            if not seguinte:
                continue
            usada = _preposicao_do_token(seguinte)
            desvio = _avaliar(infinitivo, sentido, brutos[indice], seguinte,
                              usada, normais, indice)
            if desvio:
                desvios.append(desvio)
            break
    return desvios


def _avaliar(infinitivo: str, sentido: Sentido, forma: str, seguinte: str,
             usada: str, normais: list[str], indice: int) -> DesvioRegencia | None:
    esperadas = sentido.preposicoes

    # Caso classico e proprio: "preferir A a B" nao admite "do que"/"mais".
    if infinitivo == "preferir":
        janela = normais[indice: indice + 9]
        if "que" in janela or "mais" in janela:
            return DesvioRegencia(
                verbo="preferir", forma_usada=forma, preposicao_usada="do que",
                preposicoes_esperadas=("a",),
                problema="reforco indevido",
                explicacao=(
                    "“Preferir” já traz a ideia de preferência: o segundo termo "
                    "entra com a preposição “a”, sem “do que”, “mais” ou “antes”."
                ),
                sugestao="Prefiro café a chá.",
                exemplo=sentido.exemplo,
            )
        return None

    transitividade = sentido.transitividade.strip()

    if transitividade == "direto":
        if usada and usada in {"a", "com", "de", "em"}:
            return DesvioRegencia(
                verbo=infinitivo, forma_usada=forma, preposicao_usada=usada,
                preposicoes_esperadas=(),
                problema="preposicao a mais",
                explicacao=(
                    f"“{infinitivo}” é transitivo direto neste sentido: o "
                    "complemento vem sem preposição."
                ),
                sugestao=f"{forma} {seguinte.lstrip('aàdcenopm')}".strip(),
                exemplo=sentido.exemplo,
            )
        return None

    # Bitransitivo: o termo colado ao verbo pode ser o objeto direto, entao a
    # ausencia de preposicao nao e desvio. Cuidado: "direto" e substring de
    # "indireto", entao a comparacao precisa ser exata.
    if transitividade == "direto e indireto":
        if usada and usada not in esperadas and usada not in {"para", "de"}:
            return DesvioRegencia(
                verbo=infinitivo, forma_usada=forma, preposicao_usada=usada,
                preposicoes_esperadas=esperadas,
                problema="preposicao trocada",
                explicacao=(
                    f"“{infinitivo}” rege {' ou '.join(esperadas)}, não “{usada}”."
                ),
                sugestao=sentido.exemplo,
                exemplo=sentido.exemplo,
            )
        return None

    # Transitivo indireto puro: a preposicao e obrigatoria.
    if not usada:
        # "a" sem acento diante de nome que dispensa artigo pode ser a
        # preposicao sozinha: "Cheguei a casa" esta correto.
        proximo = normais[indice + 2] if indice + 2 < len(normais) else ""
        if (normalizar(seguinte) == "a" and "a" in esperadas
                and proximo in SEM_ARTIGO_POR_NATURAL):
            return None
        return DesvioRegencia(
            verbo=infinitivo, forma_usada=forma, preposicao_usada="",
            preposicoes_esperadas=esperadas,
            problema="preposicao ausente",
            explicacao=(
                f"“{infinitivo}” é transitivo indireto: exige a preposição "
                f"“{esperadas[0]}”. Sem ela, o complemento fica solto."
            ),
            sugestao=sentido.exemplo,
            exemplo=sentido.exemplo,
        )
    if usada not in esperadas:
        return DesvioRegencia(
            verbo=infinitivo, forma_usada=forma, preposicao_usada=usada,
            preposicoes_esperadas=esperadas,
            problema="preposicao trocada",
            explicacao=(
                f"“{infinitivo}” rege {' ou '.join(esperadas)}; a frase usou "
                f"“{usada}”."
            ),
            sugestao=sentido.exemplo,
            exemplo=sentido.exemplo,
        )
    return None
