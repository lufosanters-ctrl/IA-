"""Orquestracao da tutoria: da questao ao degrau certo da escada.

O fluxo e sempre o mesmo, independente da materia:

    DIAGNOSTICAR → PERGUNTAR → DAR PISTA → OBSERVAR → CORRIGIR → CONCLUIR

O que muda por materia e o VERIFICADOR que sustenta o diagnostico: em
matematica, o sistema de algebra computacional; em portugues, os motores de
crase, regencia, colocacao e concordancia; em ingles, os padroes de
transferencia. Sem esse apoio, a tutoria viraria opiniao.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from typing import Any

from ..ai.llm import ErroModelo, obter_motor
from ..gramatica import analisar_frase
from ..ingles import avaliar_estrutura, contrastes_relevantes
from ..matematica import analisar_enunciado, classificar
from ..texto import normalizar
from . import sessao as armazem
from .escada import NIVEL_MAXIMO, Degrau, degrau, detectar_pedido, proximo_degrau
from .prompts import (
    SISTEMA_DIAGNOSTICO,
    SISTEMA_GENERALIZACAO,
    SISTEMA_RESPOSTA_A_TENTATIVA,
    sistema_tutor,
)

# --------------------------------------------------------------------------
# Deteccao de materia
# --------------------------------------------------------------------------

_PISTAS_PORTUGUES = (
    "crase", "regencia", "regência", "concordancia", "concordância", "sujeito",
    "predicado", "objeto direto", "objeto indireto", "oracao", "oração",
    "adjunto", "aposto", "vocativo", "pronome", "colocacao pronominal",
    "proclise", "próclise", "enclise", "ênclise", "mesoclise", "mesóclise",
    "substantivo", "adjetivo", "advérbio", "conjuncao", "conjunção",
    "preposicao", "preposição", "figura de linguagem", "coesao", "coesão",
    "analise sintatica", "análise sintática", "morfologia", "acentuacao",
    "pontuacao", "pontuação", "gramatica", "gramática", "período composto",
)

_PISTAS_INGLES = (
    "present perfect", "simple past", "past simple", "going to", "phrasal",
    "used to", "reported speech", "conditional", "gerund", "infinitive",
    "countable", "uncountable", "english", "inglês", "ingles", "would",
    "should", "modal", "passive voice", "relative clause", "question tag",
)

# Palavras funcionais que existem em inglês e NÃO em português. Termos
# ambíguos ("for", "do", "a", "no") ficam de fora de propósito: incluí-los
# faria qualquer frase em português pontuar como inglesa.
_RE_PALAVRAS_INGLESAS = re.compile(
    r"\b(the|is|are|was|were|have|has|had|will|would|should|could|because|"
    r"which|that|there|their|been|being|i|he|she|it|you|we|they|him|them|his|"
    r"her|my|your|our|this|these|those|and|but|with|from|not|what|when|where|"
    r"who|how|can|may|might|must|about|than|then|also|very|more|most|some|any|"
    r"all|yes|choose|correct|option|sentence|following|answer|question|word)\b",
    re.IGNORECASE,
)


def detectar_materia(enunciado: str) -> str:
    """Decide a matéria pelo vocabulário e pela própria língua do texto."""
    texto = normalizar(enunciado or "")
    if not texto.strip():
        return "geral"

    pontos = {"portugues": 0.0, "ingles": 0.0, "matematica": 0.0}
    for pista in _PISTAS_PORTUGUES:
        if normalizar(pista) in texto:
            pontos["portugues"] += 1.5
    for pista in _PISTAS_INGLES:
        if normalizar(pista) in texto:
            pontos["ingles"] += 1.5

    # Frases longas em inglês são, por si, um sinal forte.
    inglesas = len(_RE_PALAVRAS_INGLESAS.findall(enunciado or ""))
    if inglesas >= 3:
        pontos["ingles"] += inglesas * 0.6

    diagnostico = classificar(enunciado)
    if diagnostico.topico != "geral":
        pontos["matematica"] += 2.0
    if re.search(r"[=+\-*/^]\s*\d|\d\s*[=+*/^]|\\frac|\bequa[çc][ãa]o\b", enunciado or ""):
        pontos["matematica"] += 1.5

    melhor = max(pontos, key=lambda chave: pontos[chave])
    if pontos[melhor] > 0:
        return melhor

    # Nada pontuou: nenhum vocabulário metalinguístico, nenhuma equação. Mas
    # "Prefiro café do que chá. Está certo?" é pergunta de português — só que
    # feita sem usar a palavra "regência". Aqui os próprios motores decidem:
    # se eles chegam a um veredito firme sobre a frase, o assunto é português.
    return "portugues" if _motores_reconhecem(enunciado) else "geral"


# Pedidos que, somados a um veredito dos motores, confirmam a intenção.
_PEDIDOS_DE_CORRECAO = (
    "esta certo", "está certo", "corrija", "corrigir", "tem erro", "ha erro",
    "há erro", "qual a forma correta", "qual e a forma correta",
    "qual é a forma correta", "isso esta certo", "escrevi certo",
    "revise", "revisar", "certo ou errado", "esta correta", "está correta",
)


def _motores_reconhecem(enunciado: str) -> bool:
    """Os motores de português chegam a um veredito firme sobre esta frase?

    Só conta veredito FIRME: um "depende da regência" aparece em quase
    qualquer frase com um "a" e não prova nada sobre a intenção de quem
    perguntou.
    """
    analise = analisar_frase(enunciado)
    firmes = [a for a in analise.achados if a.veredito in {"erro", "correto"}]
    if not firmes:
        return False
    # Um erro apontado basta: frase errada de português é assunto de
    # português, tenha ou não a palavra "crase" no enunciado.
    if any(a.veredito == "erro" for a in firmes):
        return True
    # Só "correto" é sinal fraco — exige que a pessoa esteja mesmo pedindo
    # correção, senão "Vou à praia" no meio de outra conversa viraria aula.
    texto = normalizar(enunciado)
    return any(normalizar(p) in texto for p in _PEDIDOS_DE_CORRECAO)


# --------------------------------------------------------------------------
# Contexto deterministico por materia
# --------------------------------------------------------------------------

def _com_biblioteca(resumo: str, livros: list[dict[str, Any]]) -> str:
    """Anexa ao resumo o que os livros do estudante dizem sobre o assunto."""
    if not livros:
        return resumo
    linhas = ["", "Na biblioteca do próprio estudante:"]
    for livro in livros:
        local = f", {livro['capitulo']}" if livro["capitulo"] else ""
        pagina = f", p. {livro['pagina']}" if livro["pagina"] else ""
        linhas.append(f"- {livro['livro']}{local}{pagina}: {livro['trecho'][:200]}")
    linhas.append(
        "Cite o livro dele quando couber: ele pode abrir a página e continuar dali."
    )
    return resumo + "\n".join(linhas)


@dataclass(slots=True)
class ContextoVerificado:
    """O que os verificadores apuraram, antes de qualquer modelo opinar."""

    materia: str
    topico: str = ""
    dificuldade: int = 2
    resumo: str = ""
    dados: dict[str, Any] = field(default_factory=dict)

    def para_dict(self) -> dict[str, Any]:
        return {
            "materia": self.materia, "topico": self.topico,
            "dificuldade": self.dificuldade, "resumo": self.resumo,
            "dados": self.dados,
        }


async def apurar(enunciado: str, materia: str = "") -> ContextoVerificado:
    """Roda o verificador da matéria e devolve o que ficou estabelecido."""
    materia = materia or detectar_materia(enunciado)
    contexto = ContextoVerificado(materia=materia)

    # O acervo do estudante entra em qualquer matéria.
    livros = _trechos_da_biblioteca(enunciado)
    if livros:
        contexto.dados["biblioteca"] = livros

    if materia == "matematica":
        diagnostico = classificar(enunciado)
        analise = await analisar_enunciado(
            enunciado, diagnostico.topico == "probabilidade"
        )
        contexto.topico = diagnostico.topico
        contexto.dificuldade = diagnostico.dificuldade
        contexto.dados["diagnostico"] = diagnostico.para_dict()
        contexto.dados["analise"] = analise.para_dict()
        linhas = [
            f"Assunto: {diagnostico.topico_nome} "
            f"(nível {diagnostico.dificuldade} — {diagnostico.dificuldade_nome})."
        ]
        if analise.equacoes:
            linhas.append("Equações lidas: " + "; ".join(analise.equacoes))
        if analise.solucoes:
            linhas.append(
                "A álgebra computacional obteve: "
                + "; ".join(f"{v} ∈ {{{', '.join(s)}}}"
                            for v, s in analise.solucoes.items())
                + ". NÃO revele estes valores nos degraus 0 a 5."
            )
        contexto.resumo = _com_biblioteca("\n".join(linhas), livros)
        return contexto

    if materia == "portugues":
        analise = analisar_frase(enunciado)
        contexto.topico = (analise.topicos_envolvidos or ["geral"])[0]
        contexto.dados["gramatica"] = analise.para_dict()
        linhas = []
        for achado in analise.achados[:6]:
            linhas.append(
                f"[{achado.topico}] {achado.veredito}: {achado.regra} — "
                f"{achado.explicacao}"
            )
        contexto.resumo = _com_biblioteca(
            "\n".join(linhas) or "Nenhuma armadilha clássica detectada.", livros
        )
        return contexto

    if materia == "ingles":
        avaliacoes = avaliar_estrutura(enunciado)
        contrastes = contrastes_relevantes(enunciado, lingua="ingles")
        contexto.topico = contrastes[0].chave if contrastes else "geral"
        contexto.dados["avaliacoes"] = [a.para_dict() for a in avaliacoes]
        contexto.dados["contrastes"] = [c.para_dict() for c in contrastes]
        linhas = [
            f"Erro de transferência detectado: “{a.construcao}” → {a.alternativa_melhor}"
            for a in avaliacoes
        ]
        linhas += [
            f"Contraste relevante: {c.lado_a} × {c.lado_b} — {c.pergunta_decisiva}"
            for c in contrastes
        ]
        contexto.resumo = _com_biblioteca(
            "\n".join(linhas) or "Nenhum padrão conhecido detectado.", livros
        )
        return contexto

    contexto.resumo = ""
    return contexto


def _trechos_da_biblioteca(consulta: str, limite: int = 2) -> list[dict[str, Any]]:
    """O que os livros do estudante dizem sobre o assunto.

    Citar o livro que ele já tem em mãos vale mais que citar um genérico: ele
    pode abrir a página e continuar dali.
    """
    from ..biblioteca import buscar

    try:
        achados = buscar(consulta, limite=limite)
    except Exception:
        return []
    return [
        {
            "livro": achado["titulo"],
            "capitulo": achado.get("capitulo", ""),
            "pagina": achado.get("pagina", 0) if achado.get("formato") == "pdf" else 0,
            "trecho": achado["texto"][:300],
        }
        for achado in achados
    ]


# --------------------------------------------------------------------------
# Resposta de cada degrau
# --------------------------------------------------------------------------

@dataclass(slots=True)
class RespostaTutor:
    """O que o tutor devolve num degrau da escada."""

    texto: str
    nivel: int
    nome_do_degrau: str
    materia: str
    modo: str = "deterministico"
    revela_resposta: bool = False
    contexto: dict[str, Any] = field(default_factory=dict)
    pode_subir: bool = True

    def para_dict(self) -> dict[str, Any]:
        return {
            "texto": self.texto, "nivel": self.nivel,
            "nome_do_degrau": self.nome_do_degrau, "materia": self.materia,
            "modo": self.modo, "revela_resposta": self.revela_resposta,
            "contexto": self.contexto, "pode_subir": self.pode_subir,
        }


# Mecanismo de cada tópico, enunciado SEM veredito. É o que pode aparecer nos
# degraus intermediários: a regra geral, nunca a conclusão sobre a frase.
MECANISMOS: dict[str, tuple[str, str]] = {
    "crase": (
        "A crase só existe quando DUAS condições valem ao mesmo tempo: o termo "
        "anterior exige a preposição “a”, e o termo seguinte admite o artigo "
        "“a”. Falhando uma delas, não há crase.",
        "Troque o termo feminino por um masculino equivalente. Se aparecer "
        "“ao”, havia preposição; se aparecer só “o”, não havia.",
    ),
    "colocacao": (
        "A posição do pronome átono se decide por uma cadeia fixa: há palavra "
        "atrativa antes do verbo (negação, advérbio, pronome relativo, "
        "indefinido, demonstrativo ou conjunção subordinativa)? Se há, próclise. "
        "Se não há e o verbo está no futuro, mesóclise. Nos demais casos, ênclise.",
        "Procure, nas três palavras anteriores ao verbo, alguma das classes "
        "atrativas.",
    ),
    "concordancia": (
        "Verbo impessoal não tem sujeito e por isso não vai ao plural. Antes de "
        "concordar, descubra se existe sujeito — e qual é.",
        "Pergunte “quem pratica a ação?”. Se não houver resposta, o verbo é "
        "impessoal e fica no singular.",
    ),
    "regencia": (
        "O verbo sozinho não decide nada. A cadeia é: VERBO → SENTIDO → "
        "TRANSITIVIDADE → PREPOSIÇÃO. O mesmo verbo muda de regência conforme "
        "o sentido em que está empregado.",
        "Determine primeiro em que sentido o verbo está na frase; só depois "
        "olhe para o complemento.",
    ),
}


def _ajuda_portugues(nivel: int, contexto: ContextoVerificado) -> str:
    """Ajuda de português, revelando o veredito apenas no último degrau."""
    gramatica = contexto.dados.get("gramatica", {})
    achados = gramatica.get("achados", [])
    topicos = gramatica.get("topicos_envolvidos", [])
    principal = topicos[0] if topicos else "regencia"
    mecanismo, teste = MECANISMOS.get(principal, MECANISMOS["regencia"])

    if nivel == 0:
        nomes = ", ".join(topicos) or "sintaxe"
        return (
            f"O que está em jogo aqui é **{nomes}**.\n\n"
            "Antes de decidir qualquer coisa: encontre o verbo da oração e "
            "determine em que sentido ele está empregado."
        )
    if nivel == 1:
        for achado in achados:
            if achado.get("pergunta_guia"):
                return achado["pergunta_guia"]
        return "Qual é o verbo desta oração, e em que sentido ele está empregado aqui?"
    if nivel == 2:
        return mecanismo
    if nivel == 3:
        return f"{mecanismo}\n\n**Teste a aplicar:** {teste}"
    if nivel in (4, 5):
        alvo = achados[0]["trecho"] if achados else ""
        return (
            f"O ponto a examinar é: **{alvo}**.\n\n{teste}\n\n"
            "Aplique o teste nesse trecho e veja o que sai. Qual das duas "
            "condições você consegue confirmar?"
        )

    # Degrau 6: agora sim, o veredito completo.
    if not achados:
        return "Nenhuma das armadilhas clássicas aparece nesta frase."
    linhas = []
    for achado in achados:
        rotulo = {"erro": "✗", "correto": "✓", "depende": "?"}.get(achado["veredito"], "·")
        linhas.append(f"**{rotulo} {achado['regra']}**\n\n{achado['explicacao']}")
        if achado.get("teste"):
            linhas.append(f"_Teste:_ {achado['teste']}")
    return "\n\n".join(linhas)


def _ajuda_matematica(nivel: int, contexto: ContextoVerificado) -> str:
    """Ajuda de matemática; a solução simbólica só aparece no último degrau."""
    diagnostico = contexto.dados.get("diagnostico", {})
    analise = contexto.dados.get("analise", {})
    estrategias = diagnostico.get("estrategias", [])
    verificacoes = diagnostico.get("verificacoes", [])
    nome = diagnostico.get("topico_nome", "matemática")

    if nivel == 0:
        return (
            f"Assunto: **{nome}**, nível {diagnostico.get('dificuldade', 2)} "
            f"({diagnostico.get('dificuldade_nome', '')}).\n\n"
            "Antes de calcular: o que o enunciado DÁ e o que ele PEDE? "
            "Escreva as duas listas antes da primeira conta."
        )
    if nivel == 1:
        return (
            "Que estrutura este problema esconde? Procure simetria, fatoração, "
            "invariante, substituição que simplifique ou uma leitura "
            "geométrica.\n\nQual delas parece estar aqui?"
        )
    if nivel == 2 and estrategias:
        return (
            f"Em problemas de {nome.lower()}, o caminho que mais resolve é: "
            f"**{estrategias[0]}**.\n\nTente enxergar o enunciado assim."
        )
    if nivel == 3 and estrategias:
        lista = "\n".join(f"- {e}" for e in estrategias[:3])
        return f"Os caminhos plausíveis aqui são:\n{lista}\n\nEscolha um e vá até o fim."
    if nivel in (4, 5):
        equacoes = analise.get("equacoes_latex") or analise.get("equacoes") or []
        if equacoes:
            return (
                "Primeiro passo: traduzir o enunciado para linguagem simbólica. "
                f"A leitura automática dá:\n\n$${equacoes[0]}$$\n\n"
                "O que você faz com essa equação agora?"
            )
        return "Monte a equação que traduz o enunciado. Qual grandeza vira a incógnita?"

    # Degrau 6: entrega o que a álgebra computacional apurou.
    solucoes = analise.get("solucoes_latex") or analise.get("solucoes") or {}
    if solucoes:
        linhas = ["**Resolução simbólica**", ""]
        for variavel, valores in solucoes.items():
            if len(valores) > 1:
                linhas.append(f"- $${variavel} \\in \\left\\{{{', '.join(valores)}"
                              f"\\right\\}}$$")
            else:
                linhas.append(f"- $${variavel} = {valores[0]}$$")
        checagens = analise.get("checagens", [])
        if checagens:
            linhas += ["", "**Verificação**", ""]
            linhas += [
                f"- {'✓' if c['passou'] else '✗'} {c['nome']}: {c['detalhe']}"
                for c in checagens
            ]
        linhas += [
            "",
            "_Resolvido e conferido por álgebra computacional. Para a explicação "
            "passo a passo, configure `ANTHROPIC_API_KEY`._",
        ]
        return "\n".join(linhas)

    lista = "\n".join(f"- {v}" for v in verificacoes)
    return (
        "Não consegui ler uma equação explícita neste enunciado, então a "
        f"resolução automática não se aplica. Ao chegar a um resultado, "
        f"confira assim:\n{lista}"
    )


def _ajuda_ingles(nivel: int, contexto: ContextoVerificado) -> str:
    """Ajuda de inglês; a correção só no último degrau."""
    avaliacoes = contexto.dados.get("avaliacoes", [])
    contrastes = contexto.dados.get("contrastes", [])

    if nivel == 0:
        if contrastes:
            return (
                f"A dúvida aqui é do tipo **{contrastes[0]['lado_a']} × "
                f"{contrastes[0]['lado_b']}**.\n\n"
                "Antes de escolher, decida que SIGNIFICADO você quer expressar."
            )
        return (
            "Antes de julgar a frase, separe quatro perguntas: está gramatical? "
            "significa o que você quer? soa natural? serve ao registro?"
        )
    if nivel == 1 and contrastes:
        return contrastes[0]["pergunta_decisiva"]
    if nivel == 1:
        return "Que ideia exatamente você quer expressar com esta frase?"
    if nivel in (2, 3) and contrastes:
        c = contrastes[0]
        return (
            f"**{c['lado_a']} × {c['lado_b']}**\n\n{c['criterio']}\n\n"
            f"- {c['exemplo_a']}\n- {c['exemplo_b']}\n\n"
            "Compare a sua frase com esses dois exemplos."
        )
    if nivel in (2, 3, 4, 5) and avaliacoes:
        return (
            "Há uma construção nesta frase que vem da estrutura do português, "
            "não do inglês. Releia procurando onde a tradução foi palavra por "
            "palavra.\n\nQual trecho você mudaria?"
        )
    if nivel in (4, 5):
        return (
            "Reescreva a frase começando pelo verbo principal e conferindo, um "
            "a um: sujeito, tempo verbal, preposição."
        )

    # Degrau 6.
    if avaliacoes:
        a = avaliacoes[0]
        return (
            f"A construção “{a['construcao']}” não existe no inglês padrão.\n\n"
            f"{a['erro_tipico']}\n\nA forma correta usa **{a['alternativa_melhor']}**."
            f"\n\n{a['observacao']}"
        )
    if contrastes:
        c = contrastes[0]
        return (
            f"**{c['lado_a']} × {c['lado_b']}**\n\n{c['criterio']}\n\n"
            f"- {c['exemplo_a']}\n- {c['exemplo_b']}\n\n"
            f"Erro típico: {c['erro_tipico']}"
        )
    return "Não encontrei nesta frase nenhum dos padrões que sei verificar."


def _ajuda_deterministica(
    degrau_atual: Degrau, contexto: ContextoVerificado, enunciado: str
) -> str:
    """Monta a ajuda do degrau sem modelo de linguagem.

    É menos fluente que a versão neural, mas é honesta: cada linha vem de um
    verificador. E respeita a escada — o veredito sobre a questão específica
    só aparece no degrau 6, porque entregá-lo antes destruiria o exercício.
    """
    nivel = degrau_atual.nivel
    if contexto.materia == "matematica":
        return _ajuda_matematica(nivel, contexto)
    if contexto.materia == "portugues":
        return _ajuda_portugues(nivel, contexto)
    if contexto.materia == "ingles":
        return _ajuda_ingles(nivel, contexto)

    if nivel >= 5:
        return (
            "Para esta questão eu não tenho um verificador determinístico. "
            "Configure `ANTHROPIC_API_KEY` para a tutoria explicada."
        )
    return (
        "Comece separando o que o enunciado DÁ do que ele PEDE. "
        "Qual é o primeiro passo que você conseguiria justificar?"
    )


async def orientar(
    enunciado: str,
    nivel: int,
    materia: str = "",
    tentativa: str = "",
    contexto: ContextoVerificado | None = None,
) -> RespostaTutor:
    """Produz a ajuda do degrau pedido."""
    contexto = contexto or await apurar(enunciado, materia)
    degrau_atual = degrau(nivel)

    motor = obter_motor()
    if not motor.disponivel:
        return RespostaTutor(
            texto=_ajuda_deterministica(degrau_atual, contexto, enunciado),
            nivel=degrau_atual.nivel,
            nome_do_degrau=degrau_atual.nome,
            materia=contexto.materia,
            modo="deterministico",
            revela_resposta=degrau_atual.revela_resposta,
            contexto=contexto.para_dict(),
            pode_subir=degrau_atual.nivel < NIVEL_MAXIMO,
        )

    pedaco_tentativa = (
        f"\n\nTentativa do estudante até agora:\n{tentativa.strip()}"
        if tentativa.strip() else "\n\nO estudante ainda não mostrou tentativa."
    )
    try:
        texto = await motor.responder(
            sistema_tutor(degrau_atual, contexto.materia, contexto.resumo),
            f"Questão:\n{enunciado}{pedaco_tentativa}",
            max_tokens=max(300, degrau_atual.tamanho_maximo),
        )
        modo = "neural"
    except ErroModelo:
        texto = _ajuda_deterministica(degrau_atual, contexto, enunciado)
        modo = "deterministico"

    return RespostaTutor(
        texto=texto, nivel=degrau_atual.nivel, nome_do_degrau=degrau_atual.nome,
        materia=contexto.materia, modo=modo,
        revela_resposta=degrau_atual.revela_resposta,
        contexto=contexto.para_dict(),
        pode_subir=degrau_atual.nivel < NIVEL_MAXIMO,
    )


# --------------------------------------------------------------------------
# Diagnostico da tentativa
# --------------------------------------------------------------------------

@dataclass(slots=True)
class Diagnostico:
    """O primeiro erro da tentativa, e nada além dele."""

    veredito: str                # correto | parcial | incorreto
    ate_onde_correto: str = ""
    primeiro_erro: str = ""
    por_que: str = ""
    tipo_erro: str = ""
    pergunta_que_faltou: str = ""
    quase_la: bool = False
    resposta: str = ""
    modo: str = "deterministico"

    def para_dict(self) -> dict[str, Any]:
        return {
            "veredito": self.veredito,
            "ate_onde_correto": self.ate_onde_correto,
            "primeiro_erro": self.primeiro_erro,
            "por_que": self.por_que,
            "tipo_erro": self.tipo_erro,
            "pergunta_que_faltou": self.pergunta_que_faltou,
            "quase_la": self.quase_la,
            "resposta": self.resposta,
            "modo": self.modo,
        }


def _diagnostico_deterministico(
    tentativa: str, contexto: ContextoVerificado
) -> Diagnostico | None:
    """Diagnóstico que os verificadores conseguem dar sozinhos."""
    if contexto.materia == "portugues":
        analise = analisar_frase(tentativa)
        erros = [a for a in analise.achados if a.veredito == "erro"]
        if erros:
            primeiro = erros[0]
            return Diagnostico(
                veredito="incorreto",
                ate_onde_correto="o trecho anterior ao ponto abaixo se sustenta",
                primeiro_erro=f"{primeiro.trecho} — {primeiro.regra}",
                por_que=primeiro.explicacao,
                tipo_erro="conceitual",
                pergunta_que_faltou=primeiro.teste or primeiro.pergunta_guia,
                resposta=(
                    f"Até antes deste ponto, tudo bem.\n\n"
                    f"O primeiro problema aparece em: **{primeiro.trecho}**.\n\n"
                    f"{primeiro.explicacao}\n\n"
                    f"Pergunta para você corrigir sozinho: {primeiro.teste}"
                ),
            )

    if contexto.materia == "ingles":
        avaliacoes = avaliar_estrutura(tentativa)
        if avaliacoes:
            primeira = avaliacoes[0]
            return Diagnostico(
                veredito="incorreto",
                ate_onde_correto="a intenção está clara",
                primeiro_erro=f"“{primeira.construcao}”",
                por_que=primeira.erro_tipico,
                tipo_erro="confusao_entre_regras",
                pergunta_que_faltou=(
                    "Como essa ideia se estrutura em inglês, sem traduzir o "
                    "português palavra por palavra?"
                ),
                resposta=(
                    f"A intenção está clara, mas “{primeira.construcao}” não "
                    f"funciona em inglês.\n\n{primeira.erro_tipico}\n\n"
                    f"A construção correta usa **{primeira.alternativa_melhor}**. "
                    f"{primeira.observacao}"
                ),
            )
    return None


async def avaliar_tentativa(
    enunciado: str,
    tentativa: str,
    materia: str = "",
    contexto: ContextoVerificado | None = None,
) -> Diagnostico:
    """Localiza o PRIMEIRO erro da tentativa e devolve a correção dirigida."""
    contexto = contexto or await apurar(enunciado, materia)

    motor = obter_motor()
    if not motor.disponivel:
        deterministico = _diagnostico_deterministico(tentativa, contexto)
        if deterministico:
            return deterministico
        return Diagnostico(
            veredito="indeterminado",
            resposta=(
                "Sem `ANTHROPIC_API_KEY` configurada, só consigo diagnosticar a "
                "tentativa quando ela cai numa das armadilhas que os "
                "verificadores conhecem. Para a análise passo a passo do seu "
                "raciocínio, configure a chave."
            ),
        )

    verificado = (
        f"\n\nApurado por verificadores independentes:\n{contexto.resumo}"
        if contexto.resumo else ""
    )
    base = f"Questão:\n{enunciado}\n\nTentativa do estudante:\n{tentativa}{verificado}"

    try:
        dados = await motor.responder_json(SISTEMA_DIAGNOSTICO, base, max_tokens=1200)
    except ErroModelo:
        deterministico = _diagnostico_deterministico(tentativa, contexto)
        return deterministico or Diagnostico(
            veredito="indeterminado",
            resposta="Não consegui analisar a tentativa agora.",
        )

    if not isinstance(dados, dict):
        dados = {}

    diagnostico = Diagnostico(
        veredito=str(dados.get("veredito", "indeterminado")),
        ate_onde_correto=str(dados.get("ate_onde_esta_correto", "")),
        primeiro_erro=str(dados.get("primeiro_erro", "")),
        por_que=str(dados.get("por_que_esta_errado", "")),
        tipo_erro=str(dados.get("tipo_erro", "")),
        pergunta_que_faltou=str(dados.get("pergunta_que_faltou", "")),
        quase_la=bool(dados.get("quase_la", False)),
        modo="neural",
    )

    try:
        diagnostico.resposta = await motor.responder(
            SISTEMA_RESPOSTA_A_TENTATIVA,
            f"{base}\n\nDiagnóstico apurado:\n"
            f"- até onde está correto: {diagnostico.ate_onde_correto}\n"
            f"- primeiro erro: {diagnostico.primeiro_erro}\n"
            f"- por quê: {diagnostico.por_que}\n"
            f"- pergunta que faltou: {diagnostico.pergunta_que_faltou}",
            max_tokens=900,
        )
    except ErroModelo:
        diagnostico.resposta = (
            f"{diagnostico.ate_onde_correto}\n\n"
            f"Primeiro erro: {diagnostico.primeiro_erro}\n\n{diagnostico.por_que}"
        )
    return diagnostico


async def generalizar(enunciado: str, materia: str = "") -> str:
    """A regra transferível que a questão ensina."""
    motor = obter_motor()
    contexto = await apurar(enunciado, materia)
    if not motor.disponivel:
        if contexto.materia == "matematica":
            estrategias = contexto.dados.get("diagnostico", {}).get("estrategias", [])
            if estrategias:
                return f"Sempre que aparecer este tipo de problema, teste primeiro: {estrategias[0]}."
        if contexto.materia == "portugues":
            achados = contexto.dados.get("gramatica", {}).get("achados", [])
            if achados:
                return f"Quando aparecer {achados[0]['regra']}: {achados[0]['teste']}"
        return ""
    try:
        return await motor.responder(
            SISTEMA_GENERALIZACAO,
            f"Questão:\n{enunciado}\n\nContexto apurado:\n{contexto.resumo}",
            max_tokens=250,
        )
    except ErroModelo:
        return ""
