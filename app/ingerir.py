"""Ferramenta de linha de comando da biblioteca.

    python -m app.ingerir                      indexa tudo que estiver em biblioteca/
    python -m app.ingerir livro.pdf outro.epub indexa arquivos especificos
    python -m app.ingerir --catalogo           baixa e indexa os livros didáticos abertos
    python -m app.ingerir --catalogo --area matematica
    python -m app.ingerir --listar             mostra o que já está indexado
    python -m app.ingerir --remover 3          tira um livro da biblioteca
    python -m app.ingerir --buscar "ciclo de Calvin"
"""

from __future__ import annotations

import argparse
import asyncio
import shutil
import sys
from pathlib import Path

from . import biblioteca
from .catalogo import CATALOGO, baixar_catalogo, listar_catalogo
from .livros import FORMATOS

from .console import cores_disponiveis, escrever, preparar_saida

_COR = cores_disponiveis()
VERDE, AMARELO, VERMELHO, CINZA, FIM = (
    ("\033[32m", "\033[33m", "\033[31m", "\033[90m", "\033[0m")
    if _COR else ("", "", "", "", "")
)

SIMBOLO = {"indexado": f"{VERDE}✓{FIM}", "duplicado": f"{CINZA}·{FIM}",
           "erro": f"{VERMELHO}✗{FIM}"}


def _mostrar(resultado: biblioteca.ResultadoIngestao) -> None:
    marca = SIMBOLO.get(resultado.estado, "?")
    nome = resultado.titulo or resultado.arquivo
    detalhe = f" {CINZA}{resultado.detalhe}{FIM}" if resultado.detalhe else ""
    quanto = f" {CINZA}({resultado.trechos} trechos){FIM}" if resultado.trechos else ""
    escrever(f"  {marca} {nome}{quanto}{detalhe}")


def _resumo(resultados: list[biblioteca.ResultadoIngestao]) -> int:
    indexados = sum(1 for r in resultados if r.estado == "indexado")
    duplicados = sum(1 for r in resultados if r.estado == "duplicado")
    erros = sum(1 for r in resultados if r.estado == "erro")
    trechos = sum(r.trechos for r in resultados)
    escrever(
        f"\n{indexados} livro(s) indexado(s), {trechos} trechos"
        + (f", {duplicados} já existente(s)" if duplicados else "")
        + (f", {AMARELO}{erros} com erro{FIM}" if erros else "")
    )
    estatisticas = biblioteca.estatisticas()
    palavras = f"{estatisticas['palavras']:,}".replace(",", ".")
    escrever(
        f"{CINZA}Biblioteca: {estatisticas['livros']} livros, "
        f"{estatisticas['trechos']} trechos, {palavras} palavras{FIM}"
    )
    return 1 if erros and not indexados else 0


def _copiar_para_biblioteca(caminho: Path) -> Path:
    """Guarda o arquivo em biblioteca/ para que o acervo fique reunido."""
    destino_pasta = biblioteca.diretorio_livros()
    if caminho.parent.resolve() == destino_pasta.resolve():
        return caminho
    destino = destino_pasta / caminho.name
    if not destino.exists():
        shutil.copy2(caminho, destino)
    return destino


