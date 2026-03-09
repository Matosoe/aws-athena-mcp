param(
    [string]$PythonExecutable = ".venv/Scripts/python.exe"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $PythonExecutable)) {
    $PythonExecutable = "python"
}

& $PythonExecutable -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

& $PythonExecutable -m pip install .[build]
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

& $PythonExecutable -m PyInstaller --clean aws-athena-mcp.spec
exit $LASTEXITCODE