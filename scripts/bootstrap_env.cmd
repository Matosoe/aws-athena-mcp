@echo off
setlocal EnableExtensions

cd /d "%~dp0.."

set "ONLY_VENV=0"
if /I "%~1"=="--venv-only" set "ONLY_VENV=1"

call :select_python
if errorlevel 1 exit /b 1

set "VENV_PYTHON=.venv\Scripts\python.exe"
if exist "%VENV_PYTHON%" (
    call :is_supported_python "%VENV_PYTHON%"
    if errorlevel 1 (
        echo Removendo .venv atual porque nao usa Python 3.11 ou 3.12.
        rmdir /s /q ".venv"
        if exist ".venv" (
            echo Erro: nao foi possivel remover a .venv atual.
            exit /b 1
        )
    )
)

if not exist "%VENV_PYTHON%" (
    echo Criando .venv com %PYTHON_CMD%.
    "%PYTHON_CMD%" -m venv .venv
    if errorlevel 1 exit /b 1
)

call :is_supported_python "%VENV_PYTHON%"
if errorlevel 1 (
    echo Erro: a .venv criada nao usa Python 3.11 ou 3.12.
    exit /b 1
)

if "%ONLY_VENV%"=="1" goto :ready

"%VENV_PYTHON%" -m pip install --upgrade pip
if errorlevel 1 exit /b 1

"%VENV_PYTHON%" -m pip install -e .[dev]
if errorlevel 1 exit /b 1

:ready
echo.
echo Ambiente pronto.
echo Python selecionado: %PYTHON_CMD%
echo Ative com: .venv\Scripts\activate.bat
echo Rode o servidor com: .venv\Scripts\python.exe main.py

endlocal
exit /b 0

:select_python
for %%P in (python3.12 python3.11 python) do (
    call :is_supported_python "%%~P"
    if not errorlevel 1 (
        set "PYTHON_CMD=%%~P"
        exit /b 0
    )
)

echo Python 3.11 ou 3.12 nao encontrado no PATH.
exit /b 1

:is_supported_python
"%~1" -c "import sys; raise SystemExit(0 if sys.version_info[:2] in ((3, 11), (3, 12)) else 1)" >nul 2>&1
exit /b %errorlevel%