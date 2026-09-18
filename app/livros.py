"""Extracao de texto de livros para a biblioteca local.

Formatos aceitos: PDF, EPUB, TXT, Markdown e HTML.

O trabalho aqui nao e so "pegar o texto": livro didatico vem cheio de ruido
que estraga a busca — cabecalho repetido em toda pagina, numero de pagina
solto, palavra quebrada por hifen no fim da linha. Este modulo limpa isso
antes de indexar.
"""

from __future__ import annotations

import hashlib
import io
import re
import unicodedata
import zipfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from .texto import limpar_html

FORMATOS = {".pdf", ".epub", ".txt", ".md", ".markdown", ".htm", ".html"}

_RE_HIFEN = re.compile(r"(\w+)-\s*\n\s*(\w+)")
_RE_QUEBRA = re.compile(r"(?<![.!?:;])\n(?![\n\s*\-•\d])")
_RE_ESPACO = re.compile(r"[ \t ]{2,}")
_RE_LINHAS = re.compile(r"\n{3,}")
_RE_SO_NUMERO = re.compile(r"^\s*[ivxlcdm\d]{1,6}\s*$", re.IGNORECASE)
_RE_CAPITULO = re.compile(
    r"^\s*(cap[íi]tulo|unidade|parte|se[çc][ãa]o|chapter|unit|part|se[çc]ao)\s+"
    r"([\dIVXLC]+)\b[.:\s-]*(.{0,80})",
    re.IGNORECASE,
)
_RE_TITULO_MD = re.compile(r"^\s{0,3}(#{1,3})\s+(.{2,90})$")


@dataclass(slots=True)
class Pagina:
    """Uma pagina (PDF) ou secao (EPUB/texto) ja limpa."""

    numero: int
    texto: str
    capitulo: str = ""


@dataclass(slots=True)
class LivroExtraido:
    """Resultado da extracao, pronto para ser indexado."""

    titulo: str
    autores: list[str] = field(default_factory=list)
    idioma: str = ""
    paginas: list[Pagina] = field(default_factory=list)
    formato: str = ""

    @property
    def palavras(self) -> int:
        return sum(len(p.texto.split()) for p in self.paginas)


class ErroExtracao(RuntimeError):
    """O arquivo nao pode ser lido ou nao tem texto aproveitavel."""


# --------------------------------------------------------------------------
# Limpeza
# --------------------------------------------------------------------------

def juntar_linhas(bruto: str) -> str:
    """Remove hifenizacao e junta linhas quebradas no meio da frase."""
    texto = _RE_HIFEN.sub(r"\1\2", bruto)
    texto = _RE_QUEBRA.sub(" ", texto)
    texto = _RE_ESPACO.sub(" ", texto)
    return _RE_LINHAS.sub("\n\n", texto).strip()


# Marcador de pagina: "12", "- 12 -", "pág. 12", "Page 12 of 340", "xiv".
_RE_MARCADOR_PAGINA = re.compile(
    r"^\s*[-–—|\[]?\s*(?:p[aá]g(?:ina)?\.?|page|fl\.?)?\s*"
    r"[\divxlcdmIVXLCDM]{1,6}\s*(?:(?:/|de|of)\s*\d{1,6})?\s*[-–—|\]]?\s*$",
    re.IGNORECASE,
)


def _assinatura(linha: str) -> str:
    """Normaliza uma linha para detectar repeticao literal entre paginas.

    De proposito NAO mascara numeros. Fazer isso transformaria "Exercicio 1",
    "Exercicio 2"... na mesma assinatura, e o detector apagaria o corpo do
    livro achando que era cabecalho. Numero de pagina solto e tratado a parte,
    por `_RE_MARCADOR_PAGINA`.
    """
    base = re.sub(r"\s+", " ", linha.strip().lower())
    decomposto = unicodedata.normalize("NFD", base)
    return "".join(c for c in decomposto if unicodedata.category(c) != "Mn")


def _e_marcador_de_pagina(linha: str) -> bool:
    texto = linha.strip()
    return bool(texto) and len(texto) <= 24 and bool(_RE_MARCADOR_PAGINA.match(texto))


def remover_cabecalhos(paginas: list[str], limiar: float = 0.5) -> list[str]:
    """Descarta linhas que se repetem na maioria das paginas.

    Cabecalho de capitulo e rodape com numero de pagina aparecem identicos
    (a menos do numero) pagina apos pagina. Indexar isso polui a busca: o
    titulo do capitulo passaria a casar com toda pagina do livro.
    """
    if len(paginas) < 4:
        return paginas

    contagem: Counter[str] = Counter()
    for pagina in paginas:
        linhas = [linha for linha in pagina.split("\n") if linha.strip()]
        for linha in linhas[:3] + linhas[-3:]:
            if len(linha.strip()) <= 90:
                contagem[_assinatura(linha)] += 1

    minimo = max(3, int(len(paginas) * limiar))
    repetidas = {chave for chave, n in contagem.items() if n >= minimo}

    limpas: list[str] = []
    for pagina in paginas:
        mantidas = [
            linha for linha in pagina.split("\n")
            if _assinatura(linha) not in repetidas and not _e_marcador_de_pagina(linha)
        ]
        # Nunca devolve uma pagina vazia por excesso de zelo do detector.
        limpas.append("\n".join(mantidas) if any(m.strip() for m in mantidas) else pagina)
    return limpas


