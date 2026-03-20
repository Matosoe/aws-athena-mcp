@echo off
setlocal EnableExtensions

cd /d "%~dp0.."

call :select_python
if errorlevel 1 exit /b 1

echo Usando %PYTHON_CMD% %PYTHON_ARGS% para gerar o EXE.
if defined PYTHON_ARGS (
	"%PYTHON_CMD%" %PYTHON_ARGS% "scripts\build_windows_exe.py"
) else (
	"%PYTHON_CMD%" "scripts\build_windows_exe.py"
)
exit /b %errorlevel%

:select_python
set "PYTHON_CMD="
set "PYTHON_ARGS="

call :try_python "py" "-3.12"
if defined PYTHON_CMD exit /b 0

call :try_python "py" "-3.11"
if defined PYTHON_CMD exit /b 0

call :try_python "python3.12" ""
if defined PYTHON_CMD exit /b 0

call :try_python "python3.11" ""
if defined PYTHON_CMD exit /b 0

call :try_python "python" ""
if defined PYTHON_CMD exit /b 0

echo Python 3.11 ou 3.12 nao encontrado no PATH nem via launcher py.
exit /b 1

:try_python
"%~1" %~2 -c "import sys; raise SystemExit(0 if sys.version_info[:2] in ((3, 11), (3, 12)) else 1)" >nul 2>&1
if errorlevel 1 exit /b 0

set "PYTHON_CMD=%~1"
set "PYTHON_ARGS=%~2"
exit /b 0
