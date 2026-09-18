# Sobe o Núcleo no Windows, criando o ambiente virtual na primeira execução.
#
# Uso, no PowerShell, dentro da pasta do projeto:
#     .\iniciar.ps1
#
# Se o Windows recusar a execução do script, a política de execução está
# bloqueando arquivos .ps1. Libere só para esta sessão, sem mexer na
# configuração da máquina:
#     Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

# O Windows 11 traz um "python.exe" falso que só abre a Loja. Ele responde ao
# comando e falha na hora de instalar, então o teste é pela versão de verdade.
function Obter-Python {
    foreach ($candidato in @("py -3", "python", "python3")) {
        $partes = $candidato.Split(" ")
        $executavel = $partes[0]
        $argumentos = @($partes[1..($partes.Length - 1)]) + @("--version")
        try {
            $versao = & $executavel @argumentos 2>&1
            if ($LASTEXITCODE -eq 0 -and "$versao" -match "Python 3\.(\d+)") {
                if ([int]$Matches[1] -ge 11) { return $candidato }
            }
        } catch { }
    }
    return $null
}

$python = Obter-Python
if (-not $python) {
    Write-Host ""
    Write-Host "  Python 3.11 ou mais novo nao foi encontrado." -ForegroundColor Yellow
    Write-Host "  Instale em https://www.python.org/downloads/windows/"
    Write-Host "  e marque 'Add python.exe to PATH' no instalador."
    Write-Host ""
    exit 1
}

if (-not (Test-Path ".venv")) {
    Write-Host "-> criando ambiente virtual..."
    $partes = $python.Split(" ")
    & $partes[0] @($partes[1..($partes.Length - 1)]) -m venv .venv
    & ".\.venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
    Write-Host "-> instalando dependencias (demora um pouco na primeira vez)..."
    & ".\.venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt
    Write-Host "-> dependencias instaladas"
}

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "-> .env criado a partir do exemplo"
}

# Garante UTF-8 na saída: o console em português costuma vir em cp850, onde
# acentos e símbolos do relatório não existem.
$env:PYTHONUTF8 = "1"
& ".\.venv\Scripts\python.exe" -m app
