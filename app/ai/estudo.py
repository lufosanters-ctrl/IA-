"""Ferramentas de estudo geradas a partir do material pesquisado.

Todas as funcoes tem duas implementacoes: uma neural (quando ha chave de API)
e uma deterministica de reserva, que extrai o material diretamente dos trechos
recuperados. Assim a plataforma nunca fica inutil por falta de chave.
"""

from __future__ import annotations

import random
import re
from typing import Any

from ..texto import dividir_frases, normalizar, tokenizar, truncar
from .llm import ErroModelo, obter_motor
from .pesquisa import ResultadoPesquisa

NIVEIS = {
    "iniciante": "explique como para alguem que nunca viu o assunto, com analogias do dia a dia e zero jargao nao explicado",
    "intermediario": "explique para um estudante de graduacao que ja conhece os fundamentos da area",
    "avancado": "explique para um pos-graduando, podendo usar formalismo, notacao e termos tecnicos da area",
}

SISTEMA_FLASHCARDS = """Voce cria flashcards de estudo em portugues do Brasil a partir de material de referencia.

Regras:
- Cada cartao testa UM conceito. Frente curta e sem ambiguidade; verso completo mas enxuto (ate 3 frases).
- Nunca crie perguntas cuja resposta nao esteja no material fornecido.
- Varie o tipo: definicao, causa/efeito, comparacao, aplicacao pratica, numero-chave.
- Inclua o indice da citacao de origem em "citacao" (o numero entre colchetes do trecho usado).

Saida: array JSON de objetos {"frente": str, "verso": str, "citacao": int, "dificuldade": "facil"|"media"|"dificil"}."""

SISTEMA_QUIZ = """Voce cria questoes de multipla escolha em portugues do Brasil a partir de material de referencia.

Regras:
- 4 alternativas por questao, exatamente uma correta.
- Os distratores devem ser plausiveis e do mesmo tipo semantico da resposta certa; nada de alternativas absurdas.
- "correta" e o indice (0-3) da alternativa certa.
- "explicacao" justifica a resposta em 1 ou 2 frases, apoiada no material.
- Nunca pergunte algo que o material nao responda.

Saida: array JSON de objetos {"pergunta": str, "alternativas": [str, str, str, str], "correta": int, "explicacao": str, "citacao": int}."""

SISTEMA_PLANO = """Voce monta planos de estudo realistas em portugues do Brasil.

Regras:
- Sequencie do pre-requisito ao topico avancado; nunca cite um conceito antes de introduzi-lo.
- Cada sessao tem objetivo verificavel ("saber calcular...", "saber explicar..."), nao "entender melhor".
- Distribua a carga conforme as horas semanais informadas, com folga para revisao.
- Inclua, por sessao, uma atividade pratica concreta.

Saida: objeto JSON {"titulo": str, "resumo": str, "pre_requisitos": [str],
"sessoes": [{"numero": int, "titulo": str, "objetivo": str, "topicos": [str],
"atividade": str, "duracao_min": int}], "avaliacao": str, "recursos": [str]}."""


def _contexto_de(resultado: ResultadoPesquisa, limite: int = 9000) -> str:
    """Remonta o material citado, numerado, para alimentar o modelo."""
    partes = [
        f"[{c.numero}] {c.titulo} ({c.fonte})\n{c.trecho}" for c in resultado.citacoes
    ]
    contexto = "\n\n".join(partes)
    if len(contexto) > limite:
        contexto = contexto[:limite]
    return contexto


# --------------------------------------------------------------------------
# Flashcards
# --------------------------------------------------------------------------

_RE_DEFINICAO = re.compile(
    r"^(?P<termo>[^,.;:()]{3,60}?)\s+(?P<conector>e|é|sao|são|refere-se a|"
    r"consiste em|significa|denomina-se|is|are|refers to)\s+(?P<corpo>.{25,})$",
    re.IGNORECASE,
)

