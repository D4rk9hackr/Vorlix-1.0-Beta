"""Telegram bot for Vorlix — chat with your control layer from your phone.

Usage:
  export VORLIX_TELEGRAM_TOKEN="your_bot_token"
  python3 -c "from mcp.telegram_bot import VorlixTelegramBot; VorlixTelegramBot().run()"

Commands:
  /list_skills           — list all available skills
  /activate <skill>      — activate a skill
  /deactivate <skill>    — deactivate a skill
  /override stop         — freeze automation
  /override resume       — resume automation
  /override status       — check override state
  /memory                — read memory log
  /todo                  — list todos
  /help                  — show this message
  <free text>            — parsed as a tool call and dispatched
"""
import asyncio
import json
import os
import time
import urllib.request
import urllib.error
from typing import Optional

from core.orchestrator import Orchestrator
from core.tier_base import TierRequest, TierResult, HumanHelpRequired
from core.human_override import HumanOverride
from skills.registry import list_skills, activate_skill, deactivate_skill

API_BASE = "https://api.telegram.org/bot"
POLL_TIMEOUT = 30        # long-poll seconds
UPDATE_INTERVAL = 1.0    # seconds between poll cycles


def _api_url(token: str, method: str) -> str:
    return f"{API_BASE}{token}/{method}"


def _api_call(token: str, method: str, data: dict) -> Optional[dict]:
    """Make a POST to the Telegram Bot API. Returns parsed JSON or None."""
    url = _api_url(token, method)
    payload = json.dumps(data).encode()
    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=POLL_TIMEOUT + 5) as resp:
            return json.loads(resp.read())
    except (urllib.error.URLError, json.JSONDecodeError, OSError) as e:
        print(f"  [Telegram API error] {e}")
        return None


def _send_message(token: str, chat_id: int, text: str, reply_to: Optional[int] = None):
    """Send a plain-text message to a chat."""
    data = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_to:
        data["reply_to_message_id"] = reply_to
    _api_call(token, "sendMessage", data)


def _format_result(result: any) -> str:
    """Convert an Orchestrator dispatch result to a readable Telegram message."""
    if isinstance(result, HumanHelpRequired):
        return (
            f"⛔ <b>Human Help Required</b>\n"
            f"{result.reason}\n\n"
            f"<i>Suggestion:</i> {result.ai_suggestion}"
        )
    if hasattr(result, "result"):
        status = result.result.name
        msg = result.message or ""
        if result.data:
            data_str = json.dumps(result.data, indent=2)
            # Trim long data
            if len(data_str) > 1500:
                data_str = data_str[:1500] + "\n... (truncated)"
            return f"<b>{status}</b>\n{msg}\n<pre>{data_str}</pre>"
        return f"<b>{status}</b>\n{msg}"
    return str(result)


