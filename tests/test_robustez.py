"""Regressões de robustez: cada teste aqui reproduz um bug real já corrigido.

Não são testes de funcionalidade — são armadilhas. Cada um documenta uma
falha que chegou ao código, a entrada concreta que a disparava e o
comportamento que passou a valer. Se algum voltar a falhar, a regressão
aparece aqui antes de aparecer para o estudante.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from app import banco, livros, texto
from app.ai import estudo, verificacao
from app.catalogo import _endereco_confiavel
from app.sources.registro import escolher_fontes


# --------------------------------------------------------------------------
# Consumo de recursos
# --------------------------------------------------------------------------

def test_epub_bomba_de_descompressao_e_recusado(tmp_path: Path):
    """300 MB dentro de 300 KB travavam o processo por minutos."""
    caminho = tmp_path / "bomba.epub"
    dados = io.BytesIO()
    with zipfile.ZipFile(dados, "w", zipfile.ZIP_DEFLATED) as zip_saida:
        zip_saida.writestr("mimetype", "application/epub+zip")
        zip_saida.writestr(
            "META-INF/container.xml",
            '<container><rootfiles><rootfile full-path="c.opf"/></rootfiles></container>',
        )
        zip_saida.writestr(
            "c.opf",
            "<package><metadata><dc:title>Bomba</dc:title></metadata>"
            '<manifest><item id="a" href="cap1.xhtml"/></manifest>'
            '<spine><itemref idref="a"/></spine></package>',
        )
        zip_saida.writestr("cap1.xhtml", "<html><body>" + "A" * (80 * 1024 * 1024) + "</body></html>")
    caminho.write_bytes(dados.getvalue())

    assert caminho.stat().st_size < 1024 * 1024, "o arquivo comprimido é pequeno"
    with pytest.raises(livros.ErroExtracao):
        livros.extrair(caminho)


def test_trecho_nunca_passa_muito_do_tamanho_pedido():
    """Texto sem fronteira de frase produzia um bloco de 300 mil caracteres."""
    blocos = texto.dividir_em_trechos("palavra " * 40000, tamanho=900, sobreposicao=150)
    assert blocos
    assert max(len(b) for b in blocos) <= 900


def test_fontes_repetidas_nao_multiplicam_requisicoes():
    """`{"fontes": ["arxiv"] * 500}` abria 500 conexões para a mesma base."""
    escolhidas = escolher_fontes("teste", ["arxiv"] * 500)
    assert escolhidas == ["arxiv"]


def test_endereco_de_download_so_aceita_dominio_conhecido():
    """A URL vem do JSON do catálogo público, não de nós."""
    assert _endereco_confiavel("https://www.gutenberg.org/files/1/1-0.txt")
    assert not _endereco_confiavel("http://www.gutenberg.org/files/1/1-0.txt")
    assert not _endereco_confiavel("https://gutenberg.org.exemplo.com/x.txt")
    assert not _endereco_confiavel("https://exemplo.com/x.txt")


# --------------------------------------------------------------------------
# Corretude de dados
# --------------------------------------------------------------------------

def test_marcador_de_pagina_nao_apaga_palavras_reais():
    """“CIVIL”, “mil” e “DVD” são algarismos romanos válidos — e palavras."""
    for palavra in ("civil", "CIVIL", "mil", "DVD", "MIX", "div", "xvi"):
        assert not livros._e_marcador_de_pagina(palavra), palavra
    for marcador in ("12", "- 12 -", "pág. 12", "Page 12 of 340", "pág. xiv"):
        assert livros._e_marcador_de_pagina(marcador), marcador


def test_cabecalho_nao_apaga_conteudo_de_pagina_curta():
    """Em página de 2 linhas, cada linha era contada duas vezes."""
    paginas = [
        ("Teorema de Pitagoras\ncorpo %d" % i) if i < 3 else ("Outro titulo %d\ncorpo %d" % (i, i))
        for i in range(10)
    ]
    limpas = livros.remover_cabecalhos(paginas)
    assert all("Teorema" in limpas[i] for i in range(3))


def test_quiz_extrativo_encontra_palavra_acentuada():
    """O alvo vinha sem acento e nunca casava com a frase original."""
    frase = (
        "As plantas realizam trocas gasosas durante a respiração porque "
        "precisam liberar gás carbônico acumulado."
    )
    assert estudo._palavra_original(frase, "respiracao") == "respiração"
    assert estudo._palavra_original(frase, "carbonico") == "carbônico"
    assert estudo._palavra_original(frase, "ausente") == ""


def test_relatorio_de_verificacao_vazio_e_confiavel():
    """Resposta vazia não tem afirmação nenhuma para desconfiar."""
    relatorio = verificacao.verificar_fundamentacao("", [])
    assert relatorio.cobertura == 1.0
    assert relatorio.solidez == 1.0


# --------------------------------------------------------------------------
# Banco de dados
# --------------------------------------------------------------------------

def test_filtro_de_baralho_nunca_vaza_cartoes_de_outro():
    """`if baralho_id` fazia o id 0 virar “sem filtro”, silenciosamente.

    Como os ids começam em 1, o bug era latente. O teste fixa o contrato:
    filtrar por um baralho nunca devolve cartão de outro, e um id que não
    existe devolve lista vazia — nunca a lista inteira.
    """
    primeiro, _ = banco.criar_baralho("Filtro A")
    segundo, _ = banco.criar_baralho("Filtro B")
    banco.salvar_cartoes(primeiro, [{"frente": "pergunta A", "verso": "resposta A"}])
    banco.salvar_cartoes(segundo, [{"frente": "pergunta B", "verso": "resposta B"}])

    do_primeiro = banco.cartoes_devidos(primeiro)
    assert do_primeiro
    assert all(c["baralho_id"] == primeiro for c in do_primeiro)

    todos = banco.cartoes_devidos(None)
    assert len(todos) >= len(do_primeiro) + 1
    assert banco.cartoes_devidos(0) == []


def test_salvar_cartoes_em_baralho_inexistente_avisa():
    """A violação de chave estrangeira subia como 500 em vez de 404."""
    with pytest.raises(banco.BaralhoInexistente):
        banco.salvar_cartoes(999_999, [{"frente": "a", "verso": "b"}])


def test_criar_baralho_diz_se_reaproveitou(tmp_path):
    """Nome repetido descartava a descrição enviada sem avisar ninguém."""
    identificador, criado = banco.criar_baralho("Robustez", "primeira")
    repetido, recriado = banco.criar_baralho("Robustez", "segunda")
    assert identificador == repetido
    assert criado is True and recriado is False
