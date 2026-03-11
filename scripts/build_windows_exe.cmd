@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "PROJECT_ROOT=%~dp0.."
pushd "%PROJECT_ROOT%" >nul

set "PYTHON_EXE=%~1"
if "%PYTHON_EXE%"=="" set "PYTHON_EXE=.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=python"

if not exist "pyproject.toml" (
  echo Erro: arquivo pyproject.toml nao encontrado em "%CD%".
  popd >nul
  exit /b 1
)

set "PROJECT_VERSION="
for /f "tokens=2 delims==" %%A in ('findstr /R /C:"^version[ ]*=[ ]*\".*\"" pyproject.toml') do (
  set "PROJECT_VERSION=%%A"
  goto :version_found
)

:version_found
set "PROJECT_VERSION=!PROJECT_VERSION: =!"
set "PROJECT_VERSION=!PROJECT_VERSION:\"=!"

if "!PROJECT_VERSION!"=="" (
  echo Erro: nao foi possivel localizar project.version em pyproject.toml.
  popd >nul
  exit /b 1
)

for /f %%T in ('"%PYTHON_EXE%" -c "from datetime import datetime; print(datetime.now().strftime('%%Y%%m%%d-%%H%%M%%S'))"') do set "BUILD_TIMESTAMP=%%T"
if "!BUILD_TIMESTAMP!"=="" (
  echo Erro: nao foi possivel gerar timestamp de build.
  popd >nul
  exit /b 1
)

for /f %%V in ('"%PYTHON_EXE%" -c "import re; print(re.sub(r'[^0-9A-Za-z\.-]', '-', r'''!PROJECT_VERSION!'''))"') do set "SAFE_VERSION=%%V"
if "!SAFE_VERSION!"=="" set "SAFE_VERSION=!PROJECT_VERSION!"

set "VERSIONED_EXE_NAME=aws-athena-mcp-v!SAFE_VERSION!-!BUILD_TIMESTAMP!.exe"

echo Build version: !PROJECT_VERSION!
echo Build timestamp: !BUILD_TIMESTAMP!

"%PYTHON_EXE%" -m pip install --upgrade pip
if errorlevel 1 (
  popd >nul
  exit /b 1
)

"%PYTHON_EXE%" -m pip install .[build]
if errorlevel 1 (
  popd >nul
  exit /b 1
)

"%PYTHON_EXE%" -m PyInstaller --clean aws-athena-mcp.spec
if errorlevel 1 (
  popd >nul
  exit /b 1
)

set "DIST_DIR=dist"
set "DEFAULT_EXE=%DIST_DIR%\aws-athena-mcp.exe"
set "VERSIONED_EXE=%DIST_DIR%\!VERSIONED_EXE_NAME!"
set "LATEST_EXE=%DIST_DIR%\aws-athena-mcp-latest.exe"

if not exist "%DEFAULT_EXE%" (
  echo Erro: build concluido, mas artefato esperado nao foi encontrado: "%DEFAULT_EXE%".
  popd >nul
  exit /b 1
)

move /Y "%DEFAULT_EXE%" "%VERSIONED_EXE%" >nul
if errorlevel 1 (
  popd >nul
  exit /b 1
)

copy /Y "%VERSIONED_EXE%" "%LATEST_EXE%" >nul
if errorlevel 1 (
  popd >nul
  exit /b 1
)

(
  echo project_version=!PROJECT_VERSION!
  echo build_timestamp=!BUILD_TIMESTAMP!
  echo versioned_exe=!VERSIONED_EXE_NAME!
  echo latest_exe=aws-athena-mcp-latest.exe
) > "%DIST_DIR%\LATEST_BUILD.txt"

echo Artefato versionado: %CD%\%VERSIONED_EXE%
echo Alias estavel: %CD%\%LATEST_EXE%

popd >nul
exit /b 0
