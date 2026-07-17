"""Lightweight MCP server — 4 message types only."""
import asyncio
import ipaddress
import json
import os
import ssl
from typing import Optional

from core.orchestrator import Orchestrator
from core.tier_base import TierRequest
from skills.registry import list_skills, activate_skill, deactivate_skill


def _is_local(host: str) -> bool:
    """Check if a host string refers to a local-interface address."""
    try:
        addr = ipaddress.ip_address(host)
        return addr.is_loopback or addr.is_link_local or addr.is_private
    except ValueError:
        return host in ("localhost", "127.0.0.1", "::1", "0.0.0.0")


def generate_self_signed_cert(cert_path: str, key_path: str):
    """Generate a self-signed certificate with openssl (must be available)."""
    import subprocess, tempfile
    tmpdir = tempfile.mkdtemp()
    openssl_cfg = os.path.join(tmpdir, "openssl.cnf")
    with open(openssl_cfg, "w") as f:
        f.write(
            "[req]\n"
            "distinguished_name = dn\n"
            "x509_extensions = v3_req\n"
            "prompt = no\n"
            "[dn]\n"
            "CN = Vorlix\n"
            "[v3_req]\n"
            "subjectAltName = DNS:localhost,IP:127.0.0.1\n"
        )
    subprocess.run(
        ["openssl", "req", "-x509", "-newkey", "rsa:2048", "-keyout", key_path,
         "-out", cert_path, "-days", "3650", "-nodes",
         "-config", openssl_cfg, "-extensions", "v3_req"],
        capture_output=True, check=True,
    )
    for f in (cert_path, key_path):
        os.chmod(f, 0o600)


class LightweightMCPServer:
    """Minimal MCP server with 4 message types: list_skills, activate_skill, deactivate_skill, call_tool.

    If *tls* is True and the host is reachable from other machines — or if *cert_path* and
    *key_path* are provided — the server wraps the connection in TLS (self-signed cert).
    """

    def __init__(self, orchestrator: Orchestrator, host: str = "localhost", port: int = 8421,
                 tls: bool = False, cert_path: Optional[str] = None, key_path: Optional[str] = None):
        self.orchestrator = orchestrator
        self.host = host
        self.port = port
        self.tls = tls
        self.cert_path = cert_path or os.path.expanduser("~/.vorlix/mcp_cert.pem")
        self.key_path = key_path or os.path.expanduser("~/.vorlix/mcp_key.pem")
        self._server: Optional[asyncio.AbstractServer] = None

    async def start(self):
        ssl_ctx = None
        if self.tls or (not _is_local(self.host) and self.cert_path and self.key_path):
            if not os.path.exists(self.cert_path) or not os.path.exists(self.key_path):
                os.makedirs(os.path.dirname(self.cert_path), exist_ok=True)
                print("  Generating self-signed certificate...")
                generate_self_signed_cert(self.cert_path, self.key_path)
            ssl_ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            ssl_ctx.load_cert_chain(self.cert_path, self.key_path)

        proto = "wss" if ssl_ctx else "ws"
        self._server = await asyncio.start_server(
            self._handle_client, self.host, self.port, ssl=ssl_ctx
        )
        print(f"MCP server listening on {proto}://{self.host}:{self.port}")

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