class VorlixTelegramBot:
    """Poll-based Telegram bot that dispatches messages through the Orchestrator."""

    def __init__(self, token: Optional[str] = None, orchestrator: Optional[Orchestrator] = None):
        self.token = token or os.environ.get("VORLIX_TELEGRAM_TOKEN", "")
        if not self.token:
            raise ValueError("Telegram token required. Set VORLIX_TELEGRAM_TOKEN env var.")

        self.orch = orchestrator or Orchestrator()
        self._last_update_id = 0
        self._register_default_tiers()
        self._help_text = self._build_help()

    def _register_default_tiers(self):
        """Register all available tiers."""
        from tiers.terminal_tier import TerminalTier
        from tiers.system_query_tier import SystemQueryTier
        from tiers.time_reminders_tier import TimeRemindersTier
        from tiers.file_io_tier import FileIOTier
        from tiers.computer_vision_tier import ComputerVisionTier
        from tiers.team_tier import TeamAgentTier

        self.orch.register_tier(TerminalTier())
        self.orch.register_tier(SystemQueryTier())
        self.orch.register_tier(TimeRemindersTier())
        self.orch.register_tier(FileIOTier())
        team_tier = TeamAgentTier(orchestrator=self.orch)
        self.orch.register_tier(team_tier)
        try:
            self.orch.register_tier(ComputerVisionTier())
        except Exception:
            pass

        # Activate auto_debug
        success, msg, tier = activate_skill("auto_debug")
        if success and tier:
            self.orch.register_tier(tier)

    def _build_help(self) -> str:
        return (
            "<b>Vorlix Telegram Bot</b>\n\n"
            "<b>Commands:</b>\n"
            "/list_skills — list available skills\n"
            "/activate &lt;skill&gt; — activate a skill\n"
            "/deactivate &lt;skill&gt; — deactivate a skill\n"
            "/skillss search &lt;query&gt; — search skills.sh\n"
            "/skillss install &lt;repo&gt; — install from skills.sh\n"
            "/skillss list — list installed\n"
            "/team spawn &lt;goal&gt; — spawn a sub-agent\n"
            "/team list — list sub-agents\n"
            "/team collect — wait for all sub-agents\n"
            "/override stop — freeze automation\n"
            "/override resume — resume automation\n"
            "/override status — check override state\n"
            "/memory — read the memory log\n"
            "/todo — list todos\n"
            "/help — this message\n\n"
            "<b>Free text:</b> parsed as a tool call, e.g.:\n"
            "<code>time.now</code>\n"
            "<code>terminal.run_command --command 'ls -la'</code>\n"
            "<code>file.read pyproject.toml</code>"
        )

    # ------------------------------------------------------------------
    # Message parsing
    # ------------------------------------------------------------------

    def _parse_command(self, text: str) -> dict:
        """Convert a Telegram message into a dispatch request.

        Returns a dict with keys for the Orchestrator dispatch.
        """
        text = text.strip()
        if not text:
            return {"tool": "", "arguments": {}, "reasoning": "", "confidence": 1.0}

        parts = text.split()
        tool = parts[0].lower()

        # If it looks like a slash command, handle specially
        if tool.startswith("/"):
            return self._handle_slash_command(text)

        # Parse --key value or key=value style arguments
        args = {}
        i = 1
        while i < len(parts):
            p = parts[i]
            if p.startswith("--") and i + 1 < len(parts):
                args[p[2:]] = parts[i + 1]
                i += 2
            elif "=" in p:
                k, v = p.split("=", 1)
                args[k] = v
                i += 1
            else:
                # Positional: try "tool --arg value" pattern
                i += 1

        return {
            "tool": tool,
            "arguments": args,
            "reasoning": f"Telegram command: {text}",
            "confidence": 0.9,
        }

    def _handle_slash_command(self, text: str) -> dict:
        """Handle /commands that don't go through normal dispatch."""
        parts = text.split()
        cmd = parts[0].lower()

        if cmd == "/help":
            return {"tool": "_help", "arguments": {}, "reasoning": "", "confidence": 1.0}
        if cmd == "/list_skills":
            return {"tool": "_list_skills", "arguments": {}, "reasoning": "", "confidence": 1.0}
        if cmd == "/memory":
            return {"tool": "_memory", "arguments": {}, "reasoning": "", "confidence": 1.0}
        if cmd == "/todo":
            return {"tool": "_todo", "arguments": {}, "reasoning": "", "confidence": 1.0}
        if cmd == "/override":
            action = parts[1] if len(parts) > 1 else "status"
            return {"tool": "_override", "arguments": {"action": action}, "reasoning": "", "confidence": 1.0}
        if cmd == "/activate":
            name = parts[1] if len(parts) > 1 else ""
            return {"tool": "_activate", "arguments": {"name": name}, "reasoning": "", "confidence": 1.0}
        if cmd == "/deactivate":
            name = parts[1] if len(parts) > 1 else ""
            return {"tool": "_deactivate", "arguments": {"name": name}, "reasoning": "", "confidence": 1.0}
        if cmd == "/skillss":
            subcmd = parts[1] if len(parts) > 1 else "list"
            query = " ".join(parts[2:]) if len(parts) > 2 else ""
            return {"tool": "_skillss", "arguments": {"subcmd": subcmd, "query": query}, "reasoning": "", "confidence": 1.0}
        if cmd == "/team":
            action = parts[1] if len(parts) > 1 else "status"
            rest = " ".join(parts[2:]) if len(parts) > 2 else ""
            return {"tool": "_team", "arguments": {"action": action, "params": rest}, "reasoning": "", "confidence": 1.0}

        return {"tool": "", "arguments": {}, "reasoning": "", "confidence": 1.0}

    # ------------------------------------------------------------------
    # Dispatch handlers
    # ------------------------------------------------------------------

    async def _handle_text(self, chat_id: int, text: str, reply_id: Optional[int] = None):
        """Parse free text and dispatch through Orchestrator."""
        parsed = self._parse_command(text)
        tool = parsed["tool"]

        # Handle internal commands
        if tool == "_help":
            _send_message(self.token, chat_id, self._help_text, reply_id)
            return
        if tool == "_list_skills":
            skills = list_skills()
            if not skills:
                _send_message(self.token, chat_id, "No skills found.", reply_id)
                return
            msg = "<b>Available skills:</b>\n"
            for s in skills:
                tools = ", ".join(s.get("tools", []))
                msg += f"\n📦 <b>{s['name']}</b>\n   {s.get('description', '')}\n   Tools: {tools}\n"
            _send_message(self.token, chat_id, msg, reply_id)
            return
        if tool == "_memory":
            from core.ledger import Ledger
            mem = Ledger().read_memory()
            _send_message(self.token, chat_id, mem or "No memory entries.", reply_id)
            return
        if tool == "_todo":
            from core.ledger import Ledger
            todos = Ledger().list_todos()
            msg = "<b>Todos:</b>\n" + "\n".join(f"• {t}" for t in todos) if todos else "No todos."
            _send_message(self.token, chat_id, msg, reply_id)
            return
        if tool == "_override":
            action = parsed["arguments"].get("action", "status")
            ho = HumanOverride()
            if action == "stop":
                ho.freeze()
                _send_message(self.token, chat_id, "⛔ Automation frozen.", reply_id)
            elif action == "resume":
                ho.resume()
                _send_message(self.token, chat_id, "✅ Automation resumed.", reply_id)
            else:
                status = "⛔ FROZEN" if ho.is_overridden() else "✅ RUNNING"
                _send_message(self.token, chat_id, f"Override status: {status}", reply_id)
            return
        if tool == "_activate":
            name = parsed["arguments"].get("name", "")
            success, msg, tier = activate_skill(name)
            if success and tier:
                self.orch.register_tier(tier)
            _send_message(self.token, chat_id, msg, reply_id)
            return
        if tool == "_deactivate":
            name = parsed["arguments"].get("name", "")
            deactivate_skill(name)
            _send_message(self.token, chat_id, f"Skill '{name}' deactivated.", reply_id)
            return
        if tool == "_skillss":
            subcmd = parsed["arguments"].get("subcmd", "list")
            query = parsed["arguments"].get("query", "")
            if subcmd == "search":
                from vorlix_cli.skills_sh import search_skills_sh
                results = search_skills_sh(query, limit=5)
                if not results:
                    _send_message(self.token, chat_id, "No results.", reply_id)
                else:
                    msg = "<b>skills.sh search results:</b>\n"
                    for r in results:
                        msg += f"\n📦 <b>{r['name']}</b>\n{r.get('description', '')}\nSource: {r.get('source', '?')}\n"
                    _send_message(self.token, chat_id, msg, reply_id)
            elif subcmd == "install":
                from vorlix_cli.skills_sh import install_skill
                success, msg = install_skill(query)
                _send_message(self.token, chat_id, f"{'✅' if success else '⚠'} {msg}", reply_id)
            else:
                from vorlix_cli.skills_sh import list_with_sources
                skills = list_with_sources()
                if not skills:
                    _send_message(self.token, chat_id, "No skills installed.", reply_id)
                else:
                    msg = "<b>Installed skills:</b>\n"
                    for s in skills:
                        msg += f"\n📦 <b>{s['name']}</b> [{s.get('_source', '?')}]\n{s.get('description', '')}\n"
                    _send_message(self.token, chat_id, msg, reply_id)
            return
        if tool == "_team":
            action = parsed["arguments"].get("action", "list")
            params = parsed["arguments"].get("params", "")
            request = TierRequest(
                tool={
                    "spawn": "subagent.spawn",
                    "ask": "subagent.ask",
                    "list": "subagent.list",
                    "kill": "subagent.kill",
                    "collect": "subagent.collect",
                }.get(action, "subagent.list"),
                arguments={
                    "goal": params if action == "spawn" else "",
                    "agent_id": params if action in ("ask", "kill") else "",
                    "task": params if action == "ask" else "",
                },
                reasoning=f"Telegram team command: /team {action}",
                confidence=1.0,
            )
            result = await self.orch.dispatch(request)
            _send_message(self.token, chat_id, _format_result(result), reply_id)
            return

        if not tool:
            _send_message(self.token, chat_id, "I don't understand that. Try /help", reply_id)
            return

        # Normal dispatch
        request = TierRequest(
            tool=tool,
            arguments=parsed["arguments"],
            reasoning=parsed["reasoning"],
            confidence=parsed["confidence"],
        )
        result = await self.orch.dispatch(request)
        reply = _format_result(result)
        _send_message(self.token, chat_id, reply, reply_id)

    # ------------------------------------------------------------------
    # Polling loop
    # ------------------------------------------------------------------

    async def run(self):
        """Main polling loop — fetches updates and dispatches messages."""
        print(f"  Vorlix Telegram bot started (polling)...")
        print(f"  Send /help to @{self._get_me()} to see commands.")

        while True:
            result = _api_call(self.token, "getUpdates", {
                "offset": self._last_update_id + 1,
                "timeout": POLL_TIMEOUT,
                "allowed_updates": ["message"],
            })
            if not result or not result.get("ok"):
                await asyncio.sleep(UPDATE_INTERVAL)
                continue

            for update in result.get("result", []):
                self._last_update_id = update["update_id"]
                msg = update.get("message")
                if not msg:
                    continue
                chat_id = msg["chat"]["id"]
                text = msg.get("text", "")
                reply_id = msg.get("message_id")
                if not text:
                    continue
                await self._handle_text(chat_id, text, reply_id)

            await asyncio.sleep(UPDATE_INTERVAL)

    def _get_me(self) -> str:
        """Get the bot's username for display."""
        result = _api_call(self.token, "getMe", {})
        if result and result.get("ok"):
            return result["result"].get("username", "?")
        return "?"


if __name__ == "__main__":
    bot = VorlixTelegramBot()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(bot.run())
    except KeyboardInterrupt:
        print("\n  Bot stopped.")