def _sem_marcacao_de_titulo(texto: str) -> str:
    """Tira os '#' de titulos Markdown do texto ja indexado.

    O titulo em si e util como contexto e fica; so a marcacao sai, para a
    citacao exibida ao estudante nao mostrar '## Capitulo 3'.
    """
    def trocar(achado: re.Match[str]) -> str:
        titulo = achado.group(1).strip()
        # Sem pontuacao final, o titulo se funde com a frase seguinte e o
        # resumo extrativo sai como "Capitulo 6 Fotossintese A fotossintese e...".
        return titulo if titulo[-1:] in ".!?:" else f"{titulo}."

    return re.sub(r"^\s{0,3}#{1,6}\s+(.+)$", trocar, texto, flags=re.MULTILINE)


def detectar_capitulo(texto: str, anterior: str) -> str:
    """Identifica o capitulo corrente pelo cabecalho da pagina."""
    for linha in texto.split("\n")[:6]:
        achado = _RE_CAPITULO.match(linha.strip())
        if achado:
            rotulo = " ".join(p for p in achado.groups() if p).strip()
            return re.sub(r"\s+", " ", rotulo)[:90]
        titulo_md = _RE_TITULO_MD.match(linha)
        if titulo_md:
            return titulo_md.group(2).strip()[:90]
    return anterior


# --------------------------------------------------------------------------
# Extratores por formato
# --------------------------------------------------------------------------

def _extrair_pdf(caminho: Path) -> LivroExtraido:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover
        raise ErroExtracao(
            "leitura de PDF exige o pacote 'pypdf' (pip install pypdf)"
        ) from exc

    try:
        leitor = PdfReader(str(caminho))
        if leitor.is_encrypted:
            try:
                leitor.decrypt("")
            except Exception as exc:
                raise ErroExtracao("PDF protegido por senha") from exc
        brutas = [(pagina.extract_text() or "") for pagina in leitor.pages]
    except ErroExtracao:
        raise
    except Exception as exc:
        raise ErroExtracao(f"PDF ilegivel: {type(exc).__name__}") from exc

    if not any(b.strip() for b in brutas):
        raise ErroExtracao(
            "o PDF nao tem camada de texto (provavelmente e digitalizado). "
            "Passe por um OCR antes de adicionar."
        )

    metadados = leitor.metadata or {}
    titulo = (metadados.get("/Title") or "").strip() or caminho.stem
    autor = (metadados.get("/Author") or "").strip()

    paginas: list[Pagina] = []
    capitulo = ""
    for indice, texto in enumerate(remover_cabecalhos(brutas), start=1):
        capitulo = detectar_capitulo(texto, capitulo)
        limpo = juntar_linhas(texto)
        if len(limpo) >= 120:
            paginas.append(Pagina(numero=indice, texto=limpo, capitulo=capitulo))

    return LivroExtraido(
        titulo=titulo,
        autores=[a.strip() for a in re.split(r"[,;&]| e ", autor) if a.strip()],
        paginas=paginas,
        formato="pdf",
    )


def _extrair_epub(caminho: Path) -> LivroExtraido:
    """Le um EPUB usando apenas a biblioteca padrao (e um zip com XHTML)."""
    try:
        arquivo = zipfile.ZipFile(caminho)
    except zipfile.BadZipFile as exc:
        raise ErroExtracao("EPUB corrompido") from exc

    with arquivo:
        nomes = arquivo.namelist()
        opf = next((n for n in nomes if n.lower().endswith(".opf")), "")
        titulo, autores, idioma, ordem = caminho.stem, [], "", []

        if opf:
            try:
                manifesto = arquivo.read(opf).decode("utf-8", "ignore")
            except KeyError:
                manifesto = ""
            achado = re.search(r"<dc:title[^>]*>(.*?)</dc:title>", manifesto, re.S)
            if achado:
                titulo = limpar_html(achado.group(1)).strip() or titulo
            autores = [
                limpar_html(a).strip()
                for a in re.findall(r"<dc:creator[^>]*>(.*?)</dc:creator>", manifesto, re.S)
            ]
            idioma_achado = re.search(r"<dc:language[^>]*>(.*?)</dc:language>", manifesto, re.S)
            if idioma_achado:
                idioma = limpar_html(idioma_achado.group(1)).strip()[:5]

            # Ordem de leitura declarada no spine (idref -> href do manifest).
            itens = dict(
                re.findall(r'<item\b[^>]*id="([^"]+)"[^>]*href="([^"]+)"', manifesto)
            ) | dict(
                (i, h) for h, i in re.findall(
                    r'<item\b[^>]*href="([^"]+)"[^>]*id="([^"]+)"', manifesto
                )
            )
            base = str(Path(opf).parent)
            for idref in re.findall(r'<itemref\b[^>]*idref="([^"]+)"', manifesto):
                href = itens.get(idref)
                if not href:
                    continue
                alvo = str(Path(base) / href) if base not in (".", "") else href
                alvo = alvo.replace("\\", "/").split("#")[0]
                if alvo in nomes:
                    ordem.append(alvo)

        if not ordem:
            ordem = sorted(
                n for n in nomes
                if n.lower().endswith((".xhtml", ".html", ".htm"))
                and not n.lower().startswith("__")
            )
        if not ordem:
            raise ErroExtracao("EPUB sem capitulos legiveis")

        paginas: list[Pagina] = []
        for indice, nome in enumerate(ordem, start=1):
            try:
                bruto = arquivo.read(nome).decode("utf-8", "ignore")
            except KeyError:
                continue
            cabecalho = re.search(r"<h[1-3][^>]*>(.*?)</h[1-3]>", bruto, re.S | re.I)
            capitulo = limpar_html(cabecalho.group(1))[:90] if cabecalho else ""
            corpo = re.sub(r"<(script|style)\b.*?</\1>", " ", bruto, flags=re.S | re.I)
            texto = juntar_linhas(limpar_html(corpo))
            if len(texto) >= 200:
                paginas.append(Pagina(numero=indice, texto=texto, capitulo=capitulo))

    if not paginas:
        raise ErroExtracao("EPUB sem texto aproveitavel")

    return LivroExtraido(
        titulo=titulo, autores=autores, idioma=idioma, paginas=paginas, formato="epub"
    )


