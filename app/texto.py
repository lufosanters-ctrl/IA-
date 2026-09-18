"""Utilidades de processamento de texto em portugues e ingles.

Tudo aqui e puro Python: sem dependencias pesadas, sem download de modelos.
Isso mantem a plataforma leve e capaz de rodar offline.
"""

from __future__ import annotations

import html
import re
import unicodedata
from dataclasses import dataclass

# --------------------------------------------------------------------------
# Listas de palavras vazias (stopwords)
# --------------------------------------------------------------------------

STOPWORDS_PT = {
    "a", "à", "às", "ao", "aos", "aquela", "aquelas", "aquele", "aqueles", "aquilo",
    "as", "até", "com", "como", "da", "das", "de", "dela", "delas", "dele", "deles",
    "depois", "do", "dos", "e", "ela", "elas", "ele", "eles", "em", "entre", "era",
    "eram", "essa", "essas", "esse", "esses", "esta", "estas", "este", "estes", "eu",
    "foi", "foram", "há", "isso", "isto", "já", "lhe", "lhes", "mais", "mas", "me",
    "mesmo", "meu", "minha", "muito", "na", "nas", "nem", "no", "nos", "nossa",
    "nosso", "não", "num", "numa", "o", "os", "ou", "para", "pela", "pelas", "pelo",
    "pelos", "por", "qual", "quando", "que", "quem", "se", "sem", "ser", "seu",
    "seus", "só", "sua", "suas", "são", "também", "te", "tem", "tendo", "ter", "teu",
    "tu", "um", "uma", "vez", "você", "vocês", "à", "é", "está", "estão", "sobre",
    "quais", "onde", "porque", "pois", "todo", "toda", "todos", "todas", "cada",
}

STOPWORDS_EN = {
    "a", "about", "above", "after", "again", "all", "also", "am", "an", "and", "any",
    "are", "as", "at", "be", "because", "been", "before", "being", "below", "between",
    "both", "but", "by", "can", "did", "do", "does", "doing", "down", "during",
    "each", "few", "for", "from", "further", "had", "has", "have", "having", "he",
    "her", "here", "hers", "him", "his", "how", "i", "if", "in", "into", "is", "it",
    "its", "itself", "just", "me", "more", "most", "my", "no", "nor", "not", "now",
    "of", "off", "on", "once", "only", "or", "other", "our", "out", "over", "own",
    "same", "she", "should", "so", "some", "such", "than", "that", "the", "their",
    "them", "then", "there", "these", "they", "this", "those", "through", "to", "too",
    "under", "until", "up", "very", "was", "we", "were", "what", "when", "where",
    "which", "while", "who", "whom", "why", "will", "with", "you", "your",
}

STOPWORDS = STOPWORDS_PT | STOPWORDS_EN

_RE_TAG = re.compile(r"<[^>]+>")
_RE_ESPACO = re.compile(r"[ \t ]+")
_RE_LINHAS = re.compile(r"\n{3,}")
_RE_TOKEN = re.compile(r"[0-9a-zà-öø-ÿ]+", re.IGNORECASE)
_RE_REFS = re.compile(r"\[\d+\]")
_RE_FIM_FRASE = re.compile(r"(?<=[.!?])\s+(?=[A-ZÀ-Ý0-9\"'])")


def limpar_html(bruto: str) -> str:
    """Remove marcacao HTML e normaliza espacos."""
    if not bruto:
        return ""
    texto = _RE_TAG.sub(" ", bruto)
    texto = html.unescape(texto)
    texto = _RE_REFS.sub("", texto)
    texto = _RE_ESPACO.sub(" ", texto)
    texto = _RE_LINHAS.sub("\n\n", texto)
    return texto.strip()


def normalizar(palavra: str) -> str:
    """Minusculas sem acentos, para comparacao robusta."""
    decomposto = unicodedata.normalize("NFD", palavra.lower())
    return "".join(c for c in decomposto if unicodedata.category(c) != "Mn")


def tokenizar(texto: str, remover_stopwords: bool = True) -> list[str]:
    """Divide o texto em tokens normalizados."""
    tokens = [normalizar(t) for t in _RE_TOKEN.findall(texto or "")]
    if remover_stopwords:
        vazias = {normalizar(p) for p in STOPWORDS}
        tokens = [t for t in tokens if t not in vazias and len(t) > 1]
    return tokens


def dividir_frases(texto: str) -> list[str]:
    """Separa um texto em frases, de forma tolerante a abreviacoes simples."""
    texto = (texto or "").replace("\n", " ").strip()
    if not texto:
        return []
    protegido = re.sub(r"\b([A-Z][a-z]{0,2})\.\s", r"\1<PONTO> ", texto)
    partes = _RE_FIM_FRASE.split(protegido)
    frases: list[str] = []
    for parte in partes:
        frase = parte.replace("<PONTO>", ".").strip()
        if len(frase) >= 15:
            frases.append(frase)
    return frases


def resumir_extrativo(texto: str, consulta: str, max_frases: int = 3) -> str:
    """Resumo extrativo simples guiado pela consulta do usuario."""
    frases = dividir_frases(texto)
    if not frases:
        return (texto or "")[:400]
    termos = set(tokenizar(consulta))
    pontuadas: list[tuple[float, int, str]] = []
    for indice, frase in enumerate(frases):
        tokens = tokenizar(frase)
        if not tokens:
            continue
        cobertura = len(termos & set(tokens)) / (len(termos) or 1)
        posicao = 1.0 / (1.0 + indice * 0.35)
        tamanho = min(len(tokens) / 30.0, 1.0)
        pontuadas.append((cobertura * 2.0 + posicao + tamanho * 0.4, indice, frase))
    pontuadas.sort(key=lambda item: item[0], reverse=True)
    escolhidas = sorted(pontuadas[:max_frases], key=lambda item: item[1])
    return " ".join(frase for _, _, frase in escolhidas)


@dataclass(slots=True)
class Trecho:
    """Pedaco de texto pronto para ranqueamento e citacao."""

    texto: str
    doc_id: str
    titulo: str
    url: str
    fonte: str
    indice: int = 0
    score: float = 0.0


def dividir_em_trechos(
    texto: str,
    tamanho: int = 900,
    sobreposicao: int = 150,
) -> list[str]:
    """Quebra o texto em blocos respeitando limites de frase."""
    texto = (texto or "").strip()
    if not texto:
        return []
    if len(texto) <= tamanho:
        return [texto]

    frases = dividir_frases(texto) or [texto]
    blocos: list[str] = []
    atual = ""
    for frase in frases:
        if len(atual) + len(frase) + 1 <= tamanho:
            atual = f"{atual} {frase}".strip()
            continue
        if atual:
            blocos.append(atual)
            cauda = atual[-sobreposicao:] if sobreposicao else ""
            atual = f"{cauda} {frase}".strip() if cauda else frase
        else:
            blocos.append(frase[:tamanho])
            atual = frase[tamanho:]
    if atual.strip():
        blocos.append(atual.strip())
    return [b for b in blocos if len(b) > 60]


def truncar(texto: str, limite: int) -> str:
    """Corta o texto preservando a ultima palavra inteira."""
    texto = (texto or "").strip()
    if len(texto) <= limite:
        return texto
    corte = texto[:limite].rsplit(" ", 1)[0]
    return corte.rstrip(",;:.") + "..."