# Se o "termo" contiver um destes, a frase e uma oracao completa, nao uma
# definicao: "A arquitetura dispensa recorrencia e usa camadas..." nao rende
# o cartao "O que e A arquitetura dispensa recorrencia?".
_VERBOS_NO_TERMO = {
    "dispensa", "usa", "permite", "torna", "faz", "tem", "pode", "possui",
    "mostra", "apresenta", "indica", "define", "ocorre", "acontece", "serve",
    "inclui", "envolve", "requer", "produz", "gera", "aumenta", "reduz",
    "have", "has", "uses", "allows", "shows", "makes", "become", "provide",
}

_ARTIGOS_INICIAIS = ("o ", "a ", "os ", "as ", "um ", "uma ", "the ")


def _limpar_termo(bruto: str) -> str:
    """Normaliza o sujeito de uma definicao para virar a frente do cartao."""
    termo = bruto.strip(" \"'").rstrip(",;:")
    minusculo = termo.lower()
    for artigo in _ARTIGOS_INICIAIS:
        if minusculo.startswith(artigo):
            termo = termo[len(artigo):]
            break
    return termo.strip()


def _termo_valido(termo: str) -> bool:
    """Aceita apenas sintagmas nominais curtos, nao oracoes inteiras."""
    palavras = termo.split()
    if not 1 <= len(palavras) <= 5 or len(termo) < 3:
        return False
    if any(normalizar(p) in _VERBOS_NO_TERMO for p in palavras):
        return False
    # Um sujeito de definicao nao costuma comecar por conjuncao ou preposicao.
    return normalizar(palavras[0]) not in {"que", "isso", "isto", "ele", "ela",
                                           "este", "esta", "esse", "essa", "mas",
                                           "porem", "entao", "assim", "portanto"}


def _cartao_lacuna(frase: str, citacao: int) -> dict | None:
    """Transforma uma frase informativa em um cartao de completar."""
    candidatos = [
        palavra for palavra in re.findall(r"\b[\wÀ-ÿ-]{6,}\b", frase)
        if normalizar(palavra) not in {normalizar(s) for s in STOPWORDS_CURTAS}
    ]
    if not candidatos:
        return None
    alvo = max(candidatos, key=len)
    frente = frase.replace(alvo, "_____", 1)
    if "_____" not in frente:
        return None
    return {
        "frente": f"Complete: {truncar(frente, 260)}",
        "verso": alvo,
        "citacao": citacao,
        "dificuldade": "media",
    }


STOPWORDS_CURTAS = {
    "porque", "quando", "portanto", "durante", "tambem", "apenas", "atraves",
    "enquanto", "however", "therefore", "between", "because", "through",
}


def flashcards_extrativos(resultado: ResultadoPesquisa, quantidade: int) -> list[dict]:
    """Extrai cartoes do material recuperado, sem inventar conteudo.

    Ordem de preferencia:
    1. definicoes explicitas ("X e ..."), que rendem os melhores cartoes;
    2. frases informativas viradas em exercicio de completar;
    3. nada — e melhor devolver menos cartoes do que cartoes inuteis.
    """
    cartoes: list[dict] = []
    vistos: set[str] = set()
    frases_usadas: set[str] = set()

    # 1) definicoes
    for citacao in resultado.citacoes:
        for frase in dividir_frases(citacao.trecho):
            achado = _RE_DEFINICAO.match(frase.strip())
            if not achado:
                continue
            termo = _limpar_termo(achado.group("termo"))
            if not _termo_valido(termo):
                continue
            chave = normalizar(termo)
            if chave in vistos:
                continue
            corpo = achado.group("corpo").strip()
            vistos.add(chave)
            frases_usadas.add(frase)
            cartoes.append(
                {
                    "frente": f"O que é {termo}?",
                    "verso": truncar(corpo, 320),
                    "citacao": citacao.numero,
                    "dificuldade": "media",
                }
            )
            if len(cartoes) >= quantidade:
                return cartoes

    # 2) frases informativas como exercicio de completar
    termos_pergunta = set(tokenizar(resultado.pergunta))
    for citacao in resultado.citacoes:
        for frase in dividir_frases(citacao.trecho):
            if len(cartoes) >= quantidade:
                return cartoes
            frase = frase.strip()
            if frase in frases_usadas or len(frase) < 70:
                continue
            tokens = set(tokenizar(frase))
            if termos_pergunta and not (tokens & termos_pergunta):
                continue  # frase fora do assunto perguntado
            cartao = _cartao_lacuna(frase, citacao.numero)
            if not cartao:
                continue
            chave = normalizar(cartao["verso"])
            if chave in vistos:
                continue
            vistos.add(chave)
            frases_usadas.add(frase)
            cartoes.append(cartao)

    return cartoes[:quantidade]


