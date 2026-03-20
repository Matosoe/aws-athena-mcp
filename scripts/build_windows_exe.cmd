@echo off
setlocal EnableExtensions

cd /d "%~dp0.."

call "scripts\bootstrap_env.cmd" --venv-only
if errorlevel 1 exit /b 1

".venv\Scripts\python.exe" "scripts\build_windows_exe.py"
exit /b %errorlevel%
