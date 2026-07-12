from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import json
import re

try:
    from loguru import logger
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: Dict[str, Any]
    allowed_roles: List[str]
    action_type: str
    requires_target: bool = False
    visibility: str = "private"


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: Dict[str, Any]


@dataclass(frozen=True)
class ToolExecution:
    tool_name: str
    action: Dict[str, Any]
    content: str = ""
    valid: bool = True
    error: Optional[str] = None


ALL_TOOL_SPECS: Dict[str, ToolSpec] = {
    "speak_public": ToolSpec(
        name="speak_public",
        description="白天公开发言。发言会被所有存活玩家看见并注入记忆。",
        parameters={"speech": "string，公开发言内容"},
        allowed_roles=["villager", "werewolf", "seer", "witch", "hunter"],
        action_type="speech",
        visibility="public",
    ),
    "werewolf_private_message": ToolSpec(
        name="werewolf_private_message",
        description="狼人夜间私聊。只有存活狼人可见。",
        parameters={"speech": "string，给狼人队友的私聊内容"},
        allowed_roles=["werewolf"],
        action_type="private_chat",
        visibility="werewolf",
    ),
    "vote_day": ToolSpec(
        name="vote_day",
        description="白天公投放逐目标。只能投存活玩家。",
        parameters={"target": "int，目标玩家编号", "reason": "string，投票理由"},
        allowed_roles=["villager", "werewolf", "seer", "witch", "hunter"],
        action_type="vote",
        requires_target=True,
        visibility="public",
    ),
    "vote_werewolf_kill": ToolSpec(
        name="vote_werewolf_kill",
        description="狼人夜间投票选择击杀目标，必须选择一个目标。只能选择非狼人存活玩家。",
        parameters={"target": "int，目标玩家编号", "reason": "string，击杀理由"},
        allowed_roles=["werewolf"],
        action_type="night_kill",
        requires_target=True,
        visibility="werewolf",
    ),
    "seer_check": ToolSpec(
        name="seer_check",
        description="预言家夜间查验一名其他存活玩家。结果只进入预言家记忆。",
        parameters={"target": "int，目标玩家编号", "reason": "string，查验理由"},
        allowed_roles=["seer"],
        action_type="seer_check",
        requires_target=True,
    ),
    "witch_save": ToolSpec(
        name="witch_save",
        description="女巫使用解药救被狼人击杀的玩家。只能选择当夜刀口，根据你的判断谨慎使用，非必须使用。",
        parameters={"target": "int，刀口玩家编号", "reason": "string，救人理由"},
        allowed_roles=["witch"],
        action_type="witch_save",
        requires_target=True,
    ),
    "witch_poison": ToolSpec(
        name="witch_poison",
        description="女巫使用毒药毒杀一名其他存活玩家，根据你的判断谨慎使用，非必须使用。",
        parameters={"target": "int，目标玩家编号", "reason": "string，毒人理由"},
        allowed_roles=["witch"],
        action_type="witch_poison",
        requires_target=True,
    ),
    "abstain": ToolSpec(
        name="abstain",
        description="本次行动弃权或不使用技能。",
        parameters={"reason": "string，弃权理由"},
        allowed_roles=["villager", "werewolf", "seer", "witch", "hunter"],
        action_type="none",
    ),
    "hunter_shot": ToolSpec(
        name="hunter_shot",
        description="你被淘汰出局，发动最后一枪带走一名其他存活玩家。",
        parameters={"target": "int，目标玩家编号", "reason": "string，开枪理由"},
        allowed_roles=["hunter"],
        action_type="hunter_shot",
        requires_target=True,
    ),
}


INTENT_TOOLS: Dict[str, List[str]] = {
    "day_speech": ["speak_public"],
    "day_vote": ["vote_day", "abstain"],
    "werewolf_private_chat": ["werewolf_private_message"],
    "werewolf_kill": ["vote_werewolf_kill", "abstain"],
    "seer_night": ["seer_check", "abstain"],
    "witch_night": ["witch_save", "witch_poison", "abstain"],
    "hunter_shot": ["hunter_shot", "abstain"],
}


