"""Lightweight MCP server — 4 message types only."""
import asyncio
import json
from typing import Optional

from core.orchestrator import Orchestrator
from core.tier_base import TierRequest
from skills.registry import list_skills, activate_skill, deactivate_skill


class LightweightMCPServer:
    """Minimal MCP server with 4 message types: list_skills, activate_skill, deactivate_skill, call_tool."""

    def __init__(self, orchestrator: Orchestrator, host: str = "localhost", port: int = 8421):
        self.orchestrator = orchestrator
        self.host = host
        self.port = port
        self._server: Optional[asyncio.AbstractServer] = None

    async def start(self):
        self._server = await asyncio.start_server(
            self._handle_client, self.host, self.port
        )
        print(f"MCP server listening on ws://{self.host}:{self.port}")

    async def stop(self):
        if self._server:
            self._server.close()
            await self._server.wait_closed()

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        while True:
            try:
                data = await reader.readline()
                if not data:
                    break
                message = json.loads(data.decode().strip())
                response = await self._process_message(message)
                writer.write((json.dumps(response) + "\n").encode())
                await writer.drain()
            except (json.JSONDecodeError, ConnectionResetError, BrokenPipeError):
                break
        writer.close()

    async def _process_message(self, msg: dict) -> dict:
        msg_type = msg.get("type", "")
        msg_id = msg.get("id", "")

        if msg_type == "list_skills":
            skills = list_skills()
            return {"type": "list_skills", "id": msg_id, "skills": skills}

        elif msg_type == "activate_skill":
            name = msg.get("name", "")
            if not name:
                return {"type": "error", "id": msg_id, "error": "Missing skill name."}
            success, message, tier = activate_skill(name)
            if success and tier:
                self.orchestrator.register_tier(tier)
            return {"type": "activate_skill", "id": msg_id, "success": success, "message": message}

        elif msg_type == "deactivate_skill":
            name = msg.get("name", "")
            if not name:
                return {"type": "error", "id": msg_id, "error": "Missing skill name."}
            success = deactivate_skill(name)
            return {"type": "deactivate_skill", "id": msg_id, "success": success}

        elif msg_type == "call_tool":
            tool = msg.get("tool", "")
            arguments = msg.get("arguments", {})
            reasoning = msg.get("reasoning", "")
            confidence = msg.get("confidence", 1.0)
            if not tool:
                return {"type": "error", "id": msg_id, "error": "Missing tool name."}
            request = TierRequest(
                tool=tool,
                arguments=arguments,
                reasoning=reasoning,
                confidence=confidence,
            )
            result = await self.orchestrator.dispatch(request)
            if hasattr(result, "to_dict"):
                return {"type": "call_tool", "id": msg_id, "result": result.to_dict()}
            return {"type": "call_tool", "id": msg_id, "result": {
                "status": result.result.name if hasattr(result, "result") else "SUCCESS",
                "data": result.data if hasattr(result, "data") else str(result),
                "message": result.message if hasattr(result, "message") else "",
            }}

        else:
            return {"type": "error", "id": msg_id, "error": f"Unknown message type: {msg_type}"}
