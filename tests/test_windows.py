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
@pytest.mark.parametrize("extensao", ["", ".pdf", ".txt", ".tar.gz", ".old.pdf"])
def test_nome_reservado_do_ms_dos_e_desviado(reservado, extensao):
    """"CON.pdf" falha no Windows com qualquer extensão, simples ou composta.

    O Windows resolve o nome de dispositivo pelo segmento antes do PRIMEIRO
    ponto, então "CON.tar.gz" também é o console.
    """
    seguro = nome_de_arquivo_seguro(f"{reservado}{extensao}")
    primeiro = seguro.split(".", 1)[0]
    assert primeiro.lower() not in {r.lower() for r in RESERVADOS}, seguro


@pytest.mark.parametrize("bruto", [
    "d" * 119 + " " + "e" * 10,
    "x" * 200 + ".pdf",
    "nome muito longo " * 20 + ".md",
])
def test_nome_truncado_nao_termina_em_espaco_nem_ponto(bruto):
    """Cortar em 120 caracteres pode deixar um espaço no fim.

    O Windows grava o arquivo com o espaço cortado, e o caminho guardado no
    banco passa a apontar para um nome que o disco não tem.
    """
    seguro = nome_de_arquivo_seguro(bruto)
    base = seguro.rsplit(".", 1)[0] if "." in seguro else seguro
    assert not base.endswith((" ", ".")), repr(seguro)


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
    texto = (RAIZ / "iniciar.bat").read_text(encoding="ascii")
    abre = len(re.findall(r"(?<!\^)\(", texto))
    fecha = len(re.findall(r"(?<!\^)\)", texto))
    assert abre == fecha, f"{abre} abre, {fecha} fecha"


def test_ps1_tem_bom():
    """O PowerShell 5.1, o que vem no Windows 11, lê .ps1 sem BOM como ANSI."""
    assert (RAIZ / "iniciar.ps1").read_bytes().startswith(b"\xef\xbb\xbf")


def test_gitattributes_fixa_as_quebras_de_linha():
    texto = (RAIZ / ".gitattributes").read_text(encoding="utf-8")
    assert "*.bat" in texto and "eol=crlf" in texto
    assert "*.sh" in texto and "eol=lf" in texto


def test_saida_sobrevive_a_console_que_recusa_utf8():
    """Nem todo console aceita a troca para UTF-8.

    Aí o que salva é o segundo passo: trocar o tratamento de erro para
    `replace` na codificação que o console já usa. Sem isso, todo texto que
    NÃO passa por `escrever` — a ajuda do argparse, um traceback, uma
    mensagem de biblioteca — ainda derrubaria o programa.
    """
    class ConsoleTeimoso(io.TextIOWrapper):
        def reconfigure(self, **kwargs):            # type: ignore[override]
            if "encoding" in kwargs:
                raise OSError("este console não aceita UTF-8")
            return super().reconfigure(**kwargs)

    fluxo = ConsoleTeimoso(io.BytesIO(), encoding="cp850", errors="strict")
    console._tentar_utf8(fluxo)
    assert fluxo.errors == "replace"
    fluxo.write("travessão — visto ✓\n")            # não pode levantar


def test_ajuda_da_cli_nao_estoura_em_console_antigo():
    """O argparse imprime direto, sem passar pelo nosso escritor."""
    import subprocess

    for modulo in ("app.afericao", "app.ingerir"):
        resultado = subprocess.run(
            [sys.executable, "-m", modulo, "--help"],
            capture_output=True, text=True, cwd=str(RAIZ),
            env={**__import__("os").environ, "PYTHONIOENCODING": "cp850"},
        )
        assert resultado.returncode == 0, f"{modulo}: {resultado.stderr[-300:]}"


# --------------------------------------------------------------------------
# Regras que valem para o código inteiro
# --------------------------------------------------------------------------

def _chamadas_sem_encoding(arquivo: Path) -> list[int]:
    """Linhas com leitura ou escrita de texto sem codificação declarada."""
    texto = arquivo.read_text(encoding="utf-8")
    achados: list[int] = []
    for achado in re.finditer(r"\.(?:write_text|read_text)\s*\(", texto):
        # Percorre até fechar o parêntese: a codificação costuma vir na linha
        # seguinte, em chamada de várias linhas.
        nivel, fim = 0, len(texto)
        for posicao in range(achado.start(), min(achado.start() + 600, len(texto))):
            if texto[posicao] == "(":
                nivel += 1
            elif texto[posicao] == ")":
                nivel -= 1
                if nivel == 0:
                    fim = posicao
                    break
        if "encoding" not in texto[achado.start():fim]:
            achados.append(texto[:achado.start()].count("\n") + 1)
    return achados