def _extrair_texto_simples(caminho: Path) -> LivroExtraido:
    bruto = caminho.read_text(encoding="utf-8", errors="ignore")
    if caminho.suffix.lower() in {".htm", ".html"}:
        bruto = re.sub(r"<(script|style)\b.*?</\1>", " ", bruto, flags=re.S | re.I)
        titulo_html = re.search(r"<title[^>]*>(.*?)</title>", bruto, re.S | re.I)
        titulo = limpar_html(titulo_html.group(1)).strip() if titulo_html else caminho.stem
        bruto = limpar_html(bruto)
        formato = "html"
    else:
        titulo = caminho.stem
        primeira = bruto.lstrip().split("\n", 1)[0]
        cabecalho = _RE_TITULO_MD.match(primeira)
        if cabecalho:
            titulo = cabecalho.group(2).strip()
        formato = "markdown" if caminho.suffix.lower() in {".md", ".markdown"} else "texto"

    if len(bruto.strip()) < 200:
        raise ErroExtracao("arquivo curto demais para virar material de estudo")

    # Quebra em blocos de ~6000 caracteres, cortando em paragrafo.
    paginas: list[Pagina] = []
    capitulo = ""
    atual: list[str] = []
    tamanho = 0
    indice = 1

    def fechar() -> None:
        """Fecha a secao corrente como uma pagina."""
        nonlocal atual, tamanho, indice
        if not atual:
            return
        texto = _sem_marcacao_de_titulo(juntar_linhas("\n\n".join(atual)))
        if len(texto) >= 120:
            paginas.append(Pagina(numero=indice, texto=texto, capitulo=capitulo))
            indice += 1
        atual, tamanho = [], 0

    for paragrafo in bruto.split("\n\n"):
        novo_capitulo = detectar_capitulo(paragrafo, capitulo)
        # Um capitulo novo fecha a secao anterior. Sem isso, o livro inteiro
        # ficaria rotulado com o ultimo capitulo encontrado, e a citacao
        # apontaria para o capitulo errado.
        if novo_capitulo != capitulo and atual:
            fechar()
        capitulo = novo_capitulo
        atual.append(paragrafo)
        tamanho += len(paragrafo)
        if tamanho >= 6000:
            fechar()
    fechar()

    if not paginas:
        raise ErroExtracao("nenhum trecho aproveitavel no arquivo")

    return LivroExtraido(titulo=titulo, paginas=paginas, formato=formato)


def extrair(caminho: Path) -> LivroExtraido:
    """Extrai o texto de um livro, escolhendo o leitor pelo formato."""
    caminho = Path(caminho)
    if not caminho.exists():
        raise ErroExtracao(f"arquivo nao encontrado: {caminho}")
    sufixo = caminho.suffix.lower()
    if sufixo not in FORMATOS:
        raise ErroExtracao(
            f"formato {sufixo or '(sem extensao)'} nao suportado. "
            f"Aceitos: {', '.join(sorted(FORMATOS))}"
        )
    if sufixo == ".pdf":
        return _extrair_pdf(caminho)
    if sufixo == ".epub":
        return _extrair_epub(caminho)
    return _extrair_texto_simples(caminho)


def impressao_digital(caminho: Path) -> str:
    """SHA-256 do arquivo, usado para nao indexar o mesmo livro duas vezes."""
    resumo = hashlib.sha256()
    with open(caminho, "rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1 << 20), b""):
            resumo.update(bloco)
    return resumo.hexdigest()