async def gerar_flashcards(
    resultado: ResultadoPesquisa,
    quantidade: int = 8,
) -> dict[str, Any]:
    """Gera flashcards a partir de uma pesquisa ja realizada."""
    motor = obter_motor()
    contexto = _contexto_de(resultado)
    if motor.disponivel and contexto:
        prompt = (
            f"Tema estudado: {resultado.pergunta}\n\n"
            f"Material de referencia:\n\n{contexto}\n\n"
            f"Gere exatamente {quantidade} flashcards."
        )
        try:
            dados = await motor.responder_json(SISTEMA_FLASHCARDS, prompt, max_tokens=2600)
            cartoes = _validar_flashcards(dados, resultado)
            if cartoes:
                return {"cartoes": cartoes[:quantidade], "modo": "neural"}
        except ErroModelo:
            pass
    return {
        "cartoes": flashcards_extrativos(resultado, quantidade),
        "modo": "extrativo",
    }


def _validar_flashcards(dados: Any, resultado: ResultadoPesquisa) -> list[dict]:
    if not isinstance(dados, list):
        dados = dados.get("cartoes", []) if isinstance(dados, dict) else []
    maximo = len(resultado.citacoes)
    validos: list[dict] = []
    for item in dados:
        if not isinstance(item, dict):
            continue
        frente = str(item.get("frente", "")).strip()
        verso = str(item.get("verso", "")).strip()
        if not frente or not verso:
            continue
        try:
            citacao = int(item.get("citacao", 0))
        except (TypeError, ValueError):
            citacao = 0
        validos.append(
            {
                "frente": frente,
                "verso": verso,
                "citacao": citacao if 1 <= citacao <= maximo else 0,
                "dificuldade": item.get("dificuldade", "media"),
            }
        )
    return validos


# --------------------------------------------------------------------------
# Quiz
# --------------------------------------------------------------------------

_RE_PALAVRA_FRASE = re.compile(r"[0-9A-Za-zÀ-ÿ][0-9A-Za-zÀ-ÿ'-]*")


def _palavra_original(frase: str, alvo: str) -> str:
    """A palavra da frase cuja forma normalizada e `alvo`.

    O alvo sai de `tokenizar`, que remove acentos; procura-lo direto na frase
    original nunca casava com palavra acentuada, e toda questao extrativa em
    portugues era descartada.
    """
    normal_alvo = normalizar(alvo)
    for marca in _RE_PALAVRA_FRASE.finditer(frase):
        if normalizar(marca.group(0)) == normal_alvo:
            return marca.group(0)
    return ""


def _com_lacuna(frase: str, palavra: str) -> str:
    """Troca a primeira ocorrencia exata da palavra por uma lacuna."""
    return re.sub(rf"\b{re.escape(palavra)}\b", "_____", frase, count=1)


