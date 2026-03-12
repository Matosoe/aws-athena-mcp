param(
    [string]$PythonExecutable = ""
)

$ErrorActionPreference = "Stop"

function Test-CommandLine {
    param(
        [string]$CommandLine
    )

    cmd.exe /d /c "$CommandLine >nul 2>&1"
    return $LASTEXITCODE -eq 0
}

$BuildScript = Join-Path $PSScriptRoot "build_windows_exe.py"

if (-not (Test-Path $BuildScript)) {
    throw "Arquivo de build nao encontrado: $BuildScript"
}

if ($PythonExecutable) {
    if (-not (Test-Path $PythonExecutable)) {
        throw "Interpretador Python informado nao foi encontrado: $PythonExecutable"
    }

    & $PythonExecutable $BuildScript $PythonExecutable
}
elseif (Test-CommandLine -CommandLine "py -3.11 --version") {
    & py -3.11 $BuildScript
}
elseif (Test-CommandLine -CommandLine "py --version") {
    & py $BuildScript
}
elseif (Test-CommandLine -CommandLine "python --version") {
    & python $BuildScript
}
else {
    throw "Nenhum interpretador Python compativel foi encontrado no PATH."
}

exit $LASTEXITCODE