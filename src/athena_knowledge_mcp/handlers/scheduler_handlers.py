"""Handlers that create / remove Windows scheduled tasks for skill execution.

Each scheduled task runs the MCP task-runner CLI with a generated YAML definition
that calls `get_table_skill` (or `search_skill_catalog`) for the target skill.

A small .cmd wrapper file is written alongside the YAML so the scheduled task
can set the correct working directory without shell-escaping complexity.
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import yaml

from athena_knowledge_mcp.services.skill_catalog_service import SkillCatalogService

_TASK_FOLDER = "\\MCPTaskScheduler"
_VALID_FREQUENCIES = {"DAILY", "WEEKLY", "HOURLY", "MINUTE"}


def _sanitize_name(value: str) -> str:
    """Return a filesystem/task-safe version of a skill_id."""
    return re.sub(r"[^\w\-]", "_", value.strip())


def _project_root() -> Path:
    """Derive the project root from this package's location.

    Layout: src/athena_knowledge_mcp/handlers/scheduler_handlers.py
              ^3               ^2              ^1
    So .parent * 3 = src/, .parent * 4 = project_root.
    """
    return Path(__file__).resolve().parent.parent.parent.parent


def _scheduled_tasks_dir() -> Path:
    tasks_dir = _project_root() / "state" / "scheduled_tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    return tasks_dir


def _build_task_yaml(
    skill_id: str,
    title: str,
    database_name: str | None,
    table_name: str | None,
) -> dict:
    """Return the task definition dict to be serialised as YAML."""
    steps: list[dict] = [
        {"tool": "get_server_configuration_status", "arguments": {}},
    ]

    if database_name and table_name:
        steps.append(
            {
                "tool": "get_table_skill",
                "arguments": {
                    "database_name": database_name,
                    "table_name": table_name,
                },
            }
        )
    else:
        steps.append(
            {
                "tool": "search_skill_catalog",
                "arguments": {"query": skill_id, "limit": 1},
            }
        )

    return {
        "id": f"skill_{_sanitize_name(skill_id)}",
        "name": f"Scheduled skill: {title}",
        "tags": ["scheduled", "skill"],
        "stop_on_failure": False,
        "steps": steps,
    }


def _write_cmd_wrapper(cmd_path: Path, yaml_path: Path) -> None:
    """Write a .cmd wrapper that cd's to the project root before running the CLI."""
    project_dir = _project_root()
    python_exe = Path(sys.executable).resolve()
    # Set PYTHONPATH so scheduler is importable even without `pip install -e .`
    cmd_path.write_text(
        "@echo off\r\n"
        f'cd /D "{project_dir}"\r\n'
        f'set "PYTHONPATH={project_dir}\\src;%PYTHONPATH%"\r\n'
        f'"{python_exe}" -m scheduler.cli run --file "{yaml_path}"\r\n',
        encoding="utf-8",
    )


def _register_schtask(
    task_name: str,
    cmd_path: Path,
    frequency: str,
    time: str,
    interval: int,
    days_of_week: str | None,
) -> subprocess.CompletedProcess:
    full_task_name = f"{_TASK_FOLDER}\\{task_name}"
    args = [
        "schtasks",
        "/Create",
        "/TN",
        full_task_name,
        "/TR",
        str(cmd_path),
        "/SC",
        frequency,
        "/F",  # force overwrite
        "/RL",
        "LIMITED",
    ]

    if frequency in ("DAILY", "WEEKLY"):
        args += ["/ST", time]

    if frequency in ("MINUTE", "HOURLY"):
        args += ["/MO", str(interval)]

    if frequency == "WEEKLY" and days_of_week:
        args += ["/D", days_of_week]

    return subprocess.run(args, capture_output=True, text=True)


def _delete_schtask(task_name: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["schtasks", "/Delete", "/TN", f"{_TASK_FOLDER}\\{task_name}", "/F"],
        capture_output=True,
        text=True,
    )


def _query_schtask_folder() -> subprocess.CompletedProcess:
    return subprocess.run(
        ["schtasks", "/Query", "/TN", _TASK_FOLDER, "/FO", "LIST"],
        capture_output=True,
        text=True,
    )


