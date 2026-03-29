"""Task runner — loads task definitions from YAML and executes them via MCP.

Each task file defines a sequence of MCP tool calls with arguments.
Results are logged to a local audit log (JSON Lines).
"""

from __future__ import annotations

import asyncio
import datetime
import json
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml  # PyYAML

from scheduler.mcp_client import open_mcp_client

logger = logging.getLogger(__name__)

DEFAULT_TASKS_DIR = Path(__file__).parent / "tasks"
# Logs go outside src/ to avoid polluting the source tree
DEFAULT_LOG_DIR = Path(__file__).resolve().parent.parent.parent / "state" / "scheduler_logs"


@dataclass
class StepResult:
    tool: str
    arguments: dict[str, Any]
    success: bool
    result: Any = None
    error: str | None = None
    duration_seconds: float = 0.0


@dataclass
class TaskResult:
    task_id: str
    task_name: str
    started_at: str
    finished_at: str
    steps: list[StepResult] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return all(s.success for s in self.steps)


def _load_task_file(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _resolve_variable_refs(
    value: Any,
    context: dict[str, Any],
) -> Any:
    """Recursively resolve $ref:step_N.field.subfield references in arguments."""
    if isinstance(value, str) and value.startswith("$ref:"):
        ref_path = value[5:].split(".")
        obj: Any = context
        for part in ref_path:
            if isinstance(obj, dict):
                obj = obj.get(part)
            elif isinstance(obj, list) and part.isdigit():
                obj = obj[int(part)]
            else:
                return value  # unresolvable, keep original
        return obj
    if isinstance(value, dict):
        return {k: _resolve_variable_refs(v, context) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_variable_refs(item, context) for item in value]
    return value


async def run_task(
    task_def: dict[str, Any],
    mcp_command: list[str],
    mcp_env: dict[str, str] | None = None,
) -> TaskResult:
    """Execute all steps in a task definition sequentially."""
    task_id = task_def.get("id", "unknown")
    task_name = task_def.get("name", task_id)
    steps_def = task_def.get("steps", [])
    stop_on_failure = task_def.get("stop_on_failure", True)

    started = datetime.datetime.now(datetime.timezone.utc)
    step_results: list[StepResult] = []
    step_context: dict[str, Any] = {}

    async with open_mcp_client(mcp_command, env=mcp_env) as client:
        for idx, step in enumerate(steps_def):
            tool_name: str = step["tool"]
            raw_args: dict[str, Any] = step.get("arguments", {})

            # Resolve inter-step references
            resolved_args = _resolve_variable_refs(raw_args, step_context)

            logger.info(
                "[%s] Step %d/%d — %s(%s)",
                task_id,
                idx + 1,
                len(steps_def),
                tool_name,
                json.dumps(resolved_args, ensure_ascii=False, default=str)[:200],
            )

            t0 = asyncio.get_event_loop().time()
            try:
                result = await client.call_tool(tool_name, resolved_args)
                elapsed = asyncio.get_event_loop().time() - t0
                sr = StepResult(
                    tool=tool_name,
                    arguments=resolved_args,
                    success=True,
                    result=result,
                    duration_seconds=round(elapsed, 2),
                )
                step_context[f"step_{idx}"] = result
            except Exception as exc:
                elapsed = asyncio.get_event_loop().time() - t0
                sr = StepResult(
                    tool=tool_name,
                    arguments=resolved_args,
                    success=False,
                    error=str(exc),
                    duration_seconds=round(elapsed, 2),
                )
                logger.error("[%s] Step %d failed: %s", task_id, idx + 1, exc)

            step_results.append(sr)

            if not sr.success and stop_on_failure:
                logger.warning("[%s] Stopping — step %d failed.", task_id, idx + 1)
                break

    finished = datetime.datetime.now(datetime.timezone.utc)
    return TaskResult(
        task_id=task_id,
        task_name=task_name,
        started_at=started.isoformat(),
        finished_at=finished.isoformat(),
        steps=step_results,
    )


def _write_audit_log(result: TaskResult, log_dir: Path) -> Path:
    log_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.date.today().isoformat()
    log_path = log_dir / f"audit_{today}.jsonl"

    record = {
        "task_id": result.task_id,
        "task_name": result.task_name,
        "started_at": result.started_at,
        "finished_at": result.finished_at,
        "success": result.success,
        "steps": [
            {
                "tool": s.tool,
                "arguments": s.arguments,
                "success": s.success,
                "error": s.error,
                "duration_seconds": s.duration_seconds,
            }
            for s in result.steps
        ],
    }

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")

    return log_path


async def run_task_file(
    task_path: Path,
    mcp_command: list[str],
    mcp_env: dict[str, str] | None = None,
    log_dir: Path | None = None,
) -> TaskResult:
    task_def = _load_task_file(task_path)
    result = await run_task(task_def, mcp_command, mcp_env)
    log_path = _write_audit_log(result, log_dir or DEFAULT_LOG_DIR)
    status = "OK" if result.success else "FAILED"
    logger.info("[%s] %s — log at %s", result.task_id, status, log_path)
    return result


async def run_all_tasks(
    tasks_dir: Path | None = None,
    mcp_command: list[str] | None = None,
    mcp_env: dict[str, str] | None = None,
    log_dir: Path | None = None,
    tag_filter: str | None = None,
) -> list[TaskResult]:
    """Run all .yaml task files in the tasks directory."""
    tasks_dir = tasks_dir or DEFAULT_TASKS_DIR
    if mcp_command is None:
        mcp_command = [
            sys.executable,
            "-c",
            "from athena_knowledge_mcp.server.app import main; main()",
        ]

    results: list[TaskResult] = []
    for path in sorted(tasks_dir.glob("*.yaml")):
        task_def = _load_task_file(path)
        tags = task_def.get("tags", [])
        if tag_filter and tag_filter not in tags:
            continue
        logger.info("═══ Running task: %s (%s) ═══", task_def.get("name", "?"), path.name)
        result = await run_task_file(path, mcp_command, mcp_env, log_dir)
        results.append(result)
    return results
