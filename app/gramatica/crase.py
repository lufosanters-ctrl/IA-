"""Motor de crase: decide caso a caso, com a regra citada.

A crase e o topico de portugues que mais se parece com matematica:

    crase = preposicao "a" + artigo (ou pronome) "a"

Ou seja, duas condicoes precisam valer ao mesmo tempo. E o que este modulo faz
e testar cada uma delas separadamente, na ordem certa:

1. **Proibicoes** vem primeiro, porque sao absolutas. Se o termo seguinte e
   masculino, verbo, pronome pessoal ou esta no plural com "a" no singular,
   acabou: nao ha crase, e nem precisa olhar a regencia.
2. **Locucoes** vem em seguida, porque sao consagradas e nao dependem de
   analise ("as pressas", "a noite", "a medida que").
3. **Facultativas** sao marcadas como tal, sem fingir que ha uma unica
   resposta certa.
4. Sobrando tudo isso, a decisao **depende da regencia** do termo anterior —
   e ai o modulo consulta o dicionario de regencia e devolve a pergunta que o
   estudante precisa responder.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .lexico import (
    POSSESSIVOS_FEMININOS,
    PRONOMES_DEMONSTRATIVOS_SEM_CRASE,
    PRONOMES_INDEFINIDOS,
    PRONOMES_PESSOAIS,
    PRONOMES_TRATAMENTO,
    REPETIVEIS,
    e_comum_de_dois,
    e_numeral_cardinal,
    e_tratamento,
    e_plural,
    e_verbo_no_infinitivo,
    genero,
    normalizado,
)
from .regencia import verbos_na_frase

OBRIGATORIA = "obrigatoria"
PROIBIDA = "proibida"
FACULTATIVA = "facultativa"
DEPENDE = "depende_da_regencia"

# --------------------------------------------------------------------------
# Locucoes consagradas
# --------------------------------------------------------------------------

# Locuções femininas que SEMPRE levam crase (o acento é marca distintiva).
LOCUCOES_COM_CRASE: dict[str, str] = {
    "a noite": "locução adverbial feminina",
    "a tarde": "locução adverbial feminina",
    "as vezes": "locução adverbial feminina",
    "a toa": "locução adverbial feminina",
    "as pressas": "locução adverbial feminina",
    "as claras": "locução adverbial feminina",
    "as escondidas": "locução adverbial feminina",
    "as escuras": "locução adverbial feminina",
    "as cegas": "locução adverbial feminina",
    "as avessas": "locução adverbial feminina",
    "a forca": "locução adverbial feminina",
    "a vontade": "locução adverbial feminina",
    "a beca": "locução adverbial feminina",
    "a risca": "locução adverbial feminina",
    "a revelia": "locução adverbial feminina",
    "a direita": "locução adverbial feminina",
    "a esquerda": "locução adverbial feminina",
    "a vista": "locução adverbial feminina",
    "a mao": "locução adverbial feminina",
    "a maquina": "locução adverbial feminina",
    "a caneta": "locução adverbial feminina",
    "a tinta": "locução adverbial feminina",
    "a queima-roupa": "locução adverbial feminina",
    "a distancia": "locução adverbial feminina (quando a distância é determinada)",
    "a frente de": "locução prepositiva feminina",
    "a custa de": "locução prepositiva feminina",
    "a espera de": "locução prepositiva feminina",
    "a procura de": "locução prepositiva feminina",
    "a base de": "locução prepositiva feminina",
    "a excecao de": "locução prepositiva feminina",
    "a maneira de": "locução prepositiva feminina",
    "a moda de": "locução prepositiva feminina",
    "a luz de": "locução prepositiva feminina",
    "a merce de": "locução prepositiva feminina",
    "a disposicao de": "locução prepositiva feminina",
    "a prova de": "locução prepositiva feminina",
    "a altura de": "locução prepositiva feminina",
    "a semelhanca de": "locução prepositiva feminina",
    "a margem de": "locução prepositiva feminina",
    "a cata de": "locução prepositiva feminina",
    "a beira de": "locução prepositiva feminina",
    "as vesperas de": "locução prepositiva feminina",
    "a medida que": "locução conjuntiva feminina",
    "a proporcao que": "locução conjuntiva feminina",
    "as ordens de": "locução prepositiva feminina",
}

# Locuções masculinas: o "a" é só preposição, nunca leva acento.
LOCUCOES_SEM_CRASE: dict[str, str] = {
    "a pe": "locução com palavra masculina",
    "a cavalo": "locução com palavra masculina",
    "a lapis": "locução com palavra masculina",
    "a bordo": "locução com palavra masculina",
    "a prazo": "locução com palavra masculina",
    "a partir de": "locução com palavra masculina",
    "a respeito de": "locução com palavra masculina",
    "a fim de": "locução com palavra masculina",
    "a gosto": "locução com palavra masculina",
    "a contento": "locução com palavra masculina",
    "a sangue frio": "locução com palavra masculina",
    "a toda hora": "antes de pronome indefinido não há artigo",
    "a cada": "antes de pronome indefinido não há artigo",
}

# Locucoes que sao homografas de sintagmas nominais comuns. "A noite estava
# fria" e sujeito, nao locucao adverbial; "A vista do mar" idem. Quando uma
# delas abre a oracao sem virgula depois, e sujeito — e sujeito nao leva crase.
LOCUCOES_AMBIGUAS = {
    "a noite", "a tarde", "a vista", "a direita", "a esquerda", "a distancia",
    "a mao", "a forca", "a vontade", "a frente de", "a base de", "a maneira de",
    "a margem de", "a altura de",
    "a caneta", "a tinta", "a maquina", "a prova de", "a luz de",
}

_RE_PALAVRA = re.compile(r"[0-9A-Za-zÀ-ÿ][0-9A-Za-zÀ-ÿ'-]*")
_RE_HORA = re.compile(r"^\d{1,2}(?:[h:]\d{0,2})?$")

ARTIGOS_A = {"a", "à", "as", "às", "a"}

# Se já existe uma preposição imediatamente antes, o "a" seguinte só pode ser
# artigo — não há preposição sobrando para a crase. "Desde as 8 horas" e "para
# a praia" não levam acento. "Até" fica de fora: ali o caso é facultativo.
PREPOSICOES_ANTERIORES = {
    "de", "desde", "para", "por", "com", "em", "sobre", "sob", "entre",
    "contra", "perante", "ante", "apos", "durante", "conforme", "segundo",
    "mediante", "salvo", "exceto", "tras", "pra",
}
CONTRACOES_AQUELE = {
    "aquele", "aqueles", "aquela", "aquelas", "aquilo",
    "àquele", "àqueles", "àquela", "àquelas", "àquilo",
}


@dataclass(slots=True)
class OcorrenciaCrase:
    """Uma ocorrência de 'a/à' analisada, com a regra que a decide."""

    escrito: str
    termo_seguinte: str
    contexto: str
    situacao: str
    forma_correta: str
    regra: str
    explicacao: str
    correto: bool | None = None
    pergunta_guia: str = ""
    verbos_regentes: list[str] = field(default_factory=list)

    def para_dict(self) -> dict[str, Any]:
        return {
            "escrito": self.escrito,
            "termo_seguinte": self.termo_seguinte,
            "contexto": self.contexto,
            "situacao": self.situacao,
            "forma_correta": self.forma_correta,
            "regra": self.regra,
            "explicacao": self.explicacao,
            "correto": self.correto,
            "pergunta_guia": self.pergunta_guia,
            "verbos_regentes": self.verbos_regentes,
        }


def _tem_acento(palavra: str) -> bool:
    return "à" in palavra.lower()


def _locucao_a_partir_de(palavras: list[str], indice: int) -> tuple[str, str, bool] | None:
    """Procura, a partir do 'a', a locução mais longa que casa."""
    for tamanho in (4, 3, 2):
        trecho = " ".join(
            normalizado(p) for p in palavras[indice: indice + tamanho]
        )
        if trecho in LOCUCOES_COM_CRASE:
            return trecho, LOCUCOES_COM_CRASE[trecho], True
        if trecho in LOCUCOES_SEM_CRASE:
            return trecho, LOCUCOES_SEM_CRASE[trecho], False
    return None


def _e_sujeito_e_nao_locucao(trecho: str, marcas: list[Any], indice: int,
                             frase: str) -> bool:
    """`A noite estava fria` e sujeito; `A noite, saimos` e adverbio deslocado.

    Uma locucao adverbial homografa de sintagma nominal so vale no inicio da
    oracao quando vem separada por virgula. Sem a virgula, o que abre a frase
    e o sujeito — e sujeito nunca leva crase.
    """
    if trecho not in LOCUCOES_AMBIGUAS:
        return False
    if indice != 0:
        return False
    tamanho = len(trecho.split())
    fim = indice + tamanho - 1
    if fim >= len(marcas):
        return False
    depois = frase[marcas[fim].end(): marcas[fim].end() + 2]
    return "," not in depois


def _proibicao(seguinte: str, escrito: str, palavras: list[str],
               indice: int) -> tuple[str, str] | None:
    """Testa as proibições absolutas. Devolve (regra, explicação) ou None."""
    alvo = normalizado(seguinte)
    if not alvo:
        return None

    if e_verbo_no_infinitivo(seguinte):
        return ("antes de verbo", 
                f"“{seguinte}” é verbo. Antes de verbo não existe artigo, "
                "e sem artigo não há crase.")

    if alvo in PRONOMES_PESSOAIS and alvo not in {"a", "as"}:
        return ("antes de pronome pessoal",
                f"“{seguinte}” é pronome pessoal e não admite artigo.")

    if alvo in PRONOMES_DEMONSTRATIVOS_SEM_CRASE:
        return ("antes de pronome demonstrativo",
                f"“{seguinte}” já é demonstrativo e dispensa o artigo.")

    if alvo in PRONOMES_INDEFINIDOS:
        return ("antes de pronome indefinido",
                f"“{seguinte}” é pronome indefinido e não vem acompanhado de artigo.")

    if e_tratamento(palavras, indice + 1):
        return ("antes de pronome de tratamento",
                f"Pronomes de tratamento como “{seguinte}” não admitem artigo.")

    if e_numeral_cardinal(seguinte):
        # A exceção das horas já foi tratada antes desta função; aqui só resta
        # o numeral comum. O teste de "hora" fica como segunda barreira.
        seguintes = " ".join(normalizado(p) for p in palavras[indice + 1: indice + 3])
        if "hora" not in seguintes:
            return ("antes de numeral cardinal",
                    "Antes de numeral cardinal não há artigo — salvo em indicação "
                    "de horas determinadas.")

    if genero(seguinte) == "masculino":
        return ("antes de palavra masculina",
                f"“{seguinte}” é masculino, então o artigo seria “o”, não “a”. "
                "A única exceção é a elipse de “à moda de”.")

    # "a" singular diante de plural: houve só preposição, sem artigo.
    if e_plural(seguinte) and escrito.lower() in {"a", "à"}:
        return ("“a” singular diante de plural",
                f"“{seguinte}” está no plural. Com o “a” no singular, houve apenas "
                "preposição — o artigo plural daria “às”.")

    # Palavra repetida: "cara a cara", "gota a gota".
    anterior = normalizado(palavras[indice - 1]) if indice > 0 else ""
    if anterior and anterior == alvo and alvo in REPETIVEIS:
        return ("entre palavras repetidas",
                f"Em locuções do tipo “{anterior} a {alvo}” não há artigo.")

    return None


def _facultativa(seguinte: str, palavras: list[str], indice: int) -> tuple[str, str] | None:
    """Casos em que as duas grafias sao aceitas."""
    alvo = normalizado(seguinte)
    anterior = normalizado(palavras[indice - 1]) if indice > 0 else ""

    if anterior == "ate":
        return ("depois de “até”",
                "Depois de “até”, o uso do artigo é facultativo: “até a praia” e "
                "“até à praia” são ambas corretas.")

    if alvo in POSSESSIVOS_FEMININOS:
        return ("antes de possessivo feminino singular",
                f"Antes de “{seguinte}” o artigo é facultativo: “a minha casa” e "
                "“à minha casa” são ambas aceitas.")

    # Nome próprio feminino: começa com maiúscula e não é início de frase.
    bruto = seguinte.strip(" .,;:!?")
    if (indice > 0 and bruto[:1].isupper() and genero(bruto) == "feminino"
            and len(bruto) > 2):
        return ("antes de nome próprio feminino",
                f"Antes de nome próprio de pessoa como “{bruto}” o artigo é "
                "facultativo, e por isso a crase também é.")
    return None


# Um verbo rege o complemento que vem logo depois dele. Passando dessa
# distância, a ligação já não é confiável e o motor prefere perguntar.
_ALCANCE_DA_REGENCIA = 4


def _posicoes_dos_verbos(palavras: list[str], verbos: list[str]) -> list[tuple[int, str]]:
    """Onde, na frase, cada verbo regente aparece."""
    from .regencia import _padrao_do_verbo

    posicoes: list[tuple[int, str]] = []
    for indice, palavra in enumerate(palavras):
        limpa = normalizado(palavra)
        # "Refiro-me" é um token só: o verbo está antes do hífen.
        formas = {limpa, limpa.split("-", 1)[0]}
        for verbo in verbos:
            padrao = _padrao_do_verbo(verbo)
            if any(padrao.fullmatch(forma) for forma in formas if forma):
                posicoes.append((indice, verbo))
                break
    return posicoes


def _regido_por(indice: int, posicoes: list[tuple[int, str]]) -> str:
    """O verbo que rege a ocorrência nesta posição, se houver."""
    for posicao, verbo in posicoes:
        if 0 < indice - posicao <= _ALCANCE_DA_REGENCIA:
            return verbo
    return ""


def analisar_crase(frase: str) -> list[OcorrenciaCrase]:
    """Analisa todas as ocorrências de “a/à” de uma frase."""
    marcas = list(_RE_PALAVRA.finditer(frase or ""))
    palavras = [m.group(0) for m in marcas]
    if not palavras:
        return []

    # Separa o verbo que rege "a" sem ambiguidade do que muda com o sentido.
    # "Ir" sempre pede "a"; "assistir" depende do sentido — e nesse caso a
    # decisão não é do motor, é do estudante.
    regentes: list[str] = []
    regentes_certos: list[str] = []
    ambiguos: list[str] = []
    for verbo, sentidos in verbos_na_frase(frase):
        if not any(s.exige_a for s in sentidos):
            continue
        regentes.append(verbo)
        # So e conclusivo quando TODOS os sentidos pedem "a" e o complemento
        # que vem logo depois e mesmo o indireto. Em bitransitivos ("convidar
        # alguem PARA algo", "informar algo A alguem") o termo colado no verbo
        # e o objeto DIRETO, que nao leva crase: "Convidei a aluna" esta certo.
        conclusivo = all(
            s.exige_a and s.transitividade.strip() == "indireto" for s in sentidos
        )
        if conclusivo:
            regentes_certos.append(verbo)
        else:
            ambiguos.append(verbo)

    posicoes_regentes = _posicoes_dos_verbos(palavras, regentes_certos)
    posicoes_ambiguas = _posicoes_dos_verbos(palavras, ambiguos)
    ocorrencias: list[OcorrenciaCrase] = []

    for indice, bruta in enumerate(palavras):
        alvo = bruta.lower()
        alvo_sem_acento = normalizado(bruta)

        # Contração com "aquele/aquela/aquilo".
        if alvo in CONTRACOES_AQUELE:
            explicacao = (
                "A crase com “aquele/aquela/aquilo” depende só da regência: se o "
                "termo anterior exige a preposição “a”, escreve-se “àquele”."
            )
            ocorrencias.append(OcorrenciaCrase(
                escrito=bruta,
                termo_seguinte="",
                contexto=" ".join(palavras[max(0, indice - 3): indice + 3]),
                situacao=DEPENDE,
                forma_correta="à… se o termo anterior exigir “a”",
                regra="contração com demonstrativo",
                explicacao=explicacao,
                verbos_regentes=regentes,
                pergunta_guia=(
                    "Qual é o termo que rege esse complemento, e ele pede a "
                    "preposição “a”? Teste trocando por um masculino: se sai "
                    "“àquele”, a preposição existe."
                ),
            ))
            continue

        if alvo_sem_acento not in {"a", "as"}:
            continue

        seguinte = palavras[indice + 1] if indice + 1 < len(palavras) else ""
        contexto = " ".join(palavras[max(0, indice - 3): indice + 4])
        acentuado = _tem_acento(bruta)

        # 1) Preposição imediatamente antes: decide na frente de tudo, inclusive
        #    das horas. Em "desde as 8 horas" não há preposição sobrando.
        anterior = normalizado(palavras[indice - 1]) if indice > 0 else ""
        if anterior in PREPOSICOES_ANTERIORES:
            ocorrencias.append(OcorrenciaCrase(
                escrito=bruta, termo_seguinte=seguinte, contexto=contexto,
                situacao=PROIBIDA,
                forma_correta="a" if alvo_sem_acento == "a" else "as",
                regra="depois de outra preposição",
                explicacao=(
                    f"“{palavras[indice - 1]}” já é a preposição. O “a” seguinte "
                    "só pode ser artigo, e sem preposição sobrando não há crase."
                ),
                correto=not acentuado, verbos_regentes=regentes,
            ))
            continue

        # 2) Locuções consagradas.
        locucao = _locucao_a_partir_de(palavras, indice)
        if locucao and _e_sujeito_e_nao_locucao(locucao[0], marcas, indice, frase):
            ocorrencias.append(OcorrenciaCrase(
                escrito=bruta, termo_seguinte=seguinte, contexto=contexto,
                situacao=PROIBIDA,
                forma_correta="a" if alvo_sem_acento == "a" else "as",
                regra="artigo do sujeito",
                explicacao=(
                    f"Aqui \u201c{bruta} {seguinte}\u201d abre a ora\u00e7\u00e3o como sujeito, n\u00e3o como "
                    "locu\u00e7\u00e3o adverbial. Sujeito n\u00e3o vem regido de preposi\u00e7\u00e3o, "
                    "ent\u00e3o o \u201ca\u201d \u00e9 s\u00f3 artigo e fica sem acento."
                ),
                correto=not acentuado, verbos_regentes=regentes,
            ))
            continue
        if locucao:
            trecho, motivo, com_crase = locucao
            ocorrencias.append(OcorrenciaCrase(
                escrito=bruta, termo_seguinte=seguinte, contexto=contexto,
                situacao=OBRIGATORIA if com_crase else PROIBIDA,
                forma_correta="à" if com_crase else "a",
                regra=f"locução consagrada ({trecho})",
                explicacao=(
                    f"“{trecho}” é {motivo}, então "
                    + ("o acento é obrigatório." if com_crase
                       else "não há artigo e o “a” fica sem acento.")
                ),
                correto=acentuado == com_crase,
                verbos_regentes=regentes,
            ))
            continue

        if not seguinte:
            continue

        # 3) Horas determinadas. Só vale com evidência de horário: sem ela,
        #    "de 2 a 4 semanas" viraria "às 4 semanas".
        vizinhanca = " ".join(normalizado(p) for p in palavras[indice: indice + 3])
        fala_de_hora = (
            "hora" in vizinhanca
            or re.search(r"\d\s*[h:]", " ".join(palavras[indice: indice + 2]))
            or "meio-dia" in vizinhanca
            or "meia-noite" in vizinhanca
        )
        if fala_de_hora and (
            _RE_HORA.match(normalizado(seguinte))
            or e_numeral_cardinal(seguinte)
            or normalizado(seguinte) in {"uma", "duas", "meia"}
        ):
            ocorrencias.append(OcorrenciaCrase(
                escrito=bruta, termo_seguinte=seguinte, contexto=contexto,
                situacao=OBRIGATORIA, forma_correta="à" if alvo_sem_acento == "a" else "às",
                regra="horas determinadas",
                explicacao=(
                    "Em indicação de hora determinada há preposição e artigo: "
                    "“às 8 horas”, “à uma hora”. O teste é trocar por “ao meio-dia”: "
                    "se aparece “ao”, a preposição existe."
                ),
                correto=acentuado, verbos_regentes=regentes,
            ))
            continue

        # 4) Proibições absolutas.
        proibicao = _proibicao(seguinte, bruta, palavras, indice)
        if proibicao:
            regra, explicacao = proibicao
            ocorrencias.append(OcorrenciaCrase(
                escrito=bruta, termo_seguinte=seguinte, contexto=contexto,
                situacao=PROIBIDA, forma_correta="a" if alvo_sem_acento == "a" else "as",
                regra=regra, explicacao=explicacao,
                correto=not acentuado, verbos_regentes=regentes,
            ))
            continue

        # 5) Casos facultativos.
        facultativa = _facultativa(seguinte, palavras, indice)
        if facultativa:
            regra, explicacao = facultativa
            ocorrencias.append(OcorrenciaCrase(
                escrito=bruta, termo_seguinte=seguinte, contexto=contexto,
                situacao=FACULTATIVA, forma_correta="à ou a (ambas corretas)",
                regra=regra, explicacao=explicacao,
                correto=True, verbos_regentes=regentes,
            ))
            continue

        # 6) Sobrou a regência: a segunda condição já está satisfeita.
        genero_seguinte = genero(seguinte)
        if genero_seguinte != "feminino":
            continue

        # A segunda condição (artigo) está satisfeita. Falta a preposição.
        # Só conclui quando o verbo regente está REALMENTE antes desta
        # ocorrência: numa frase com vários "a", o verbo rege um deles, não
        # todos.
        regido = _regido_por(indice, posicoes_regentes)
        regido_ambiguo = _regido_por(indice, posicoes_ambiguas)

        if regido and not regido_ambiguo:
            verbo = regido
            ocorrencias.append(OcorrenciaCrase(
                escrito=bruta, termo_seguinte=seguinte, contexto=contexto,
                situacao=OBRIGATORIA,
                forma_correta="à" if alvo_sem_acento == "a" else "às",
                regra=f"regência de “{verbo}” + artigo feminino",
                explicacao=(
                    f"“{verbo}” exige a preposição “a” em todos os sentidos "
                    f"registrados, e “{seguinte}” é feminino e admite artigo. "
                    "As duas condições da crase estão satisfeitas."
                ),
                correto=acentuado, verbos_regentes=regentes,
            ))
            continue

        explicacao = (
            f"“{seguinte}” é feminino e admite artigo, então metade da conta "
            "está fechada. Falta saber se o termo anterior exige a preposição "
            "“a”."
        )
        pergunta = (
            "Troque o termo feminino por um masculino equivalente. "
            "Se aparecer “ao”, havia preposição e a crase existe; "
            "se aparecer só “o”, não havia."
        )
        if regido_ambiguo:
            explicacao += (
                f" Atenção: “{regido_ambiguo}” muda de regência conforme o "
                "sentido, então a resposta depende de qual sentido está em jogo."
            )
            pergunta = f"Em que sentido “{regido_ambiguo}” está empregado nesta frase?"
        elif regentes:
            explicacao += (
                " Verbos de regência cobrada presentes na frase: "
                + ", ".join(regentes) + "."
            )

        ocorrencias.append(OcorrenciaCrase(
            escrito=bruta, termo_seguinte=seguinte, contexto=contexto,
            situacao=DEPENDE, forma_correta="depende da regência",
            regra="condição do artigo satisfeita; falta a preposição",
            explicacao=explicacao, correto=None, verbos_regentes=regentes,
            pergunta_guia=pergunta,
        ))
    return ocorrencias


def teste_do_masculino(frase: str, termo_feminino: str, termo_masculino: str) -> str:
    """Aplica o teste clássico: trocar o termo feminino por um masculino."""
    trocada = re.sub(
        rf"\b[aà]s?\s+{re.escape(termo_feminino)}\b",
        f"ao {termo_masculino}", frase, flags=re.IGNORECASE
    )
    return trocada