def quiz_extrativo(resultado: ResultadoPesquisa, quantidade: int) -> list[dict]:
    """Monta questoes de lacuna (cloze) a partir de frases reais das fontes."""
    aleatorio = random.Random(normalizar(resultado.pergunta))
    candidatas: list[tuple[str, str, int]] = []

    for citacao in resultado.citacoes:
        for frase in dividir_frases(citacao.trecho):
            tokens = [t for t in tokenizar(frase) if len(t) > 4]
            if len(frase) < 60 or len(tokens) < 6:
                continue
            candidatas.append((frase, tokens[len(tokens) // 2], citacao.numero))

    questoes: list[dict] = []
    vocabulario = list({t for _, t, _ in candidatas})
    for frase, alvo, numero in candidatas[: quantidade * 3]:
        if len(questoes) >= quantidade:
            break
        correta = _palavra_original(frase, alvo)
        if not correta:
            continue
        tokens_da_frase = {normalizar(t) for t in tokenizar(frase)}
        # Um bom distrator: nao esta na propria frase (senao a eliminacao e
        # trivial) e tem tamanho parecido com a resposta certa.
        distratores = [
            v for v in vocabulario
            if normalizar(v) != normalizar(correta)
            and normalizar(v) not in tokens_da_frase
            and abs(len(v) - len(correta)) <= max(4, len(correta) // 2)
        ]
        if len(distratores) < 3:
            # Relaxa o criterio de tamanho antes de desistir da questao.
            distratores = [
                v for v in vocabulario
                if normalizar(v) != normalizar(correta)
                and normalizar(v) not in tokens_da_frase
            ]
        if len(distratores) < 3:
            continue
        alternativas = aleatorio.sample(distratores, 3) + [correta]
        aleatorio.shuffle(alternativas)
        questoes.append(
            {
                "pergunta": f"Complete: {_com_lacuna(frase, correta)}",
                "alternativas": alternativas,
                "correta": alternativas.index(correta),
                "explicacao": f"A fonte [{numero}] traz exatamente esta formulação.",
                "citacao": numero,
            }
        )
    return questoes


async def gerar_quiz(
    resultado: ResultadoPesquisa,
    quantidade: int = 5,
) -> dict[str, Any]:
    """Gera um questionario de multipla escolha sobre o material."""
    motor = obter_motor()
    contexto = _contexto_de(resultado)
    if motor.disponivel and contexto:
        prompt = (
            f"Tema estudado: {resultado.pergunta}\n\n"
            f"Material de referencia:\n\n{contexto}\n\n"
            f"Gere exatamente {quantidade} questoes de multipla escolha."
        )
        try:
            dados = await motor.responder_json(SISTEMA_QUIZ, prompt, max_tokens=3000)
            questoes = _validar_quiz(dados)
            if questoes:
                return {"questoes": questoes[:quantidade], "modo": "neural"}
        except ErroModelo:
            pass
    return {"questoes": quiz_extrativo(resultado, quantidade), "modo": "extrativo"}


def _validar_quiz(dados: Any) -> list[dict]:
    if not isinstance(dados, list):
        dados = dados.get("questoes", []) if isinstance(dados, dict) else []
    validas: list[dict] = []
    for item in dados:
        if not isinstance(item, dict):
            continue
        alternativas = item.get("alternativas") or []
        if not isinstance(alternativas, list) or len(alternativas) < 2:
            continue
        alternativas = [str(a) for a in alternativas][:4]
        try:
            correta = int(item.get("correta", 0))
        except (TypeError, ValueError):
            continue
        if not 0 <= correta < len(alternativas):
            continue
        pergunta = str(item.get("pergunta", "")).strip()
        if not pergunta:
            continue
        validas.append(
            {
                "pergunta": pergunta,
                "alternativas": alternativas,
                "correta": correta,
                "explicacao": str(item.get("explicacao", "")).strip(),
                "citacao": item.get("citacao", 0),
            }
        )
    return validas


# --------------------------------------------------------------------------
# Plano de estudo
# --------------------------------------------------------------------------

def plano_extrativo(
    tema: str,
    semanas: int,
    horas_semana: int,
    resultado: ResultadoPesquisa | None,
) -> dict[str, Any]:
    """Plano de estudo montado a partir dos titulos e topicos encontrados."""
    topicos: list[str] = []
    if resultado:
        for citacao in resultado.citacoes:
            titulo = truncar(citacao.titulo, 80)
            if titulo and titulo not in topicos:
                topicos.append(titulo)
    if not topicos:
        topicos = [f"Fundamentos de {tema}", f"Aplicações de {tema}", f"Revisão de {tema}"]

    sessoes_totais = max(semanas * max(horas_semana // 2, 1), 3)
    duracao = max(60, (horas_semana * 60) // max(horas_semana // 2, 1))
    sessoes = []
    for i in range(sessoes_totais):
        topico = topicos[i % len(topicos)]
        sessoes.append(
            {
                "numero": i + 1,
                "titulo": f"Sessão {i + 1}: {truncar(topico, 60)}",
                "objetivo": f"Saber explicar com suas palavras o conteúdo de '{truncar(topico, 60)}'.",
                "topicos": [topico],
                "atividade": "Ler a fonte, resumir em meia página e responder ao quiz gerado.",
                "duracao_min": duracao,
            }
        )
    return {
        "titulo": f"Plano de estudo: {tema}",
        "resumo": (
            f"{semanas} semanas, cerca de {horas_semana}h por semana, "
            f"organizado a partir das fontes encontradas."
        ),
        "pre_requisitos": [],
        "sessoes": sessoes,
        "avaliacao": "Ao final de cada semana, refaça o quiz e revise os flashcards errados.",
        "recursos": [c.url for c in (resultado.citacoes if resultado else [])][:8],
        "modo": "extrativo",
    }


async def gerar_plano(
    tema: str,
    semanas: int = 4,
    horas_semana: int = 5,
    nivel: str = "iniciante",
    resultado: ResultadoPesquisa | None = None,
) -> dict[str, Any]:
    """Monta um plano de estudo sequenciado para o tema."""
    motor = obter_motor()
    if motor.disponivel:
        contexto = _contexto_de(resultado, 6000) if resultado else "(sem material previo)"
        prompt = (
            f"Tema: {tema}\n"
            f"Nivel do estudante: {nivel} ({NIVEIS.get(nivel, '')})\n"
            f"Duracao: {semanas} semanas, {horas_semana} horas por semana.\n\n"
            f"Material de referencia encontrado nas bases publicas:\n\n{contexto}\n\n"
            "Monte o plano de estudo."
        )
        try:
            dados = await motor.responder_json(SISTEMA_PLANO, prompt, max_tokens=3000)
            if isinstance(dados, dict) and dados.get("sessoes"):
                dados["modo"] = "neural"
                if resultado:
                    # O modelo pode devolver "recursos" como numero ou null.
                    # `list(5)` levantava TypeError e virava 500 na API.
                    bruto = dados.get("recursos")
                    recursos = [str(r) for r in bruto] if isinstance(bruto, list) else []
                    dados["recursos"] = recursos[:8] or [
                        c.url for c in resultado.citacoes[:8]
                    ]
                return dados
        except ErroModelo:
            pass
    return plano_extrativo(tema, semanas, horas_semana, resultado)


# --------------------------------------------------------------------------
# Explicacao por nivel
# --------------------------------------------------------------------------

SISTEMA_EXPLICAR = """Voce e um tutor que explica conceitos em portugues do Brasil, apoiado em material de referencia.

Regras:
- Use apenas o material fornecido; cite com [n].
- Adapte a linguagem exatamente ao nivel pedido.
- Estruture em: intuicao -> mecanismo -> exemplo concreto -> erro comum.
- Termine com uma pergunta que faca o estudante testar se entendeu."""


async def explicar(
    conceito: str,
    nivel: str,
    resultado: ResultadoPesquisa,
) -> dict[str, Any]:
    """Reexplica um conceito ja pesquisado no nivel pedido."""
    motor = obter_motor()
    contexto = _contexto_de(resultado)
    if motor.disponivel and contexto:
        prompt = (
            f"Conceito: {conceito}\n"
            f"Nivel pedido: {nivel} — {NIVEIS.get(nivel, NIVEIS['intermediario'])}\n\n"
            f"Material:\n\n{contexto}"
        )
        try:
            texto = await motor.responder(SISTEMA_EXPLICAR, prompt)
            return {"texto": texto, "modo": "neural", "nivel": nivel}
        except ErroModelo:
            pass
    trechos = "\n\n".join(
        f"- {truncar(c.trecho, 300)} [{c.numero}]" for c in resultado.citacoes[:5]
    )
    return {
        "texto": (
            f"**{conceito}** — material selecionado das fontes (modo extrativo, "
            f"nível solicitado: {nivel}):\n\n{trechos}"
        ),
        "modo": "extrativo",
        "nivel": nivel,
    }
