"""Regras do Windows que o Linux não impõe.

O projeto foi escrito e testado no Linux, e o Linux aceita coisas que o
Windows recusa: nome de arquivo com dois-pontos, arquivo chamado CON, ponto
no fim do nome, acento no console. Cada teste aqui trava uma dessas regras
para que a plataforma continue rodando nos dois sistemas.

Os testes valem em qualquer sistema: verificam a REGRA, não o sistema em que
estão rodando. É assim que a incompatibilidade aparece na integração contínua
do Linux antes de aparecer na máquina do estudante.
"""

from __future__ import annotations

import io
import re
import sys
from pathlib import Path

import pytest

from app import console
from app.catalogo import _nome_seguro
from app.livros import nome_de_arquivo_seguro

# Os nove caracteres que o Windows recusa em nome de arquivo.
PROIBIDOS = '<>:"/\\|?*'

RESERVADOS = ["CON", "PRN", "AUX", "NUL", "COM1", "COM9", "LPT1", "LPT9"]


@pytest.mark.parametrize("bruto", [
    "livro:2024.pdf", "cap<1>.md", "arquivo|x.txt", "nome*.pdf",
    'aspas".pdf', "pergunta?.txt", "a>b.md", "a<b.md",
])
def test_caractere_proibido_nunca_sobra_no_nome(bruto):
    seguro = nome_de_arquivo_seguro(bruto)
    assert not any(c in seguro for c in PROIBIDOS), seguro


@pytest.mark.parametrize("reservado", RESERVADOS)
@pytest.mark.parametrize("extensao", ["", ".pdf", ".txt"])
def test_nome_reservado_do_ms_dos_e_desviado(reservado, extensao):
    """"CON.pdf" falha no Windows com qualquer extensão."""
    seguro = nome_de_arquivo_seguro(f"{reservado}{extensao}")
    base = seguro.rsplit(".", 1)[0] if "." in seguro else seguro
    assert base.lower() not in {r.lower() for r in RESERVADOS}


@pytest.mark.parametrize("bruto, esperado_fim", [
    ("fim .txt", "fim.txt"),
    ("ponto..pdf", "ponto.pdf"),
    ("espaço no fim .md", "espaço no fim.md"),
])
def test_ponto_e_espaco_no_fim_saem_do_nome(bruto, esperado_fim):
    """O Windows corta ponto e espaço finais em silêncio.

    O arquivo é gravado com um nome e existe com outro, então o caminho
    guardado no banco deixa de existir.
    """
    assert nome_de_arquivo_seguro(bruto) == esperado_fim


@pytest.mark.parametrize("bruto", [
    "C:\\Users\\alguem\\livro.pdf",
    "..\\..\\windows\\system32\\cmd.exe",
    "/home/alguem/livro.pdf",
    "../../etc/passwd",
])
def test_caminho_completo_vira_so_o_nome(bruto):
    """Os dois separadores contam, venha o arquivo de onde vier."""
    seguro = nome_de_arquivo_seguro(bruto)
    assert "/" not in seguro and "\\" not in seguro
    assert ".." not in seguro


def test_acento_sobrevive_ao_saneamento():
    """O Windows aceita Unicode em nome de arquivo; tirar acento é perda seca."""
    assert nome_de_arquivo_seguro("Álgebra Linear.pdf") == "Álgebra Linear.pdf"
    assert nome_de_arquivo_seguro("Introdução à Física.epub") == "Introdução à Física.epub"


def test_nome_vazio_ou_so_pontuacao_ganha_padrao():
    for bruto in ["", "   ", ".", "..", "/", "\\"]:
        assert nome_de_arquivo_seguro(bruto) == "livro"


def test_titulo_do_catalogo_tambem_passa_pelas_regras():
    """O título vem de catálogo público: pode ser qualquer coisa."""
    assert _nome_seguro("Aux", ".txt").rsplit(".", 1)[0].lower() not in {"aux"}
    for titulo in ["CON", "Cálculo: Volume 1", "A|B", "fim ."]:
        nome = _nome_seguro(titulo, ".txt")
        assert not any(c in nome for c in PROIBIDOS), nome


# --------------------------------------------------------------------------
# Console
# --------------------------------------------------------------------------

def _com_codificacao(codificacao: str):
    """Troca stdout por um fluxo com a codificação pedida."""
    return io.TextIOWrapper(io.BytesIO(), encoding=codificacao, errors="strict")


@pytest.mark.parametrize("codificacao", ["cp850", "cp1252", "ascii"])
def test_saida_da_cli_nunca_estoura_por_codificacao(codificacao, monkeypatch):
    """O console do Windows em português vem em cp850, não em UTF-8."""
    fluxo = _com_codificacao(codificacao)
    monkeypatch.setattr(sys, "stdout", fluxo)
    texto = "Aferição do Núcleo — 175/175 ✓ “tudo certo” … ✗ → ≥ π"
    adaptado = console.adaptar(texto)
    adaptado.encode(codificacao, errors="strict")   # não pode levantar


def test_texto_intacto_quando_o_console_aceita(monkeypatch):
    monkeypatch.setattr(sys, "stdout", _com_codificacao("utf-8"))
    texto = "Aferição — 175/175 ✓"
    assert console.adaptar(texto) == texto


def test_escrever_nunca_derruba_o_programa(monkeypatch):
    fluxo = _com_codificacao("ascii")
    monkeypatch.setattr(sys, "stdout", fluxo)
    console.escrever("Núcleo — ✓ pronto")          # não pode levantar


def test_cor_desligada_quando_a_saida_nao_e_terminal(monkeypatch):
    """Redirecionar para arquivo não pode encher o texto de `←[32m`."""
    monkeypatch.delenv("FORCE_COLOR", raising=False)
    assert console.cores_disponiveis(_com_codificacao("utf-8")) is False


def test_no_color_e_respeitado(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    assert console.cores_disponiveis() is False


# --------------------------------------------------------------------------
# Scripts de inicialização
# --------------------------------------------------------------------------

RAIZ = Path(__file__).resolve().parent.parent


def test_existe_um_iniciador_para_cada_sistema():
    for nome in ("iniciar.sh", "iniciar.bat", "iniciar.ps1"):
        assert (RAIZ / nome).exists(), f"falta {nome}"


def test_bat_usa_crlf_e_so_ascii():
    """Com LF, os blocos `if (...)` de várias linhas falham no cmd.exe."""
    bruto = (RAIZ / "iniciar.bat").read_bytes()
    assert b"\r\n" in bruto
    assert bruto.count(b"\n") == bruto.count(b"\r\n"), "há linha sem CR"
    bruto.decode("ascii")   # o .bat é lido na página de código do console


def test_bat_tem_blocos_balanceados():
    texto = (RAIZ / "iniciar.bat").read_text()
    abre = len(re.findall(r"(?<!\^)\(", texto))
    fecha = len(re.findall(r"(?<!\^)\)", texto))
    assert abre == fecha, f"{abre} abre, {fecha} fecha"


def test_ps1_tem_bom():
    """O PowerShell 5.1, o que vem no Windows 11, lê .ps1 sem BOM como ANSI."""
    assert (RAIZ / "iniciar.ps1").read_bytes().startswith(b"\xef\xbb\xbf")


def test_gitattributes_fixa_as_quebras_de_linha():
    texto = (RAIZ / ".gitattributes").read_text()
    assert "*.bat" in texto and "eol=crlf" in texto
    assert "*.sh" in texto and "eol=lf" in texto