@dataclass(slots=True)
class SchedulerHandlers:
    create_skill_catalog_service: Callable[[], SkillCatalogService]

    # ── public MCP tool handlers ──────────────────────────────────────

    def schedule_skill_execution(
        self,
        skill_id: str,
        frequency: str = "DAILY",
        time: str = "08:00",
        interval: int = 1,
        days_of_week: str | None = None,
    ) -> dict[str, object]:
        """Create a Windows scheduled task that executes a skill periodically."""
        frequency = frequency.upper().strip()
        if frequency not in _VALID_FREQUENCIES:
            return {
                "success": False,
                "error": (
                    f"frequency '{frequency}' inválida. "
                    f"Valores aceitos: {sorted(_VALID_FREQUENCIES)}"
                ),
            }

        # Look up the skill in the catalog (best-effort — proceed even if not found)
        catalog_service = self.create_skill_catalog_service()
        entry = catalog_service.get_entry(skill_id)

        safe_id = _sanitize_name(skill_id)
        task_name = f"Skill_{safe_id}"
        title = entry.title if entry else skill_id
        db_name = entry.database_name if entry else None
        tbl_name = entry.table_name if entry else None

        tasks_dir = _scheduled_tasks_dir()
        yaml_path = tasks_dir / f"skill_{safe_id}.yaml"
        cmd_path = tasks_dir / f"skill_{safe_id}.cmd"

        # Write YAML task definition
        task_def = _build_task_yaml(skill_id, title, db_name, tbl_name)
        yaml_path.write_text(
            yaml.dump(task_def, allow_unicode=True, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )

        # Write CMD wrapper
        _write_cmd_wrapper(cmd_path, yaml_path)

        # Register with Windows Task Scheduler
        result = _register_schtask(
            task_name=task_name,
            cmd_path=cmd_path,
            frequency=frequency,
            time=time,
            interval=interval,
            days_of_week=days_of_week,
        )

        if result.returncode != 0:
            return {
                "success": False,
                "error": result.stderr.strip() or result.stdout.strip(),
                "task_name": task_name,
                "yaml_path": str(yaml_path),
            }

        schedule_summary = frequency
        if frequency in ("DAILY", "WEEKLY"):
            schedule_summary = f"{frequency} às {time}"
        elif frequency in ("MINUTE", "HOURLY"):
            schedule_summary = f"cada {interval} {frequency.lower()}(s)"
        if frequency == "WEEKLY" and days_of_week:
            schedule_summary += f" nos dias {days_of_week}"

        return {
            "success": True,
            "task_name": f"{_TASK_FOLDER}\\{task_name}",
            "skill_id": skill_id,
            "skill_title": title,
            "schedule": schedule_summary,
            "yaml_path": str(yaml_path),
            "cmd_path": str(cmd_path),
            "steps": [s["tool"] for s in task_def["steps"]],
        }

    def unschedule_skill_execution(self, skill_id: str) -> dict[str, object]:
        """Remove a previously scheduled skill execution task."""
        safe_id = _sanitize_name(skill_id)
        task_name = f"Skill_{safe_id}"

        result = _delete_schtask(task_name)

        # Clean up generated files if they exist
        tasks_dir = _scheduled_tasks_dir()
        removed_files: list[str] = []
        for suffix in (".yaml", ".cmd"):
            path = tasks_dir / f"skill_{safe_id}{suffix}"
            if path.exists():
                path.unlink()
                removed_files.append(str(path))

        if result.returncode != 0:
            return {
                "success": False,
                "error": result.stderr.strip() or result.stdout.strip(),
                "task_name": task_name,
            }

        return {
            "success": True,
            "task_name": f"{_TASK_FOLDER}\\{task_name}",
            "skill_id": skill_id,
            "removed_files": removed_files,
        }

    def list_scheduled_skill_tasks(self) -> dict[str, object]:
        """List skill execution tasks currently registered in Windows Task Scheduler."""
        result = _query_schtask_folder()
        raw_output = result.stdout if result.returncode == 0 else ""
        error = result.stderr.strip() if result.returncode != 0 else None

        # Parse task names from LIST output
        task_names: list[str] = []
        for line in raw_output.splitlines():
            if line.startswith("TaskName:"):
                task_names.append(line.split(":", 1)[1].strip())

        # List generated YAML/CMD files in state dir
        tasks_dir = _scheduled_tasks_dir()
        scheduled_files = sorted(p.name for p in tasks_dir.glob("skill_*.yaml"))

        return {
            "task_count": len(task_names),
            "tasks": task_names,
            "scheduled_files": scheduled_files,
            "raw_output": raw_output if task_names else None,
            "error": error,
        }
