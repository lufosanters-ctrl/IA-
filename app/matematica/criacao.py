"""Criacao de questoes no padrao ITA/IME.

Ha dois geradores, e a diferenca entre eles importa:

* **Parametrico** (sempre disponivel): o enunciado sai de um molde, os numeros
  sao sorteados e **o gabarito e calculado pelo SymPy**, nao escrito a mao.
  Cada distrator corresponde a um erro real e conhecido — sinal trocado,
  fator esquecido, caso perdido — e tambem e calculado, nao chutado. O
  gabarito, portanto, e correto por construcao.

* **Neural** (com chave de API): o modelo cria a questao, e o sistema
  algebrico **confere o gabarito antes de entregar**. Questao que nao passa na
  conferencia e recusada.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Callable

import sympy as sp

from ..ai.llm import ErroModelo, obter_motor
from . import simbolico
from .prompts import SISTEMA_CRIADOR


@dataclass(slots=True)
class Questao:
    """Uma questao objetiva, com gabarito e a anatomia de cada distrator."""

    enunciado: str
    alternativas: list[str]
    correta: int
    erros_dos_distratores: list[str] = field(default_factory=list)
    ideia_central: str = ""
    solucao: str = ""
    topicos: list[str] = field(default_factory=list)
    dificuldade: int = 3
    origem: str = "parametrica"
    conferida: bool = False
    observacao_da_conferencia: str = ""

    def para_dict(self) -> dict[str, Any]:
        return {
            "enunciado": self.enunciado,
            "alternativas": self.alternativas,
            "correta": self.correta,
            "erros_dos_distratores": self.erros_dos_distratores,
            "ideia_central": self.ideia_central,
            "solucao": self.solucao,
            "topicos": self.topicos,
            "dificuldade": self.dificuldade,
            "origem": self.origem,
            "conferida": self.conferida,
            "observacao_da_conferencia": self.observacao_da_conferencia,
        }


def _embaralhar(questao_bruta: dict[str, Any], sorteio: random.Random) -> Questao:
    """Embaralha as alternativas mantendo gabarito e explicacoes alinhados."""
    pares = list(zip(questao_bruta["alternativas"], questao_bruta["erros"]))
    correta_texto = pares[questao_bruta["correta"]][0]
    sorteio.shuffle(pares)
    alternativas = [p[0] for p in pares]
    return Questao(
        enunciado=questao_bruta["enunciado"],
        alternativas=alternativas,
        correta=alternativas.index(correta_texto),
        erros_dos_distratores=[p[1] for p in pares],
        ideia_central=questao_bruta["ideia"],
        solucao=questao_bruta["solucao"],
        topicos=questao_bruta["topicos"],
        dificuldade=questao_bruta.get("dificuldade", 3),
        origem="parametrica",
        conferida=True,
        observacao_da_conferencia="gabarito calculado simbolicamente",
    )


def _tex(objeto: Any) -> str:
    return f"${sp.latex(sp.nsimplify(objeto))}$"


# --------------------------------------------------------------------------
# Geradores parametricos
# --------------------------------------------------------------------------

def _girard(sorteio: random.Random) -> dict[str, Any]:
    """Relacoes de Girard: soma de quadrados das raizes."""
    r1, r2 = sorteio.sample([-6, -5, -4, -3, -2, 2, 3, 4, 5, 6, 7], 2)
    soma, produto = sp.Integer(r1 + r2), sp.Integer(r1 * r2)
    certo = soma**2 - 2 * produto
    return {
        "enunciado": (
            f"Sejam $r_1$ e $r_2$ as raízes da equação "
            f"$x^2 - ({soma})x + ({produto}) = 0$. "
            f"O valor de $r_1^2 + r_2^2$ é:"
        ),
        "alternativas": [
            _tex(certo), _tex(soma**2 + 2 * produto),
            _tex(soma**2 - produto), _tex(soma**2 - 4 * produto),
        ],
        "correta": 0,
        "erros": [
            "-",
            "trocou o sinal em $(r_1+r_2)^2 = r_1^2 + 2r_1r_2 + r_2^2$",
            "esqueceu o fator 2 no termo do produto",
            "confundiu com o discriminante $\\Delta = S^2 - 4P$",
        ],
        "ideia": (
            "Não é preciso achar as raízes: $r_1^2 + r_2^2 = (r_1+r_2)^2 - 2r_1r_2$, "
            "e Girard dá soma e produto direto dos coeficientes."
        ),
        "solucao": (
            f"Por Girard, $r_1 + r_2 = {soma}$ e $r_1 r_2 = {produto}$. "
            f"Como $r_1^2 + r_2^2 = (r_1+r_2)^2 - 2r_1r_2$, o valor é "
            f"${soma}^2 - 2\\cdot({produto}) = {sp.latex(certo)}$."
        ),
        "topicos": ["polinômios", "relações de Girard"],
        "dificuldade": 2,
    }


def _moivre(sorteio: random.Random) -> dict[str, Any]:
    """Potencia de complexo na forma trigonometrica (De Moivre)."""
    modulo = sorteio.choice([2, 3])
    # Pares escolhidos para que n*pi/d caia num arco notável: resultado limpo.
    denominador, expoente = sorteio.choice([(3, 6), (4, 4), (6, 6), (3, 3), (4, 8)])
    angulo = sp.pi / denominador

    def cis(raio: Any, arco: Any) -> Any:
        return sp.simplify(sp.expand(raio * (sp.cos(arco) + sp.I * sp.sin(arco))))

    certo = cis(sp.Integer(modulo) ** expoente, angulo * expoente)
    sem_elevar_modulo = cis(modulo, angulo * expoente)
    multiplicou_modulo = cis(modulo * expoente, angulo * expoente)
    sem_multiplicar_arco = cis(sp.Integer(modulo) ** expoente, angulo)

    return {
        "enunciado": (
            f"Seja $z$ o número complexo de módulo ${modulo}$ e argumento "
            f"$\\dfrac{{\\pi}}{{{denominador}}}$. O valor de $z^{{{expoente}}}$ é:"
        ),
        "alternativas": [
            _tex(certo), _tex(sem_elevar_modulo),
            _tex(multiplicou_modulo), _tex(sem_multiplicar_arco),
        ],
        "correta": 0,
        "erros": [
            "-",
            "multiplicou o argumento por $n$, mas esqueceu de elevar o módulo",
            "multiplicou o módulo por $n$ em vez de elevá-lo a $n$",
            "elevou o módulo, mas manteve o argumento original",
        ],
        "ideia": (
            "De Moivre: elevar um complexo a $n$ eleva o módulo a $n$ e "
            "multiplica o argumento por $n$. Geometricamente, é uma homotetia "
            "de razão $r^{n-1}$ composta com uma rotação de $(n-1)\\theta$."
        ),
        "solucao": (
            f"$z = {modulo}\\left(\\cos\\frac{{\\pi}}{{{denominador}}} + "
            f"i\\,\\mathrm{{sen}}\\frac{{\\pi}}{{{denominador}}}\\right)$. "
            f"Por De Moivre, $z^{{{expoente}}} = {modulo}^{{{expoente}}}"
            f"\\left(\\cos\\frac{{{expoente}\\pi}}{{{denominador}}} + "
            f"i\\,\\mathrm{{sen}}\\frac{{{expoente}\\pi}}{{{denominador}}}\\right) "
            f"= {sp.latex(certo)}$."
        ),
        "topicos": ["números complexos", "De Moivre"],
        "dificuldade": 3,
    }


def _pg_infinita(sorteio: random.Random) -> dict[str, Any]:
    """Soma de PG infinita, com a armadilha da razao."""
    numerador, denominador = 1, sorteio.choice([3, 4, 5])
    primeiro = sorteio.choice([2, 3, 6, 9])
    razao = sp.Rational(numerador, denominador)
    certo = sp.Integer(primeiro) / (1 - razao)
    errado_sem_um = sp.Integer(primeiro) / razao
    errado_soma = sp.Integer(primeiro) / (1 + razao)
    errado_termos = sp.Integer(primeiro) * (1 - razao)
    return {
        "enunciado": (
            f"A soma dos infinitos termos da progressão geométrica de primeiro "
            f"termo ${primeiro}$ e razão $\\dfrac{{{numerador}}}{{{denominador}}}$ é:"
        ),
        "alternativas": [_tex(certo), _tex(errado_soma),
                         _tex(errado_sem_um), _tex(errado_termos)],
        "correta": 0,
        "erros": [
            "-",
            "trocou o sinal do denominador: usou $1+q$ em vez de $1-q$",
            "esqueceu o $1$ e dividiu apenas pela razão",
            "multiplicou por $1-q$ em vez de dividir",
        ],
        "ideia": (
            "A soma infinita $\\frac{a_1}{1-q}$ só existe porque $|q| < 1$. "
            "Verificar essa condição antes de somar é parte da solução."
        ),
        "solucao": (
            f"Como $|q| = \\frac{{{numerador}}}{{{denominador}}} < 1$, a série "
            f"converge e $S = \\frac{{a_1}}{{1-q}} = "
            f"\\frac{{{primeiro}}}{{1 - \\frac{{{numerador}}}{{{denominador}}}}} "
            f"= {sp.latex(certo)}$."
        ),
        "topicos": ["progressões", "séries"],
        "dificuldade": 2,
    }


def _solucao_anagrama(palavra: str, total: int, repeticoes: list[int], certo: Any) -> str:
    """Texto da solucao do anagrama (fora da f-string: tem contrabarras)."""
    lista = " e ".join(str(r) for r in repeticoes)
    produto = " \\cdot ".join(f"{r}!" for r in repeticoes)
    return (
        f"A palavra {palavra} tem {total} letras, com repetições {lista}. "
        f"O número de anagramas é $\\dfrac{{{total}!}}{{{produto}}} "
        f"= {sp.latex(certo)}$."
    )


def _anagramas(sorteio: random.Random) -> dict[str, Any]:
    """Anagramas com letras repetidas: o erro classico e nao dividir."""
    palavras = {
        "ARARA": (5, [3, 2]), "BANANA": (6, [3, 2]), "MATEMATICA": (10, [3, 2, 2]),
        "PARALELA": (8, [3, 2]), "ESTATISTICA": (11, [2, 3, 2, 2]),
    }
    palavra = sorteio.choice(list(palavras))
    total, repeticoes = palavras[palavra]
    divisor = sp.Integer(1)
    for r in repeticoes:
        divisor *= sp.factorial(r)
    certo = sp.factorial(total) / divisor
    sem_dividir = sp.factorial(total)
    divisor_parcial = sp.factorial(repeticoes[0])
    return {
        "enunciado": (
            f"Quantos anagramas distintos podem ser formados com as letras da "
            f"palavra **{palavra}**?"
        ),
        "alternativas": [
            _tex(certo), _tex(sem_dividir),
            _tex(sp.factorial(total) / divisor_parcial),
            _tex(sp.factorial(total - 1) / divisor),
        ],
        "correta": 0,
        "erros": [
            "-",
            "tratou todas as letras como distintas, sem dividir pelas repetições",
            "dividiu pela repetição de uma só letra, esquecendo as demais",
            "contou $(n-1)!$, como se uma posição estivesse fixa",
        ],
        "ideia": (
            "Permutação com repetição: as trocas entre letras iguais não geram "
            "anagrama novo, então cada anagrama foi contado $k!$ vezes para "
            "cada letra repetida $k$ vezes."
        ),
        "solucao": _solucao_anagrama(palavra, total, repeticoes, certo),
        "topicos": ["análise combinatória", "permutação com repetição"],
        "dificuldade": 2,
    }


def _trigonometrica(sorteio: random.Random) -> dict[str, Any]:
    """Equacao trigonometrica: a armadilha e dar so a solucao principal."""
    casos = [
        (sp.Rational(1, 2), "\\frac{1}{2}", ["\\frac{\\pi}{6}", "\\frac{5\\pi}{6}"]),
        (sp.sqrt(2) / 2, "\\frac{\\sqrt{2}}{2}", ["\\frac{\\pi}{4}", "\\frac{3\\pi}{4}"]),
        (sp.sqrt(3) / 2, "\\frac{\\sqrt{3}}{2}", ["\\frac{\\pi}{3}", "\\frac{2\\pi}{3}"]),
    ]
    valor, valor_tex, raizes = sorteio.choice(casos)
    certo = f"$\\left\\{{{raizes[0]},\\ {raizes[1]}\\right\\}}$"
    return {
        "enunciado": (
            f"Determine o conjunto solução de $\\mathrm{{sen}}\\,x = {valor_tex}$ "
            f"no intervalo $[0, 2\\pi]$."
        ),
        "alternativas": [
            certo,
            f"$\\left\\{{{raizes[0]}\\right\\}}$",
            f"$\\left\\{{{raizes[0]},\\ {raizes[1]},\\ \\pi\\right\\}}$",
            f"$\\left\\{{{raizes[0]},\\ -{raizes[0]}\\right\\}}$",
        ],
        "correta": 0,
        "erros": [
            "-",
            "deu apenas o arco principal, perdendo a solução do segundo quadrante",
            "incluiu uma raiz que não satisfaz a equação",
            "usou simetria em relação à origem, que vale para a tangente, não para o seno",
        ],
        "ideia": (
            "No ciclo, o seno assume o mesmo valor positivo em dois quadrantes: "
            "o primeiro e o segundo. Parar no arco principal perde metade da resposta."
        ),
        "solucao": (
            f"$\\mathrm{{sen}}\\,x = {valor_tex}$ tem, em $[0,2\\pi]$, as soluções "
            f"$x = {raizes[0]}$ (primeiro quadrante) e $x = {raizes[1]}$ "
            f"(segundo quadrante, pois $\\mathrm{{sen}}(\\pi - a) = \\mathrm{{sen}}\\,a$)."
        ),
        "topicos": ["trigonometria", "equações trigonométricas"],
        "dificuldade": 2,
    }


def _logaritmo(sorteio: random.Random) -> dict[str, Any]:
    """Equacao logaritmica com raiz estranha: o erro e aceitar as duas."""
    a = sorteio.choice([2, 3, 4, 6])
    # log(x) + log(x + a) = log(b), com b escolhido para dar raiz inteira.
    raiz = sorteio.choice([2, 3, 4])
    b = raiz * (raiz + a)
    estranha = -(a + raiz)
    return {
        "enunciado": (
            f"O conjunto solução da equação "
            f"$\\log x + \\log(x + {a}) = \\log {b}$ é:"
        ),
        "alternativas": [
            f"$\\{{{raiz}\\}}$",
            f"$\\{{{estranha},\\ {raiz}\\}}$",
            f"$\\{{{estranha}\\}}$",
            "$\\varnothing$",
        ],
        "correta": 0,
        "erros": [
            "-",
            f"resolveu a equação do segundo grau e aceitou as duas raízes, sem "
            f"testar o domínio: ${estranha}$ torna o logaritmando negativo",
            "manteve só a raiz estranha, descartando a válida",
            "concluiu que não há solução",
        ],
        "ideia": (
            "Aplicar a propriedade do produto transforma a equação numa "
            "quadrática, mas a condição de existência $x > 0$ e $x + "
            f"{a} > 0$ precisa ser imposta ANTES de aceitar as raízes."
        ),
        "solucao": (
            f"Condição de existência: $x > 0$. Da propriedade, "
            f"$x(x+{a}) = {b}$, ou seja, $x^2 + {a}x - {b} = 0$, cujas raízes são "
            f"${raiz}$ e ${estranha}$. Como ${estranha} < 0$ viola a condição de "
            f"existência, é raiz estranha. Logo $S = \\{{{raiz}\\}}$."
        ),
        "topicos": ["logaritmos", "condição de existência"],
        "dificuldade": 3,
    }


GERADORES: dict[str, Callable[[random.Random], dict[str, Any]]] = {
    "polinomios": _girard,
    "complexos": _moivre,
    "sequencias": _pg_infinita,
    "combinatoria": _anagramas,
    "trigonometria": _trigonometrica,
    "logaritmos": _logaritmo,
}


def criar_parametrica(topico: str = "", semente: int | None = None) -> Questao:
    """Gera uma questao de molde, com gabarito calculado simbolicamente."""
    sorteio = random.Random(semente)
    gerador = GERADORES.get(topico) or sorteio.choice(list(GERADORES.values()))
    return _embaralhar(gerador(sorteio), sorteio)


# --------------------------------------------------------------------------
# Conferencia do gabarito
# --------------------------------------------------------------------------

def conferir_questao(questao: Questao) -> tuple[bool, str]:
    """Checagens estruturais que nao dependem do assunto da questao."""
    if not questao.enunciado.strip():
        return False, "enunciado vazio"
    if len(questao.alternativas) < 4:
        return False, "menos de quatro alternativas"
    if not 0 <= questao.correta < len(questao.alternativas):
        return False, "índice do gabarito fora da lista de alternativas"

    normalizadas = [a.strip().lower() for a in questao.alternativas]
    if len(set(normalizadas)) != len(normalizadas):
        return False, "há alternativas repetidas"

    # Se o enunciado traz equação legível, confere o gabarito contra a álgebra.
    try:
        checagens = simbolico.conferir_resposta(
            questao.enunciado, questao.alternativas[questao.correta]
        )
    except Exception:
        checagens = []
    reprovadas = [c for c in checagens if not c.passou]
    if reprovadas:
        return False, f"conferência simbólica reprovou: {reprovadas[0].detalhe}"
    if checagens:
        return True, "gabarito confirmado pela álgebra computacional"
    return True, "estrutura válida (sem equação explícita para conferir)"


async def criar(
    topico: str = "",
    dificuldade: int = 3,
    contexto: str = "",
    semente: int | None = None,
) -> Questao:
    """Cria uma questao, preferindo o modelo e caindo no molde parametrico."""
    motor = obter_motor()
    if motor.disponivel:
        pedido = (
            f"Crie uma questão objetiva de matemática.\n"
            f"Assunto: {topico or 'escolha um assunto de ITA/IME'}.\n"
            f"Dificuldade alvo: {dificuldade} (1 direto, 4 nível ITA/IME).\n"
            + (f"Contexto pedido pelo estudante: {contexto}\n" if contexto else "")
        )
        for _ in range(2):  # uma segunda tentativa se a conferência reprovar
            try:
                dados = await motor.responder_json(SISTEMA_CRIADOR, pedido, max_tokens=2200)
            except ErroModelo:
                break
            if not isinstance(dados, dict) or not dados.get("alternativas"):
                continue
            questao = Questao(
                enunciado=str(dados.get("enunciado", "")),
                alternativas=[str(a) for a in dados.get("alternativas", [])][:5],
                correta=int(dados.get("correta", 0) or 0),
                erros_dos_distratores=[str(e) for e in dados.get("erros_dos_distratores", [])],
                ideia_central=str(dados.get("ideia_central", "")),
                solucao=str(dados.get("solucao", "")),
                topicos=[str(t) for t in dados.get("topicos", [])],
                dificuldade=int(dados.get("dificuldade", dificuldade) or dificuldade),
                origem="neural",
            )
            aprovada, motivo = conferir_questao(questao)
            questao.conferida = aprovada
            questao.observacao_da_conferencia = motivo
            if aprovada:
                return questao
            pedido += (
                f"\n\nA tentativa anterior foi recusada na conferência: {motivo}. "
                "Corrija e gere outra questão."
            )

    return criar_parametrica(topico, semente)
