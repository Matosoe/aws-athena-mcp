$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

& cmd /d /c "scripts\build_windows_exe.cmd"

if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

exit 0