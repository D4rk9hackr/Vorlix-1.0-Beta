"""Terminal tier — direct shell command execution."""

import asyncio
import platform
import shlex
import subprocess
import sys
from typing import List, Tuple

from core.tier_base import AutomationTier, TierRequest, TierResponse, TierResult

DESTRUCTIVE_PATTERNS: List[str] = [
    "rm -rf /",
    "rm -rf /*",
    "rm -rf ~",
    "rm -rf .",
    "del /f",
    "del /p",
    "format",
    "format:",
    "mkfs",
    "dd if=",
    "dd of=",
    ":(){ :|:& };:",  # fork bomb
    "drop database",
    "drop table",
    "truncate table",
    "shutdown -s",
    "shutdown -r",
    "reboot",
    "poweroff",
    "halt",
    "> /dev/sda",
    "> /dev/hda",
    "chmod -r 0",
    "chmod 000",
    "mv /* /dev/null",
    "wget --delete-after",
    "curl -o /dev/null",
]


class TerminalTier(AutomationTier):
    """Executes terminal/shell commands with destructive-command blacklist."""

    def __init__(self):
        super().__init__("TerminalTier")
        self._system = platform.system()

    def is_within_guardrails(self, request: TierRequest) -> bool:
        if request.tool != "terminal.run_command":
            return True
        command = request.arguments.get("command", "").strip().lower()
        for pattern in DESTRUCTIVE_PATTERNS:
            if pattern in command:
                return False
        return True

    async def execute(self, request: TierRequest) -> TierResponse:
        tool = request.tool
        args = request.arguments

        if tool == "terminal.run_command":
            return await self._run_command(args)
        else:
            return TierResponse(
                result=TierResult.BLOCKED,
                message=f"Unknown tool: {tool}",
            )

    async def _run_command(self, args: dict) -> TierResponse:
        command = args.get("command", "").strip()
        if not command:
            return TierResponse(
                result=TierResult.BLOCKED,
                message="No command provided.",
            )

        timeout_ms = args.get("execution_timeout_ms", 30000)
        timeout_s = timeout_ms / 1000.0

        shell = True if self._system == "Windows" else False

        try:
            if self._system == "Windows":
                proc = await asyncio.create_subprocess_shell(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
            else:
                proc = await asyncio.create_subprocess_exec(
                    *shlex.split(command),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout_s
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return TierResponse(
                    result=TierResult.BLOCKED,
                    message=f"Command timed out after {timeout_ms}ms.",
                    data={"command": command, "timeout_ms": timeout_ms},
                )

            exit_code = proc.returncode
            output = stdout.decode(errors="replace")
            error = stderr.decode(errors="replace")

            if exit_code != 0:
                return TierResponse(
                    result=TierResult.FAILED,
                    message=error.strip() or f"Exit code: {exit_code}",
                    data={
                        "command": command,
                        "exit_code": exit_code,
                        "stdout": output,
                        "stderr": error,
                    },
                )

            return TierResponse(
                result=TierResult.SUCCESS,
                data={
                    "command": command,
                    "exit_code": 0,
                    "stdout": output,
                    "stderr": error,
                },
                message="Command executed successfully.",
            )

        except FileNotFoundError:
            return TierResponse(
                result=TierResult.BLOCKED,
                message=f"Command not found: {command}",
            )
        except Exception as exc:
            return TierResponse(
                result=TierResult.FAILED,
                message=str(exc),
            )
