"""Catalogo de livros didaticos abertos que a plataforma sabe baixar sozinha.

Duas fontes, ambas de acesso livre e com API estavel:

* **Wikilivros** (pt.wikibooks.org) — livros didaticos escritos em portugues,
  licenca CC BY-SA. O download monta o livro inteiro a partir da pagina
  principal e de todas as suas subpaginas, na ordem.
* **Project Gutenberg** (via API Gutendex) — obras em dominio publico,
  incluindo classicos didaticos de matematica e ciencias.

O catalogo guarda *consultas*, nao identificadores fixos: cada item e
resolvido por busca no momento do download. Assim o comando continua
funcionando quando um livro e renomeado ou substituido por edicao melhor.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx

from .biblioteca import ResultadoIngestao, diretorio_livros, indexar
from .livros import nome_de_arquivo_seguro
from .texto import limpar_html

log = logging.getLogger("nucleo.catalogo")

LICENCA_WIKILIVROS = "CC BY-SA 3.0 (Wikilivros)"
LICENCA_GUTENBERG = "Domínio público (Project Gutenberg)"


@dataclass(slots=True)
class ItemCatalogo:
    """Um livro que a plataforma sabe buscar e indexar."""

    chave: str
    titulo: str
    area: str
    origem: str          # "wikilivros" ou "gutenberg"
    consulta: str
    descricao: str = ""

    def para_dict(self) -> dict[str, Any]:
        return {
            "chave": self.chave, "titulo": self.titulo, "area": self.area,
            "origem": self.origem, "descricao": self.descricao,
        }


CATALOGO: list[ItemCatalogo] = [
    # --- exatas ---------------------------------------------------------
    ItemCatalogo("matematica-elementar", "Matemática elementar", "matematica",
                 "wikilivros", "Matemática elementar",
                 "Aritmética, álgebra e funções, do básico ao ensino médio."),
    ItemCatalogo("calculo", "Cálculo", "matematica", "wikilivros", "Cálculo",
                 "Limites, derivadas, integrais e séries."),
    ItemCatalogo("algebra-linear", "Álgebra linear", "matematica", "wikilivros",
                 "Álgebra linear", "Vetores, matrizes, espaços e transformações."),
    ItemCatalogo("estatistica", "Estatística", "estatistica", "wikilivros",
                 "Estatística", "Descritiva, probabilidade e inferência."),
    ItemCatalogo("fisica", "Física", "fisica", "wikilivros", "Física",
                 "Mecânica, termodinâmica, ondas e eletromagnetismo."),
    ItemCatalogo("quimica-geral", "Química geral", "quimica", "wikilivros",
                 "Química geral", "Átomos, ligações, reações e estequiometria."),
    # --- biologicas e saude ---------------------------------------------
    ItemCatalogo("biologia", "Biologia", "biologia", "wikilivros", "Biologia",
                 "Célula, genética, evolução e ecologia."),
    ItemCatalogo("anatomia", "Anatomia e fisiologia humana", "medicina",
                 "wikilivros", "Anatomia e fisiologia humana",
                 "Sistemas do corpo humano."),
    # --- computacao -----------------------------------------------------
    ItemCatalogo("python", "Programação em Python", "computacao", "wikilivros",
                 "Python", "Linguagem Python do zero, com exercícios."),
    ItemCatalogo("algoritmos", "Algoritmos e estruturas de dados", "computacao",
                 "wikilivros", "Algoritmos e Estruturas de Dados",
                 "Estruturas clássicas e análise de complexidade."),
    # --- humanas --------------------------------------------------------
    ItemCatalogo("historia-brasil", "História do Brasil", "humanas", "wikilivros",
                 "História do Brasil", "Da colônia à república."),
    ItemCatalogo("portugues", "Português", "humanas", "wikilivros", "Português",
                 "Gramática, sintaxe e interpretação de texto."),
    # --- classicos em dominio publico -----------------------------------
    ItemCatalogo("calculus-made-easy", "Calculus Made Easy", "matematica",
                 "gutenberg", "Calculus Made Easy",
                 "Clássico de Silvanus Thompson: cálculo explicado sem formalismo."),
    ItemCatalogo("origin-of-species", "On the Origin of Species", "biologia",
                 "gutenberg", "On the Origin of Species",
                 "Darwin, texto integral."),
    ItemCatalogo("euclid-elements", "Euclid's Elements", "matematica",
                 "gutenberg", "First Six Books of the Elements of Euclid",
                 "Geometria euclidiana na fonte."),
]

CATALOGO_POR_CHAVE = {item.chave: item for item in CATALOGO}


def listar_catalogo(area: str = "") -> list[dict[str, Any]]:
    itens = [i for i in CATALOGO if not area or i.area == area]
    return [i.para_dict() for i in itens]


class ErroDownload(RuntimeError):
    """Nao foi possivel obter o livro."""


def _nome_seguro(titulo: str, extensao: str) -> str:
    """Nome de arquivo a partir do título do livro do catálogo.

    O título vem de um catálogo público, então pode trazer qualquer coisa.
    Além da limpeza para leitura, passa pelas regras do sistema de arquivos:
    um livro chamado "Aux" viraria "aux.txt", que o Windows recusa.
    """
    base = re.sub(r"[^\w\s-]", "", titulo, flags=re.UNICODE).strip()
    base = re.sub(r"[\s_]+", "-", base).lower()[:80] or "livro"
    return nome_de_arquivo_seguro(f"{base}{extensao}")


# --------------------------------------------------------------------------
# Wikilivros
# --------------------------------------------------------------------------

API_WIKILIVROS = "https://pt.wikibooks.org/w/api.php"


async def _achar_wikilivro(cliente: httpx.AsyncClient, consulta: str) -> str:
    """Encontra o titulo real do livro na Wikilivros."""
    resposta = await cliente.get(API_WIKILIVROS, params={
        "action": "query", "format": "json", "list": "search",
        "srsearch": consulta, "srnamespace": 0, "srlimit": 5,
    })
    resposta.raise_for_status()
    achados = (resposta.json().get("query") or {}).get("search") or []
    if not achados:
        raise ErroDownload(f"nenhum livro na Wikilivros para “{consulta}”")
    # Prefere a pagina principal do livro (sem barra no titulo).
    principais = [a["title"] for a in achados if "/" not in a["title"]]
    return (principais or [achados[0]["title"]])[0]


async def _paginas_do_wikilivro(
    cliente: httpx.AsyncClient, titulo: str, maximo: int = 60
) -> list[str]:
    """Lista a pagina principal e todas as subpaginas (capitulos), em ordem."""
    paginas = [titulo]
    continuar: dict[str, str] = {}
    while len(paginas) < maximo:
        resposta = await cliente.get(API_WIKILIVROS, params={
            "action": "query", "format": "json", "list": "allpages",
            "apprefix": f"{titulo}/", "apnamespace": 0,
            "aplimit": min(50, maximo - len(paginas)), **continuar,
        })
        resposta.raise_for_status()
        dados = resposta.json()
        paginas.extend(p["title"] for p in (dados.get("query") or {}).get("allpages", []))
        proximo = (dados.get("continue") or {}).get("apcontinue")
        if not proximo:
            break
        continuar = {"apcontinue": proximo}
    return paginas[:maximo]


async def baixar_wikilivro(
    cliente: httpx.AsyncClient, consulta: str, destino: Path | None = None
) -> tuple[Path, str, str]:
    """Baixa um livro da Wikilivros como Markdown. Devolve (arquivo, titulo, url)."""
    titulo = await _achar_wikilivro(cliente, consulta)
    paginas = await _paginas_do_wikilivro(cliente, titulo)

    partes: list[str] = [f"# {titulo}\n"]
    for lote_inicio in range(0, len(paginas), 10):
        lote = paginas[lote_inicio:lote_inicio + 10]
        resposta = await cliente.get(API_WIKILIVROS, params={
            "action": "query", "format": "json", "prop": "extracts",
            "explaintext": 1, "exsectionformat": "plain",
            "titles": "|".join(lote),
        })
        resposta.raise_for_status()
        obtidas = (resposta.json().get("query") or {}).get("pages") or {}
        ordem = {t: i for i, t in enumerate(lote)}
        for pagina in sorted(obtidas.values(), key=lambda p: ordem.get(p.get("title", ""), 99)):
            corpo = (pagina.get("extract") or "").strip()
            if len(corpo) < 200:
                continue
            capitulo = pagina.get("title", "").split("/")[-1]
            partes.append(f"\n## {capitulo}\n\n{corpo}\n")

    conteudo = "\n".join(partes)
    if len(conteudo) < 1500:
        raise ErroDownload(f"“{titulo}” tem conteúdo curto demais para virar material")

    destino = destino or diretorio_livros()
    destino.mkdir(parents=True, exist_ok=True)
    arquivo = destino / _nome_seguro(titulo, ".md")
    arquivo.write_text(conteudo, encoding="utf-8")
    url = f"https://pt.wikibooks.org/wiki/{titulo.replace(' ', '_')}"
    return arquivo, titulo, url


# --------------------------------------------------------------------------
# Project Gutenberg (via Gutendex)
# --------------------------------------------------------------------------

API_GUTENDEX = "https://gutendex.com/books"


async def baixar_gutenberg(
    cliente: httpx.AsyncClient, consulta: str, destino: Path | None = None
) -> tuple[Path, str, str]:
    """Baixa um livro em dominio publico do Project Gutenberg."""
    resposta = await cliente.get(API_GUTENDEX, params={"search": consulta})
    resposta.raise_for_status()
    achados = resposta.json().get("results") or []
    if not achados:
        raise ErroDownload(f"nada no Project Gutenberg para “{consulta}”")

    livro = achados[0]
    formatos = livro.get("formats") or {}
    endereco = next(
        (
            url for tipo, url in formatos.items()
            if tipo.startswith("text/plain") and not url.endswith(".zip")
        ),
        "",
    )
    if not endereco:
        raise ErroDownload("o livro não tem versão em texto simples")

    if not _endereco_confiavel(endereco):
        raise ErroDownload(
            "o endereço do arquivo não aponta para um domínio conhecido do "
            "Project Gutenberg"
        )
    texto = await _baixar_texto(cliente, endereco)
    if len(texto) < 3000:
        raise ErroDownload("arquivo baixado é curto demais")

    # Corta o cabecalho e o rodape de licenca do Gutenberg.
    inicio = re.search(r"\*\*\*\s*START OF (THE|THIS) PROJECT GUTENBERG.*?\*\*\*", texto)
    fim = re.search(r"\*\*\*\s*END OF (THE|THIS) PROJECT GUTENBERG.*?\*\*\*", texto)
    miolo = texto[inicio.end() if inicio else 0: fim.start() if fim else len(texto)]

    titulo = livro.get("title") or consulta
    autores = ", ".join(a.get("name", "") for a in (livro.get("authors") or []))
    conteudo = f"# {titulo}\n\n{autores}\n\n{miolo.strip()}"

    destino = destino or diretorio_livros()
    destino.mkdir(parents=True, exist_ok=True)
    arquivo = destino / _nome_seguro(titulo, ".txt")
    arquivo.write_text(conteudo, encoding="utf-8")
    url = f"https://www.gutenberg.org/ebooks/{livro.get('id', '')}"
    return arquivo, titulo, url


# Teto para o corpo de um livro baixado. O endereco vem do JSON de terceiro e
# `resposta.text` sem limite carregava o que viesse na memoria.
MAX_BYTES_DOWNLOAD = 32 * 1024 * 1024

# Dominios de onde aceitamos baixar. A URL vem do catalogo publico, nao de
# nos: sem esta checagem, o catalogo poderia nos apontar para qualquer host.
DOMINIOS_CONFIAVEIS = (
    "gutenberg.org", "www.gutenberg.org", "gutenberg.pglaf.org",
    "aleph.gutenberg.org", "wikimedia.org", "wikibooks.org",
    "pt.wikibooks.org", "upload.wikimedia.org",
)


def _endereco_confiavel(endereco: str) -> bool:
    partes = urlsplit(endereco)
    if partes.scheme != "https":
        return False
    hospedeiro = partes.hostname or ""
    return any(
        hospedeiro == dominio or hospedeiro.endswith("." + dominio)
        for dominio in DOMINIOS_CONFIAVEIS
    )


async def _baixar_texto(cliente: httpx.AsyncClient, endereco: str) -> str:
    """Baixa um texto abortando se passar do teto."""
    partes: list[bytes] = []
    total = 0
    async with cliente.stream("GET", endereco) as resposta:
        resposta.raise_for_status()
        async for bloco in resposta.aiter_bytes(1 << 16):
            total += len(bloco)
            if total > MAX_BYTES_DOWNLOAD:
                raise ErroDownload(
                    f"o arquivo passa de {MAX_BYTES_DOWNLOAD // (1024 * 1024)} MB"
                )
            partes.append(bloco)
    return b"".join(partes).decode("utf-8", "ignore")


# --------------------------------------------------------------------------
# Orquestracao
# --------------------------------------------------------------------------

async def baixar_item(
    cliente: httpx.AsyncClient, item: ItemCatalogo
) -> ResultadoIngestao:
    """Baixa e indexa um item do catalogo."""
    try:
        if item.origem == "wikilivros":
            arquivo, titulo, url = await baixar_wikilivro(cliente, item.consulta)
            licenca = LICENCA_WIKILIVROS
        elif item.origem == "gutenberg":
            arquivo, titulo, url = await baixar_gutenberg(cliente, item.consulta)
            licenca = LICENCA_GUTENBERG
        else:
            return ResultadoIngestao(
                arquivo=item.chave, titulo=item.titulo, estado="erro",
                detalhe=f"origem desconhecida: {item.origem}",
            )
    except ErroDownload as exc:
        return ResultadoIngestao(arquivo=item.chave, titulo=item.titulo,
                                 estado="erro", detalhe=str(exc))
    except httpx.HTTPError as exc:
        return ResultadoIngestao(arquivo=item.chave, titulo=item.titulo,
                                 estado="erro",
                                 detalhe=f"falha de rede: {type(exc).__name__}")
    except (OSError, ValueError) as exc:
        # Disco cheio, permissao negada, JSON malformado do catalogo: tudo
        # isso subia ate o FastAPI e derrubava a rota inteira com 500.
        log.warning("falha ao baixar %s: %s", item.chave, exc)
        return ResultadoIngestao(arquivo=item.chave, titulo=item.titulo,
                                 estado="erro",
                                 detalhe=f"falha ao gravar ou ler o arquivo: {exc}")

    try:
        resultado = indexar(
            arquivo, area=item.area, origem=f"catalogo:{item.origem}",
            licenca=licenca, url=url,
        )
    except Exception as exc:  # noqa: BLE001 - a rota nao pode cair por um item
        # Indexacao falhou: o arquivo baixado ficaria orfao em biblioteca/.
        arquivo.unlink(missing_ok=True)
        log.warning("falha ao indexar %s: %s", arquivo.name, exc)
        return ResultadoIngestao(arquivo=arquivo.name, titulo=titulo,
                                 estado="erro", detalhe=f"falha ao indexar: {exc}")
    if resultado.estado == "erro":
        arquivo.unlink(missing_ok=True)
    if resultado.estado == "indexado":
        resultado.titulo = resultado.titulo or titulo
    return resultado


async def baixar_catalogo(
    area: str = "",
    chaves: list[str] | None = None,
    cliente: httpx.AsyncClient | None = None,
    ao_progredir=None,
) -> list[ResultadoIngestao]:
    """Baixa e indexa varios livros do catalogo, um de cada vez.

    Sequencial de proposito: sao servicos publicos e gratuitos, e disparar
    quinze downloads em paralelo contra eles seria abuso.
    """
    from .ai.pesquisa import criar_cliente

    if chaves:
        itens = [CATALOGO_POR_CHAVE[c] for c in chaves if c in CATALOGO_POR_CHAVE]
    else:
        itens = [i for i in CATALOGO if not area or i.area == area]

    proprio = cliente is None
    cliente = cliente or criar_cliente()
    resultados: list[ResultadoIngestao] = []
    try:
        for item in itens:
            if ao_progredir:
                await ao_progredir(item)
            resultados.append(await baixar_item(cliente, item))
    finally:
        if proprio:
            await cliente.aclose()
    return resultados