INTENT_INSTRUCTIONS: Dict[str, str] = {
    "day_speech": "现在轮到你白天公开发言。必须调用 speak_public。发言要推动局势，不要机械复读‘信息不足’。",
    "day_vote": "现在进入白天公投。只要 eligible_targets 非空，必须调用 vote_day 投给当前最高嫌疑人；只有没有合法目标时才允许 abstain。",
    "werewolf_private_chat": "现在是狼人夜间私聊。必须调用 werewolf_private_message，讨论伪装、刀口和白天抗推方向。",
    "werewolf_kill": "现在是狼人夜间击杀投票。必须调用 vote_werewolf_kill 选择一个非狼人存活玩家；只有没有合法目标时才允许 abstain。",
    "seer_night": "现在是预言家夜间行动。必须调用 seer_check 查验一名其他存活玩家；只有没有合法目标时才允许 abstain。",
    "witch_night": "现在是女巫夜间行动。根据可用工具选择 witch_save、witch_poison，或在没有合适目标时 abstain。解药和毒药都是一次性资源。",
    "hunter_shot": "你已被淘汰出局，可以发动最后一枪带走一名其他存活玩家。如果不打算开枪，选择 abstain。",
}


class AgentToolRuntime:
    def __init__(self, agents: List[Any]):
        self.agents = agents

    def available_tools(
        self,
        agent: Any,
        intent: str,
        eligible_targets: Optional[List[int]] = None,
        allowed_tool_names: Optional[List[str]] = None,
    ) -> List[ToolSpec]:
        names = INTENT_TOOLS.get(intent, ["abstain"])
        if allowed_tool_names is not None:
            allowed = set(allowed_tool_names)
            names = [name for name in names if name in allowed]
        tools = []
        for name in names:
            spec = ALL_TOOL_SPECS[name]
            if agent.role in spec.allowed_roles:
                tools.append(spec)
        if not tools:
            tools = [ALL_TOOL_SPECS["abstain"]]
        return tools

    def build_prompt(
        self,
        agent: Any,
        intent: str,
        game_state: Dict[str, Any],
        tools: List[ToolSpec],
        eligible_targets: Optional[List[int]] = None,
        extra_context: Optional[Dict[str, Any]] = None,
        eligible_targets_by_tool: Optional[Dict[str, List[int]]] = None,
    ) -> str:
        extra_context = extra_context or {}
        role_info = self._role_allocation_info()
        teammates = self._werewolf_teammates(agent, game_state)
        public_speeches = game_state.get("public_speeches", [])[-8:]
        private_chat = game_state.get("werewolf_private_chat", [])[-8:]
        short_memory = "\n".join(agent.short_memory[-8:]) if getattr(agent, "short_memory", None) else "无"
        prediction_memory = json.dumps(getattr(agent, "prediction_memory", {}) or {}, ensure_ascii=False)
        eligible_targets_by_tool = eligible_targets_by_tool or {}
        tools_payload = [
            {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
                "requires_target": tool.requires_target,
                "action_type": tool.action_type,
                "eligible_targets": eligible_targets_by_tool.get(tool.name, eligible_targets or []),
            }
            for tool in tools
        ]
        context_payload = {
            "day": game_state.get("day"),
            "phase": game_state.get("phase"),
            "alive_agents": game_state.get("alive_agents", []),
            "eliminated_agents": game_state.get("eliminated_agents", []),
            "eligible_targets": eligible_targets or [],
            "role_allocation": role_info,
            "known_werewolf_teammates": teammates,
            "public_speeches": public_speeches,
            "werewolf_private_chat": private_chat if agent.role == "werewolf" else [],
            "extra": extra_context,
        }
        return f"""
你是狼人杀游戏中的 Agent {agent.agent_id}，身份 {agent.role}，阵营 {agent.team}。固定规则已在 system prompt 中给出。

当前任务：{INTENT_INSTRUCTIONS.get(intent, intent)}

可见游戏状态：
{json.dumps(context_payload, ensure_ascii=False, indent=2)}

你的短期记忆：
{short_memory}

你的预测/信念：
{prediction_memory}

可调用工具如下。你只能调用其中一个工具，不能虚构工具名：
{json.dumps(tools_payload, ensure_ascii=False, indent=2)}

输出格式必须是严格 JSON，不要输出额外解释：
{{
  "tool_call": {{
    "name": "工具名",
    "arguments": {{}}
  }}
}}

要求：
- 一次只能调用一个工具。发言也是工具调用，不允许在 tool_call 外输出发言。
- 如果工具有 target，target 必须来自该工具自己的 eligible_targets。
- 白天投票不能投自己；不要因为“第一天信息少”自动弃票，必须根据发言、身份收益、票型或风险选出最高嫌疑人。
- 公开发言不能泄漏夜间私聊、队友、刀口、未公开查验/用药等不可见信息；狼人公开发言必须伪装好人。
- speech/reason 使用简体中文，具体、有行动倾向；发言控制在 120 字以内，避免输出过长导致 JSON 截断，也避免所有人重复同一句“信息不足”。
""".strip()

    def execute(
        self,
        agent: Any,
        tool_call: ToolCall,
        tools: List[ToolSpec],
        eligible_targets: Optional[List[int]] = None,
        eligible_targets_by_tool: Optional[Dict[str, List[int]]] = None,
    ) -> ToolExecution:
        tool_by_name = {tool.name: tool for tool in tools}
        if tool_call.name not in tool_by_name:
            return self._invalid(tool_call.name, f"tool_not_available:{tool_call.name}")

        spec = tool_by_name[tool_call.name]
        args = tool_call.arguments or {}
        target_pool = (eligible_targets_by_tool or {}).get(spec.name, eligible_targets or [])
        target = self._parse_target(args.get("target"), target_pool)
        reason = str(args.get("reason") or args.get("explain") or "").strip()

        if spec.requires_target and target is None:
            return self._invalid(spec.name, "invalid_or_missing_target")

        if spec.action_type in {"speech", "private_chat"}:
            speech = str(args.get("speech") or args.get("message") or args.get("content") or "").strip()
            if not speech:
                return self._invalid(spec.name, "missing_speech")
            return ToolExecution(
                tool_name=spec.name,
                action={"type": spec.action_type, "target": None, "explain": speech},
                content=speech,
            )

        action = {
            "type": spec.action_type,
            "target": target,
            "explain": reason or f"Agent {agent.agent_id} called {spec.name}",
        }
        return ToolExecution(tool_name=spec.name, action=action)

    def parse_tool_call(
        self,
        response_text: str,
        tools: Optional[List[ToolSpec]] = None,
        eligible_targets: Optional[List[int]] = None,
        eligible_targets_by_tool: Optional[Dict[str, List[int]]] = None,
        agent: Any = None,
    ) -> ToolCall:
        try:
            payload = self._extract_json(response_text)
        except Exception as exc:
            logger.warning(f"Recovering malformed tool call JSON: {exc}; response={response_text}")
            return self._fallback_tool_call(
                response_text=response_text,
                tools=tools or [],
                eligible_targets=eligible_targets or [],
                eligible_targets_by_tool=eligible_targets_by_tool or {},
                agent=agent,
            )

        if "tool_call" in payload:
            payload = payload["tool_call"]
        name = str(payload.get("name") or payload.get("tool") or payload.get("tool_name") or "abstain")
        arguments = payload.get("arguments") or payload.get("args") or {}
        if not isinstance(arguments, dict):
            arguments = {"value": arguments}
        return ToolCall(name=name, arguments=arguments)

    def _fallback_tool_call(
        self,
        response_text: str,
        tools: List[ToolSpec],
        eligible_targets: List[int],
        eligible_targets_by_tool: Dict[str, List[int]],
        agent: Any = None,
    ) -> ToolCall:
        tool_by_name = {tool.name: tool for tool in tools}
        agent_id = getattr(agent, "agent_id", "该")

        if "speak_public" in tool_by_name:
            speech = (
                self._recover_text_argument(response_text, "speech")
                or self._recover_text_argument(response_text, "content")
                or f"我是{agent_id}号玩家。上一轮输出被截断，我先基于公开信息继续观察，并会在投票阶段给出明确选择。"
            )
            return ToolCall(name="speak_public", arguments={"speech": speech})

        if "werewolf_private_message" in tool_by_name:
            speech = (
                self._recover_text_argument(response_text, "speech")
                or self._recover_text_argument(response_text, "message")
                or "上一轮输出被截断，建议优先选择对好人阵营威胁更大的目标，并保持白天发言一致。"
            )
            return ToolCall(name="werewolf_private_message", arguments={"speech": speech})

        if "abstain" in tool_by_name:
            return ToolCall(name="abstain", arguments={"reason": "模型输出为空或无法解析，系统按合法工具降级为弃权"})

        for tool in tools:
            if not tool.requires_target:
                return ToolCall(name=tool.name, arguments={"reason": "模型输出为空或无法解析，系统选择当前合法工具"})

            target_pool = eligible_targets_by_tool.get(tool.name, eligible_targets)
            if target_pool:
                return ToolCall(
                    name=tool.name,
                    arguments={
                        "target": target_pool[0],
                        "reason": "模型输出为空或无法解析，系统按首个合法目标兜底",
                    },
                )

        return ToolCall(name="abstain", arguments={"reason": "模型输出为空或无法解析，且无可用工具"})

    def _recover_text_argument(self, response_text: str, key: str) -> str:
        text = str(response_text or "")
        marker = f'"{key}"'
        start = text.find(marker)
        if start == -1:
            return ""
        colon = text.find(":", start)
        if colon == -1:
            return ""
        quote = text.find('"', colon + 1)
        if quote == -1:
            return ""

        chars: List[str] = []
        escaped = False
        for char in text[quote + 1:]:
            if escaped:
                chars.append(char)
                escaped = False
                continue
            if char == "\\":
                escaped = True
                continue
            if char == '"':
                break
            chars.append(char)
        return "".join(chars).strip()

    def _extract_json(self, response_text: str) -> Dict[str, Any]:
        text = str(response_text).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start == -1 or end <= start:
                raise
            return json.loads(text[start:end])

    def _parse_target(self, raw_target: Any, eligible_targets: List[int]) -> Optional[int]:
        eligible = set(eligible_targets)
        if raw_target is None:
            return None
        if isinstance(raw_target, int):
            return raw_target if raw_target in eligible else None
        for match in re.finditer(r"\d+", str(raw_target)):
            target = int(match.group(0))
            if target in eligible:
                return target
        return None

    def _invalid(self, tool_name: str, error: str) -> ToolExecution:
        return ToolExecution(
            tool_name=tool_name,
            action={"type": "none", "target": None, "explain": error},
            valid=False,
            error=error,
        )

    def _role_allocation_info(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for agent in self.agents:
            counts[agent.role] = counts.get(agent.role, 0) + 1
        return counts

    def _werewolf_teammates(self, agent: Any, game_state: Dict[str, Any]) -> List[int]:
        if agent.role != "werewolf":
            return []
        alive = set(game_state.get("alive_agents", []))
        return sorted(
            other.agent_id
            for other in self.agents
            if other.role == "werewolf" and other.agent_id != agent.agent_id and other.agent_id in alive
        )
