"""Register / unregister tasks in Windows Task Scheduler.

Creates scheduled tasks that invoke the MCP task runner CLI
at configured times. Uses schtasks.exe — no admin required for
per-user tasks.
"""

from __future__ import annotations

import logging
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

_TASK_FOLDER = "\\MCPTaskScheduler"


@dataclass
class ScheduleSpec:
    """Describes when a Windows scheduled task should run."""

    frequency: str = "DAILY"  # DAILY | WEEKLY | HOURLY | MINUTE
    time: str = "08:00"  # HH:MM (for DAILY/WEEKLY)
    interval: int = 1  # repeat interval (for MINUTE/HOURLY)
    days_of_week: str | None = None  # MON,TUE,... (for WEEKLY)


def _python_exe() -> str:
    return sys.executable


def _build_schtasks_args(
    task_name: str,
    schedule: ScheduleSpec,
    cli_args: str,
    project_dir: Path,
) -> list[str]:
    python = _python_exe()
    command = f'"{python}" -m scheduler.cli run {cli_args}'

    args = [
        "schtasks",
        "/Create",
        "/TN",
        f"{_TASK_FOLDER}\\{task_name}",
        "/TR",
        command,
        "/SC",
        schedule.frequency,
        "/ST",
        schedule.time,
        "/F",  # force overwrite
        "/RL",
        "LIMITED",  # run with least privilege
    ]

    if schedule.frequency in ("MINUTE", "HOURLY"):
        args += ["/MO", str(schedule.interval)]

    if schedule.frequency == "WEEKLY" and schedule.days_of_week:
        args += ["/D", schedule.days_of_week]

    return args


def create_scheduled_task(
    task_name: str,
    schedule: ScheduleSpec,
    cli_args: str = "",
    project_dir: Path | None = None,
) -> bool:
    project_dir = project_dir or Path(__file__).parent.parent
    args = _build_schtasks_args(task_name, schedule, cli_args, project_dir)

    logger.info("Creating scheduled task: %s", " ".join(args))
    result = subprocess.run(
        args,
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        logger.info("Task '%s' registered successfully.", task_name)
        return True
    else:
        logger.error(
            "Failed to register task '%s': %s",
            task_name,
            result.stderr.strip(),
        )
        return False


def delete_scheduled_task(task_name: str) -> bool:
    args = [
        "schtasks",
        "/Delete",
        "/TN",
        f"{_TASK_FOLDER}\\{task_name}",
        "/F",
    ]
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode == 0:
        logger.info("Task '%s' deleted.", task_name)
        return True
    logger.error("Failed to delete task '%s': %s", task_name, result.stderr.strip())
    return False


def list_scheduled_tasks() -> str:
    result = subprocess.run(
        ["schtasks", "/Query", "/TN", _TASK_FOLDER, "/FO", "LIST"],
        capture_output=True,
        text=True,
    )
    return result.stdout if result.returncode == 0 else result.stderr


# ── Convenience presets ──────────────────────────────────────────────


def install_daily_preset(
    task_file_pattern: str = "",
    tag: str = "daily",
    time: str = "08:00",
) -> bool:
    """Register a daily task that runs all YAML files with the 'daily' tag."""
    cli_args = f"--tag {tag}" if tag else ""
    if task_file_pattern:
        cli_args = f"--file {task_file_pattern}"
    return create_scheduled_task(
        task_name=f"Daily_{tag or 'all'}",
        schedule=ScheduleSpec(frequency="DAILY", time=time),
        cli_args=cli_args,
    )


def install_weekly_preset(
    tag: str = "weekly",
    time: str = "07:00",
    days: str = "MON",
) -> bool:
    return create_scheduled_task(
        task_name=f"Weekly_{tag}",
        schedule=ScheduleSpec(
            frequency="WEEKLY",
            time=time,
            days_of_week=days,
        ),
        cli_args=f"--tag {tag}",
    )
