# Sobe o Núcleo no Windows, criando o ambiente virtual na primeira execução.
#
# Uso, no PowerShell, dentro da pasta do projeto:
#     .\iniciar.ps1
#
# Se o Windows recusar o script, a política de execução está bloqueando
# arquivos .ps1. Libere só para esta janela, sem mexer na configuração da
# máquina:
#     Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

$ErrorActionPreference = "Stop"

if ($PSScriptRoot) { Set-Location -LiteralPath $PSScriptRoot }

# O caminho do Python dentro do ambiente virtual. No Windows fica em
# Scripts\python.exe, e não em bin/python como no Linux e no macOS.
$PythonDoVenv = Join-Path (Get-Location) ".venv\Scripts\python.exe"

# Procura um Python 3.11+ de verdade.
#
# Cada candidato é uma LISTA — o executável e os argumentos fixos separados.
# Montar isso a partir de uma string com Split daria a armadilha clássica do
# PowerShell: para uma lista de um elemento, o intervalo 1..0 conta ao
# contrário e devolve os índices 1 e 0, embaralhando os argumentos.
$Candidatos = @(
    @("py", @("-3")),
    @("python", @()),
    @("python3", @())
)

function Obter-Python {
    foreach ($candidato in $Candidatos) {
        $executavel = $candidato[0]
        $fixos = $candidato[1]
        if (-not (Get-Command $executavel -ErrorAction SilentlyContinue)) { continue }
        try {
            # O "python.exe" que o Windows 11 traz por padrão é um atalho para
            # a Loja: responde ao comando e falha na hora de instalar. Pedir a
            # versão separa um do outro.
            $versao = & $executavel @fixos "--version" 2>&1 | Out-String
            if ($versao -match "Python 3\.(\d+)" -and [int]$Matches[1] -ge 11) {
                return ,@($executavel, $fixos)
            }
        } catch {
            continue
        }
    }
    return $null
}

$python = Obter-Python
if ($null -eq $python) {
    Write-Host ""
    Write-Host "  Python 3.11 ou mais novo nao foi encontrado." -ForegroundColor Yellow
    Write-Host "  Instale em https://www.python.org/downloads/windows/"
    Write-Host "  e marque 'Add python.exe to PATH' na primeira tela."
    Write-Host ""
    exit 1
}

if (-not (Test-Path -LiteralPath $PythonDoVenv)) {
    Write-Host "-> criando ambiente virtual..."
    & $python[0] @($python[1]) -m venv .venv
    if ($LASTEXITCODE -ne 0) { Write-Host "  falhou ao criar .venv"; exit 1 }

    & $PythonDoVenv -m pip install --quiet --upgrade pip
    Write-Host "-> instalando dependencias, demora um pouco na primeira vez..."
    & $PythonDoVenv -m pip install --quiet -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "  A instalacao falhou. Apague a pasta .venv e tente de novo."
        Write-Host ""
        exit 1
    }
    Write-Host "-> dependencias instaladas"
}

if (-not (Test-Path -LiteralPath ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "-> .env criado a partir do exemplo"
}

# UTF-8 na saída: o console em português costuma vir em cp850, onde os
# acentos e os símbolos do relatório não existem.
$env:PYTHONUTF8 = "1"
& $PythonDoVenv -m app