def main(argumentos: list[str] | None = None) -> int:
    # Sobe o console para UTF-8 antes de imprimir qualquer acento. No Windows
    # ele costuma vir em cp850, onde "ç" existe mas "—" e "✓" não.
    preparar_saida()
    analisador = argparse.ArgumentParser(
        prog="python -m app.ingerir",
        description="Adiciona livros à biblioteca do Núcleo.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    analisador.add_argument("arquivos", nargs="*", type=Path,
                            help="livros a indexar (PDF, EPUB, TXT, MD, HTML)")
    analisador.add_argument("--area", default="",
                            help="marca os livros com uma área do conhecimento")
    analisador.add_argument("--catalogo", action="store_true",
                            help="baixa os livros didáticos abertos do catálogo")
    analisador.add_argument("--livro", action="append", default=[], metavar="CHAVE",
                            help="baixa só este item do catálogo (pode repetir)")
    analisador.add_argument("--listar", action="store_true",
                            help="mostra os livros já indexados")
    analisador.add_argument("--catalogo-disponivel", action="store_true",
                            help="mostra o que o catálogo oferece")
    analisador.add_argument("--remover", type=int, metavar="ID",
                            help="remove um livro da biblioteca")
    analisador.add_argument("--buscar", metavar="TEXTO",
                            help="testa a busca na biblioteca")
    opcoes = analisador.parse_args(argumentos)

    biblioteca.iniciar()

    if opcoes.catalogo_disponivel:
        escrever(f"\nCatálogo de livros didáticos abertos ({len(CATALOGO)} títulos)\n")
        area_atual = ""
        for item in sorted(listar_catalogo(opcoes.area), key=lambda i: i["area"]):
            if item["area"] != area_atual:
                area_atual = item["area"]
                escrever(f"  {AMARELO}{area_atual}{FIM}")
            escrever(f"    {item['chave']:24} {item['titulo']}")
            if item["descricao"]:
                escrever(f"    {' ' * 24} {CINZA}{item['descricao']}{FIM}")
        escrever(f"\nBaixe tudo com: python -m app.ingerir --catalogo")
        escrever(f"Ou um só com:   python -m app.ingerir --livro calculo\n")
        return 0

    if opcoes.listar:
        livros = biblioteca.listar_livros()
        if not livros:
            escrever("\nBiblioteca vazia. Coloque livros em biblioteca/ e rode "
                  "'python -m app.ingerir'.\n")
            return 0
        escrever(f"\n{len(livros)} livro(s) na biblioteca:\n")
        for livro in livros:
            area = f" {CINZA}[{livro['area']}]{FIM}" if livro["area"] else ""
            escrever(f"  {livro['id']:>3}  {livro['titulo']}{area}")
            escrever(f"       {CINZA}{livro['trechos']} trechos · {livro['paginas']} páginas"
                  f" · {livro['formato']} · {livro['origem']}{FIM}")
        escrever()
        return 0

    if opcoes.remover is not None:
        if biblioteca.remover_livro(opcoes.remover):
            escrever(f"{VERDE}✓{FIM} livro {opcoes.remover} removido da biblioteca")
            return 0
        escrever(f"{VERMELHO}✗{FIM} não existe livro com id {opcoes.remover}")
        return 1

    if opcoes.buscar:
        achados = biblioteca.buscar(opcoes.buscar, limite=5)
        if not achados:
            escrever(f"\nNada encontrado para “{opcoes.buscar}”.\n")
            return 0
        escrever(f"\n{len(achados)} trecho(s) para “{opcoes.buscar}”:\n")
        for achado in achados:
            local = f"p. {achado['pagina']}" if achado["pagina"] else ""
            escrever(f"  {AMARELO}{achado['titulo']}{FIM} {CINZA}{achado['capitulo']} "
                  f"{local}{FIM}")
            escrever(f"    {achado['texto'][:220].strip()}…\n")
        return 0

    if opcoes.catalogo or opcoes.livro:
        chaves = opcoes.livro or None
        alvo = chaves or [i["chave"] for i in listar_catalogo(opcoes.area)]
        escrever(f"\nBaixando {len(alvo)} livro(s) do catálogo aberto…")
        escrever(f"{CINZA}As fontes são públicas e gratuitas; os downloads são "
              f"sequenciais de propósito.{FIM}\n")

        async def progresso(item) -> None:
            escrever(f"  {CINZA}↓ {item.titulo} ({item.origem}){FIM}")

        resultados = asyncio.run(
            baixar_catalogo(area=opcoes.area, chaves=chaves, ao_progredir=progresso)
        )
        escrever()
        for resultado in resultados:
            _mostrar(resultado)
        return _resumo(resultados)

    if opcoes.arquivos:
        resultados = []
        escrever()
        for caminho in opcoes.arquivos:
            if not caminho.exists():
                resultados.append(biblioteca.ResultadoIngestao(
                    arquivo=str(caminho), estado="erro", detalhe="arquivo não encontrado"))
                _mostrar(resultados[-1])
                continue
            if caminho.is_dir():
                for resultado in biblioteca.indexar_pasta(caminho, area=opcoes.area):
                    resultados.append(resultado)
                    _mostrar(resultado)
                continue
            guardado = _copiar_para_biblioteca(caminho)
            resultado = biblioteca.indexar(guardado, area=opcoes.area)
            resultados.append(resultado)
            _mostrar(resultado)
        return _resumo(resultados)

    pasta = biblioteca.diretorio_livros()
    escrever(f"\nProcurando livros em {pasta}/ …")
    resultados = biblioteca.indexar_pasta(pasta, area=opcoes.area)
    if not resultados:
        escrever(f"\n{AMARELO}Nenhum livro encontrado.{FIM}")
        escrever(f"Coloque arquivos {', '.join(sorted(FORMATOS))} em {pasta}/ "
              f"e rode de novo,")
        escrever(f"ou baixe livros didáticos abertos com: "
              f"{VERDE}python -m app.ingerir --catalogo{FIM}\n")
        return 0
    escrever()
    for resultado in resultados:
        _mostrar(resultado)
    return _resumo(resultados)


if __name__ == "__main__":
    sys.exit(main())
