#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_CMD="python"
else
    echo "Python 3.11+ nao encontrado no PATH."
    exit 1
fi

"$PYTHON_CMD" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)'

if [ ! -x .venv/bin/python ]; then
    "$PYTHON_CMD" -m venv .venv
fi

. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'

echo
echo "Ambiente pronto."
echo "Ative com: source .venv/bin/activate"
echo "Rode o servidor com: python main.py"