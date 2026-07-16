"""FastMCP stdio server for MAWS agent tools."""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, List, Optional

os.environ.setdefault("FASTMCP_LOG_LEVEL", "WARNING")
os.environ.setdefault("FASTMCP_ENABLE_RICH_LOGGING", "false")

# Running this file as a script sets sys.path to src/mcp_tools. Add src so the
# existing non-package imports used by the game engine still resolve.
SRC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from fastmcp import FastMCP

from agent_tools import ALL_TOOL_SPECS
from mcp_tools.executor import execute_agent_tool

mcp = FastMCP("maws-agent-tools")


def _register_tool(tool_name: str) -> None:
    spec = ALL_TOOL_SPECS[tool_name]

    @mcp.tool(name=tool_name, description=spec.description)
    def game_tool(
        agent: Dict[str, Any],
        arguments: Dict[str, Any],
        allowed_tools: List[str],
        eligible_targets: Optional[List[int]] = None,
        eligible_targets_by_tool: Optional[Dict[str, List[int]]] = None,
    ) -> Dict[str, Any]:
        return execute_agent_tool(tool_name, {
            "agent": agent,
            "arguments": arguments,
            "allowed_tools": allowed_tools,
            "eligible_targets": eligible_targets or [],
            "eligible_targets_by_tool": eligible_targets_by_tool or {},
        })


for _tool_name in ALL_TOOL_SPECS:
    _register_tool(_tool_name)


def main() -> None:
    mcp.run(transport="stdio", show_banner=False)


if __name__ == "__main__":
    main()
