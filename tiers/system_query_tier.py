"""System Query tier — process and window information."""

import asyncio
import platform
import subprocess
from typing import Dict, List, Optional

from core.tier_base import AutomationTier, TierRequest, TierResponse, TierResult
from core.human_override import HumanOverride


class SystemQueryTier(AutomationTier):
    """Read-only system introspection — processes and windows."""

    def __init__(self):
        super().__init__("SystemQueryTier")
        self._system = platform.system()
        self._human_override = HumanOverride()
        self._psutil_available = False
        self._init_psutil()

    def _init_psutil(self):
        try:
            global psutil
            import psutil
            self._psutil_available = True
        except ImportError:
            self._psutil_available = False

    def is_within_guardrails(self, request: TierRequest) -> bool:
        return True

    async def execute(self, request: TierRequest) -> TierResponse:
        tool = request.tool
        args = request.arguments

        if tool == "process.list":
            return self._process_list(args)
        elif tool == "process.is_running":
            return self._process_is_running(args)
        elif tool == "window.list":
            return await self._window_list(args)
        elif tool == "window.focus":
            return await self._window_focus(args)
        elif tool == "window.resize":
            return await self._window_resize(args)
        else:
            return TierResponse(
                result=TierResult.BLOCKED,
                message=f"Unknown tool: {tool}",
            )

    def _process_list(self, args: dict) -> TierResponse:
        if not self._psutil_available:
            return TierResponse(
                result=TierResult.BLOCKED,
                message="psutil not installed. Run: pip install psutil",
            )

        name_filter = args.get("name_filter", "").strip().lower()
        processes = []
        for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
            try:
                info = proc.info
                if name_filter and name_filter not in info["name"].lower():
                    continue
                processes.append({
                    "pid": info["pid"],
                    "name": info["name"],
                    "cpu_percent": info["cpu_percent"],
                    "memory_percent": info["memory_percent"],
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        processes.sort(key=lambda p: p["cpu_percent"], reverse=True)
        return TierResponse(
            result=TierResult.SUCCESS,
            data=processes,
            message=f"{len(processes)} process(es) found.",
        )

    def _process_is_running(self, args: dict) -> TierResponse:
        if not self._psutil_available:
            return TierResponse(
                result=TierResult.BLOCKED,
                message="psutil not installed. Run: pip install psutil",
            )

        name = args.get("name", "").strip().lower()
        if not name:
            return TierResponse(
                result=TierResult.BLOCKED,
                message="No process name provided.",
            )

        for proc in psutil.process_iter(["pid", "name"]):
            try:
                if proc.info["name"].lower() == name:
                    return TierResponse(
                        result=TierResult.SUCCESS,
                        data={"name": name, "running": True, "pid": proc.info["pid"]},
                        message=f"Process '{name}' is running (PID {proc.info['pid']}).",
                    )
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        return TierResponse(
            result=TierResult.SUCCESS,
            data={"name": name, "running": False},
            message=f"Process '{name}' is not running.",
        )

    async def _window_list(self, args: dict) -> TierResponse:
        if self._system == "Windows":
            return TierResponse(
                result=TierResult.BLOCKED,
                message="Window listing not yet implemented for Windows.",
            )
        elif self._system == "Linux":
            return await self._linux_window_list()
        elif self._system == "Darwin":
            return TierResponse(
                result=TierResult.BLOCKED,
                message="Not yet implemented for macOS.",
            )
        else:
            return TierResponse(
                result=TierResult.BLOCKED,
                message=f"Unsupported platform: {self._system}",
            )

    async def _linux_window_list(self) -> TierResponse:
        try:
            result = await asyncio.create_subprocess_exec(
                "wmctrl", "-l",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            stdout, stderr = await result.communicate()
            if result.returncode != 0:
                return TierResponse(
                    result=TierResult.BLOCKED,
                    message="wmctrl not available. Install with: pkg install wmctrl",
                )

            windows = []
            for line in stdout.decode(errors="replace").strip().split("\n"):
                if not line.strip():
                    continue
                parts = line.split(None, 3)
                if len(parts) >= 4:
                    windows.append({
                        "id": parts[0],
                        "desktop": parts[1],
                        "pid": parts[2],
                        "title": parts[3],
                    })

            return TierResponse(
                result=TierResult.SUCCESS,
                data=windows,
                message=f"{len(windows)} window(s) found.",
            )
        except FileNotFoundError:
            return TierResponse(
                result=TierResult.BLOCKED,
                message="wmctrl not installed. Run: pkg install wmctrl",
            )
        except Exception as exc:
            return TierResponse(
                result=TierResult.FAILED,
                message=str(exc),
            )

    async def _window_focus(self, args: dict) -> TierResponse:
        if self._human_override.is_overridden():
            return TierResponse(
                result=TierResult.BLOCKED,
                message="Human override is active — cannot focus windows while frozen.",
            )

        title_contains = args.get("title_contains", "").strip()
        if not title_contains:
            return TierResponse(
                result=TierResult.BLOCKED,
                message="No title_contains provided.",
            )

        if self._system == "Linux":
            return await self._linux_window_focus(title_contains)
        elif self._system == "Windows":
            return TierResponse(
                result=TierResult.BLOCKED,
                message="Window focus not yet implemented for Windows.",
            )
        elif self._system == "Darwin":
            return TierResponse(
                result=TierResult.BLOCKED,
                message="Not yet implemented for macOS.",
            )
        else:
            return TierResponse(
                result=TierResult.BLOCKED,
                message=f"Unsupported platform: {self._system}",
            )

    async def _linux_window_focus(self, title_contains: str) -> TierResponse:
        try:
            list_proc = await asyncio.create_subprocess_exec(
                "wmctrl", "-l",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            stdout, _ = await list_proc.communicate()
            target_id = None
            for line in stdout.decode(errors="replace").strip().split("\n"):
                if title_contains.lower() in line.lower():
                    target_id = line.split()[0]
                    break

            if not target_id:
                return TierResponse(
                    result=TierResult.BLOCKED,
                    message=f"No window found with title containing '{title_contains}'.",
                )

            focus_proc = await asyncio.create_subprocess_exec(
                "wmctrl", "-ia", target_id,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            _, stderr = await focus_proc.communicate()

            if focus_proc.returncode != 0:
                return TierResponse(
                    result=TierResult.FAILED,
                    message=stderr.decode(errors="replace").strip(),
                )

            return TierResponse(
                result=TierResult.SUCCESS,
                data={"window_id": target_id, "title_contains": title_contains},
                message=f"Window '{title_contains}' focused.",
            )
        except FileNotFoundError:
            return TierResponse(
                result=TierResult.BLOCKED,
                message="wmctrl not installed. Run: pkg install wmctrl",
            )
        except Exception as exc:
            return TierResponse(
                result=TierResult.FAILED,
                message=str(exc),
            )

    async def _window_resize(self, args: dict) -> TierResponse:
        if self._human_override.is_overridden():
            return TierResponse(
                result=TierResult.BLOCKED,
                message="Human override is active — cannot resize windows while frozen.",
            )

        title_contains = args.get("title_contains", "").strip()
        width = args.get("width")
        height = args.get("height")

        if not title_contains:
            return TierResponse(
                result=TierResult.BLOCKED,
                message="No title_contains provided.",
            )
        if not width or not height:
            return TierResponse(
                result=TierResult.BLOCKED,
                message="width and height are required.",
            )

        if self._system == "Linux":
            try:
                list_proc = await asyncio.create_subprocess_exec(
                    "wmctrl", "-l",
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                stdout, _ = await list_proc.communicate()
                target_id = None
                for line in stdout.decode(errors="replace").strip().split("\n"):
                    if title_contains.lower() in line.lower():
                        target_id = line.split()[0]
                        break

                if not target_id:
                    return TierResponse(
                        result=TierResult.BLOCKED,
                        message=f"No window found with title containing '{title_contains}'.",
                    )

                resize_proc = await asyncio.create_subprocess_exec(
                    "wmctrl", "-ir", target_id, "-e", f"0,-1,-1,{width},{height}",
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                _, stderr = await resize_proc.communicate()

                if resize_proc.returncode != 0:
                    return TierResponse(
                        result=TierResult.FAILED,
                        message=stderr.decode(errors="replace").strip(),
                    )

                return TierResponse(
                    result=TierResult.SUCCESS,
                    data={"window_id": target_id, "width": width, "height": height},
                    message=f"Window '{title_contains}' resized to {width}x{height}.",
                )
            except FileNotFoundError:
                return TierResponse(
                    result=TierResult.BLOCKED,
                    message="wmctrl not installed. Run: pkg install wmctrl",
                )
            except Exception as exc:
                return TierResponse(
                    result=TierResult.FAILED,
                    message=str(exc),
                )
        elif self._system == "Windows":
            return TierResponse(
                result=TierResult.BLOCKED,
                message="Window resize not yet implemented for Windows.",
            )
        elif self._system == "Darwin":
            return TierResponse(
                result=TierResult.BLOCKED,
                message="Not yet implemented for macOS.",
            )
        else:
            return TierResponse(
                result=TierResult.BLOCKED,
                message=f"Unsupported platform: {self._system}",
            )
