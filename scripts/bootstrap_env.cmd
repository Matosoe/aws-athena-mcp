@echo off
setlocal

cd /d "%~dp0.."

set "PYTHON_CMD=py -3"
%PYTHON_CMD% -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
if errorlevel 1 (
    set "PYTHON_CMD=python"
    %PYTHON_CMD% -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
    if errorlevel 1 (
        echo Python 3.11+ nao encontrado no PATH.
        exit /b 1
    )
)

if not exist ".venv\Scripts\python.exe" (
    %PYTHON_CMD% -m venv .venv
    if errorlevel 1 exit /b 1
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
if errorlevel 1 exit /b 1

python -m pip install -e .[dev]
if errorlevel 1 exit /b 1

echo.
echo Ambiente pronto.
echo Ative com: .venv\Scripts\activate
echo Rode o servidor com: python main.py

endlocal