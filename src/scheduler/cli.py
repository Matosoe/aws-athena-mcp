"""CLI entry-point for the MCP Task Scheduler.

Usage examples::

    # Run all daily tasks
    python -m scheduler.cli run --tag daily

    # Run a single task file
    python -m scheduler.cli run --file scheduler/tasks/01_daily_catalog_refresh.yaml

    # List available tools in the MCP server
    python -m scheduler.cli tools

    # Install a daily scheduled task in Windows Task Scheduler
    python -m scheduler.cli install --preset daily --time 08:00

    # Uninstall a scheduled task
    python -m scheduler.cli uninstall --name Daily_daily

    # Show registered scheduled tasks
    python -m scheduler.cli status
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import anyio

from scheduler.mcp_client import open_mcp_client
from scheduler.task_runner import (
    DEFAULT_LOG_DIR,
    DEFAULT_TASKS_DIR,
    run_all_tasks,
    run_task_file,
)
from scheduler.win_scheduler import (
    delete_scheduled_task,
    install_daily_preset,
    install_weekly_preset,
    list_scheduled_tasks,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("scheduler")


def _default_mcp_command() -> list[str]:
    return [
        sys.executable, "-c",
        "from athena_knowledge_mcp.server.app import main; main()",
    ]


# ── Commands ─────────────────────────────────────────────────────────


async def cmd_run(args: argparse.Namespace) -> int:
    mcp_cmd = _default_mcp_command()

    if args.file:
        path = Path(args.file)
        if not path.exists():
            logger.error("Task file not found: %s", path)
            return 1
        result = await run_task_file(path, mcp_cmd, log_dir=Path(args.log_dir))
        _print_result(result)
        return 0 if result.success else 1

    results = await run_all_tasks(
        tasks_dir=Path(args.tasks_dir),
        mcp_command=mcp_cmd,
        log_dir=Path(args.log_dir),
        tag_filter=args.tag,
    )
    for r in results:
        _print_result(r)
    failed = sum(1 for r in results if not r.success)
    return 1 if failed else 0


async def cmd_tools(args: argparse.Namespace) -> int:
    mcp_cmd = _default_mcp_command()
    async with open_mcp_client(mcp_cmd) as client:
        tools = await client.list_tools()
    print(f"\n{'='*60}")
    print(f"  MCP Tools Available ({len(tools)})")
    print(f"{'='*60}")
    for t in tools:
        name = t.get("name", "?")
        desc = t.get("description", "")[:80]
        print(f"  {name:40s} {desc}")
    print()
    return 0


async def cmd_call(args: argparse.Namespace) -> int:
    """Call a single MCP tool interactively."""
    mcp_cmd = _default_mcp_command()
    arguments = {}
    if args.args:
        arguments = json.loads(args.args)

    async with open_mcp_client(mcp_cmd) as client:
        result = await client.call_tool(args.tool_name, arguments)
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    return 0


def cmd_install(args: argparse.Namespace) -> int:
    if args.preset == "daily":
        ok = install_daily_preset(
            tag=args.tag or "daily",
            time=args.time or "08:00",
        )
    elif args.preset == "weekly":
        ok = install_weekly_preset(
            tag=args.tag or "weekly",
            time=args.time or "07:00",
            days=args.days or "MON",
        )
    else:
        logger.error("Unknown preset: %s", args.preset)
        return 1
    return 0 if ok else 1


def cmd_uninstall(args: argparse.Namespace) -> int:
    ok = delete_scheduled_task(args.name)
    return 0 if ok else 1


def cmd_status(_args: argparse.Namespace) -> int:
    output = list_scheduled_tasks()
    print(output)
    return 0


# ── Helpers ──────────────────────────────────────────────────────────


def _print_result(result: object) -> None:
    from scheduler.task_runner import TaskResult

    if not isinstance(result, TaskResult):
        return
    status = "OK" if result.success else "FAILED"
    print(f"\n  [{status}] {result.task_name} ({result.task_id})")
    print(f"    Started:  {result.started_at}")
    print(f"    Finished: {result.finished_at}")
    for i, step in enumerate(result.steps):
        icon = "+" if step.success else "X"
        extra = f" ({step.duration_seconds}s)" if step.duration_seconds else ""
        err = f" — {step.error}" if step.error else ""
        print(f"    [{icon}] Step {i+1}: {step.tool}{extra}{err}")


# ── Argument parser ──────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mcp-scheduler",
        description="MCP Task Scheduler — automate MCP tool calls on a schedule",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # run
    p_run = sub.add_parser("run", help="Execute task files")
    p_run.add_argument("--file", "-f", help="Path to a single task YAML file")
    p_run.add_argument("--tag", "-t", help="Only run tasks with this tag")
    p_run.add_argument(
        "--tasks-dir",
        default=str(DEFAULT_TASKS_DIR),
        help="Directory containing task YAML files",
    )
    p_run.add_argument(
        "--log-dir",
        default=str(DEFAULT_LOG_DIR),
        help="Directory for audit logs",
    )

    # tools
    sub.add_parser("tools", help="List available MCP tools")

    # call
    p_call = sub.add_parser("call", help="Call a single MCP tool")
    p_call.add_argument("tool_name", help="Name of the MCP tool")
    p_call.add_argument(
        "--args",
        "-a",
        default="{}",
        help='JSON string with tool arguments (e.g. \'{"database": "mydb"}\')',
    )

    # install
    p_inst = sub.add_parser("install", help="Register in Windows Task Scheduler")
    p_inst.add_argument("--preset", required=True, choices=["daily", "weekly"])
    p_inst.add_argument("--tag", help="Tag filter for tasks")
    p_inst.add_argument("--time", help="HH:MM start time")
    p_inst.add_argument("--days", help="Days for weekly (e.g. MON,WED,FRI)")

    # uninstall
    p_uninst = sub.add_parser("uninstall", help="Remove from Windows Task Scheduler")
    p_uninst.add_argument("--name", required=True, help="Task name to remove")

    # status
    sub.add_parser("status", help="Show registered scheduled tasks")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command in ("run", "tools", "call"):
        handlers = {"run": cmd_run, "tools": cmd_tools, "call": cmd_call}
        handler = handlers[args.command]

        async def _run() -> int:
            return await handler(args)

        exit_code = anyio.run(_run)
    elif args.command == "install":
        exit_code = cmd_install(args)
    elif args.command == "uninstall":
        exit_code = cmd_uninstall(args)
    elif args.command == "status":
        exit_code = cmd_status(args)
    else:
        parser.print_help()
        exit_code = 1

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
