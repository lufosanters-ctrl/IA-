"""Aferição: mede se os motores estão respondendo certo.

Teste de unidade prova que o código faz o que o código diz. Isto aqui é outra
coisa: um conjunto de casos com GABARITO CONHECIDO, tirados das regras
consagradas e do tipo de questão que cai em prova, rodados contra os motores
determinísticos para responder a uma pergunta que nenhum teste de unidade
responde — *a plataforma está acertando?*

O resultado é uma taxa de acerto por área e a lista do que errou. Quando um
motor regride, aparece aqui antes de aparecer para o estudante.

    python -m app.afericao              roda tudo
    python -m app.afericao --area crase
    python -m app.afericao --falhas     mostra só o que errou
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from typing import Any, Callable

# --------------------------------------------------------------------------
# Casos de referência
# --------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Caso:
    """Uma entrada com resposta conhecida."""

    area: str
    entrada: str
    esperado: Any
    porque: str = ""

    @property
    def rotulo(self) -> str:
        return f"[{self.area}] {self.entrada[:70]}"


# Crase: "obrigatoria" quando o acento é exigido, "proibida" quando é vedado,
# "facultativa" quando as duas grafias são aceitas, "depende" quando a decisão
# exige saber o sentido do verbo.
CASOS_CRASE: tuple[Caso, ...] = (
    Caso("crase", "Ele começou a chorar de repente.", "proibida", "antes de verbo"),
    Caso("crase", "Entreguei o livro a ela.", "proibida", "antes de pronome pessoal"),
    Caso("crase", "Refiro-me a esta questão.", "proibida", "antes de demonstrativo"),
    Caso("crase", "Não cheguei a nenhuma conclusão.", "proibida", "antes de indefinido"),
    Caso("crase", "Dirigiu-se a Vossa Excelência.", "proibida", "pronome de tratamento"),
    Caso("crase", "Referiu-se a pessoas ausentes.", "proibida", "“a” singular, termo plural"),
    Caso("crase", "Vou a supermercado novo.", "proibida", "palavra masculina"),
    Caso("crase", "Ficaram cara a cara.", "proibida", "palavras repetidas"),
    Caso("crase", "Fomos a pé até lá.", "proibida", "locução masculina"),
    Caso("crase", "Esperava desde as 8 horas.", "proibida", "preposição já presente"),
    Caso("crase", "Vou para a praia.", "proibida", "“para” é a preposição"),
    Caso("crase", "O prazo vai de 2 a 4 semanas.", "proibida", "numeral cardinal"),

    Caso("crase", "Saímos às pressas.", "obrigatoria", "locução adverbial feminina"),
    Caso("crase", "Trabalha à noite.", "obrigatoria", "locução adverbial feminina"),
    Caso("crase", "Agiu à revelia do chefe.", "obrigatoria", "locução adverbial"),
    Caso("crase", "Ficou à frente de todos.", "obrigatoria", "locução prepositiva"),
    Caso("crase", "À medida que estudava, melhorava.", "obrigatoria", "locução conjuntiva"),
    Caso("crase", "A aula começa às 14 horas.", "obrigatoria", "horas determinadas"),
    Caso("crase", "Vou à praia amanhã.", "obrigatoria", "“ir” rege “a” + artigo"),
    Caso("crase", "Obedeço às normas da casa.", "obrigatoria", "“obedecer” rege “a”"),
    Caso("crase", "Refiro-me à questão anterior.", "obrigatoria", "“referir” rege “a”"),
    Caso("crase", "Cheguei à escola cedo.", "obrigatoria", "“chegar” rege “a”"),

    Caso("crase", "Entreguei o convite a Maria.", "facultativa", "nome próprio feminino"),
    Caso("crase", "Referiu-se a minha proposta.", "facultativa", "possessivo feminino"),
    Caso("crase", "Andamos até a esquina.", "facultativa", "depois de “até”"),

    Caso("crase", "Assisti a sessão de cinema.", "depende_da_regencia",
         "“assistir” muda de regência conforme o sentido"),
    Caso("crase", "Visava a vaga de estágio.", "depende_da_regencia",
         "“visar” muda de regência conforme o sentido"),

    # Frases corretas que o motor já acusou indevidamente. Cada uma marca um
    # falso positivo real, corrigido e agora vigiado.
    Caso("crase", "A noite estava fria e silenciosa.", "proibida",
         "“a noite” aqui é sujeito, não locução adverbial"),
    Caso("crase", "A vista do mar é linda daqui.", "proibida",
         "“a vista” é sujeito, não locução"),
    Caso("crase", "A direita venceu a eleição.", "proibida",
         "“a direita” é sujeito, não locução"),
    Caso("crase", "Convidei a aluna ontem.", "depende_da_regencia",
         "“convidar” é bitransitivo: o termo colado é objeto direto"),
    Caso("crase", "Informei a diretora sobre o caso.", "depende_da_regencia",
         "“informar” é bitransitivo"),
    Caso("crase", "Prefiro a matemática.", "depende_da_regencia",
         "“preferir” é bitransitivo: aqui o termo é objeto direto"),
    Caso("crase", "Refiro-me à mulher que chegou.", "obrigatoria",
         "“mulher” é substantivo feminino, não verbo no infinitivo"),
    Caso("crase", "A prova começa às oito horas.", "obrigatoria",
         "hora determinada escrita por extenso"),
    Caso("crase", "Dedicou o livro à sua mãe.", "facultativa",
         "possessivo feminino: “sua” não é pronome de tratamento"),
    Caso("crase", "Levou o filho a escola nova.", "depende_da_regencia",
         "“escola” é feminino; falta saber a regência de “levar”"),
    Caso("crase", "Comprei o carro à vista.", "obrigatoria",
         "locução adverbial fora da posição de sujeito"),
)

# Colocação: a posição que a norma-padrão exige.
CASOS_COLOCACAO: tuple[Caso, ...] = (
    Caso("colocacao", "Não me disseram a verdade.", "próclise", "negação atrai"),
    Caso("colocacao", "Ninguém me avisou disso.", "próclise", "indefinido atrai"),
    Caso("colocacao", "Sempre me ajudaram muito.", "próclise", "advérbio atrai"),
    Caso("colocacao", "Quando me chamaram, atendi.", "próclise", "conjunção subordinativa"),
    Caso("colocacao", "O livro que me deram é bom.", "próclise", "pronome relativo"),
    Caso("colocacao", "Entregaram-me o prêmio ontem.", "ênclise", "sem fator de próclise"),
    Caso("colocacao", "Chamou-me para conversar.", "ênclise", "início de período"),
    Caso("colocacao", "Dar-te-ei o recado amanhã.", "mesóclise", "futuro sem atrativa"),
    Caso("colocacao", "Falar-lhe-ia sobre o assunto.", "mesóclise", "futuro do pretérito"),

    # Falsos positivos corrigidos.
    Caso("colocacao", "Ele mora no Brasil desde criança.", "nenhum pronome",
         "“no” é contração, não pronome átono"),
    Caso("colocacao", "Deixei o livro na estante da sala.", "nenhum pronome",
         "“na” é contração, não pronome átono"),
    Caso("colocacao", "Quando cheguei, sentei-me à mesa.", "ênclise",
         "a vírgula fecha a oração: “Quando” não atrai o pronome seguinte"),
    Caso("colocacao", "Portanto, entregou-se à leitura.", "ênclise",
         "“portanto” coordena e não atrai"),
    Caso("colocacao", "Assim que terminou, levantou-se.", "ênclise",
         "a atrativa ficou na oração anterior"),
    Caso("colocacao", "Ele considera-se preparado.", "ênclise",
         "“considera” é presente, não futuro: não cabe mesóclise"),
    Caso("colocacao", "Ainda que soubesse, não me diria nada.", "próclise",
         "locução conjuntiva subordinativa atrai"),
)

# Concordância: "erro" quando a frase viola a norma, "correto" quando respeita.
CASOS_CONCORDANCIA: tuple[Caso, ...] = (
    Caso("concordancia", "Haviam muitas pessoas na fila.", "erro", "haver impessoal"),
    Caso("concordancia", "Houveram problemas na prova.", "erro", "haver impessoal"),
    Caso("concordancia", "Havia muitas pessoas na fila.", "correto", "singular certo"),
    Caso("concordancia", "Fazem dois anos que não o vejo.", "erro", "fazer temporal"),
    Caso("concordancia", "Precisa-se de professores.", "correto", "indeterminação do sujeito"),

    # Falsos positivos corrigidos.
    Caso("concordancia", "Eles haviam chegado antes de nós.", "correto",
         "“haver” auxiliar de tempo composto concorda normalmente"),
    Caso("concordancia", "Os alunos haviam estudado bastante.", "correto",
         "auxiliar, não impessoal"),
    Caso("concordancia", "Refere-se aos alunos aprovados.", "nada detectado",
         "“aos” é contração, não sujeito no plural: nada a acusar"),
    Caso("concordancia", "Trata-se das questões mais difíceis.", "nada detectado",
         "“das” é contração, não sujeito: nada a acusar"),
    Caso("concordancia", "Vendem-se casas na praia.", "correto",
         "passiva sintética com verbo no plural"),
    Caso("concordancia", "Vende-se casas na praia.", "erro",
         "passiva sintética exige plural"),
)

# Regência em uso: a frase usou a preposição que o verbo pede?
CASOS_REGENCIA_USO: tuple[Caso, ...] = (
    Caso("regencia_uso", "Prefiro café do que chá.", True, "“preferir” não aceita “do que”"),
    Caso("regencia_uso", "Obedeço as regras da escola.", True, "“obedecer” exige “a”"),
    Caso("regencia_uso", "Cheguei em casa tarde demais.", True, "“chegar” rege “a”"),
    Caso("regencia_uso", "Namorei com a Ana por dois anos.", True, "“namorar” é direto"),
    Caso("regencia_uso", "Aludiu o caso durante a aula.", True, "“aludir” exige “a”"),
    Caso("regencia_uso", "Isso depende em você.", True, "“depender” rege “de”"),
    Caso("regencia_uso", "Respondi a carta ontem.", True, "“responder” rege “a”"),

    Caso("regencia_uso", "Prefiro café a chá.", False, "construção correta"),
    Caso("regencia_uso", "Obedeço às regras da escola.", False, "construção correta"),
    Caso("regencia_uso", "Cheguei a casa tarde demais.", False,
         "“casa” sem determinante dispensa artigo"),
    Caso("regencia_uso", "Namorei a Ana por dois anos.", False, "construção correta"),
    Caso("regencia_uso", "Gosto de estudar à noite.", False, "construção correta"),
    Caso("regencia_uso", "Moro em São Paulo há dez anos.", False, "construção correta"),
    Caso("regencia_uso", "Simpatizo com a proposta dele.", False, "construção correta"),
)

# Regência: o verbo exige a preposição "a" em ALGUM sentido registrado?
CASOS_REGENCIA: tuple[Caso, ...] = (
    Caso("regencia", "assistir", True, "assistir a um filme"),
    Caso("regencia", "obedecer", True, "obedecer a algo"),
    Caso("regencia", "aspirar", True, "aspirar a um cargo"),
    Caso("regencia", "visar", True, "visar a um objetivo"),
    Caso("regencia", "preferir", True, "preferir X a Y"),
    Caso("regencia", "gostar", False, "gostar DE algo"),
    Caso("regencia", "consistir", False, "consistir EM algo"),
    Caso("regencia", "simpatizar", False, "simpatizar COM algo"),
    Caso("regencia", "depender", False, "depender DE algo"),
    Caso("regencia", "namorar", False, "transitivo direto"),
)

# Inglês: a construção tem erro de transferência do português?
CASOS_INGLES: tuple[Caso, ...] = (
    Caso("ingles", "People is waiting outside.", True, "people é plural"),
    Caso("ingles", "Can you explain me this rule?", True, "explain exige “to”"),
    Caso("ingles", "It depends of the weather.", True, "depend on"),
    Caso("ingles", "She is married with a doctor.", True, "married to"),
    Caso("ingles", "I have 20 years old.", True, "be + idade"),
    Caso("ingles", "I live here since three years.", True, "since × for"),
    Caso("ingles", "He gave me some good advices.", True, "advice é incontável"),
    Caso("ingles", "I didn't see nothing there.", True, "dupla negação"),
    Caso("ingles", "People are waiting outside.", False, "correta"),
    Caso("ingles", "It depends on the weather.", False, "correta"),
    Caso("ingles", "She told me the truth.", False, "correta"),
    Caso("ingles", "I have lived here for three years.", False, "correta"),
    Caso("ingles", "I have been here since 2020.", False, "correta"),

    # Falsos positivos e negativos corrigidos.
    Caso("ingles", "He will explain her position to the class.", False,
         "“her” aqui é possessivo, não objeto indireto"),
    Caso("ingles", "I have lived here since three years ago.", False,
         "“since … ago” marca ponto no tempo e é correto"),
    Caso("ingles", "Actually, I finished the report today.", False,
         "“actually” com sentido de “na verdade” está correto"),
    Caso("ingles", "Don't pretend to work when you are tired.", False,
         "“pretend” aqui significa mesmo fingir"),
    Caso("ingles", "My brother have 20 years old.", True,
         "idade com “have”, com sujeito que não é pronome"),
    Caso("ingles", "Can you explain them the rule?", True,
         "“explain” exige “to” antes do objeto indireto"),
)

# Matemática: o tópico que o classificador deve reconhecer.
CASOS_TOPICO: tuple[Caso, ...] = (
    Caso("topico", "Determine as raízes do polinômio x^3 - 6x^2 + 11x - 6.", "polinomios"),
    Caso("topico", "Seja z de módulo 2 e argumento pi/3. Calcule z^6.", "complexos"),
    Caso("topico", "Resolva sen(2x) = cos(x) no intervalo dado.", "trigonometria"),
    Caso("topico", "Calcule a área do triângulo de lados 3, 4 e 5.", "geometria_plana"),
    Caso("topico", "Determine a equação da elipse de focos F1 e F2.", "geometria_analitica"),
    Caso("topico", "Calcule o volume de um tronco de cone.", "geometria_espacial"),
    Caso("topico", "Calcule o determinante da matriz A.", "matrizes"),
    Caso("topico", "De quantos modos formar comissões de 3 pessoas?", "combinatoria"),
    Caso("topico", "Qual a probabilidade de sair soma 7 com dois dados?", "probabilidade"),
    Caso("topico", "Calcule o limite de (sen x)/x quando x tende a zero.", "calculo"),
    Caso("topico", "Numa progressão aritmética de razão 3, some os termos.", "sequencias"),
    Caso("topico", "Resolva a equação exponencial 2^(x+1) = 8 com logaritmo.", "logaritmos"),
    Caso("topico", "Mostre que n^3 - n é divisível por 6.", "teoria_numeros"),
    Caso("topico", "Resolva sen(x) = 1/2 no intervalo [0, 2pi].", "trigonometria",
         "colchete de intervalo não é notação de matriz"),
    Caso("topico", "Calcule a integral definida de x^2 em [0, 1].", "calculo",
         "colchete de intervalo não é notação de matriz"),
)

# Matemática simbólica: o conjunto solução que a álgebra deve devolver.
CASOS_ALGEBRA: tuple[Caso, ...] = (
    Caso("algebra", "Resolva a equação x^2 - 5x + 6 = 0.", {"2", "3"}),
    Caso("algebra", "Resolva a equação x^2 - 4 = 0.", {"-2", "2"}),
    Caso("algebra", "Resolva a equação 2x + 6 = 0.", {"-3"}),
    Caso("algebra", "Resolva a equação sqrt(x + 3) = x - 3.", {"6"}),
    Caso("algebra", "Resolva a equação x^2 + 2x + 1 = 0.", {"-1"}),
    Caso("algebra", "Resolva a equação x^3 - 6x^2 + 11x - 6 = 0.", {"1", "2", "3"}),
)

# Léxico: gênero e classe de palavra. É a camada de que crase e colocação
# dependem — errar aqui contamina todo o resto.
CASOS_LEXICO: tuple[Caso, ...] = (
    Caso("lexico", "genero:chá", "masculino", "-á tônico é masculino"),
    Caso("lexico", "genero:sofá", "masculino", "-á tônico"),
    Caso("lexico", "genero:coração", "masculino", "exceção ao sufixo -ção"),
    Caso("lexico", "genero:balcão", "masculino", "exceção ao sufixo"),
    Caso("lexico", "genero:tribo", "feminino", "termina em -o e é feminino"),
    Caso("lexico", "genero:foto", "feminino", "apócope de fotografia"),
    Caso("lexico", "genero:mão", "feminino", "exceção clássica"),
    Caso("lexico", "genero:nação", "feminino", "sufixo -ção"),
    Caso("lexico", "genero:problema", "masculino", "-a de origem grega"),
    Caso("lexico", "genero:casa", "feminino", "padrão regular"),
    Caso("lexico", "genero:colega", "indeterminado", "comum de dois gêneros"),
    Caso("lexico", "genero:atleta", "indeterminado", "comum de dois gêneros"),
    Caso("lexico", "genero:grama", "indeterminado", "homógrafo de gêneros distintos"),
    Caso("lexico", "genero:pá", "feminino", "exceção ao -á tônico"),
    Caso("lexico", "verbo:mulher", False, "substantivo, não infinitivo em -er"),
    Caso("lexico", "verbo:colher", False, "substantivo no contexto de crase"),
    Caso("lexico", "verbo:lugar", False, "substantivo em -ar"),
    Caso("lexico", "verbo:amor", False, "substantivo em -or"),
    Caso("lexico", "verbo:estudar", True, "infinitivo regular"),
    Caso("lexico", "verbo:escolher", True, "infinitivo em -er"),
    Caso("lexico", "verbo:pôr", True, "infinitivo em -or"),
    Caso("lexico", "verbo:ser", True, "infinitivo irregular"),
)

# Matéria que o roteador do tutor deve escolher.
CASOS_MATERIA: tuple[Caso, ...] = (
    Caso("materia", "Resolva a equação x^2 - 5x + 6 = 0.", "matematica"),
    Caso("materia", "Analise a crase em: Vou a praia.", "portugues"),
    Caso("materia", "Choose the correct option: I have seen him yesterday.", "ingles"),
    Caso("materia", "Qual é o objeto indireto da oração?", "portugues"),
    Caso("materia", "Is this sentence correct? She don't like it.", "ingles"),
    Caso("materia", "Quantos anagramas tem a palavra ARARA?", "matematica"),
)

TODOS_OS_CASOS: tuple[Caso, ...] = (
    CASOS_CRASE + CASOS_COLOCACAO + CASOS_CONCORDANCIA + CASOS_REGENCIA
    + CASOS_REGENCIA_USO + CASOS_INGLES + CASOS_TOPICO + CASOS_ALGEBRA
    + CASOS_LEXICO + CASOS_MATERIA
)


# --------------------------------------------------------------------------
# Execução
# --------------------------------------------------------------------------

@dataclass(slots=True)
class Resultado:
    """O que o motor respondeu num caso."""

    caso: Caso
    obtido: Any
    acertou: bool
    detalhe: str = ""

    def para_dict(self) -> dict[str, Any]:
        return {
            "area": self.caso.area,
            "entrada": self.caso.entrada,
            "esperado": _texto(self.caso.esperado),
            "obtido": _texto(self.obtido),
            "acertou": self.acertou,
            "porque": self.caso.porque,
            "detalhe": self.detalhe,
        }


def _texto(valor: Any) -> str:
    if isinstance(valor, (set, frozenset)):
        return "{" + ", ".join(sorted(str(v) for v in valor)) + "}"
    return str(valor)


def _situacao_da_crase(frase: str) -> str:
    from .gramatica.crase import analisar_crase

    ocorrencias = analisar_crase(frase)
    if not ocorrencias:
        return "nenhuma ocorrência"
    # Quando há várias, vale a mais informativa: a que não é apenas "depende".
    for prioridade in ("obrigatoria", "proibida", "facultativa"):
        for ocorrencia in ocorrencias:
            if ocorrencia.situacao == prioridade:
                return ocorrencia.situacao
    return ocorrencias[0].situacao


def _posicao_correta(frase: str) -> str:
    from .gramatica.colocacao import analisar_colocacao

    ocorrencias = analisar_colocacao(frase)
    return ocorrencias[0].posicao_correta if ocorrencias else "nenhum pronome"


def _veredito_concordancia(frase: str) -> str:
    from .gramatica.concordancia import analisar_concordancia

    achados = analisar_concordancia(frase)
    if any(a.veredito == "erro" for a in achados):
        return "erro"
    return "correto" if achados else "nada detectado"


def _regencia_exige_a(verbo: str) -> bool:
    from .gramatica.regencia import consultar_verbo

    return any(s.exige_a for s in consultar_verbo(verbo))


def _ingles_tem_erro(frase: str) -> bool:
    from .ingles import avaliar_estrutura

    # Construção "suspeita" (falso cognato que também tem leitura correta)
    # vira aviso, não acusação: só o agramatical conta como erro.
    return any(a.grammaticality == "agramatical" for a in avaliar_estrutura(frase))


def _consulta_lexico(entrada: str) -> Any:
    """`genero:palavra` devolve o gênero; `verbo:palavra`, se é infinitivo."""
    from .gramatica.lexico import e_verbo_no_infinitivo, genero

    tipo, _, palavra = entrada.partition(":")
    if tipo == "genero":
        return genero(palavra)
    return e_verbo_no_infinitivo(palavra)


def _regencia_desviou(frase: str) -> bool:
    from .gramatica.regencia import conferir_regencia

    return bool(conferir_regencia(frase))


def _topico_matematico(enunciado: str) -> str:
    from .matematica import classificar

    return classificar(enunciado).topico


def _solucoes(enunciado: str) -> set[str]:
    from .matematica.simbolico import analisar

    analise = analisar(enunciado)
    return {v for valores in analise.solucoes.values() for v in valores}


def _materia(enunciado: str) -> str:
    from .tutor.tutoria import detectar_materia

    return detectar_materia(enunciado)


VERIFICADORES: dict[str, Callable[[str], Any]] = {
    "crase": _situacao_da_crase,
    "colocacao": _posicao_correta,
    "concordancia": _veredito_concordancia,
    "regencia": _regencia_exige_a,
    "regencia_uso": _regencia_desviou,
    "lexico": _consulta_lexico,
    "ingles": _ingles_tem_erro,
    "topico": _topico_matematico,
    "algebra": _solucoes,
    "materia": _materia,
}


@dataclass(slots=True)
class Relatorio:
    """A aferição completa, por área."""

    resultados: list[Resultado] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.resultados)

    @property
    def acertos(self) -> int:
        return sum(1 for r in self.resultados if r.acertou)

    @property
    def taxa(self) -> float:
        return self.acertos / self.total * 100 if self.total else 0.0

    @property
    def falhas(self) -> list[Resultado]:
        return [r for r in self.resultados if not r.acertou]

    def por_area(self) -> dict[str, dict[str, Any]]:
        areas: dict[str, dict[str, Any]] = {}
        for resultado in self.resultados:
            entrada = areas.setdefault(
                resultado.caso.area, {"total": 0, "acertos": 0, "falhas": []}
            )
            entrada["total"] += 1
            if resultado.acertou:
                entrada["acertos"] += 1
            else:
                entrada["falhas"].append(resultado.para_dict())
        for entrada in areas.values():
            entrada["taxa"] = round(entrada["acertos"] / entrada["total"] * 100, 1)
        return areas

    def para_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "acertos": self.acertos,
            "taxa": round(self.taxa, 1),
            "por_area": self.por_area(),
            "falhas": [r.para_dict() for r in self.falhas],
        }


def aferir(area: str = "") -> Relatorio:
    """Roda os casos de referência e compara com o gabarito."""
    relatorio = Relatorio()
    casos = [c for c in TODOS_OS_CASOS if not area or c.area == area]

    for caso in casos:
        verificador = VERIFICADORES.get(caso.area)
        if verificador is None:
            relatorio.resultados.append(
                Resultado(caso, "sem verificador", False, "área desconhecida")
            )
            continue
        try:
            obtido = verificador(caso.entrada)
        except Exception as exc:  # um motor quebrado é uma falha, não um crash
            relatorio.resultados.append(
                Resultado(caso, f"exceção: {type(exc).__name__}", False, str(exc)[:120])
            )
            continue
        relatorio.resultados.append(Resultado(caso, obtido, obtido == caso.esperado))

    return relatorio


# --------------------------------------------------------------------------
# Linha de comando
# --------------------------------------------------------------------------

VERDE, AMARELO, VERMELHO, CINZA, FIM = (
    "\033[32m", "\033[33m", "\033[31m", "\033[90m", "\033[0m"
)


def _cor_da_taxa(taxa: float) -> str:
    return VERDE if taxa >= 95 else AMARELO if taxa >= 80 else VERMELHO


def main(argumentos: list[str] | None = None) -> int:
    analisador = argparse.ArgumentParser(
        prog="python -m app.afericao",
        description="Mede se os motores estão respondendo certo.",
    )
    analisador.add_argument("--area", default="",
                            choices=sorted(VERIFICADORES) + [""],
                            help="afere apenas uma área")
    analisador.add_argument("--falhas", action="store_true",
                            help="mostra somente os casos que erraram")
    opcoes = analisador.parse_args(argumentos)

    relatorio = aferir(opcoes.area)
    print(f"\n  Aferição do Núcleo — {relatorio.total} casos de referência\n")

    for area, dados in sorted(relatorio.por_area().items()):
        cor = _cor_da_taxa(dados["taxa"])
        barra = "█" * round(dados["taxa"] / 5) + "·" * (20 - round(dados["taxa"] / 5))
        print(f"  {area:14} {cor}{barra}{FIM} "
              f"{dados['acertos']:>3}/{dados['total']:<3} {cor}{dados['taxa']:>5.1f}%{FIM}")

    if relatorio.falhas:
        print(f"\n  {VERMELHO}{len(relatorio.falhas)} caso(s) errado(s):{FIM}\n")
        for falha in relatorio.falhas:
            print(f"  {VERMELHO}✗{FIM} {falha.caso.entrada}")
            print(f"    esperado: {_texto(falha.caso.esperado)}")
            print(f"    obtido:   {_texto(falha.obtido)}")
            if falha.caso.porque:
                print(f"    {CINZA}regra: {falha.caso.porque}{FIM}")
            print()
    elif not opcoes.falhas:
        print(f"\n  {VERDE}Todos os casos de referência passaram.{FIM}")

    cor = _cor_da_taxa(relatorio.taxa)
    print(f"\n  Total: {cor}{relatorio.acertos}/{relatorio.total} "
          f"({relatorio.taxa:.1f}%){FIM}\n")
    return 0 if not relatorio.falhas else 1


if __name__ == "__main__":
    sys.exit(main())
