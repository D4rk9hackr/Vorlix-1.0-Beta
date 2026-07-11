"""File I/O tier — read-only file inspection and targeted patching."""
import difflib
import os

from core.tier_base import AutomationTier, TierRequest, TierResponse, TierResult
from core.human_override import HumanOverride
from core.ledger import Ledger

BLOCKED_PATH_PARTS = [
    ".ssh",
    ".aws",
    ".gcp",
    ".azure",
    ".config/gcloud",
    "/etc/shadow",
    "/etc/passwd",
    "/etc/security",
    "/etc/ssl",
    ".pem",
    "id_rsa",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
]


class FileIOTier(AutomationTier):
    """Read-only file inspection and targeted source-code patching."""

    def __init__(self, project_dir: str | None = None):
        super().__init__("FileIOTier")
        self._project_dir = os.path.abspath(project_dir or os.getcwd())
        self._human_override = HumanOverride()
        self._ledger = Ledger()

    # ------------------------------------------------------------------
    # Path resolution & guardrails
    # ------------------------------------------------------------------

    def _resolve_path(self, path: str) -> str:
        if os.path.isabs(path):
            return os.path.normpath(path)
        return os.path.normpath(os.path.join(self._project_dir, path))

    def _is_safe_path(self, resolved: str) -> bool:
        sep = os.sep
        pd = self._project_dir
        if not (resolved.startswith(pd + sep) or resolved == pd):
            return False
        for part in BLOCKED_PATH_PARTS:
            if part in resolved:
                return False
        return True

    def is_within_guardrails(self, request: TierRequest) -> bool:
        tool = request.tool
        if tool not in ("file.read", "file.patch"):
            return True
        path = request.arguments.get("path", "")
        if not path:
            return False
        resolved = self._resolve_path(path)
        return self._is_safe_path(resolved)

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    async def execute(self, request: TierRequest) -> TierResponse:
        tool = request.tool
        args = request.arguments

        if tool == "file.read":
            return self._file_read(args)
        elif tool == "file.patch":
            return self._file_patch(args, request.reasoning)
        else:
            return TierResponse(
                result=TierResult.BLOCKED,
                message=f"Unknown tool: {tool}",
            )

    # ------------------------------------------------------------------
    # file.read
    # ------------------------------------------------------------------

    def _file_read(self, args: dict) -> TierResponse:
        path = args.get("path", "").strip()
        if not path:
            return TierResponse(
                result=TierResult.BLOCKED,
                message="No path provided.",
            )

        resolved = self._resolve_path(path)
        if not self._is_safe_path(resolved):
            return TierResponse(
                result=TierResult.BLOCKED,
                message=f"path blocked by guardrails: {path}",
            )

        if not os.path.isfile(resolved):
            return TierResponse(
                result=TierResult.BLOCKED,
                message=f"File not found: {path}",
            )

        try:
            with open(resolved, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except Exception as exc:
            return TierResponse(
                result=TierResult.BLOCKED,
                message=str(exc),
            )

        total = len(lines)
        max_lines = args.get("max_lines", 200)
        truncated = total > max_lines
        content = "".join(lines[:max_lines])

        return TierResponse(
            result=TierResult.SUCCESS,
            data={
                "path": path,
                "content": content,
                "total_lines": total,
                "returned_lines": min(total, max_lines),
                "truncated": truncated,
            },
            message=f"Read {min(total, max_lines)}/{total} lines from {path}"
            + (" (truncated)" if truncated else ""),
        )

    # ------------------------------------------------------------------
    # file.patch
    # ------------------------------------------------------------------

    def _file_patch(self, args: dict, reasoning: str) -> TierResponse:
        path = args.get("path", "").strip()
        old_content = args.get("old_content", "")
        new_content = args.get("new_content", "")

        if not path:
            return TierResponse(
                result=TierResult.BLOCKED,
                message="No path provided.",
            )
        if not old_content:
            return TierResponse(
                result=TierResult.BLOCKED,
                message="No old_content provided.",
            )
        if not new_content:
            return TierResponse(
                result=TierResult.BLOCKED,
                message="No new_content provided.",
            )

        # Human override check
        if self._human_override.is_overridden():
            return TierResponse(
                result=TierResult.BLOCKED,
                message="Human override is active — cannot patch files while frozen.",
            )

        resolved = self._resolve_path(path)
        if not self._is_safe_path(resolved):
            return TierResponse(
                result=TierResult.BLOCKED,
                message=f"path blocked by guardrails: {path}",
            )

        if not os.path.isfile(resolved):
            return TierResponse(
                result=TierResult.BLOCKED,
                message=f"File not found: {path}",
            )

        # Read current content
        try:
            with open(resolved, "r", encoding="utf-8", errors="replace") as f:
                current_content = f.read()
        except Exception as exc:
            return TierResponse(
                result=TierResult.BLOCKED,
                message=str(exc),
            )

        # Check old_content appears exactly once
        count = current_content.count(old_content)
        if count == 0:
            return TierResponse(
                result=TierResult.BLOCKED,
                message=f"old_content not found in {path}",
            )
        if count > 1:
            return TierResponse(
                result=TierResult.BLOCKED,
                message=f"old_content appears {count} times in {path} — refusing ambiguous patch",
            )

        # Build diff for logging
        diff_lines = list(
            difflib.unified_diff(
                current_content.splitlines(keepends=True),
                current_content.replace(old_content, new_content).splitlines(keepends=True),
                fromfile=f"a/{path}",
                tofile=f"b/{path}",
            )
        )
        diff_text = "".join(diff_lines)

        # Log diff to memory.md BEFORE applying
        self._ledger.write_memory(
            current_thought=f"Applying patch to {path} (reasoning: {reasoning})",
            blockers="None — patch logged before execution for traceability",
            recovery_route=f"Revert by restoring original content of {path}. Diff:\n```diff\n{diff_text}\n```",
        )

        # Apply patch
        try:
            with open(resolved, "w", encoding="utf-8") as f:
                f.write(current_content.replace(old_content, new_content))
        except Exception as exc:
            return TierResponse(
                result=TierResult.BLOCKED,
                message=str(exc),
            )

        return TierResponse(
            result=TierResult.SUCCESS,
            data={
                "path": path,
                "diff": diff_text,
            },
            message=f"Patch applied to {path} ({count} replacement{'s' if count > 1 else ''}).",
        )
