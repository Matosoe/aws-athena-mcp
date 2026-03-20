from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
import subprocess
import sys
import tomllib


SUPPORTED_PYTHON_VERSIONS = {(3, 11), (3, 12)}


def run_command(args: list[str]) -> None:
    completed = subprocess.run(args, check=False)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def is_supported_python(args: list[str]) -> bool:
    version_check = "\n".join(
        [
            "import sys",
            "raise SystemExit(",
            "    0 if sys.version_info[:2] in ((3, 11), (3, 12)) else 1",
            ")",
        ]
    )
    completed = subprocess.run(
        [
            *args,
            "-c",
            version_check,
        ],
        check=False,
    )
    return completed.returncode == 0


def remove_if_exists(path: Path) -> bool:
    if not path.exists():
        return True
    try:
        path.unlink()
    except PermissionError:
        print(f"Erro: arquivo em uso, nao foi possivel remover: {path}")
        return False
    return True


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    python_cmd = str(Path(sys.executable))
    python_base_args: list[str] = []

    # Preferencia: argumento explicito. Sem argumento, reutilize o
    # interpretador atual, o que permite que a task do VS Code use a .venv.
    if len(sys.argv) > 1 and sys.argv[1]:
        python_exe = Path(sys.argv[1])
    else:
        python_exe = Path(sys.executable)

    if python_exe and python_exe.exists():
        python_cmd = str(python_exe)
        python_base_args = []

    # python_cmd e python_base_args definem como chamar o python
    if not is_supported_python([python_cmd, *python_base_args]):
        print(
            "Erro: o build exige Python 3.11 ou 3.12. "
            "Recrie a .venv com scripts\\bootstrap_env.cmd "
            "ou bash scripts/bootstrap_env.sh."
        )
        return 1

    pyproject_path = root / "pyproject.toml"
    if not pyproject_path.exists():
        print(f"Erro: arquivo nao encontrado: {pyproject_path}")
        return 1

    project_data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    project_version = str(project_data["project"]["version"])
    print(f"Build version: {project_version}")

    # helper para invocar o comando python com args base opcionais
    def run_py(args: list[str]) -> None:
        run_command([python_cmd, *python_base_args, *args])

    run_py(["-m", "pip", "install", "--upgrade", "pip"])
    run_py(["-m", "pip", "install", ".[build]"])
    run_py(["-m", "PyInstaller", "--clean", "aws-athena-mcp.spec"])

    dist_dir = root / "dist"
    default_exe = dist_dir / "aws-athena-mcp.exe"
    latest_exe = dist_dir / "aws-athena-mcp-latest.exe"
    if not default_exe.exists():
        print("Erro: build concluido, mas artefato esperado nao foi encontrado: " f"{default_exe}")
        return 1

    if not remove_if_exists(latest_exe):
        return 1

    for stale_versioned_exe in dist_dir.glob("aws-athena-mcp-v*.exe"):
        if not remove_if_exists(stale_versioned_exe):
            return 1

    try:
        default_exe.rename(latest_exe)
    except PermissionError:
        print(
            "Erro: nao foi possivel finalizar o artefato latest porque ele esta em uso: "
            f"{latest_exe}"
        )
        return 1

    latest_build_file = dist_dir / "LATEST_BUILD.txt"
    latest_build_file.write_text(
        "\n".join(
            [
                f"project_version={project_version}",
                "latest_exe=aws-athena-mcp-latest.exe",
            ]
        )
        + "\n",
        encoding="ascii",
    )

    print(f"Artefato gerado: {latest_exe}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
