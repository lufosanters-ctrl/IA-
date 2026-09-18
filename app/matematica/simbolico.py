"""Camada simbolica: um sistema de algebra computacional como fonte de verdade.

Um modelo de linguagem escreve matematica convincente e, as vezes, errada. O
que torna a resolucao confiavel nao e o texto prometer que verificou — e um
verificador independente conferir.

Este modulo:

* le expressoes e equacoes do enunciado;
* resolve o que for resolvivel sem nenhum modelo de linguagem;
* confronta a resposta apresentada com o resultado simbolico;
* aplica os testes do protocolo anti-erro (substituicao, dominio, intervalo
  de probabilidade, identidade, verificacao numerica aleatoria).

Seguranca: a entrada do usuario nunca chega a `eval` livre. Ha um filtro de
caracteres, uma lista de termos proibidos e um espaco de nomes fechado, sem
builtins.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from typing import Any

import sympy as sp
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)

TRANSFORMACOES = standard_transformations + (
    convert_xor,                          # aceita ^ como potencia
    implicit_multiplication_application,  # aceita 2x e 3sen(x)
)

# Caracteres aceitos numa expressao matematica. Tudo fora disso e recusado.
_PERMITIDOS = re.compile(r"^[0-9A-Za-zÀ-ÿ_+\-*/^()\[\]{},.=<>!|\s'πθαβγλμσΔ√²³]*$")

# Termos que nao tem o que fazer num enunciado de matematica.
_PROIBIDOS = (
    "__", "import", "lambda", "exec", "eval", "open", "globals", "locals",
    "getattr", "setattr", "compile", "input", "subprocess", "os.", "sys.",
)

_RE_ATRIBUTO = re.compile(r"\.\s*[A-Za-z_]")

# Nomes que o usuario pode usar. Qualquer outro vira simbolo livre.
_FUNCOES: dict[str, Any] = {
    "sen": sp.sin, "sin": sp.sin, "cos": sp.cos, "tg": sp.tan, "tan": sp.tan,
    "cotg": sp.cot, "cot": sp.cot, "sec": sp.sec, "cossec": sp.csc, "csc": sp.csc,
    "arcsen": sp.asin, "asin": sp.asin, "arccos": sp.acos, "acos": sp.acos,
    "arctg": sp.atan, "atan": sp.atan,
    "senh": sp.sinh, "cosh": sp.cosh, "tgh": sp.tanh,
    "exp": sp.exp, "ln": sp.log, "log": sp.log, "sqrt": sp.sqrt, "raiz": sp.sqrt,
    "abs": sp.Abs, "modulo": sp.Abs, "floor": sp.floor, "ceil": sp.ceiling,
    "fatorial": sp.factorial, "factorial": sp.factorial,
    "binomial": sp.binomial, "C": sp.binomial,
    "mdc": sp.gcd, "gcd": sp.gcd, "mmc": sp.lcm, "lcm": sp.lcm,
    "Matrix": sp.Matrix, "matriz": sp.Matrix, "det": sp.det,
    "re": sp.re, "im": sp.im, "conj": sp.conjugate, "arg": sp.arg,
    "pi": sp.pi, "π": sp.pi, "e": sp.E, "E": sp.E, "I": sp.I, "i": sp.I,
    "oo": sp.oo, "infinito": sp.oo, "√": sp.sqrt,
}

def _montar_espaco_global() -> dict[str, Any]:
    """Namespace do SymPy, sem os builtins do Python.

    O interpretador do SymPy gera codigo que chama `Integer`, `Symbol` e afins,
    entao o namespace dele precisa estar presente. O que sai e o
    `__builtins__`: sem ele, `open`, `__import__` e companhia nao existem
    dentro da avaliacao, mesmo que passassem pelo filtro de texto.
    """
    espaco: dict[str, Any] = {}
    exec("from sympy import *", espaco)  # noqa: S102 - namespace fixo, nao entrada do usuario
    espaco["__builtins__"] = {}
    return espaco


_ESPACO_GLOBAL: dict[str, Any] = _montar_espaco_global()

# Um literal gigante ou uma torre de potencias trava o processo antes mesmo de
# chegar a um resultado. Barrados na leitura.
_RE_INTEIRO_LONGO = re.compile(r"\d{10,}")
_RE_TORRE = re.compile(r"(\^|\*\*)\s*[^\s()]*\s*(\^|\*\*)")
_LIMITE_FATORIAL = 2000


class ErroSimbolico(ValueError):
    """A expressao nao pode ser lida com seguranca ou nao faz sentido."""


def _texto(objeto: Any) -> str:
    """Representacao textual estavel de um objeto simbolico."""
    return sp.sstr(objeto)


# --------------------------------------------------------------------------
# Leitura segura
# --------------------------------------------------------------------------

def _higienizar(bruto: str) -> str:
    """Recusa entradas que nao sejam matematica."""
    texto = (bruto or "").strip()
    if not texto:
        raise ErroSimbolico("expressão vazia")
    if len(texto) > 600:
        raise ErroSimbolico("expressão longa demais")
    minusculo = texto.lower()
    for proibido in _PROIBIDOS:
        if proibido in minusculo:
            raise ErroSimbolico(f"termo não permitido na expressão: {proibido!r}")
    if _RE_ATRIBUTO.search(texto):
        raise ErroSimbolico("acesso a atributo não é permitido")
    if not _PERMITIDOS.match(texto):
        invalidos = sorted({c for c in texto if not _PERMITIDOS.match(c)})
        raise ErroSimbolico(f"caractere não aceito: {' '.join(invalidos[:5])}")
    if _RE_INTEIRO_LONGO.search(texto):
        raise ErroSimbolico("número grande demais para o cálculo simbólico")
    if _RE_TORRE.search(texto):
        raise ErroSimbolico("torre de potências não é aceita")
    for achado in re.findall(r"(?:factorial|fatorial)\s*\(\s*(\d+)", texto):
        if int(achado) > _LIMITE_FATORIAL:
            raise ErroSimbolico(f"fatorial acima de {_LIMITE_FATORIAL} não é calculado")
    return texto


def _normalizar(texto: str) -> str:
    """Converte notacao escrita a mao para a que o interpretador entende."""
    texto = texto.replace("²", "^2").replace("³", "^3")
    # "√9" precisa virar "sqrt(9)". Sem os parênteses, "sqrt9" seria lido como
    # o produto s·q·r·t·9 pela multiplicação implícita.
    texto = re.sub(
        r"√\s*(\([^()]*\)|\d+(?:\.\d+)?|[A-Za-zÀ-ÿ]\w*)", r"sqrt(\1)", texto
    )
    texto = texto.replace("√", "sqrt")
    texto = re.sub(r"(?<![A-Za-z])sen\s*\(", "sin(", texto)
    texto = re.sub(r"(?<![A-Za-z])tg\s*\(", "tan(", texto)
    texto = re.sub(r"(\d)\s*!", r"factorial(\1)", texto)
    texto = re.sub(r"\)\s*!", ")_FAT_", texto)          # marcado abaixo
    texto = texto.replace("_FAT_", "")                  # ! apos parentese: ignora
    texto = re.sub(r"\s*=\s*", "=", texto)
    return texto.strip()


# Letras que, seguidas de parêntese, significam função e não multiplicação.
# Restrito de propósito: "x(x+1)" continua sendo produto, como se espera.
_NOMES_DE_FUNCAO = {"f", "g", "h", "F", "G", "H", "P", "u", "v"}


def _funcoes_declaradas(texto: str) -> dict[str, Any]:
    """Declara f, g, h... como funções quando aparecem aplicadas."""
    declaradas: dict[str, Any] = {}
    for nome in re.findall(r"\b([A-Za-z]\w*)\s*\(", texto):
        if nome in _FUNCOES:
            continue
        if nome in _NOMES_DE_FUNCAO or len(nome) > 1:
            declaradas[nome] = sp.Function(nome)
    return declaradas


def ler(bruto: str) -> sp.Expr:
    """Le uma expressao (sem sinal de igual) com seguranca."""
    texto = _normalizar(_higienizar(bruto))
    if "=" in texto:
        raise ErroSimbolico("use `ler_equacao` para expressões com igualdade")
    try:
        expressao = parse_expr(
            texto,
            local_dict=dict(_FUNCOES) | _funcoes_declaradas(texto),
            global_dict=_ESPACO_GLOBAL,
            transformations=TRANSFORMACOES,
            evaluate=True,
        )
    except Exception as exc:
        raise ErroSimbolico(f"não consegui interpretar “{bruto.strip()}”") from exc
    if not isinstance(expressao, (sp.Expr, sp.Matrix, sp.MatrixBase)):
        raise ErroSimbolico("a entrada não é uma expressão matemática")
    return expressao


def ler_equacao(bruto: str) -> sp.Eq:
    """Le uma igualdade `lado esquerdo = lado direito`."""
    texto = _normalizar(_higienizar(bruto))
    partes = [p for p in texto.split("=") if p.strip()]
    if len(partes) != 2:
        raise ErroSimbolico("a equação precisa ter exatamente um sinal de igual")
    return sp.Eq(ler(partes[0]), ler(partes[1]))


def incognitas(objeto: sp.Basic) -> list[sp.Symbol]:
    """Simbolos livres, em ordem previsivel (x, y, z primeiro)."""
    preferencia = {"x": 0, "y": 1, "z": 2, "t": 3, "n": 4, "k": 5}
    simbolos = sorted(objeto.free_symbols, key=lambda s: (preferencia.get(s.name, 9), s.name))
    return list(simbolos)


# --------------------------------------------------------------------------
# Extracao de matematica do enunciado
# --------------------------------------------------------------------------

_RE_LATEX = re.compile(r"\$+([^$]{2,200})\$+")

# Um token "matematico": so digitos, letras ASCII e operadores.
_RE_TOKEN_MAT = re.compile(r"^[0-9A-Za-z^*/+\-().,|=<>!π√²³]+$")

# Palavras curtas do portugues que nunca devem ser lidas como variavel quando
# aparecem na borda de uma expressao. "x = 3 e y = 2" nao define a variavel e.
_BORDAS_PROIBIDAS = {
    "o", "a", "e", "é", "os", "as", "da", "de", "do", "em", "no", "na", "um",
    "uma", "se", "que", "com", "por", "ao", "é", "ou", "nas", "nos", "sao",
}

_PALAVRAS_MATEMATICAS = set(_FUNCOES) | {"pi", "oo"}


def _e_token_matematico(token: str) -> bool:
    """O token pode fazer parte de uma expressão?"""
    if not token or not _RE_TOKEN_MAT.match(token):
        return False
    if token.lower() in _PALAVRAS_MATEMATICAS:
        return True
    # Tem dígito, operador, ou é uma letra isolada (uma variável).
    if any(c.isdigit() for c in token):
        return True
    if any(c in token for c in "+-*/^()=<>|√"):
        return True
    return len(token.strip(".,;:")) == 1


def _trechos_matematicos(texto: str) -> list[str]:
    """Extrai as sequências de tokens matemáticos contíguos de uma frase.

    Percorrer token a token é o que separa a matemática da prosa. Uma regex
    sobre o texto corrido acaba engolindo letras de palavras vizinhas — o "o"
    de "equação" virava uma variável e corrompia a equação inteira.
    """
    trechos: list[str] = []
    corrente: list[str] = []

    for bruto in re.split(r"\s+", texto or ""):
        token = bruto.strip()
        if not token:
            continue
        if _e_token_matematico(token):
            corrente.append(token)
            continue
        if corrente:
            trechos.append(" ".join(corrente))
            corrente = []
    if corrente:
        trechos.append(" ".join(corrente))

    # Apara artigos e conjunções que ficaram nas pontas.
    aparados: list[str] = []
    for trecho in trechos:
        tokens = trecho.split()
        while tokens and tokens[0].lower().strip(".,;:") in _BORDAS_PROIBIDAS:
            tokens.pop(0)
        while tokens and tokens[-1].lower().strip(".,;:") in _BORDAS_PROIBIDAS:
            tokens.pop()
        if tokens:
            aparados.append(" ".join(tokens))
    return aparados


def _candidatos_a_equacao(texto: str) -> list[str]:
    """Trechos com exatamente um sinal de igual, prontos para leitura."""
    candidatos: list[str] = []
    for trecho in _trechos_matematicos(texto):
        # "x + y = 3, x - y = 1" traz duas equações num trecho só.
        pedacos = re.split(r"[,;]\s*(?=[^=]*=)", trecho)
        # A conjunção "e" também liga duas equações. Só separa quando o trecho
        # tem mais de uma igualdade — em "ln(e) = 1", o e é a constante.
        separados: list[str] = []
        for pedaco in pedacos:
            if pedaco.count("=") > 1:
                separados.extend(re.split(r"\s+e\s+", pedaco))
            else:
                separados.append(pedaco)

        for pedaco in separados:
            limpo = pedaco.strip(" .,;:")
            if limpo.count("=") != 1:
                continue
            esquerda, direita = limpo.split("=")
            if not esquerda.strip() or not direita.strip():
                continue
            candidatos.append(limpo)
    return candidatos


def extrair_equacoes(enunciado: str, maximo: int = 6) -> list[sp.Eq]:
    """Acha as igualdades presentes no texto do problema."""
    candidatos: list[str] = []
    # O que vem entre cifrões é matemática declarada: entra sem filtro.
    for achado in _RE_LATEX.findall(enunciado or ""):
        if achado.count("=") == 1:
            candidatos.append(achado.strip())
    candidatos.extend(_candidatos_a_equacao(enunciado))

    equacoes: list[sp.Eq] = []
    vistas: set[str] = set()
    for bruto in candidatos:
        if bruto in vistas:
            continue
        vistas.add(bruto)
        try:
            equacao = ler_equacao(bruto)
        except ErroSimbolico:
            continue
        # Uma "equação" sem incógnita nenhuma costuma ser um trecho de texto.
        if not equacao.free_symbols:
            continue
        chave = _texto(equacao)
        if chave in vistas:
            continue
        vistas.add(chave)
        equacoes.append(equacao)
        if len(equacoes) >= maximo:
            break
    return equacoes


_RE_NUMERO = re.compile(r"-?\d+(?:[.,]\d+)?(?:/\d+)?")


def extrair_numeros(texto: str, maximo: int = 12) -> list[sp.Rational]:
    """Numeros mencionados num texto, para confronto com o resultado."""
    valores: list[sp.Rational] = []
    for bruto in _RE_NUMERO.findall(texto or "")[:60]:
        try:
            valores.append(sp.Rational(bruto.replace(",", ".")))
        except (TypeError, ValueError, sp.SympifyError):
            continue
        if len(valores) >= maximo:
            break
    return valores


# --------------------------------------------------------------------------
# Resolucao e verificacao
# --------------------------------------------------------------------------

@dataclass(slots=True)
class Checagem:
    """Um teste do protocolo anti-erro, com veredito."""

    nome: str
    passou: bool
    detalhe: str = ""

    def para_dict(self) -> dict[str, Any]:
        return {"nome": self.nome, "passou": self.passou, "detalhe": self.detalhe}


@dataclass(slots=True)
class AnaliseSimbolica:
    """O que o sistema algebrico conseguiu estabelecer sozinho."""

    equacoes: list[str] = field(default_factory=list)
    equacoes_latex: list[str] = field(default_factory=list)
    solucoes: dict[str, list[str]] = field(default_factory=dict)
    solucoes_latex: dict[str, list[str]] = field(default_factory=dict)
    checagens: list[Checagem] = field(default_factory=list)
    observacoes: list[str] = field(default_factory=list)
    resolveu: bool = False

    def para_dict(self) -> dict[str, Any]:
        return {
            "equacoes": self.equacoes,
            "equacoes_latex": self.equacoes_latex,
            "solucoes": self.solucoes,
            "solucoes_latex": self.solucoes_latex,
            "checagens": [c.para_dict() for c in self.checagens],
            "observacoes": self.observacoes,
            "resolveu": self.resolveu,
        }


def resolver(equacao: sp.Eq, variavel: sp.Symbol | None = None) -> list[sp.Expr]:
    """Resolve a equacao, preferindo solucao exata."""
    livres = incognitas(equacao)
    if not livres:
        return []
    alvo = variavel or livres[0]
    try:
        solucoes = sp.solve(equacao, alvo, dict=False)
    except (NotImplementedError, sp.PolynomialError, TypeError, ValueError):
        try:
            solucoes = list(sp.solveset(equacao, alvo, domain=sp.S.Reals))
        except Exception:
            return []
    if isinstance(solucoes, dict):
        solucoes = [solucoes.get(alvo)]
    return [s for s in solucoes if s is not None]


def resolver_sistema(equacoes: list[sp.Eq]) -> dict[sp.Symbol, sp.Expr]:
    """Resolve um sistema simultaneo, quando as equacoes compartilham variaveis."""
    if len(equacoes) < 2:
        return {}
    variaveis = sorted(
        {s for equacao in equacoes for s in equacao.free_symbols}, key=lambda s: s.name
    )
    if not variaveis or len(variaveis) > 6:
        return {}
    try:
        solucao = sp.solve(equacoes, variaveis, dict=True)
    except (NotImplementedError, TypeError, ValueError, sp.PolynomialError):
        return {}
    if not solucao or not isinstance(solucao[0], dict):
        return {}
    return solucao[0]


def verificar_sistema(
    equacoes: list[sp.Eq], solucao: dict[sp.Symbol, sp.Expr]
) -> Checagem:
    """Substitui a solucao em TODAS as equacoes do sistema."""
    if not solucao:
        return Checagem("substituição no sistema", False, "sem solução para testar")
    falhas: list[str] = []
    for equacao in equacoes:
        residuo = sp.simplify((equacao.lhs - equacao.rhs).subs(solucao))
        if residuo.free_symbols:
            continue
        if sp.simplify(residuo) != 0:
            falhas.append(f"{_texto(equacao)} deixa resíduo {_texto(residuo)}")
    if falhas:
        return Checagem("substituição no sistema", False, "; ".join(falhas[:2]))
    return Checagem(
        "substituição no sistema", True,
        f"solução verificada nas {len(equacoes)} equações do sistema",
    )


def verificar_por_substituicao(
    equacao: sp.Eq, variavel: sp.Symbol, valores: list[sp.Expr]
) -> Checagem:
    """Substitui cada solucao na equacao original e confere o residuo."""
    if not valores:
        return Checagem("substituição", False, "nenhum valor para testar")
    falhas: list[str] = []
    for valor in valores:
        residuo = sp.simplify(equacao.lhs - equacao.rhs).subs(variavel, valor)
        try:
            residuo = sp.simplify(residuo)
        except Exception:
            pass
        if residuo.free_symbols:
            continue  # solução paramétrica: substituição não decide
        try:
            nulo = bool(sp.Abs(sp.N(residuo, 30)) < sp.Float("1e-20"))
        except (TypeError, ValueError):
            nulo = residuo == 0
        if not nulo:
            falhas.append(f"{variavel}={_texto(valor)} deixa resíduo {_texto(residuo)}")
    if falhas:
        return Checagem("substituição", False, "; ".join(falhas[:3]))
    return Checagem(
        "substituição", True,
        f"{len(valores)} raiz(es) substituída(s) na equação original, resíduo nulo",
    )


def verificar_identidade(esquerda: str, direita: str) -> Checagem:
    """Confere se duas expressoes sao iguais para todo valor admissivel."""
    try:
        a, b = ler(esquerda), ler(direita)
    except ErroSimbolico as exc:
        return Checagem("identidade", False, str(exc))

    diferenca = sp.simplify(a - b)
    if diferenca == 0:
        return Checagem("identidade", True, "simplificação da diferença dá zero")

    # Simplificacao pode falhar em identidades verdadeiras; testa numericamente.
    variaveis = incognitas(a - b)
    sorteio = random.Random(20260918)
    for _ in range(12):
        valores = {v: sp.Rational(sorteio.randint(1, 40), sorteio.randint(1, 9))
                   for v in variaveis}
        try:
            valor = complex(sp.N((a - b).subs(valores), 25))
        except (TypeError, ValueError, ZeroDivisionError):
            continue
        if abs(valor) > 1e-12:
            return Checagem(
                "identidade", False,
                f"falha em {', '.join(f'{k}={_texto(v)}' for k, v in valores.items())}",
            )
    return Checagem(
        "identidade", True, "diferença nula em 12 pontos aleatórios (simplificação inconclusiva)"
    )


def verificar_intervalo_probabilidade(valores: list[sp.Rational]) -> Checagem | None:
    """Toda probabilidade precisa cair em [0, 1]."""
    if not valores:
        return None
    fora = [v for v in valores if v < 0 or v > 1]
    if fora:
        return Checagem(
            "intervalo de probabilidade", False,
            f"valor fora de [0,1]: {', '.join(_texto(v) for v in fora[:3])}",
        )
    return Checagem("intervalo de probabilidade", True, "todos os valores em [0,1]")


def verificar_dominio(equacao: sp.Eq, variavel: sp.Symbol,
                      valores: list[sp.Expr]) -> Checagem | None:
    """Raiz que anula denominador ou negativa radicando e raiz estranha."""
    expressao = equacao.lhs - equacao.rhs
    denominadores = [d for d in expressao.atoms(sp.Pow)
                     if d.exp.is_negative] if expressao.atoms(sp.Pow) else []
    radicais = [r for r in expressao.atoms(sp.Pow)
                if r.exp.is_Rational and r.exp.q != 1]
    logaritmos = list(expressao.atoms(sp.log))
    if not (denominadores or radicais or logaritmos):
        return None

    problemas: list[str] = []
    for valor in valores:
        if valor.free_symbols:
            continue
        for termo in denominadores:
            base = termo.base.subs(variavel, valor)
            if sp.simplify(base) == 0:
                problemas.append(f"{variavel}={_texto(valor)} anula um denominador")
        for termo in radicais:
            dentro = sp.simplify(termo.base.subs(variavel, valor))
            if dentro.is_real and dentro.is_negative:
                problemas.append(f"{variavel}={_texto(valor)} deixa radicando negativo")
        for termo in logaritmos:
            dentro = sp.simplify(termo.args[0].subs(variavel, valor))
            if dentro.is_real and (dentro.is_negative or dentro == 0):
                problemas.append(f"{variavel}={_texto(valor)} deixa logaritmando ≤ 0")
    if problemas:
        return Checagem("domínio", False, "; ".join(dict.fromkeys(problemas))[:220])
    return Checagem(
        "domínio", True, "nenhuma raiz anula denominador, radicando ou logaritmando"
    )


def analisar(enunciado: str, verificar_probabilidade: bool = False) -> AnaliseSimbolica:
    """Le o enunciado, resolve o que der e roda o protocolo anti-erro."""
    analise = AnaliseSimbolica()
    try:
        equacoes = extrair_equacoes(enunciado)
    except ErroSimbolico as exc:
        analise.observacoes.append(str(exc))
        return analise

    if not equacoes:
        analise.observacoes.append(
            "Nenhuma equação explícita no enunciado: a conferência simbólica não se aplica."
        )
        return analise

    for equacao in equacoes:
        analise.equacoes.append(_texto(equacao))
        analise.equacoes_latex.append(sp.latex(equacao))

    # Várias equações compartilhando incógnitas formam um sistema: resolvê-las
    # em conjunto dá a resposta certa, uma a uma daria apenas relações.
    if len(equacoes) >= 2:
        compartilhadas = set(equacoes[0].free_symbols)
        for equacao in equacoes[1:]:
            compartilhadas &= equacao.free_symbols
        if compartilhadas:
            solucao = resolver_sistema(equacoes)
            if solucao:
                analise.resolveu = True
                for variavel, valor in solucao.items():
                    analise.solucoes.setdefault(variavel.name, []).append(_texto(valor))
                    analise.solucoes_latex.setdefault(variavel.name, []).append(
                        sp.latex(valor)
                    )
                analise.checagens.append(verificar_sistema(equacoes, solucao))
                if verificar_probabilidade:
                    checagem = verificar_intervalo_probabilidade(
                        extrair_numeros(enunciado)
                    )
                    if checagem:
                        analise.checagens.append(checagem)
                return analise

    for equacao in equacoes:
        livres = incognitas(equacao)
        if not livres:
            continue
        alvo = livres[0]
        solucoes = resolver(equacao, alvo)
        if not solucoes:
            analise.observacoes.append(
                f"Não consegui resolver {_texto(equacao)} de forma fechada."
            )
            continue

        analise.resolveu = True
        chave = alvo.name
        analise.solucoes.setdefault(chave, []).extend(_texto(s) for s in solucoes)
        analise.solucoes_latex.setdefault(chave, []).extend(sp.latex(s) for s in solucoes)
        analise.checagens.append(verificar_por_substituicao(equacao, alvo, solucoes))
        dominio = verificar_dominio(equacao, alvo, solucoes)
        if dominio:
            analise.checagens.append(dominio)

    if verificar_probabilidade:
        checagem = verificar_intervalo_probabilidade(extrair_numeros(enunciado))
        if checagem:
            analise.checagens.append(checagem)

    return analise


# O confronto "a resposta contém as raízes?" só faz sentido quando a pergunta
# é justamente resolver a equação. Em "calcule r1² + r2²", a resposta CERTA não
# contém as raízes — e o confronto acusaria um erro que não existe.
_RE_PEDE_RAIZES = re.compile(
    r"\bresolva\b|\bresolu[çc][ãa]o\b|\bconjunto solu[çc][ãa]o\b|"
    r"\bra[íi]zes? (?:da|das|de|do) equa[çc][ãa]o\s+(?:s[ãa]o|[ée])\b|"
    r"\bvalores? de [a-z] que satisfaz|\bqual o valor de [a-z] (?:na|que)\b|"
    r"\bdetermine [a-z] (?:tal que|sabendo)\b|\bencontre as ra[íi]zes\b",
    re.IGNORECASE,
)


def pede_resolver_equacao(enunciado: str) -> bool:
    """O enunciado pede as raízes em si, ou pede algo calculado a partir delas?"""
    return bool(_RE_PEDE_RAIZES.search(enunciado or ""))


def conferir_resposta(enunciado: str, resposta: str) -> list[Checagem]:
    """Confronta os valores afirmados na resposta com o resultado simbolico.

    E a checagem que mais importa: o texto pode dizer "logo x = 4" com toda a
    confianca do mundo. Aqui o sistema algebrico resolve por conta propria e
    compara.
    """
    checagens: list[Checagem] = []
    if not pede_resolver_equacao(enunciado):
        return checagens
    try:
        equacoes = extrair_equacoes(enunciado)
    except ErroSimbolico:
        return checagens
    if not equacoes:
        return checagens

    afirmados = set(extrair_numeros(resposta, maximo=20))
    if not afirmados:
        return checagens

    for equacao in equacoes[:3]:
        livres = incognitas(equacao)
        if not livres:
            continue
        solucoes = resolver(equacao, livres[0])
        reais = [s for s in solucoes if not s.free_symbols and s.is_real]
        if not reais:
            continue

        exatas = set()
        for solucao in reais:
            try:
                exatas.add(sp.nsimplify(solucao, rational=True))
            except Exception:
                exatas.add(solucao)

        encontradas = [s for s in exatas if s in afirmados or any(
            abs(complex(sp.N(s - a, 20))) < 1e-9 for a in afirmados
        )]
        faltando = [s for s in exatas if s not in encontradas]

        if not faltando:
            checagens.append(Checagem(
                "confronto com a álgebra", True,
                f"a resposta contém todas as raízes de {_texto(equacao)}: "
                f"{', '.join(_texto(s) for s in sorted(exatas, key=_texto))}",
            ))
        else:
            checagens.append(Checagem(
                "confronto com a álgebra", False,
                f"{_texto(equacao)} tem raiz(es) {', '.join(_texto(s) for s in faltando)} "
                f"que não aparecem na resposta",
            ))
    return checagens
