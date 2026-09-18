"""Diagnostico do problema: de que assunto e, quao dificil e, o que tentar.

A profundidade do raciocinio precisa ser adaptativa. Gastar tres passes de
verificacao numa equacao do segundo grau e desperdicio; resolver um problema
de ITA com uma unica passada e imprudencia. Este modulo decide qual dos dois
casos e o atual, antes de qualquer processamento caro.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from ..texto import normalizar

# --------------------------------------------------------------------------
# Topicos e as ferramentas que costumam destravar cada um
# --------------------------------------------------------------------------

@dataclass(slots=True)
class Topico:
    """Um assunto, com as estrategias e verificacoes que lhe sao proprias."""

    chave: str
    nome: str
    pistas: tuple[str, ...]
    estrategias: tuple[str, ...]
    verificacoes: tuple[str, ...]
    ferramentas: tuple[str, ...] = ()


TOPICOS: tuple[Topico, ...] = (
    Topico(
        "polinomios", "Polinômios e equações algébricas",
        ("polinomio", "raiz", "raizes", "grau do polinomio", "girard", "fatorar",
         "fatoracao", "divisao de polinomios", "briot", "ruffini", "equacao do segundo grau",
         "discriminante", "delta", "coeficiente"),
        ("relações de Girard entre coeficientes e raízes",
         "fatoração e teorema das raízes racionais",
         "substituição que reduz o grau",
         "análise do discriminante e do sinal",
         "divisão por Briot-Ruffini quando há raiz conhecida"),
        ("substituir cada raiz no polinômio original",
         "conferir soma e produto das raízes contra os coeficientes",
         "verificar multiplicidade e grau: o número de raízes fecha?"),
        ("expandir", "fatorar", "resolver", "raizes_racionais"),
    ),
    Topico(
        "complexos", "Números complexos",
        ("complexo", "imaginario", "moivre", "argumento", "conjugado", "z =",
         "plano de argand", "forma trigonometrica", "forma polar", "raiz enesima",
         "modulo de z", "afixo"),
        ("passar para a forma trigonométrica e usar De Moivre",
         "interpretar geometricamente no plano de Argand-Gauss",
         "usar que as raízes n-ésimas formam polígono regular",
         "explorar conjugado e módulo: z·z̄ = |z|²",
         "ver a multiplicação por um complexo como rotação e homotetia"),
        ("conferir módulo e argumento do resultado",
         "verificar se o resultado satisfaz a equação original",
         "checar se o lugar geométrico obtido é coerente com os dados"),
        ("expandir", "simplificar", "resolver"),
    ),
    Topico(
        "trigonometria", "Trigonometria",
        ("sen", "cos", "tg", "tangente", "seno", "cosseno", "cotg", "secante",
         "cossecante", "arco duplo", "arco metade", "identidade trigonometrica",
         "lei dos senos", "lei dos cossenos", "ciclo trigonometrico", "radiano"),
        ("reduzir tudo a seno e cosseno de um mesmo arco",
         "usar arco duplo ou arco metade para baixar o grau",
         "transformar soma em produto (prostaférese)",
         "substituição t = tg(x/2)",
         "interpretar no ciclo trigonométrico"),
        ("verificar o período e listar TODAS as soluções, não só a principal",
         "conferir o domínio: tangente e secante excluem pontos",
         "testar numericamente a identidade em pontos aleatórios"),
        ("simplificar", "identidade", "resolver"),
    ),
    Topico(
        "geometria_plana", "Geometria plana",
        ("triangulo", "quadrilatero", "circunferencia", "poligono", "angulo",
         "bissetriz", "mediana", "altura", "incentro", "baricentro", "ortocentro",
         "circuncentro", "semelhanca", "congruencia", "area do triangulo",
         "potencia de ponto", "ceva", "menelaus", "ptolomeu", "stewart", "inscrito"),
        ("procurar semelhança de triângulos",
         "traçar uma construção auxiliar (altura, paralela, prolongamento)",
         "usar potência de ponto ou o quadrilátero inscritível",
         "aplicar Ceva, Menelaus, Ptolomeu ou Stewart",
         "colocar coordenadas e resolver analiticamente",
         "usar áreas como razão entre segmentos"),
        ("conferir se a configuração desenhada decorre mesmo dos dados",
         "testar a desigualdade triangular e a coerência das medidas",
         "verificar o caso degenerado (pontos colineares, ângulo reto)"),
        ("resolver", "simplificar"),
    ),
    Topico(
        "geometria_analitica", "Geometria analítica",
        ("reta", "circunferencia de centro", "elipse", "hiperbole", "parabola",
         "coordenadas", "distancia entre", "lugar geometrico", "foco", "diretriz",
         "excentricidade", "vetor", "produto escalar", "produto vetorial", "baricentro de"),
        ("escrever a condição do lugar geométrico e simplificar",
         "usar vetores em vez de coordenadas quando houver simetria",
         "reconhecer a cônica pela forma reduzida",
         "escolher o sistema de eixos que simplifica os dados",
         "usar produto escalar para ângulo e perpendicularidade"),
        ("verificar se pontos dados satisfazem a equação obtida",
         "conferir o sinal e o domínio dos parâmetros",
         "checar casos degenerados da cônica"),
        ("expandir", "simplificar", "resolver"),
    ),
    Topico(
        "geometria_espacial", "Geometria espacial",
        ("prisma", "piramide", "cilindro", "cone", "esfera", "tetraedro",
         "cubo de aresta", "aresta do cubo", "diagonal do cubo", "volume",
         "area total", "area lateral", "secao transversal", "tronco de",
         "solido", "inscrita na esfera", "circunscrito", "octaedro", "dodecaedro"),
        ("reduzir a um problema plano por uma seção bem escolhida",
         "usar semelhança entre o sólido e o tronco",
         "colocar coordenadas no espaço",
         "decompor o sólido em pedaços de volume conhecido",
         "explorar a simetria do sólido"),
        ("conferir a homogeneidade dimensional (volume é comprimento ao cubo)",
         "verificar se a seção usada é realmente plana",
         "testar o caso limite (altura zero, raio igual)"),
        ("simplificar", "resolver"),
    ),
    Topico(
        "matrizes", "Matrizes, determinantes e sistemas",
        ("matriz", "determinante", "sistema linear", "escalonamento", "inversa",
         "transposta", "cramer", "posto", "autovalor", "singular", "cofator"),
        ("escalonar o sistema e discutir conforme o parâmetro",
         "usar propriedades do determinante em vez de expandir",
         "reconhecer a estrutura da matriz (triangular, simétrica, blocos)",
         "interpretar o sistema geometricamente"),
        ("substituir a solução em todas as equações do sistema",
         "conferir se o determinante nulo foi tratado como caso separado",
         "verificar a discussão completa: única, infinitas ou nenhuma"),
        ("determinante", "resolver_sistema", "simplificar"),
    ),
    Topico(
        "combinatoria", "Análise combinatória",
        ("quantas maneiras", "de quantos modos", "permutacao", "arranjo",
         "combinacao", "anagrama", "contagem", "casa dos pombos", "principio da inclusao",
         "quantos numeros", "quantas comissoes", "fatorial", "binomio de newton",
         "triangulo de pascal", "quantos subconjuntos"),
        ("contar o complementar em vez do caso pedido",
         "usar inclusão-exclusão",
         "estabelecer uma bijeção com um problema já resolvido",
         "separar em casos disjuntos e somar",
         "montar uma recorrência",
         "dupla contagem: contar o mesmo conjunto de dois jeitos"),
        ("recontar por um segundo método e comparar",
         "testar o caso pequeno (n = 1, 2, 3) na mão",
         "conferir se casos foram contados duas vezes ou esquecidos"),
        ("binomial", "fatorial", "simplificar"),
    ),
    Topico(
        "probabilidade", "Probabilidade",
        ("probabilidade", "chance de", "espaco amostral", "evento", "independente",
         "condicional", "bayes", "esperanca", "media de", "sorteio", "dado",
         "moeda", "aleatorio", "ao acaso"),
        ("montar o espaço amostral equiprovável",
         "condicionar num evento intermediário",
         "usar o complementar",
         "explorar simetria entre resultados",
         "calcular esperança por linearidade, sem a distribuição toda"),
        ("conferir que toda probabilidade está em [0,1]",
         "verificar se as probabilidades dos casos somam 1",
         "checar independência antes de multiplicar"),
        ("binomial", "simplificar"),
    ),
    Topico(
        "calculo", "Cálculo e análise",
        ("limite", "limite de", "tende a", "tende ao", "derivada", "derivar",
         "integral", "integrar", "primitiva", "continuidade", "assintota",
         "maximo", "minimo", "ponto critico", "concavidade", "inflexao",
         "taxa de variacao", "area sob a curva", "serie", "convergencia"),
        ("derivar e analisar o sinal da derivada",
         "usar substituição na integral",
         "aplicar o teorema do valor médio ou de Rolle",
         "estudar convexidade para desigualdades",
         "reconhecer o limite notável"),
        ("conferir o domínio e a continuidade nos pontos críticos",
         "testar o valor nos extremos do intervalo",
         "derivar o resultado da integral para voltar ao integrando"),
        ("derivar", "integrar", "limite", "simplificar"),
    ),
    Topico(
        "sequencias", "Sequências, progressões e recorrências",
        ("progressao aritmetica", "progressao geometrica", "pa ", "pg ", "razao da",
         "termo geral", "soma dos termos", "recorrencia", "sequencia definida",
         "fibonacci", "termo enesimo", "soma infinita", "soma dos n primeiros",
         "n primeiros", "por inducao", "somatorio"),
        ("achar o termo geral e provar por indução",
         "somar telescopicamente",
         "resolver a recorrência linear pela equação característica",
         "reconhecer PA ou PG disfarçada após uma substituição"),
        ("testar o termo geral nos primeiros índices",
         "conferir a convergência antes de somar série infinita",
         "verificar o índice inicial: começa em 0 ou em 1?"),
        ("simplificar", "resolver"),
    ),
    Topico(
        "logaritmos", "Exponenciais e logaritmos",
        ("logaritmo", "log ", "ln ", "exponencial", "base do logaritmo",
         "mudanca de base", "cologaritmo", "antilogaritmo", "equacao exponencial"),
        ("igualar as bases",
         "aplicar logaritmo dos dois lados",
         "mudar de base para unificar",
         "substituir t = a^x para cair numa equação algébrica"),
        ("conferir a condição de existência: logaritmando > 0 e base válida",
         "descartar raízes que violam o domínio",
         "substituir a solução na equação original"),
        ("resolver", "simplificar"),
    ),
    Topico(
        "teoria_numeros", "Teoria dos números",
        ("divisibilidade", "divisivel por", "congruencia", "modulo n", "resto da divisao",
         "mdc", "mmc", "numero primo", "fatoracao em primos", "diofantina",
         "algarismos de", "base numerica", "paridade"),
        ("trabalhar módulo um inteiro conveniente",
         "usar paridade ou o último algarismo",
         "fatorar em primos e comparar expoentes",
         "descida infinita ou princípio do menor elemento",
         "testar casos pequenos para achar o padrão"),
        ("testar a conclusão em casos pequenos",
         "conferir se o módulo escolhido cobre todos os restos",
         "verificar a existência de solução inteira, não só racional"),
        ("mdc", "fatorar", "simplificar"),
    ),
    Topico(
        "algebra", "Álgebra geral, funções e inequações",
        ("funcao", "dominio da funcao", "imagem da funcao", "funcao inversa",
         "funcao composta", "inequacao", "modulo de", "grafico da funcao",
         "injetora", "sobrejetora", "bijetora", "funcao afim", "funcao quadratica",
         "valor absoluto", "estudo do sinal"),
        ("estudar o sinal de cada fator",
         "separar em casos pelo módulo",
         "substituir para simplificar a estrutura",
         "usar monotonicidade para garantir unicidade",
         "analisar graficamente antes de calcular"),
        ("conferir o domínio e excluir raízes estranhas",
         "testar um ponto de cada intervalo da inequação",
         "substituir a solução na equação original"),
        ("resolver", "simplificar", "fatorar"),
    ),
)

TOPICO_PADRAO = Topico(
    "geral", "Matemática geral", (),
    ("traduzir o enunciado para linguagem simbólica",
     "procurar a estrutura escondida antes de calcular",
     "testar um caso pequeno para entender o mecanismo",
     "trabalhar de trás para frente, a partir do que se quer provar"),
    ("substituir o resultado nas condições do enunciado",
     "conferir se a resposta responde exatamente ao que foi perguntado"),
    ("simplificar",),
)

TOPICOS_POR_CHAVE = {t.chave: t for t in TOPICOS} | {"geral": TOPICO_PADRAO}


# --------------------------------------------------------------------------
# Dificuldade
# --------------------------------------------------------------------------

# Sinais de que o problema pede mais do que aplicação direta de fórmula.
_SINAIS_DIFICULDADE: tuple[tuple[str, float, str], ...] = (
    (r"\bdemonstre\b|\bprove\b|\bmostre que\b", 2.0, "pede demonstração"),
    (r"\bpara todo\b|\bqualquer que seja\b|\bexiste\b|\bexistem\b", 1.2, "quantificador"),
    (r"\bdetermine todos\b|\btodos os valores\b|\btodas as\b", 1.0, "exige exaustividade"),
    (r"\bdiscuta\b|\bem funç[ãa]o do par[âa]metro\b|\bconforme os valores\b", 1.5,
     "discussão por parâmetro"),
    (r"\bcondi[çc][ãa]o necess[áa]ria\b|\bsuficiente\b|\bse e somente se\b", 1.5,
     "necessário e suficiente"),
    (r"\bm[áa]ximo\b|\bm[íi]nimo\b|\bmaior valor\b|\bmenor valor\b", 0.8, "otimização"),
    (r"\bn[ãa]o existe\b|\bimposs[íi]vel\b", 1.2, "impossibilidade"),
    (r"\blugar geom[ée]trico\b", 1.2, "lugar geométrico"),
    (r"\bindu[çc][ãa]o\b|\brecorr[êe]ncia\b", 1.0, "indução ou recorrência"),
    (r"\bgeneraliz", 1.0, "generalização"),
    (r"\bvalores? (?:reais |inteiros |positivos )?d[eo] [a-zA-Z]\b", 1.2,
     "discussão por parâmetro"),
    (r"\btenha (?:duas|dois|tr[êe]s|exatamente|pelo menos|no m[áa]ximo)\b", 0.8,
     "condição sobre a natureza das soluções"),
    (r"\bde (?:modo|forma|maneira) que\b|\bde tal (?:modo|forma)\b", 0.9,
     "contagem com restrição"),
    (r"\bpelo menos\b|\bno m[áa]ximo\b|\bexatamente\b|\bnenhum[a]?\b", 0.6,
     "restrição de contagem"),
    (r"\bITA\b|\bIME\b|\bolimp[íi]ada\b|\bIMO\b|\bOBM\b", 1.5, "prova de alto nível"),
)

NIVEIS = {
    1: ("direto", "aplicação direta de uma definição ou fórmula"),
    2: ("intermediário", "exige montar o modelo e verificar o resultado"),
    3: ("difícil", "pede escolha de estratégia entre caminhos possíveis"),
    4: ("ITA/IME", "exige ideia não evidente, decomposição e verificação independente"),
}


@dataclass(slots=True)
class Diagnostico:
    """O que o sistema entendeu do problema antes de tentar resolvê-lo."""

    topico: str
    topico_nome: str
    topicos_secundarios: list[str] = field(default_factory=list)
    dificuldade: int = 2
    dificuldade_nome: str = ""
    dificuldade_descricao: str = ""
    sinais: list[str] = field(default_factory=list)
    estrategias: list[str] = field(default_factory=list)
    verificacoes: list[str] = field(default_factory=list)
    pede_demonstracao: bool = False
    pede_valor: bool = True

    @property
    def usar_critico(self) -> bool:
        """Problemas dificeis merecem um segundo passe de critica."""
        return self.dificuldade >= 3

    @property
    def usar_estrategias_multiplas(self) -> bool:
        return self.dificuldade >= 3

    @property
    def orcamento_tokens(self) -> int:
        """Profundidade adaptativa: esforço proporcional à dificuldade."""
        return {1: 1200, 2: 2200, 3: 3600, 4: 5000}[self.dificuldade]

    def para_dict(self) -> dict[str, Any]:
        return {
            "topico": self.topico,
            "topico_nome": self.topico_nome,
            "topicos_secundarios": self.topicos_secundarios,
            "dificuldade": self.dificuldade,
            "dificuldade_nome": self.dificuldade_nome,
            "dificuldade_descricao": self.dificuldade_descricao,
            "sinais": self.sinais,
            "estrategias": self.estrategias,
            "verificacoes": self.verificacoes,
            "pede_demonstracao": self.pede_demonstracao,
        }


@lru_cache(maxsize=512)
def _padrao_da_pista(alvo: str) -> re.Pattern[str]:
    """Casa a pista como palavra inteira, aceitando plural.

    Substring simples não serve: "sen" precisa casar em "sen(2x)", onde não há
    espaço depois, mas não pode casar dentro de "sentido".
    """
    return re.compile(rf"(?<![a-z0-9]){re.escape(alvo)}s?(?![a-z])")


def _pontuar_topicos(enunciado: str) -> list[tuple[float, Topico]]:
    texto = normalizar(enunciado)
    pontuados: list[tuple[float, Topico]] = []
    for topico in TOPICOS:
        pontos = 0.0
        for pista in topico.pistas:
            alvo = normalizar(pista).strip()
            if not alvo:
                continue
            # Expressões de várias palavras são sinal muito mais forte.
            peso = 1.0 + 0.9 * alvo.count(" ")
            if _padrao_da_pista(alvo).search(texto):
                pontos += peso
        if pontos:
            pontuados.append((pontos, topico))
    pontuados.sort(key=lambda par: par[0], reverse=True)
    return pontuados


def _notacao(enunciado: str) -> list[str]:
    """Sinais dados pela notação, que o vocabulário sozinho não pega."""
    marcas: list[str] = []
    if re.search(r"∫|\bintegral\b", enunciado):
        marcas.append("calculo")
    if re.search(r"\bd/dx\b|\bf'\(|\by'\b", enunciado):
        marcas.append("calculo")
    if re.search(r"\blim\b|→|\bx\s*->|\btende a\b|\btendendo a\b", enunciado):
        marcas.append("calculo")
    # "algo elevado ao quadrado igualado a zero" é equação polinomial.
    if re.search(r"[\^²³]\s*\d?[^=]{0,40}=\s*0\b", enunciado):
        marcas.append("polinomios")
    if re.search(r"\b[zZ]\s*=.*\bi\b|\b\d\s*\+\s*\d?\s*i\b|\bcis\b", enunciado):
        marcas.append("complexos")
    if re.search(r"Σ|\bsomatorio\b|\bsomatório\b", enunciado):
        marcas.append("sequencias")
    if re.search(r"\bC\(\s*\d+\s*,|\bbinom|\b\d+!\B|\bP\(\s*[A-Z]", enunciado):
        marcas.append("combinatoria")
    if re.search(r"\[\s*[-\d].*\]|\bdet\s*\(", enunciado):
        marcas.append("matrizes")
    return marcas


def classificar(enunciado: str) -> Diagnostico:
    """Diagnostica assunto e dificuldade a partir do enunciado."""
    pontuados = _pontuar_topicos(enunciado)
    por_notacao = _notacao(enunciado)

    for chave in por_notacao:
        topico = TOPICOS_POR_CHAVE.get(chave)
        if topico is None:
            continue
        existente = next((i for i, (_, t) in enumerate(pontuados) if t.chave == chave), None)
        if existente is None:
            pontuados.append((1.5, topico))
        else:
            pontos, _ = pontuados[existente]
            pontuados[existente] = (pontos + 1.5, topico)
    pontuados.sort(key=lambda par: par[0], reverse=True)

    principal = pontuados[0][1] if pontuados else TOPICO_PADRAO
    secundarios = [t.nome for _, t in pontuados[1:3]]

    # --- dificuldade ----------------------------------------------------
    pontos = 1.0
    sinais: list[str] = []
    for padrao, peso, rotulo in _SINAIS_DIFICULDADE:
        if re.search(padrao, enunciado, re.IGNORECASE):
            pontos += peso
            sinais.append(rotulo)

    # Cruzamento de assuntos costuma ser o que torna a questão difícil.
    assuntos_fortes = [t for p, t in pontuados if p >= 2.0]
    if len(assuntos_fortes) >= 2:
        pontos += 1.0
        sinais.append(f"cruza {len(assuntos_fortes)} assuntos")

    # Enunciado longo com muitas condições encadeadas.
    if len(enunciado.split()) > 70:
        pontos += 0.6
        sinais.append("enunciado extenso")
    if enunciado.count(",") + enunciado.count(";") >= 6:
        pontos += 0.4
        sinais.append("muitas condições")

    if pontos >= 4.0:
        nivel = 4
    elif pontos >= 2.6:
        nivel = 3
    elif pontos >= 1.6:
        nivel = 2
    else:
        nivel = 1

    nome, descricao = NIVEIS[nivel]
    pede_demonstracao = bool(
        re.search(r"\bdemonstre\b|\bprove\b|\bmostre que\b|\bjustifique\b",
                  enunciado, re.IGNORECASE)
    )

    return Diagnostico(
        topico=principal.chave,
        topico_nome=principal.nome,
        topicos_secundarios=secundarios,
        dificuldade=nivel,
        dificuldade_nome=nome,
        dificuldade_descricao=descricao,
        sinais=sinais,
        estrategias=list(principal.estrategias),
        verificacoes=list(principal.verificacoes),
        pede_demonstracao=pede_demonstracao,
        pede_valor=not pede_demonstracao,
    )
