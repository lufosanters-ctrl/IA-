"""Testes da extracao de texto de livros."""

import zipfile

import pytest

from app.livros import (
    ErroExtracao,
    detectar_capitulo,
    extrair,
    impressao_digital,
    juntar_linhas,
    remover_cabecalhos,
)

TEXTO = """# Manual de Estudos

## Capítulo 1 — Introdução

A aprendizagem significativa ocorre quando o novo conteúdo se ancora em
conhecimento prévio do estudante. Esse ancoramento é o que diferencia
compreender de memorizar mecanicamente uma informação qualquer.

A repetição espaçada aproveita o efeito de espaçamento: revisar em intervalos
crescentes produz retenção muito maior do que repetir tudo de uma vez.
"""


def test_juntar_linhas_desfaz_hifenizacao():
    assert juntar_linhas("conheci-\nmento") == "conhecimento"


def test_juntar_linhas_preserva_fim_de_frase():
    resultado = juntar_linhas("Primeira frase.\nSegunda frase continua aqui")
    assert "\n" in resultado


def test_remover_cabecalhos_descarta_linha_repetida():
    paginas = [f"Biologia Moderna\nconteúdo próprio da página {i}\n{i + 10}"
               for i in range(6)]
    limpas = remover_cabecalhos(paginas)
    assert all("Biologia Moderna" not in p for p in limpas)
    assert all(f"conteúdo próprio da página {i}" in limpas[i] for i in range(6))


def test_remover_cabecalhos_preserva_itens_numerados():
    """Regressao: 'Exercicio 1', 'Exercicio 2'... nao sao cabecalho repetido."""
    paginas = [f"Exercício {i}\nEnunciado do exercício número {i} da lista."
               for i in range(1, 7)]
    limpas = remover_cabecalhos(paginas)
    assert all(f"Exercício {i}" in limpas[i - 1] for i in range(1, 7))


def test_remover_cabecalhos_tira_numero_de_pagina():
    paginas = [f"Assunto {i} tratado em detalhe nesta parte do livro\n- {i + 4} -"
               for i in range(6)]
    limpas = remover_cabecalhos(paginas)
    assert all(f"- {i + 4} -" not in limpas[i] for i in range(6))


def test_remover_cabecalhos_preserva_livro_curto():
    paginas = ["Capa", "Sumário"]
    assert remover_cabecalhos(paginas) == paginas


def test_remover_cabecalhos_nao_apaga_texto_unico():
    paginas = [f"Assunto diferente {i}\ncorpo {i}" for i in range(6)]
    limpas = remover_cabecalhos(paginas)
    assert all(limpa.strip() for limpa in limpas)


def test_detectar_capitulo_em_varios_formatos():
    assert "Fotossíntese" in detectar_capitulo("Capítulo 3 — Fotossíntese\ntexto", "")
    assert detectar_capitulo("## Ligações químicas\ntexto", "") == "Ligações químicas"
    assert detectar_capitulo("texto qualquer", "Anterior") == "Anterior"


def test_extrair_markdown(tmp_path):
    arquivo = tmp_path / "manual.md"
    arquivo.write_text(TEXTO, encoding="utf-8")
    livro = extrair(arquivo)
    assert livro.titulo == "Manual de Estudos"
    assert livro.formato == "markdown"
    assert livro.paginas
    assert livro.palavras > 40


def test_extrair_texto_puro(tmp_path):
    arquivo = tmp_path / "notas.txt"
    arquivo.write_text("Conteúdo de estudo. " * 40, encoding="utf-8")
    livro = extrair(arquivo)
    assert livro.formato == "texto"
    assert livro.paginas


def test_extrair_html_usa_o_titulo(tmp_path):
    arquivo = tmp_path / "pagina.html"
    arquivo.write_text(
        "<html><head><title>Apostila de Física</title></head>"
        "<body><script>ignorar()</script><p>" + ("Movimento uniforme. " * 40) +
        "</p></body></html>",
        encoding="utf-8",
    )
    livro = extrair(arquivo)
    assert livro.titulo == "Apostila de Física"
    assert "ignorar" not in livro.paginas[0].texto


def test_extrair_epub(tmp_path):
    caminho = tmp_path / "livro.epub"
    corpo = "<html><body><h1>Capítulo 1</h1><p>" + ("Conteúdo didático. " * 40) + "</p></body></html>"
    with zipfile.ZipFile(caminho, "w") as pacote:
        pacote.writestr("content.opf", """<?xml version="1.0"?>
            <package><metadata>
              <dc:title xmlns:dc="http://purl.org/dc/elements/1.1/">Livro Teste</dc:title>
              <dc:creator xmlns:dc="http://purl.org/dc/elements/1.1/">Autora Exemplo</dc:creator>
              <dc:language xmlns:dc="http://purl.org/dc/elements/1.1/">pt</dc:language>
            </metadata>
            <manifest><item id="c1" href="cap1.xhtml" media-type="application/xhtml+xml"/></manifest>
            <spine><itemref idref="c1"/></spine></package>""")
        pacote.writestr("cap1.xhtml", corpo)
    livro = extrair(caminho)
    assert livro.titulo == "Livro Teste"
    assert livro.autores == ["Autora Exemplo"]
    assert livro.idioma == "pt"
    assert livro.paginas[0].capitulo == "Capítulo 1"


def test_formato_nao_suportado(tmp_path):
    arquivo = tmp_path / "planilha.xlsx"
    arquivo.write_bytes(b"conteudo binario")
    with pytest.raises(ErroExtracao, match="não suportado|nao suportado"):
        extrair(arquivo)


def test_arquivo_inexistente(tmp_path):
    with pytest.raises(ErroExtracao, match="encontrado"):
        extrair(tmp_path / "fantasma.pdf")


def test_arquivo_curto_demais(tmp_path):
    arquivo = tmp_path / "vazio.txt"
    arquivo.write_text("oi", encoding="utf-8")
    with pytest.raises(ErroExtracao):
        extrair(arquivo)


def test_epub_corrompido(tmp_path):
    arquivo = tmp_path / "quebrado.epub"
    arquivo.write_bytes(b"isto nao e um zip")
    with pytest.raises(ErroExtracao, match="corrompido"):
        extrair(arquivo)


def test_impressao_digital_muda_com_o_conteudo(tmp_path):
    a, b = tmp_path / "a.txt", tmp_path / "b.txt"
    a.write_text("conteúdo um", encoding="utf-8")
    b.write_text("conteúdo dois", encoding="utf-8")
    assert impressao_digital(a) != impressao_digital(b)
    assert impressao_digital(a) == impressao_digital(a)


def test_titulo_de_capitulo_nao_gruda_na_frase_seguinte(tmp_path):
    """Regressao: sem ponto, o titulo virava parte da primeira frase."""
    from app.texto import dividir_frases

    arquivo = tmp_path / "apostila.md"
    arquivo.write_text(
        "# Manual\n\n## Capítulo 6 — Fotossíntese\n\n"
        "A fotossíntese converte energia luminosa em energia química nas plantas "
        "verdes, dentro de organelas chamadas cloroplastos que contêm clorofila. "
        "A fase clara ocorre nas membranas dos tilacoides e produz ATP e NADPH, "
        "que alimentam a fase bioquímica no estroma do cloroplasto. O ciclo de "
        "Calvin fixa o dióxido de carbono em compostos de três carbonos.\n",
        encoding="utf-8",
    )
    texto = extrair(arquivo).paginas[-1].texto
    assert "#" not in texto
    frases = dividir_frases(texto)
    assert any(f.strip().startswith("A fotossíntese") for f in frases)
