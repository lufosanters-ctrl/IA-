@echo off
REM Sobe o Nucleo no Windows. Basta dar um duplo clique neste arquivo.
REM Quem prefere o PowerShell pode usar iniciar.ps1, que faz o mesmo.
setlocal
cd /d "%~dp0"

REM UTF-8 na saida: sem isto o console em portugues quebra nos acentos.
set PYTHONUTF8=1
chcp 65001 >nul 2>&1

REM Acha o Python. O "py" (Python Launcher) vem junto com o instalador
REM oficial e e o caminho mais confiavel; "python" sozinho pode ser o atalho
REM da Microsoft Store, que responde ao comando e falha na hora de instalar.
set PYEXE=
py -3 --version >nul 2>&1 && set PYEXE=py -3
if not defined PYEXE (
  python --version >nul 2>&1 && set PYEXE=python
)
if not defined PYEXE (
  echo.
  echo   Python 3.11 ou mais novo nao foi encontrado.
  echo   Instale em https://www.python.org/downloads/windows/
  echo   e marque "Add python.exe to PATH" no instalador.
  echo.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo  ^> criando ambiente virtual...
  %PYEXE% -m venv .venv
  if errorlevel 1 goto :falhou
  ".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
  echo  ^> instalando dependencias, demora um pouco na primeira vez...
  ".venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt
  if errorlevel 1 goto :falhou
  echo  ^> dependencias instaladas
)

if not exist ".env" (
  copy ".env.example" ".env" >nul
  echo  ^> .env criado a partir do exemplo
)

".venv\Scripts\python.exe" -m app
pause
exit /b 0

:falhou
echo.
echo   A instalacao falhou. Apague a pasta .venv e tente de novo.
echo.
pause
exit /b 1
