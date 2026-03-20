@echo off
setlocal EnableExtensions

set "SCRIPT_DIR=%~dp0"
set "PYTHON_EXE=%~1"

if "%PYTHON_EXE%"=="" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%build_windows_exe.ps1"
) else (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%build_windows_exe.ps1" -PythonExecutable "%PYTHON_EXE%"
)

exit /b %ERRORLEVEL%
