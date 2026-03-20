#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

only_venv=0
if [ "${1-}" = "--venv-only" ]; then
    only_venv=1
fi

is_supported_python() {
    "$1" -c 'import sys; raise SystemExit(0 if sys.version_info[:2] in ((3, 11), (3, 12)) else 1)' >/dev/null 2>&1
}

select_python() {
    local candidate
    for candidate in python3.12 python3.11 python3 python; do
        if command -v "$candidate" >/dev/null 2>&1 && is_supported_python "$candidate"; then
            printf '%s\n' "$candidate"
            return 0
        fi
    done

    return 1
}

venv_python_path() {
    if [ -f .venv/Scripts/python.exe ]; then
        printf '%s\n' ".venv/Scripts/python.exe"
    elif [ -f .venv/bin/python ]; then
        printf '%s\n' ".venv/bin/python"
    elif [[ "$(uname -s)" =~ ^(MINGW|MSYS|CYGWIN) ]]; then
        printf '%s\n' ".venv/Scripts/python.exe"
    else
        printf '%s\n' ".venv/bin/python"
    fi
}

venv_activate_path() {
    if [ -f .venv/Scripts/activate ]; then
        printf '%s\n' ".venv/Scripts/activate"
    else
        printf '%s\n' ".venv/bin/activate"
    fi
}

if ! PYTHON_CMD="$(select_python)"; then
    echo "Python 3.11 ou 3.12 nao encontrado no PATH."
    exit 1
fi

VENV_PYTHON="$(venv_python_path)"
if [ -f "$VENV_PYTHON" ] && ! is_supported_python "$VENV_PYTHON"; then
    echo "Removendo .venv atual porque nao usa Python 3.11 ou 3.12."
    rm -rf .venv
fi

VENV_PYTHON="$(venv_python_path)"
if [ ! -f "$VENV_PYTHON" ]; then
    echo "Criando .venv com $PYTHON_CMD."
    "$PYTHON_CMD" -m venv .venv
fi

VENV_PYTHON="$(venv_python_path)"
if ! is_supported_python "$VENV_PYTHON"; then
    echo "Erro: a .venv criada nao usa Python 3.11 ou 3.12."
    exit 1
fi

if [ "$only_venv" -eq 0 ]; then
    "$VENV_PYTHON" -m pip install --upgrade pip
    "$VENV_PYTHON" -m pip install -e '.[dev]'
fi

echo
echo "Ambiente pronto."
echo "Python selecionado: $PYTHON_CMD"
echo "Ative com: source $(venv_activate_path)"
echo "Rode o servidor com: $VENV_PYTHON main.py"