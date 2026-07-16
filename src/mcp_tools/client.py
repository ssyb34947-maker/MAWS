"""Synchronous wrapper around a persistent FastMCP stdio client."""

from __future__ import annotations

import asyncio
import atexit
import threading
from concurrent.futures import Future
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastmcp import Client

try:
    from agent_tools import ToolCall, ToolExecution
except ImportError:
    from ..agent_tools import ToolCall, ToolExecution


class MCPToolClient:
    def __init__(self, server_path: Optional[str] = None):
        self.server_path = server_path or str(Path(__file__).resolve().parent / "server.py")
        self._loop = asyncio.new_event_loop()
        self._client: Optional[Client] = None
        self._ready: Optional[Future] = Future()
        self._closed = False
        self._thread = threading.Thread(target=self._run_loop, name="maws-mcp-tools", daemon=True)
        self._thread.start()
        atexit.register(self.close)
        self._ready.result(timeout=15)

    def execute(
        self,
        agent: Any,
        tool_call: ToolCall,
        allowed_tool_names: List[str],
        eligible_targets: Optional[List[int]] = None,
        eligible_targets_by_tool: Optional[Dict[str, List[int]]] = None,
    ) -> ToolExecution:
        future = asyncio.run_coroutine_threadsafe(
            self._execute_async(
                agent=agent,
                tool_call=tool_call,
                allowed_tool_names=allowed_tool_names,
                eligible_targets=eligible_targets or [],
                eligible_targets_by_tool=eligible_targets_by_tool or {},
            ),
            self._loop,
        )
        payload = future.result(timeout=30)
        return ToolExecution(
            tool_name=payload.get("tool_name", tool_call.name),
            action=payload.get("action") or {"type": "none", "target": None, "explain": "mcp_empty_action"},
            content=payload.get("content") or "",
            valid=bool(payload.get("valid", False)),
            error=payload.get("error"),
        )

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self._shutdown(), self._loop).result(timeout=5)
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread.is_alive():
            self._thread.join(timeout=5)

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._startup())
        self._loop.run_forever()
        self._loop.run_until_complete(self._shutdown())
        self._loop.close()

    async def _startup(self) -> None:
        try:
            self._client = Client(self.server_path)
            await self._client.__aenter__()
            assert self._ready is not None
            self._ready.set_result(True)
        except Exception as exc:
            assert self._ready is not None
            self._ready.set_exception(exc)
            raise

    async def _shutdown(self) -> None:
        if self._client is not None:
            client = self._client
            self._client = None
            await client.__aexit__(None, None, None)

    async def _execute_async(
        self,
        agent: Any,
        tool_call: ToolCall,
        allowed_tool_names: List[str],
        eligible_targets: List[int],
        eligible_targets_by_tool: Dict[str, List[int]],
    ) -> Dict[str, Any]:
        if self._client is None:
            raise RuntimeError("MCP tool client is not connected")
        result = await self._client.call_tool(tool_call.name, {
            "agent": {"id": getattr(agent, "agent_id", 0), "role": getattr(agent, "role", "")},
            "arguments": tool_call.arguments or {},
            "allowed_tools": allowed_tool_names,
            "eligible_targets": eligible_targets,
            "eligible_targets_by_tool": eligible_targets_by_tool,
        })
        return self._coerce_payload(result)

    def _coerce_payload(self, result: Any) -> Dict[str, Any]:
        if isinstance(result, dict):
            return result
        structured = (
            getattr(result, "structured_content", None)
            or getattr(result, "structuredContent", None)
            or getattr(result, "data", None)
        )
        if isinstance(structured, dict):
            return structured
        content = getattr(result, "content", None) or []
        for item in content:
            text = getattr(item, "text", None)
            if text:
                import json
                payload = json.loads(text)
                return payload if isinstance(payload, dict) else {}
        return {}
