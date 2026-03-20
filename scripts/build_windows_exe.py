from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys
import tomllib


def run_command(args: list[str]) -> None:
    completed = subprocess.run(args, check=False)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def command_works(args: list[str]) -> bool:
    completed = subprocess.run(
        args,
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return completed.returncode == 0


def remove_if_exists(path: Path) -> bool:
    if not path.exists():
        return True

    try:
        path.unlink()
    except PermissionError:
        print(
            "Erro: nao foi possivel substituir o artefato porque ele esta em uso: "
            f"{path}"
        )
        return False

    return True


def resolve_python_command(explicit_python: str | None) -> tuple[str, list[str]]:
    if explicit_python:
        python_exe = Path(explicit_python)
        if python_exe.exists():
            return str(python_exe), []

    candidates = [
        ("py", ["-3.11"]),
        ("py", []),
        ("python", []),
    ]

    for command, base_args in candidates:
        if not shutil.which(command):
            continue
        if command_works([command, *base_args, "--version"]):
            return command, base_args

    raise SystemExit(
        "Erro: nenhum interpretador Python compativel foi encontrado no PATH."
    )


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    python_arg = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] else None
    python_cmd, python_base_args = resolve_python_command(python_arg)

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
        print(
            "Erro: build concluido, mas artefato esperado nao foi encontrado: "
            f"{default_exe}"
        )
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
