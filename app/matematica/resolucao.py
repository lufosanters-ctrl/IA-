"""Orquestracao da resolucao: COMPREENDER → MODELAR → EXPLORAR → RESOLVER →
VERIFICAR → EXPLICAR → GENERALIZAR.

O ponto importante nao e a sequencia de fases, e o fato de a verificacao ser
**independente**: quem confere nao e o mesmo processo que resolveu. O sistema
algebrico resolve por conta propria e confronta o resultado; so depois disso
um segundo passe critica a solucao, ja de posse do veredito do verificador.

A profundidade e adaptativa. Problema de aplicacao direta faz uma passada.
Problema de nivel ITA/IME faz escolha de estrategia, resolucao, verificacao
simbolica, critica e, se preciso, correcao.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from ..ai.llm import ErroModelo, obter_motor
from . import simbolico
from .classificacao import Diagnostico, classificar
from .prompts import (
    SISTEMA_CORRECAO,
    SISTEMA_CRITICO,
    SISTEMA_ESTRATEGIAS,
    sistema_resolvedor,
    sistema_socratico,
)
from .simbolico import AnaliseSimbolica, Checagem

# Tempo maximo para o trabalho simbolico, que e CPU pura e roda fora do laco.
LIMITE_SIMBOLICO = 12.0


@dataclass(slots=True)
class Problema:
    """Um problema de matematica submetido ao motor."""

    enunciado: str
    tentativa: str = ""
    nivel_aluno: str = "intermediario"


@dataclass(slots=True)
class Resolucao:
    """Tudo o que o motor produziu, incluindo o que nao deu certo."""

    enunciado: str
    diagnostico: Diagnostico
    analise: AnaliseSimbolica
    texto: str = ""
    modo: str = "simbolico"           # neural | simbolico
    estrategias: dict[str, Any] = field(default_factory=dict)
    critica: dict[str, Any] = field(default_factory=dict)
    confronto: list[Checagem] = field(default_factory=list)
    passes: list[str] = field(default_factory=list)
    aviso: str = ""
    duracao_ms: int = 0

    @property
    def verificado(self) -> bool:
        """O resultado pode ser apresentado como resposta CONFERIDA do problema?

        Não basta as checagens passarem. A substituição confere a raiz na
        equação que o motor leu — nunca na pergunta que o enunciado fez. Se o
        enunciado impõe uma condição em prosa que a leitura não aplicou, ou
        se a pergunta não era pelas raízes, o que existe é uma leitura
        parcial, e chamá-la de verificada ensina errado.
        """
        todas = list(self.analise.checagens) + list(self.confronto)
        if not todas or not all(c.passou for c in todas):
            return False
        return not self.analise.ressalvas and self.analise.responde_a_pergunta

    @property
    def ressalvas(self) -> list[str]:
        """O que a leitura automática deixou de fora, em português claro."""
        avisos = list(self.analise.ressalvas)
        if not self.analise.responde_a_pergunta and self.analise.solucoes:
            avisos.append(
                "o enunciado não pede as raízes em si, mas algo calculado a "
                "partir delas — o que está abaixo é a leitura da equação, não "
                "a resposta final"
            )
        return avisos

    @property
    def tem_alerta(self) -> bool:
        return any(not c.passou for c in list(self.analise.checagens) + list(self.confronto))

    def para_dict(self) -> dict[str, Any]:
        return {
            "enunciado": self.enunciado,
            "diagnostico": self.diagnostico.para_dict(),
            "analise": self.analise.para_dict(),
            "texto": self.texto,
            "modo": self.modo,
            "estrategias": self.estrategias,
            "critica": self.critica,
            "confronto": [c.para_dict() for c in self.confronto],
            "passes": self.passes,
            "verificado": self.verificado,
            "ressalvas": self.ressalvas,
            "tem_alerta": self.tem_alerta,
            "aviso": self.aviso,
            "duracao_ms": self.duracao_ms,
        }


# --------------------------------------------------------------------------
# Trabalho simbolico, fora do laco de eventos
# --------------------------------------------------------------------------

async def analisar_enunciado(enunciado: str, probabilidade: bool = False) -> AnaliseSimbolica:
    """Roda o sistema algebrico numa thread, com teto de tempo."""
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(simbolico.analisar, enunciado, probabilidade),
            timeout=LIMITE_SIMBOLICO,
        )
    except asyncio.TimeoutError:
        analise = AnaliseSimbolica()
        analise.observacoes.append(
            "A conferência simbólica passou do tempo limite e foi interrompida."
        )
        return analise
    except Exception as exc:  # o verificador nunca pode derrubar a resolução
        analise = AnaliseSimbolica()
        analise.observacoes.append(f"Falha na conferência simbólica: {type(exc).__name__}")
        return analise


async def confrontar_resposta(enunciado: str, resposta: str) -> list[Checagem]:
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(simbolico.conferir_resposta, enunciado, resposta),
            timeout=LIMITE_SIMBOLICO,
        )
    except (asyncio.TimeoutError, Exception):
        return []


# --------------------------------------------------------------------------
# Texto auxiliar
# --------------------------------------------------------------------------

def _fatos_simbolicos(analise: AnaliseSimbolica) -> str:
    """O que o verificador ja estabeleceu, para o resolvedor nao contradizer."""
    if not analise.equacoes and not analise.solucoes:
        return ""
    linhas = ["Apurado por um sistema de álgebra computacional independente:"]
    if analise.equacoes:
        linhas.append("- equações lidas do enunciado: " + "; ".join(analise.equacoes))
    for variavel, valores in analise.solucoes.items():
        linhas.append(f"- {variavel} ∈ {{{', '.join(valores)}}}")
    for checagem in analise.checagens:
        marca = "confirmado" if checagem.passou else "FALHOU"
        linhas.append(f"- {checagem.nome}: {marca} — {checagem.detalhe}")
    linhas.append(
        "Estes fatos vêm de leitura automática do enunciado e podem não ser a "
        "resposta final do problema. Se você discordar, explique o porquê em vez "
        "de ignorá-los."
    )
    return "\n".join(linhas)


def _resolucao_simbolica(analise: AnaliseSimbolica, diagnostico: Diagnostico) -> str:
    """Resposta construida so com o sistema algebrico, sem modelo de linguagem.

    Nao e uma explicacao didatica, mas e matematica correta e verificada — bem
    mais util do que um texto plausivel sem conferencia.
    """
    linhas = ["## Ideia central", ""]
    if analise.resolveu:
        linhas.append(
            f"Assunto: {diagnostico.topico_nome}. O enunciado traz equação(ões) "
            "explícita(s), então o sistema de álgebra computacional resolveu e "
            "conferiu diretamente."
        )
    else:
        linhas.append(
            f"Assunto: {diagnostico.topico_nome}. Não há equação explícita no "
            "enunciado para resolver automaticamente — abaixo estão os caminhos "
            "que costumam destravar este tipo de problema."
        )

    linhas += ["", "## Solução", ""]
    equacoes = analise.equacoes_latex or analise.equacoes
    if equacoes:
        linhas.append("Equações lidas do enunciado:")
        linhas += [f"- $${e}$$" for e in equacoes]
        linhas.append("")
    if analise.solucoes_latex or analise.solucoes:
        for variavel, valores in (analise.solucoes_latex or analise.solucoes).items():
            if len(valores) > 1:
                conjunto = ", ".join(valores)
                linhas.append(f"- $${variavel} \\in \\left\\{{{conjunto}\\right\\}}$$")
            else:
                linhas.append(f"- $${variavel} = {valores[0]}$$")
        linhas.append("")
    if not analise.resolveu:
        linhas.append("Caminhos a considerar:")
        linhas += [f"- {e}" for e in diagnostico.estrategias]
        linhas.append("")

    linhas += ["## Verificação", ""]
    if analise.checagens:
        for checagem in analise.checagens:
            marca = "✓" if checagem.passou else "✗"
            linhas.append(f"- {marca} **{checagem.nome}**: {checagem.detalhe}")
    else:
        linhas.append(
            "Nenhuma verificação automática se aplicou. Confira manualmente:"
        )
        linhas += [f"- {v}" for v in diagnostico.verificacoes]
    for observacao in analise.observacoes:
        linhas.append(f"- {observacao}")

    ressalvas = list(analise.ressalvas)
    if not analise.responde_a_pergunta and analise.solucoes:
        ressalvas.append(
            "o enunciado não pede as raízes em si, mas algo calculado a partir "
            "delas"
        )

    titulo = "## Resposta" if not ressalvas else "## O que a álgebra leu"
    linhas += ["", titulo, ""]
    if analise.solucoes:
        partes = [
            " ou ".join(f"${variavel} = {valor}$" for valor in valores)
            for variavel, valores in (analise.solucoes_latex or analise.solucoes).items()
        ]
        linhas.append("; ".join(partes))
        if ressalvas:
            linhas += [
                "",
                "**Isto ainda não é a resposta do problema.** A leitura "
                "automática deixou de fora:",
                "",
            ]
            linhas += [f"- {r}" for r in ressalvas]
            linhas += [
                "",
                "Retome a partir daqui aplicando essa condição você mesmo — é "
                "justamente o passo que o enunciado está cobrando.",
            ]
    else:
        linhas.append(
            "Sem chave de API configurada, o motor só resolve automaticamente o "
            "que consegue ler como equação. Este enunciado precisa de "
            "interpretação — configure `ANTHROPIC_API_KEY` para a resolução "
            "explicada."
        )

    if ressalvas:
        rodape = (
            "> _Modo simbólico, leitura parcial: a álgebra resolveu a equação "
            "que conseguiu ler, e a substituição confere nessa equação — não "
            "na pergunta completa do enunciado._"
        )
    else:
        rodape = (
            "> _Modo simbólico: resolvido e verificado por álgebra computacional, "
            "sem modelo de linguagem. Cada valor acima foi substituído na equação "
            "original._"
        )
    linhas += ["", rodape]
    return "\n".join(linhas)


def _texto_da_critica(critica: dict[str, Any]) -> str:
    problemas = critica.get("problemas") or []
    if not problemas:
        return "Nenhum problema encontrado."
    return "\n".join(
        f"- [{p.get('gravidade', '?')}] {p.get('onde', '')}: {p.get('qual', '')}"
        f" → {p.get('como_corrigir', '')}"
        for p in problemas
    )


# --------------------------------------------------------------------------
# Resolucao
# --------------------------------------------------------------------------

async def resolver(problema: Problema) -> Resolucao:
    """Resolve o problema com profundidade proporcional a sua dificuldade."""
    inicio = asyncio.get_running_loop().time()
    enunciado = problema.enunciado.strip()
    diagnostico = classificar(enunciado)

    analise = await analisar_enunciado(enunciado, diagnostico.topico == "probabilidade")

    resolucao = Resolucao(
        enunciado=enunciado, diagnostico=diagnostico, analise=analise,
    )
    resolucao.passes.append("diagnóstico")
    resolucao.passes.append("álgebra computacional")

    motor = obter_motor()
    if not motor.disponivel:
        resolucao.texto = _resolucao_simbolica(analise, diagnostico)
        resolucao.modo = "simbolico"
        resolucao.aviso = (
            "Sem ANTHROPIC_API_KEY configurada: resolução feita por álgebra "
            "computacional, sem explicação em linguagem natural."
        )
        resolucao.duracao_ms = int((asyncio.get_running_loop().time() - inicio) * 1000)
        return resolucao

    fatos = _fatos_simbolicos(analise)
    contexto_aluno = (
        f"\n\nNível do estudante: {problema.nivel_aluno}. "
        "Ajuste a linguagem, não o rigor."
    )
    tentativa = (
        f"\n\nO estudante tentou assim:\n{problema.tentativa.strip()}\n"
        "Aponte onde a tentativa sai do rumo, se sair."
        if problema.tentativa.strip() else ""
    )

    # --- Fase de exploração: só para problema que a justifica ------------
    if diagnostico.usar_estrategias_multiplas:
        try:
            estrategias = await motor.responder_json(
                SISTEMA_ESTRATEGIAS,
                f"Enunciado:\n{enunciado}\n\n{fatos}",
                max_tokens=1400,
            )
            if isinstance(estrategias, dict):
                resolucao.estrategias = estrategias
                resolucao.passes.append("escolha de estratégia")
        except ErroModelo:
            pass

    escolha = ""
    if resolucao.estrategias.get("escolhido"):
        escolha = (
            f"\n\nEstratégia escolhida na fase de exploração: "
            f"{resolucao.estrategias['escolhido']}. "
            f"Estrutura identificada: "
            f"{resolucao.estrategias.get('estrutura_escondida', 'não declarada')}. "
            "Siga essa estratégia, a menos que ela se mostre inviável no meio do "
            "caminho — nesse caso, diga por quê e mude."
        )

    # --- Resolução --------------------------------------------------------
    prompt = (
        f"Problema:\n{enunciado}{contexto_aluno}{tentativa}{escolha}\n\n"
        f"{fatos}\n\nResolva."
    )
    try:
        resolucao.texto = await motor.responder(
            sistema_resolvedor(diagnostico), prompt,
            max_tokens=diagnostico.orcamento_tokens,
        )
        resolucao.modo = "neural"
        resolucao.passes.append("resolução")
    except ErroModelo as exc:
        resolucao.texto = _resolucao_simbolica(analise, diagnostico)
        resolucao.modo = "simbolico"
        resolucao.aviso = f"O modelo falhou ({exc}); caí para a resolução simbólica."
        resolucao.duracao_ms = int((asyncio.get_running_loop().time() - inicio) * 1000)
        return resolucao

    # --- Confronto independente ------------------------------------------
    resolucao.confronto = await confrontar_resposta(enunciado, resolucao.texto)
    if resolucao.confronto:
        resolucao.passes.append("confronto simbólico")

    # --- Crítica: em problema difícil, ou sempre que algo não fechou -----
    precisa_criticar = diagnostico.usar_critico or resolucao.tem_alerta
    if precisa_criticar:
        veredito_simbolico = "\n".join(
            f"- {c.nome}: {'confirmado' if c.passou else 'FALHOU'} — {c.detalhe}"
            for c in list(analise.checagens) + list(resolucao.confronto)
        ) or "- o verificador simbólico não teve o que checar neste problema"

        try:
            critica = await motor.responder_json(
                SISTEMA_CRITICO,
                f"Enunciado:\n{enunciado}\n\nSolução apresentada:\n{resolucao.texto}\n\n"
                f"Verificação simbólica independente:\n{veredito_simbolico}",
                max_tokens=1600,
            )
            if isinstance(critica, dict):
                resolucao.critica = critica
                resolucao.passes.append("crítica interna")
        except ErroModelo:
            pass

        # --- Correção, se a crítica encontrou algo que importa -----------
        graves = [
            p for p in (resolucao.critica.get("problemas") or [])
            if p.get("gravidade") in {"critico", "serio"}
        ]
        if graves or resolucao.critica.get("veredito") in {"corrigir", "refazer"}:
            try:
                corrigida = await motor.responder(
                    SISTEMA_CORRECAO,
                    f"Enunciado:\n{enunciado}\n\nSolução anterior:\n{resolucao.texto}\n\n"
                    f"Crítica:\n{_texto_da_critica(resolucao.critica)}\n\n"
                    f"Verificação simbólica:\n{veredito_simbolico}",
                    max_tokens=diagnostico.orcamento_tokens,
                )
                if corrigida.strip():
                    resolucao.texto = corrigida
                    resolucao.passes.append("correção")
                    # A correção muda a resposta: confronta de novo.
                    resolucao.confronto = await confrontar_resposta(enunciado, resolucao.texto)
            except ErroModelo:
                pass

    resolucao.duracao_ms = int((asyncio.get_running_loop().time() - inicio) * 1000)
    return resolucao


# --------------------------------------------------------------------------
# Modo socratico
# --------------------------------------------------------------------------

@dataclass(slots=True)
class Pista:
    """Uma dica graduada, que nao entrega a resposta."""

    texto: str
    nivel: int
    modo: str = "simbolico"
    diagnostico: dict[str, Any] = field(default_factory=dict)

    def para_dict(self) -> dict[str, Any]:
        return {
            "texto": self.texto, "nivel": self.nivel, "modo": self.modo,
            "diagnostico": self.diagnostico,
        }


def _pista_estrutural(diagnostico: Diagnostico, nivel: int) -> str:
    """Pista montada sem modelo de linguagem, a partir do diagnostico."""
    estrategias = diagnostico.estrategias or ["traduzir o enunciado para símbolos"]
    if nivel <= 1:
        return (
            f"Este é um problema de **{diagnostico.topico_nome.lower()}**. "
            "Antes de calcular, pergunte-se: que estrutura o enunciado está "
            "escondendo? O que se repete, o que é simétrico, o que se conserva?"
        )
    if nivel == 2:
        return (
            f"Em problemas de {diagnostico.topico_nome.lower()}, o caminho mais "
            f"frequente é: **{estrategias[0]}**. Tente enxergar o enunciado "
            "dessa forma antes de escrever contas."
        )
    if nivel == 3:
        alternativas = "\n".join(f"- {e}" for e in estrategias[:3])
        return (
            f"Os caminhos que costumam funcionar aqui:\n{alternativas}\n\n"
            "Escolha um e vá até o fim antes de trocar."
        )
    verificacoes = "\n".join(f"- {v}" for v in diagnostico.verificacoes)
    return (
        f"Desenvolva pelo caminho **{estrategias[0]}**. Quando chegar a um "
        f"resultado, confira assim:\n{verificacoes}\n\n"
        "Se quiser a resolução completa, use o botão de resolver."
    )


async def dar_pista(problema: Problema, nivel: int = 1) -> Pista:
    """Modo socratico: a menor ajuda capaz de destravar o estudante."""
    nivel = max(1, min(4, int(nivel)))
    enunciado = problema.enunciado.strip()
    diagnostico = classificar(enunciado)

    motor = obter_motor()
    if not motor.disponivel:
        return Pista(
            texto=_pista_estrutural(diagnostico, nivel), nivel=nivel,
            modo="simbolico", diagnostico=diagnostico.para_dict(),
        )

    tentativa = (
        f"\n\nTentativa do estudante:\n{problema.tentativa.strip()}"
        if problema.tentativa.strip() else
        "\n\nO estudante ainda não mostrou tentativa."
    )
    contexto = (
        f"Assunto detectado: {diagnostico.topico_nome}. "
        f"Nível do problema: {diagnostico.dificuldade_nome}."
    )
    try:
        texto = await motor.responder(
            sistema_socratico(nivel),
            f"Problema:\n{enunciado}{tentativa}\n\n{contexto}",
            max_tokens=700,
        )
        return Pista(texto=texto, nivel=nivel, modo="neural",
                     diagnostico=diagnostico.para_dict())
    except ErroModelo:
        return Pista(
            texto=_pista_estrutural(diagnostico, nivel), nivel=nivel,
            modo="simbolico", diagnostico=diagnostico.para_dict(),
        )
