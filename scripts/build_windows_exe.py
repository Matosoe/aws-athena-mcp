from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tomllib


def run_command(args: list[str]) -> None:
    completed = subprocess.run(args, check=False)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    # preferencia: argumentos fornecem caminho para interpretador
    # caso contrario, tente o launcher `py -3.11` e depois `python`.
    if len(sys.argv) > 1 and sys.argv[1]:
        python_exe = Path(sys.argv[1])
    else:
        # nao assumimos mais .venv; instale direto no sistema
        # tente py -3.11 se o launcher estiver disponível
        if shutil.which("py"):
            python_cmd = "py"
            python_base_args = ["-3.11"]
        else:
            python_cmd = "python"
            python_base_args = []
        python_exe = None

    if python_exe and python_exe.exists():
        python_cmd = str(python_exe)
        python_base_args = []

    # python_cmd e python_base_args definem como chamar o python
    

    pyproject_path = root / "pyproject.toml"
    if not pyproject_path.exists():
        print(f"Erro: arquivo nao encontrado: {pyproject_path}")
        return 1

    project_data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    project_version = str(project_data["project"]["version"])
    safe_version = re.sub(r"[^0-9A-Za-z\.-]", "-", project_version)
    build_timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    versioned_exe_name = (
        f"aws-athena-mcp-v{safe_version}-{build_timestamp}.exe"
    )

    print(f"Build version: {project_version}")
    print(f"Build timestamp: {build_timestamp}")

    # helper para invocar o comando python com args base opcionais
    def run_py(args: list[str]) -> None:
        run_command([python_cmd, *python_base_args, *args])

    run_py(["-m", "pip", "install", "--upgrade", "pip"])
    run_py(["-m", "pip", "install", ".[build]"])
    run_py(["-m", "PyInstaller", "--clean", "aws-athena-mcp.spec"])

    dist_dir = root / "dist"
    default_exe = dist_dir / "aws-athena-mcp.exe"
    if not default_exe.exists():
        print(
            "Erro: build concluido, mas artefato esperado nao foi encontrado: "
            f"{default_exe}"
        )
        return 1

    versioned_exe = dist_dir / versioned_exe_name
    latest_exe = dist_dir / "aws-athena-mcp-latest.exe"

    if versioned_exe.exists():
        versioned_exe.unlink()
    if latest_exe.exists():
        latest_exe.unlink()

    default_exe.rename(versioned_exe)
    shutil.copy2(versioned_exe, latest_exe)

    latest_build_file = dist_dir / "LATEST_BUILD.txt"
    latest_build_file.write_text(
        "\n".join(
            [
                f"project_version={project_version}",
                f"build_timestamp={build_timestamp}",
                f"versioned_exe={versioned_exe_name}",
                "latest_exe=aws-athena-mcp-latest.exe",
            ]
        )
        + "\n",
        encoding="ascii",
    )

    print(f"Artefato versionado: {versioned_exe}")
    print(f"Alias estavel: {latest_exe}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
