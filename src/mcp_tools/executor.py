"""Pure tool execution logic shared by the FastMCP server."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Dict, List

try:
    from agent_tools import ALL_TOOL_SPECS, AgentToolRuntime, ToolCall
except ImportError:
    from ..agent_tools import ALL_TOOL_SPECS, AgentToolRuntime, ToolCall


def execute_agent_tool(tool_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    allowed_names: List[str] = list(payload.get("allowed_tools") or [])
    if tool_name not in allowed_names:
        allowed_names.append(tool_name)

    tools = [ALL_TOOL_SPECS[name] for name in allowed_names if name in ALL_TOOL_SPECS]
    agent_payload = payload.get("agent") or {}
    agent = SimpleNamespace(
        agent_id=int(agent_payload.get("id", 0)),
        role=str(agent_payload.get("role", "")),
    )

    execution = AgentToolRuntime([]).execute(
        agent=agent,
        tool_call=ToolCall(name=tool_name, arguments=payload.get("arguments") or {}),
        tools=tools,
        eligible_targets=payload.get("eligible_targets") or [],
        eligible_targets_by_tool=payload.get("eligible_targets_by_tool") or {},
    )
    return {
        "tool_name": execution.tool_name,
        "action": execution.action,
        "content": execution.content,
        "valid": execution.valid,
        "error": execution.error,
    }
