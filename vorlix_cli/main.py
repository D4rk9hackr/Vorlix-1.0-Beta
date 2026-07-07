"""Vorlix CLI — command-line interface for the control layer."""
import argparse
import asyncio
import os
import sys

from core.art import print_banner, print_freeze, print_resume, print_tier
from core.human_override import HumanOverride
from core.orchestrator import Orchestrator
from core.tier_base import TierRequest
from skills.registry import list_skills, activate_skill

VERSION = "Vorlix 1.0.0-beta.4"


def _get_workspace() -> str:
    return os.environ.get("VORLIX_WORKSPACE", os.path.join(os.getcwd(), "workspace"))


def _build_orchestrator() -> Orchestrator:
    from core.ledger import Ledger
    orch = Orchestrator()
    orch.ledger = Ledger(_get_workspace())
    return orch


async def cmd_run(args: argparse.Namespace):
    orch = _build_orchestrator()

    # Activate required skills on demand
    if args.skill:
        for skill_name in args.skill:
            success, msg, tier = activate_skill(skill_name)
            if success and tier:
                orch.register_tier(tier)
                print_tier(skill_name)
                print(f"  {msg}")
            else:
                print(f"  ⚠ {msg}")

    # Parse --arg key=value pairs
    arguments = {}
    for a in args.arg or []:
        if "=" in a:
            k, v = a.split("=", 1)
            arguments[k] = v

    request = TierRequest(
        tool=args.tool,
        arguments=arguments,
        reasoning=args.reason or "",
        confidence=args.confidence,
    )

    print(f"\n▶ Dispatching: {request.tool}")
    result = await orch.dispatch(request)

    if hasattr(result, "to_dict"):
        import json
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(f"  Status: {result.result.name if hasattr(result, 'result') else 'SUCCESS'}")
        print(f"  Message: {result.message if hasattr(result, 'message') else ''}")
        if hasattr(result, 'data') and result.data:
            print(f"  Data: {result.data}")


async def cmd_todo(args: argparse.Namespace):
    from core.ledger import Ledger
    ledger = Ledger(_get_workspace())

    if args.action == "list":
        todos = ledger.list_todos()
        if not todos:
            print("  No todos.")
        for i, todo in enumerate(todos):
            print(f"  [{i}] {todo}")
    elif args.action == "add":
        ledger.add_todo(args.description)
        print(f"  Added: {args.description}")


async def cmd_memory(args: argparse.Namespace):
    from core.ledger import Ledger
    ledger = Ledger(_get_workspace())
    content = ledger.read_memory()
    print(content if content else "  No memory entries.")


async def cmd_override(args: argparse.Namespace):
    override = HumanOverride()

    if args.action == "status":
        if override.is_overridden():
            print("  ⛔ Automation is FROZEN (human override active)")
        else:
            print("  ✅ Automation is RUNNING (no override)")
    elif args.action == "stop":
        override.freeze()
        print_freeze()
    elif args.action == "resume":
        confirm = input("  Resume automation? (y/N): ").strip().lower()
        if confirm == "y":
            override.resume()
            print_resume()
        else:
            print("  Resume cancelled.")


async def cmd_skills(args: argparse.Namespace):
    skills = list_skills()
    if not skills:
        print("  No skills found.")
    for s in skills:
        tools_str = ", ".join(s.get("tools", []))
        print(f"  📦 {s['name']}")
        print(f"     {s.get('description', '')}")
        if tools_str:
            print(f"     Tools: {tools_str}")
        print()


def main():
    parser = argparse.ArgumentParser(
        description="Vorlix — The AI Hand Control Layer CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  vorlix run terminal.run_command --arg command="ls -la" --reason "List files"
  vorlix run time.now --skill time_reminders
  vorlix todo list
  vorlix memory show
  vorlix override status
  vorlix override stop
        """,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")

    sub = parser.add_subparsers(dest="command")

    # run
    run_p = sub.add_parser("run", help="Dispatch a tool request")
    run_p.add_argument("tool", help="Tool name (e.g. terminal.run_command)")
    run_p.add_argument("--arg", action="append", help="Key=value arguments (repeatable)")
    run_p.add_argument("--reason", default="", help="Reasoning for the action")
    run_p.add_argument("--confidence", type=float, default=1.0, help="Confidence score 0-1")
    run_p.add_argument("--skill", action="append", help="Pre-activate a skill by name (repeatable)")

    # todo
    todo_p = sub.add_parser("todo", help="Manage todo list")
    todo_p.add_argument("action", choices=["list", "add"])
    todo_p.add_argument("description", nargs="?", default="", help="Description for 'add'")

    # memory
    mem_p = sub.add_parser("memory", help="Show memory")
    mem_p.add_argument("action", choices=["show"])

    # override
    ovr_p = sub.add_parser("override", help="Manage human override")
    ovr_p.add_argument("action", choices=["status", "stop", "resume"])

    # skills
    sub.add_parser("skills", help="List available skills")

    args = parser.parse_args()

    print_banner()

    if args.command == "run":
        asyncio.run(cmd_run(args))
    elif args.command == "todo":
        asyncio.run(cmd_todo(args))
    elif args.command == "memory":
        asyncio.run(cmd_memory(args))
    elif args.command == "override":
        asyncio.run(cmd_override(args))
    elif args.command == "skills":
        asyncio.run(cmd_skills(args))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