def test_nenhuma_leitura_de_texto_confia_na_codificacao_do_sistema():
    """`open()` sem `encoding` usa a do sistema — cp1252 no Windows.

    Todo texto deste projeto é em português. Ler um arquivo UTF-8 como cp1252
    não levanta erro: troca os acentos por lixo, em silêncio, e o estudante
    vê "InstalaÃ§Ã£o" no lugar de "Instalação". É a pior classe de bug de
    portabilidade justamente por não fazer barulho.
    """
    problemas: dict[str, list[int]] = {}
    for arquivo in sorted(RAIZ.glob("app/**/*.py")) + sorted(RAIZ.glob("tests/**/*.py")):
        linhas = _chamadas_sem_encoding(arquivo)
        if linhas:
            problemas[str(arquivo.relative_to(RAIZ))] = linhas
    assert not problemas, f"declare encoding='utf-8' em: {problemas}"


def test_nenhum_caminho_absoluto_de_linux_no_codigo():
    """`/tmp`, `/home` e `/usr` não existem no Windows."""
    padrao = re.compile(r'["\'](?:/tmp|/home/|/usr/|/etc/|/var/)')
    problemas = []
    for arquivo in sorted(RAIZ.glob("app/**/*.py")):
        for numero, linha in enumerate(
            arquivo.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if padrao.search(linha) and "#" not in linha.split('"')[0]:
                problemas.append(f"{arquivo.relative_to(RAIZ)}:{numero}")
    assert not problemas, f"caminho absoluto de Linux em: {problemas}"


def test_nenhuma_chamada_exclusiva_de_posix():
    """Módulos e funções que simplesmente não existem no Windows."""
    proibidos = re.compile(
        r"\b(?:os\.fork|os\.setsid|os\.getuid|os\.geteuid|os\.chown|"
        r"import\s+fcntl|import\s+pwd|import\s+grp|import\s+termios|"
        r"signal\.SIGKILL)\b"
    )
    problemas = []
    for arquivo in sorted(RAIZ.glob("app/**/*.py")):
        for numero, linha in enumerate(
            arquivo.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if proibidos.search(linha):
                problemas.append(f"{arquivo.relative_to(RAIZ)}:{numero} — {linha.strip()}")
    assert not problemas, f"chamada exclusiva de POSIX em: {problemas}"


def test_ps1_nao_cai_na_armadilha_do_intervalo_invertido():
    """No PowerShell, `$a[1..($a.Length-1)]` conta ao contrário numa lista de
    um elemento: `1..0` devolve os índices 1 e 0, e os argumentos saem
    embaralhados. Montar a lista à mão evita o caso.
    """
    texto = (RAIZ / "iniciar.ps1").read_text(encoding="utf-8-sig")
    assert "1..(" not in texto and "[1.." not in texto


def test_ps1_usa_o_caminho_do_venv_do_windows():
    """No Windows o executável fica em Scripts\\python.exe, não em bin/python."""
    codigo = "\n".join(
        linha for linha in
        (RAIZ / "iniciar.ps1").read_text(encoding="utf-8-sig").splitlines()
        if not linha.lstrip().startswith("#")
    )
    assert r".venv\Scripts\python.exe" in codigo
    assert "bin/python" not in codigo, "caminho de venv do Linux no script do Windows"


def test_iniciadores_do_windows_conferem_o_resultado_da_instalacao():
    """Instalação que falha em silêncio deixa um .venv quebrado."""
    for nome, marca in (("iniciar.ps1", "LASTEXITCODE"), ("iniciar.bat", "errorlevel")):
        texto = (RAIZ / nome).read_text(encoding="utf-8-sig")
        assert marca in texto, f"{nome} não confere o resultado da instalação"


def test_git_guarda_lf_e_entrega_crlf_no_windows():
    """`.gitattributes` decide a quebra de linha do clone, não o sistema.

    Sem isso, o Git do Windows converte tudo para CRLF na cópia de trabalho e
    o `iniciar.sh` deixa de rodar no WSL; ou converte tudo para LF e o
    `iniciar.bat` falha nos blocos de várias linhas.
    """
    regras = (RAIZ / ".gitattributes").read_text(encoding="utf-8")
    for extensao in ("*.bat", "*.cmd", "*.ps1"):
        assert f"{extensao}" in regras and "eol=crlf" in regras
    assert "*.sh" in regras and "eol=lf" in regras


# --------------------------------------------------------------------------
# Configuração e serviço de arquivos estáticos
# --------------------------------------------------------------------------

def test_caminho_do_env_com_escape_e_recusado_com_explicacao():
    """`DIRETORIO_BIBLIOTECA="C:\\Users\\nome"` chega aqui partido ao meio.

    O leitor de .env interpreta escapes dentro de aspas duplas, e o `\\n` de
    "\\nome" vira quebra de linha. Sem esta checagem, o `mkdir` seguinte falha
    com um erro do sistema que não menciona o .env, durante o import — o
    servidor não sobe e não diz por quê.
    """
    from app.config import ErroDeConfiguracao, _conferir_caminho

    corrompido = Path("C:\\Users\nome\\livros")
    with pytest.raises(ErroDeConfiguracao) as erro:
        _conferir_caminho("a biblioteca", "DIRETORIO_BIBLIOTECA", corrompido)
    mensagem = str(erro.value)
    assert ".env" in mensagem
    assert "aspas duplas" in mensagem
    assert "DIRETORIO_BIBLIOTECA=" in mensagem


def test_caminho_normal_do_windows_passa():
    from app.config import _conferir_caminho

    for bom in ("C:\\Users\\aluno\\livros", "C:/Users/aluno/livros", "./biblioteca"):
        _conferir_caminho("a biblioteca", "DIRETORIO_BIBLIOTECA", Path(bom))


def test_env_de_exemplo_avisa_sobre_as_aspas():
    texto = (RAIZ / ".env.example").read_text(encoding="utf-8")
    assert "aspas duplas" in texto


def test_tipos_mime_nao_dependem_do_registro_do_windows():
    """No Windows, `mimetypes` lê o registro e sobrescreve o mapa embutido.

    É comum um instalador de terceiro ter deixado ".css" como "text/plain", e
    em modo padrão o navegador recusa folha de estilo que não venha como
    "text/css": a interface abriria inteira sem estilo, sem erro no servidor.
    """
    import mimetypes

    mimetypes.add_type("text/plain", ".css", True)     # simula o registro
    mimetypes.add_type("text/plain", ".js", True)
    import importlib

    import app.main
    importlib.reload(app.main)

    assert mimetypes.guess_type("estilo.css")[0] == "text/css"
    assert mimetypes.guess_type("app.js")[0] in {"text/javascript",
                                                 "application/javascript"}
    assert mimetypes.guess_type("icone.svg")[0] == "image/svg+xml"


def test_pragma_do_journal_e_conferido_e_nao_apenas_enviado():
    """`PRAGMA journal_mode` não levanta erro quando falha: devolve o modo."""
    import sqlite3
    import tempfile

    from app.console import conferir_journal

    caminho = Path(tempfile.mkdtemp()) / "teste.db"
    conexao = sqlite3.connect(caminho)
    try:
        assert conferir_journal(conexao, caminho) == "wal"
    finally:
        conexao.close()


def test_upload_usa_temporario_unico_por_requisicao():
    """Nome fixo faria dois envios simultâneos colidirem.

    No Windows, arquivo aberto por outra requisição não pode ser renomeado
    nem apagado: a colisão vira "Acesso negado" e deixa um .parcial órfão.
    """
    fonte = (RAIZ / "app" / "main.py").read_text(encoding="utf-8")
    assert '.parcial"' in fonte
    assert 'f".{nome}.parcial"' not in fonte, "o temporário depende do nome enviado"
    assert "uuid4().hex" in fonte


def test_caminho_completo_cabe_no_limite_do_windows():
    """O Windows limita o caminho inteiro a 260 caracteres sem opt-in.

    O pior caso é uma pasta funda do OneDrive corporativo mais o nome máximo,
    o prefixo do arquivo temporário e o sufixo de desambiguação.
    """
    from app.livros import _MAX_NOME

    titulo = (
        "Introdução ao Cálculo Diferencial e Integral com Aplicações em "
        "Física e Engenharia - Volume 2 - Edição Revisada e Ampliada.pdf"
    )
    nome = nome_de_arquivo_seguro(titulo)
    pasta = "C:\\Users\\Fulano de Tal\\OneDrive - Escola\\Documentos\\Projetos\\IA-\\biblioteca"
    pior_caso = len(pasta) + 1 + len(".") + len(nome) + len(".parcial") + len(" (999)")
    assert pior_caso < 260, f"{pior_caso} caracteres"
    assert _MAX_NOME <= 90


def test_servidor_prepara_a_saida_mesmo_sem_o_ponto_de_entrada():
    """`uvicorn app.main:app` não passa por `python -m app`."""
    fonte = (RAIZ / "app" / "main.py").read_text(encoding="utf-8")
    assert "preparar_saida()" in fonte
