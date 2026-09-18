"""Inteligencia de consulta: entender a pergunta antes de sair buscando.

Tres mecanismos, todos testaveis e sem dependencia externa:

1. **Intencao.** "O que e entropia?" e "quais os avancos recentes em entropia?"
   pedem material diferente. A intencao detectada muda quais bases pesam mais
   e como a resposta deve ser estruturada.

2. **Ponte bilingue.** Boa parte da literatura esta em ingles. Perguntar
   "mecanismo de atencao" ao arXiv devolve quase nada; "attention mechanism"
   devolve o campo inteiro. A tradução usa os langlinks da Wikipedia (o mesmo
   conceito ligado entre idiomas) e cai num glossario academico embutido
   quando a rede falha.

3. **Realimentacao de relevancia (Rocchio).** Depois da primeira rodada, os
   melhores trechos revelam o vocabulario real do assunto. Esses termos
   reforcam a consulta numa segunda rodada — e como aprender o jargao lendo
   a primeira pagina antes de procurar direito.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

import httpx

from .texto import Trecho, normalizar, tokenizar

# --------------------------------------------------------------------------
# 1. Intencao da pergunta
# --------------------------------------------------------------------------

@dataclass(slots=True)
class Intencao:
    """O que o estudante quer, e o que isso muda na busca."""

    tipo: str
    rotulo: str
    # Multiplicador de peso por fonte: livro didatico vale mais para definicao,
    # pre-print vale mais para estado da arte.
    pesos: dict[str, float] = field(default_factory=dict)
    fontes_preferidas: tuple[str, ...] = ()
    orientacao: str = ""          # instrucao extra enviada ao modelo

    def para_dict(self) -> dict[str, Any]:
        return {"tipo": self.tipo, "rotulo": self.rotulo,
                "fontes_preferidas": list(self.fontes_preferidas)}


INTENCOES: dict[str, Intencao] = {
    "definicao": Intencao(
        tipo="definicao",
        rotulo="definição",
        pesos={"biblioteca": 1.45, "wikipedia": 1.25, "openlibrary": 1.10,
               "arxiv": 0.85, "stackexchange": 0.80},
        fontes_preferidas=("biblioteca", "wikipedia", "openalex"),
        orientacao=(
            "Comece por uma definição de uma frase, precisa e sem rodeio. "
            "Depois destrinche os termos dessa definição."
        ),
    ),
    "procedimento": Intencao(
        tipo="procedimento",
        rotulo="como fazer",
        pesos={"biblioteca": 1.35, "stackexchange": 1.30, "wikipedia": 1.00,
               "crossref": 0.75, "openlibrary": 0.80},
        fontes_preferidas=("biblioteca", "stackexchange", "wikipedia"),
        orientacao=(
            "Responda em passos numerados, na ordem de execução. "
            "Cada passo diz o que fazer e como saber que deu certo."
        ),
    ),
    "comparacao": Intencao(
        tipo="comparacao",
        rotulo="comparação",
        pesos={"biblioteca": 1.30, "wikipedia": 1.15, "openalex": 1.10},
        fontes_preferidas=("biblioteca", "wikipedia", "openalex"),
        orientacao=(
            "Compare em uma tabela markdown, com um critério por linha. "
            "Depois diga, em duas frases, quando escolher cada um."
        ),
    ),
    "causa": Intencao(
        tipo="causa",
        rotulo="causa e efeito",
        pesos={"biblioteca": 1.25, "openalex": 1.20, "pubmed": 1.15,
               "wikipedia": 1.10},
        fontes_preferidas=("biblioteca", "wikipedia", "openalex", "pubmed"),
        orientacao=(
            "Separe causa de correlação. Se as fontes mostram associação sem "
            "mecanismo estabelecido, diga isso explicitamente."
        ),
    ),
    "estado_da_arte": Intencao(
        tipo="estado_da_arte",
        rotulo="pesquisa recente",
        pesos={"arxiv": 1.45, "semanticscholar": 1.35, "openalex": 1.30,
               "pubmed": 1.25, "wikipedia": 0.80, "openlibrary": 0.65,
               "biblioteca": 0.85},
        fontes_preferidas=("arxiv", "semanticscholar", "openalex", "pubmed"),
        orientacao=(
            "Priorize o material mais recente e diga o ano de cada achado. "
            "Deixe claro o que ainda é questão aberta."
        ),
    ),
    "exercicio": Intencao(
        tipo="exercicio",
        rotulo="resolução",
        pesos={"biblioteca": 1.40, "stackexchange": 1.25, "wikipedia": 1.05},
        fontes_preferidas=("biblioteca", "stackexchange", "wikipedia"),
        orientacao=(
            "Mostre o raciocínio passo a passo antes do resultado. "
            "Aponte o erro mais comum nesse tipo de exercício."
        ),
    ),
    "geral": Intencao(
        tipo="geral",
        rotulo="pergunta aberta",
        pesos={"biblioteca": 1.20},
        fontes_preferidas=(),
        orientacao="",
    ),
}

# Cada pista vale um ponto; expressoes de varias palavras valem mais.
PISTAS_INTENCAO: dict[str, tuple[str, ...]] = {
    "definicao": (
        "o que e", "o que sao", "que e", "defina", "definicao de", "conceito de",
        "significado de", "quem foi", "quem e", "what is", "define",
    ),
    "procedimento": (
        "como fazer", "como calcular", "como implementar", "como funciona",
        "passo a passo", "tutorial", "como usar", "como montar", "como resolver",
        "how to", "como aplicar", "como demonstrar",
    ),
    "comparacao": (
        "diferenca entre", "diferencas entre", "versus", " vs ", "comparar",
        "comparacao entre", "melhor que", "qual a diferenca", "difference between",
        "vantagens e desvantagens",
    ),
    "causa": (
        "por que", "porque", "por quê", "o que causa", "causas de", "causas da",
        "consequencias de", "o que provoca", "why does", "efeitos de", "impacto de",
    ),
    "estado_da_arte": (
        "estado da arte", "pesquisas recentes", "avancos recentes", "ultimos avancos",
        "novidades em", "tendencias em", "pesquisa atual", "artigos recentes",
        "state of the art", "recent advances", "o que ha de novo",
    ),
    "exercicio": (
        "calcule", "resolva", "determine o valor", "exercicio", "demonstre que",
        "prove que", "quanto vale", "encontre o valor",
    ),
}


def classificar_intencao(pergunta: str) -> Intencao:
    """Deduz a intencao pela forma da pergunta."""
    texto = f" {normalizar(pergunta)} "
    pontos: Counter[str] = Counter()
    for tipo, pistas in PISTAS_INTENCAO.items():
        for pista in pistas:
            alvo = normalizar(pista)
            if alvo.strip() in texto:
                pontos[tipo] += 1.0 + 0.7 * alvo.strip().count(" ")

    # Ano recente na pergunta e sinal forte de "quero o que ha de mais novo".
    if re.search(r"\b20(2[3-9]|[3-9]\d)\b", pergunta):
        pontos["estado_da_arte"] += 1.5

    if not pontos:
        return INTENCOES["geral"]
    return INTENCOES[pontos.most_common(1)[0][0]]


# --------------------------------------------------------------------------
# 2. Ponte bilingue
# --------------------------------------------------------------------------

# Glossario de reserva: usado quando a Wikipedia nao responde. Cobre os termos
# que mais aparecem em duvidas de estudo.
GLOSSARIO_PT_EN: dict[str, str] = {
    "aprendizado de maquina": "machine learning",
    "aprendizado profundo": "deep learning",
    "rede neural": "neural network",
    "redes neurais": "neural networks",
    "mecanismo de atencao": "attention mechanism",
    "processamento de linguagem natural": "natural language processing",
    "visao computacional": "computer vision",
    "aprendizado por reforco": "reinforcement learning",
    "arvore de decisao": "decision tree",
    "regressao linear": "linear regression",
    "estrutura de dados": "data structure",
    "banco de dados": "database",
    "algoritmo": "algorithm",
    "criptografia": "cryptography",
    "computacao quantica": "quantum computing",
    "fotossintese": "photosynthesis",
    "mitocondria": "mitochondria",
    "celula": "cell biology",
    "divisao celular": "cell division",
    "acido nucleico": "nucleic acid",
    "expressao genica": "gene expression",
    "sistema imunologico": "immune system",
    "sistema nervoso": "nervous system",
    "neuronio": "neuron",
    "neurotransmissor": "neurotransmitter",
    "metabolismo": "metabolism",
    "evolucao": "evolution",
    "selecao natural": "natural selection",
    "ecossistema": "ecosystem",
    "cadeia alimentar": "food chain",
    "diabetes": "diabetes mellitus",
    "hipertensao": "hypertension",
    "cancer": "cancer",
    "vacina": "vaccine",
    "antibiotico": "antibiotic",
    "inflamacao": "inflammation",
    "ensaio clinico": "clinical trial",
    "relatividade": "relativity",
    "relatividade geral": "general relativity",
    "mecanica quantica": "quantum mechanics",
    "termodinamica": "thermodynamics",
    "entropia": "entropy",
    "eletromagnetismo": "electromagnetism",
    "campo magnetico": "magnetic field",
    "energia cinetica": "kinetic energy",
    "movimento harmonico": "harmonic motion",
    "onda": "wave",
    "derivada": "derivative",
    "integral": "integral calculus",
    "limite": "limit mathematics",
    "matriz": "matrix mathematics",
    "algebra linear": "linear algebra",
    "probabilidade": "probability",
    "estatistica": "statistics",
    "distribuicao normal": "normal distribution",
    "teorema": "theorem",
    "numero primo": "prime number",
    "geometria analitica": "analytic geometry",
    "trigonometria": "trigonometry",
    "logaritmo": "logarithm",
    "equacao diferencial": "differential equation",
    "ligacao quimica": "chemical bond",
    "tabela periodica": "periodic table",
    "reacao quimica": "chemical reaction",
    "estequiometria": "stoichiometry",
    "acido e base": "acid base chemistry",
    "revolucao francesa": "french revolution",
    "revolucao industrial": "industrial revolution",
    "guerra fria": "cold war",
    "segunda guerra mundial": "world war ii",
    "iluminismo": "age of enlightenment",
    "capitalismo": "capitalism",
    "democracia": "democracy",
    "inflacao": "inflation economics",
    "microeconomia": "microeconomics",
    "psicologia cognitiva": "cognitive psychology",
    "memoria de trabalho": "working memory",
    "aprendizagem": "learning",
}


def traduzir_pelo_glossario(consulta: str) -> str:
    """Traducao aproximada por casamento de expressoes conhecidas."""
    texto = normalizar(consulta)
    achados: list[str] = []
    # Expressoes longas primeiro, para "rede neural convolucional" nao virar
    # apenas "neural network".
    for termo in sorted(GLOSSARIO_PT_EN, key=len, reverse=True):
        if termo in texto:
            traducao = GLOSSARIO_PT_EN[termo]
            if traducao not in achados:
                achados.append(traducao)
            texto = texto.replace(termo, " ")
    return " ".join(achados)


async def traduzir_pela_wikipedia(
    cliente: httpx.AsyncClient,
    consulta: str,
    idioma_origem: str = "pt",
) -> str:
    """Usa os langlinks da Wikipedia para achar o termo equivalente em ingles.

    E uma tradutora de conceitos, nao de frases: encontra o verbete que melhor
    corresponde a pergunta e devolve o titulo dele em ingles. Como o mesmo
    conceito costuma ter nome consagrado diferente nos dois idiomas, isso e
    mais preciso que traducao palavra a palavra.
    """
    url = f"https://{idioma_origem}.wikipedia.org/w/api.php"
    resposta = await cliente.get(
        url,
        params={
            "action": "query", "format": "json", "generator": "search",
            "gsrsearch": consulta, "gsrlimit": 2,
            "prop": "langlinks", "lllang": "en", "lllimit": 2,
        },
    )
    resposta.raise_for_status()
    paginas = (resposta.json().get("query") or {}).get("pages") or {}
    titulos: list[str] = []
    for pagina in paginas.values():
        for link in pagina.get("langlinks") or []:
            titulo = (link.get("*") or "").strip()
            if titulo and titulo not in titulos:
                titulos.append(titulo)
    return " ".join(titulos[:2])


async def versao_em_ingles(
    cliente: httpx.AsyncClient | None,
    consulta: str,
    idioma: str = "pt",
) -> tuple[str, str]:
    """Devolve (consulta em ingles, como foi obtida).

    Se a pergunta ja parece estar em ingles, devolve ela mesma.
    """
    if idioma.startswith("en") or _parece_ingles(consulta):
        return consulta, "original"

    if cliente is not None:
        try:
            traduzida = await traduzir_pela_wikipedia(cliente, consulta, "pt")
            if traduzida:
                return traduzida, "wikipedia"
        except Exception:
            pass  # sem rede ou verbete inexistente: cai no glossario

    pelo_glossario = traduzir_pelo_glossario(consulta)
    if pelo_glossario:
        return pelo_glossario, "glossario"
    return consulta, "sem_traducao"


_PALAVRAS_PT = {
    "que", "como", "qual", "quais", "por", "para", "uma", "uns", "umas", "dos",
    "das", "nao", "com", "sao", "ser", "mais", "entre", "sobre", "quando",
    "onde", "porque", "de", "da", "do", "em", "na", "no", "nas", "nos", "ao",
    "aos", "pelo", "pela", "seu", "sua", "isso", "este", "esta", "esse", "essa",
    "quem", "quanto", "quantas", "quantos", "muito", "tambem", "ja", "sem",
}

# Acentos e cedilha que praticamente so aparecem em portugues.
_MARCAS_PT = "ãõçáéíóúâêôà"

_PALAVRAS_EN = {
    "the", "is", "are", "what", "how", "why", "which", "of", "and", "in", "to",
    "for", "with", "does", "do", "difference", "between", "explain", "about",
    "example", "can", "should", "when", "where", "who",
}


def _parece_ingles(texto: str) -> bool:
    """A pergunta ja esta em ingles?

    Na duvida responde `False`: tentar traduzir uma pergunta que ja estava em
    ingles custa pouco (a traducao devolve o proprio texto), enquanto deixar de
    traduzir uma pergunta em portugues custa metade da literatura.
    """
    if any(marca in texto.lower() for marca in _MARCAS_PT):
        return False
    tokens = {normalizar(t) for t in re.findall(r"[\wÀ-ÿ]+", texto)}
    if tokens & _PALAVRAS_PT:
        return False
    return bool(tokens & _PALAVRAS_EN)


# --------------------------------------------------------------------------
# 3. Realimentacao de relevancia (Rocchio / pseudo-relevance feedback)
# --------------------------------------------------------------------------

def termos_de_realimentacao(
    trechos: list[Trecho],
    consulta: str,
    quantidade: int = 6,
    trechos_considerados: int = 5,
) -> list[str]:
    """Extrai o vocabulario caracteristico dos melhores trechos da 1a rodada.

    Pontua cada termo por frequencia nos trechos bons dividida pela frequencia
    no conjunto todo: o que aparece muito nos bons e pouco no resto e o jargao
    especifico do assunto. Termos ja presentes na pergunta sao ignorados.
    """
    if len(trechos) < 3:
        return []

    da_pergunta = {normalizar(t) for t in tokenizar(consulta)}
    bons = trechos[:trechos_considerados]
    resto = trechos[trechos_considerados:] or trechos

    conta_bons: Counter[str] = Counter()
    for trecho in bons:
        conta_bons.update(set(tokenizar(trecho.texto)))
    conta_resto: Counter[str] = Counter()
    for trecho in resto:
        conta_resto.update(set(tokenizar(trecho.texto)))

    pontuados: list[tuple[float, str]] = []
    for termo, frequencia in conta_bons.items():
        if termo in da_pergunta or len(termo) < 4 or termo.isdigit():
            continue
        if frequencia < 2:
            continue
        rara_no_resto = 1.0 / (1.0 + conta_resto.get(termo, 0))
        pontuados.append((frequencia * rara_no_resto, termo))

    pontuados.sort(reverse=True)
    return [termo for _, termo in pontuados[:quantidade]]


def consulta_expandida(consulta: str, extras: list[str]) -> str:
    """Junta a pergunta original aos termos aprendidos na primeira rodada."""
    if not extras:
        return consulta
    return f"{consulta} {' '.join(extras)}"
