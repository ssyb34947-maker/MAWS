from typing import Dict, List, Any, Optional
from agent import WerewolfAgent
from agent_tools import AgentToolRuntime, ToolExecution
from game_control import MemoryEvent, MemoryInjector, TiePolicy, Visibility, VoteKind, VoteSession
from logger import GameLogger
from utils import load_config, assign_roles
import random
import os
try:
    from loguru import logger
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)


class GameEngine:
    """
    狼人杀游戏引擎
    """

    def __init__(self, config_path: str):
        """
        初始化游戏引擎
        
        Args:
            config_path: 配置文件路径
        """
        self.config = load_config(config_path)
        # 设置project_root属性
        self.project_root = os.path.dirname(os.path.abspath(config_path))
        print(f"Project root: {self.project_root}")
        self.agents: List[WerewolfAgent] = []
        self.game_state: Dict[str, Any] = {
            "day": 0,
            "phase": "init",
            "alive_agents": [],
            "eliminated_agents": [],
            "votes": {},
            "public_speeches": [],  # 公共交流列表
            "werewolf_private_chat": [],  # 狼人私聊记录
            "vote_history": [],  # 历史投票决议
            "current_speaker": None,  # 当前发言人
            "speaking_order": [],  # 发言顺序
            "last_night_result": None,  # 昨晚结果
            "current_voting": {},  # 当前投票情况
            "witch_resources": {}  # 女巫一次性药品状态，key 为 agent_id
        }
        
        # 初始化日志记录器
        log_pattern = self.config["game"].get("logging", {}).get("file", "logs/game_{timestamp}.log")
        self.logger = GameLogger(log_pattern)
        
        # 注意：不再在初始化时设置固定的随机种子，让每次运行都有不同的随机分布

    def initialize_game(self):
        """
        初始化游戏
        """
        self.logger.log_system("init", "Initializing game...")
        
        # 分配角色
        roles_config = self.config["roles"]["default_setup"]["roles"]
        total_agents = self.config["roles"]["default_setup"]["total_agents"]
        assigned_agents = assign_roles(roles_config, total_agents)
        
        # 创建Agent实例
        self.agents = []
        self.model_list=[]
        for agent_info in assigned_agents:
            agent,modelname = self._create_agent(agent_info)
            self.agents.append(agent)
            self.model_list.append(modelname)
            self.game_state["alive_agents"].append(agent.agent_id)
            if agent.role == "witch":
                self.game_state["witch_resources"][agent.agent_id] = {
                    "save_used": False,
                    "poison_used": False,
                }
        
        self.logger.log_system("init", f"Created {len(self.agents)} agents")
        
        # 记录初始状态
        for i,agent in enumerate(self.agents):
            self.logger.log_system("init", f"Agent {agent.agent_id}: {agent.role},using the model {self.model_list[i]}")

    def _create_agent(self, agent_info: Dict[str, Any]) -> WerewolfAgent:
        """
        根据角色信息创建Agent实例
        
        Args:
            agent_info: Agent信息字典
            
        Returns:
            Agent实例
        """
        # 使用绝对导入替换相对导入
        from agent import WerewolfAgent
        from models_adapter import ModelsAdapter
        
        class RealAgent(WerewolfAgent):
            def __init__(self, agent_id: int, role: str, team: str, 
                         model_config: Dict[str, Any], prompt_template: str,
                         role_allocation: Dict[str, int]):
                super().__init__(agent_id, role, team, model_config, prompt_template, role_allocation=role_allocation)
                self.model_adapter = ModelsAdapter(model_config)
        
        # 获取模型配置
        # 根据agent_id选择模型，实现每个模型2个Agent
        model_names = list(self.config["models"]["adapters"].keys())
        model_index = (agent_info["agent_id"] - 1) % len(model_names)
        selected_model = model_names[model_index]
        model_config = self.config["models"]["adapters"][selected_model]
        role_allocation = {
            role_cfg["name"]: role_cfg.get("count", 0)
            for role_cfg in self.config["roles"]["default_setup"]["roles"]
        }
        
        agent = RealAgent(
            agent_id=agent_info["agent_id"],
            role=agent_info["role"],
            team=agent_info["team"],
            model_config=model_config,
            prompt_template="",
            role_allocation=role_allocation
        )
        
        # 为agent添加config属性和project_root
        agent.config = self.config
        agent.project_root = self.project_root
        
        # 设置对游戏引擎的引用
        agent.game_engine_ref = self
        return agent,selected_model

    def run_night_phase(self):
        """
        执行夜间阶段
        """
        self.game_state["day"] += 1
        self.game_state["phase"] = "night"
        self.logger.log_system("night", f"Starting night {self.game_state['day']}")
        
        # 清空狼人私聊记录
        self.game_state["werewolf_private_chat"] = []
        
        # 按顺序执行各角色夜间行动
        # 1. 狼人
        werewolves = [agent for agent in self.agents if agent.role == "werewolf" and agent.agent_id in self.game_state["alive_agents"]]
        
        # 狼人内部讨论
        if len(werewolves) > 1:
            # 构建狼人私聊上下文
            private_context = {
                "private_chat_history": self.game_state["werewolf_private_chat"],
                "alive_agents": self.game_state["alive_agents"],
                "eliminated_agents": self.game_state["eliminated_agents"],
                "day": self.game_state["day"]
            }
            
            # 每个狼人都通过私聊工具参与讨论
            for werewolf in werewolves:
                execution = self._call_agent_tool(
                    werewolf,
                    intent="werewolf_private_chat",
                    extra_context=private_context,
                )
                message_content = execution.content or execution.action.get("explain", "")

                private_message = {
                    "sender": werewolf.agent_id,
                    "message": message_content,
                    "timestamp": self.game_state["day"]
                }
                self.game_state["werewolf_private_chat"].append(private_message)
                self.logger.log("night", werewolf.agent_id, "private_chat", message_content)
                self._inject_memory_event(
                    phase="night",
                    source=f"{werewolf.agent_id}号狼人私聊",
                    content=message_content,
                    visibility=Visibility.WEREWOLF,
                )
        
        # 狼人集体决策 - 基于私聊信息做出最终决策
        werewolf_actions = []
        if len(werewolves) >= 1:
            decision_context = {
                "private_chat_history": self.game_state["werewolf_private_chat"],
                "alive_agents": self.game_state["alive_agents"],
                "eliminated_agents": self.game_state["eliminated_agents"],
                "day": self.game_state["day"]
            }
            werewolf_ids = [agent.agent_id for agent in werewolves]
            werewolf_target_ids = [
                agent_id for agent_id in self.game_state["alive_agents"]
                if agent_id not in werewolf_ids
            ]
            decision_context["eligible_targets"] = werewolf_target_ids
            vote_session = VoteSession(
                kind=VoteKind.WEREWOLF_KILL,
                eligible_voters=werewolf_ids,
                eligible_targets=werewolf_target_ids,
                tie_policy=TiePolicy.SEAT_ORDER,
                allow_abstain=True,
            )

            for werewolf in werewolves:
                # Retry up to 3 times if the tool call returns an invalid target
                execution = None
                for attempt in range(3):
                    execution = self._call_agent_tool(
                        werewolf,
                        intent="werewolf_kill",
                        eligible_targets=vote_session.eligible_targets,
                        extra_context=decision_context,
                    )
                    action = execution.action
                    target = action.get("target") if action.get("type") == "night_kill" else None
                    if target is not None and target in vote_session.eligible_targets:
                        break
                    self.logger.log(
                        "night", werewolf.agent_id, "system",
                        f"werewolf_kill retry {attempt + 1}/3: invalid target={target}"
                    )
                else:
                    # All 3 retries failed — pick a random eligible target
                    fallback = random.choice(vote_session.eligible_targets)
                    self.logger.log(
                        "night", werewolf.agent_id, "system",
                        f"werewolf_kill fallback after 3 retries: random target={fallback}"
                    )
                    execution = ToolExecution(
                        tool_name="vote_werewolf_kill",
                        action={"type": "night_kill", "target": fallback, "explain": "系统随机选择目标"},
                        content=f"系统随机选择{fallback}号",
                        valid=True,
                    )

                action = execution.action
                target = action.get("target") if action.get("type") == "night_kill" else None
                if target is None:
                    vote_session.cast(werewolf.agent_id, None, action.get("explain", "invalid_or_abstain"))
                else:
                    vote_session.cast(werewolf.agent_id, target, action.get("explain", "werewolf_kill"))

                werewolf_actions.append(action)
                self.logger.log_agent_action("night", werewolf.agent_id, action)

            wolf_resolution = vote_session.resolve()
            self.game_state["current_voting"] = {
                voter: vote.target for voter, vote in vote_session.votes.items() if vote.target is not None
            }
            self.game_state["vote_history"].append(wolf_resolution.to_dict())
            self.logger.log_system("night", {"werewolf_vote_resolution": wolf_resolution.to_dict()})
            if wolf_resolution.target is not None:
                werewolf_actions = [{
                    "type": "night_kill",
                    "target": wolf_resolution.target,
                    "explain": f"Werewolf vote resolved to kill player {wolf_resolution.target}"
                }]
            else:
                werewolf_actions = []

        # 2. 预言家
        seers = [agent for agent in self.agents if agent.role == "seer" and agent.agent_id in self.game_state["alive_agents"]]
        seer_actions = []
        for seer in seers:
            eligible_targets = [agent_id for agent_id in self.game_state["alive_agents"] if agent_id != seer.agent_id]
            vote_session = VoteSession(
                kind=VoteKind.SEER_CHECK,
                eligible_voters=[seer.agent_id],
                eligible_targets=eligible_targets,
                tie_policy=TiePolicy.SEAT_ORDER,
                allow_abstain=True,
            )
            execution = self._call_agent_tool(
                seer,
                intent="seer_night",
                eligible_targets=eligible_targets,
            )
            action = execution.action
            target = action.get("target") if action.get("type") == "seer_check" else None
            if vote_session.cast(seer.agent_id, target, action.get("explain", "seer_check")) and target is not None:
                seer_actions.append(action)
            else:
                action = {"type": "none", "target": None, "explain": action.get("explain", "invalid_or_abstain")}
                vote_session.cast(seer.agent_id, None, action["explain"])
                seer_actions.append(action)
            resolution = vote_session.resolve()
            self.game_state["vote_history"].append(resolution.to_dict())
            self.logger.log_agent_action("night", seer.agent_id, action)
            self.logger.log_system("night", {"seer_vote_resolution": resolution.to_dict()})
        
        # 3. 女巫
        witches = [agent for agent in self.agents if agent.role == "witch" and agent.agent_id in self.game_state["alive_agents"]]
        witch_actions = []
        wolf_kill_targets = [
            a["target"] for a in werewolf_actions
            if a.get("type") == "night_kill" and a.get("target") is not None
        ]
        for witch in witches:
            resources = self.game_state.setdefault("witch_resources", {}).setdefault(
                witch.agent_id,
                {"save_used": False, "poison_used": False},
            )
            save_targets = [] if resources.get("save_used") else wolf_kill_targets
            poison_targets = [] if resources.get("poison_used") else [
                agent_id for agent_id in self.game_state["alive_agents"] if agent_id != witch.agent_id
            ]
            eligible_targets_by_tool = {
                "witch_save": save_targets,
                "witch_poison": poison_targets,
                "abstain": [],
            }
            allowed_tool_names = ["abstain"]
            if save_targets:
                allowed_tool_names.insert(0, "witch_save")
            if poison_targets:
                allowed_tool_names.insert(0, "witch_poison")
            eligible_targets = sorted(set(save_targets + poison_targets))
            execution = self._call_agent_tool(
                witch,
                intent="witch_night",
                eligible_targets=eligible_targets,
                eligible_targets_by_tool=eligible_targets_by_tool,
                allowed_tool_names=allowed_tool_names,
                extra_context={
                    "wolf_kill_targets": wolf_kill_targets,
                    "witch_resources": resources,
                },
            )
            action = execution.action
            action_type = action.get("type")
            if action_type == "witch_save":
                kind = VoteKind.WITCH_SAVE
                target_candidates = save_targets
            elif action_type == "witch_poison":
                kind = VoteKind.WITCH_POISON
                target_candidates = poison_targets
            else:
                kind = VoteKind.WITCH_SAVE
                target_candidates = []

            vote_session = VoteSession(
                kind=kind,
                eligible_voters=[witch.agent_id],
                eligible_targets=target_candidates,
                tie_policy=TiePolicy.SEAT_ORDER,
                allow_abstain=True,
            )
            target = action.get("target") if action_type in {"witch_save", "witch_poison"} else None
            if target is not None:
                action["actor"] = witch.agent_id
            if vote_session.cast(witch.agent_id, target, action.get("explain", action_type or "none")) and target is not None:
                witch_actions.append(action)
            else:
                action = {"type": "none", "target": None, "explain": action.get("explain", "invalid_or_abstain")}
                vote_session.cast(witch.agent_id, None, action["explain"])
                witch_actions.append(action)
            resolution = vote_session.resolve()
            self.game_state["vote_history"].append(resolution.to_dict())
            self.logger.log_agent_action("night", witch.agent_id, action)
            self.logger.log_system("night", {"witch_vote_resolution": resolution.to_dict()})
        
        # 夜间结算
        self._settle_night(werewolf_actions, seer_actions, witch_actions)

    def _settle_night(self, werewolf_actions: List[Dict[str, Any]], 
                      seer_actions: List[Dict[str, Any]] = None, 
                      witch_actions: List[Dict[str, Any]] = None):
        """
        夜间结算
        
        Args:
            werewolf_actions: 狼人的行动列表
            seer_actions: 预言家的行动列表
            witch_actions: 女巫的行动列表
        """
        # 确定狼人目标
        wolf_target = None
        for action in werewolf_actions:
            if action["type"] == "night_kill" and action["target"] is not None:
                wolf_target = action["target"]
                self.logger.log_system("night", f"Werewolf decided to kill player {wolf_target}")
                break
        
        # 处理预言家技能
        seer_check_result = None
        if seer_actions:
            for action in seer_actions:
                if action["type"] == "seer_check" and action["target"] is not None:
                    target_agent = next((a for a in self.agents if a.agent_id == action["target"]), None)
                    if target_agent:
                        seer_check_result = {
                            "target": action["target"],
                            "role": target_agent.role
                        }
                        break
        
        # 处理女巫技能
        witch_save_target = None
        witch_save_actor = None
        witch_poison_target = None
        witch_poison_actor = None
        if witch_actions:
            for action in witch_actions:
                if action["type"] == "witch_save" and action["target"] is not None:
                    witch_save_target = action["target"]
                    witch_save_actor = action.get("actor")
                elif action["type"] == "witch_poison" and action["target"] is not None:
                    witch_poison_target = action["target"]
                    witch_poison_actor = action.get("actor")
        
        # 应用技能效果
        eliminated_players = []
        
        # 女巫救人（如果选择救人且目标是被狼人击杀的玩家）
        final_wolf_target = wolf_target
        if witch_save_target is not None and witch_save_target == wolf_target:
            final_wolf_target = None  # 救下被击杀的玩家
            if witch_save_actor is not None:
                self.game_state.setdefault("witch_resources", {}).setdefault(
                    witch_save_actor,
                    {"save_used": False, "poison_used": False},
                )["save_used"] = True
            self.logger.log_system("night", f"Witch saved player {witch_save_target}")
        
        # 狼人击杀
        if final_wolf_target is not None and final_wolf_target in self.game_state["alive_agents"]:
            self.game_state["alive_agents"].remove(final_wolf_target)
            self.game_state["eliminated_agents"].append(final_wolf_target)
            eliminated_players.append(final_wolf_target)
            self.logger.log_system("night", f"Agent {final_wolf_target} was eliminated at night")
        
        # 女巫毒人
        if witch_poison_target is not None and witch_poison_target in self.game_state["alive_agents"]:
            self.game_state["alive_agents"].remove(witch_poison_target)
            self.game_state["eliminated_agents"].append(witch_poison_target)
            eliminated_players.append(witch_poison_target)
            if witch_poison_actor is not None:
                self.game_state.setdefault("witch_resources", {}).setdefault(
                    witch_poison_actor,
                    {"save_used": False, "poison_used": False},
                )["poison_used"] = True
            self.logger.log_system("night", f"Agent {witch_poison_target} was poisoned by witch")
        
        # Hunter last shot: any eliminated hunter can shoot before night ends
        hunter_shot_targets = []
        for elim_id in list(eliminated_players):
            hunter = next((a for a in self.agents if a.agent_id == elim_id and a.role == "hunter"), None)
            if hunter:
                self.logger.log_system("night", f"Hunter {elim_id} was killed at night, triggering last shot")
                self._process_hunter_last_shot(hunter, "night")

        self.logger.log_system("night", "Night settlement completed")

        # 更新所有Agent的环境感知
        for eliminated_player in eliminated_players:
            self._update_agents_environmental_awareness("night", eliminated_player)
        
        # 更新预言家查验信息到所有预言家的记忆中
        if seer_check_result:
            self._update_seer_check_info(seer_check_result)
        
        # 更新女巫技能使用情况到所以女巫的记忆中
        if witch_actions:
            self._update_witch_skill_info(witch_actions)
        
    def run_day_phase(self):
        """
        执行白天阶段
        """
        self.game_state["phase"] = "day"
        self.logger.log_system("day", f"Starting day {self.game_state['day']}")
        
        # 清空之前的公共发言记录
        self.game_state["public_speeches"] = []
        
        # 公告夜间结果
        # （已在夜间结算中记录）
        
        # 按座位顺序发言
        speeches = {}
        for agent_id in sorted(self.game_state["alive_agents"]):
            self.game_state["current_speaker"] = agent_id
            agent = next(a for a in self.agents if a.agent_id == agent_id)
            execution = self._call_agent_tool(agent, intent="day_speech")
            speech = execution.content or execution.action.get("explain", "")
            speeches[agent_id] = speech
            
            # 添加到公共交流列表
            speech_record = {
                "speaker": agent_id,
                "content": speech,
                "timestamp": self.game_state['day']
            }
            self.game_state["public_speeches"].append(speech_record)
            self.logger.log_agent_speech("day", agent_id, speech)
            self._inject_memory_event(
                phase="day",
                source=f"{agent_id}号玩家发言",
                content=speech,
                visibility=Visibility.PUBLIC,
            )
        
        
        # 投票
        alive_voters = sorted(self.game_state["alive_agents"])
        vote_session = VoteSession(
            kind=VoteKind.DAY_ELIMINATION,
            eligible_voters=alive_voters,
            eligible_targets=alive_voters,
            tie_policy=TiePolicy.NO_ELIMINATION,
            allow_abstain=True,
        )
        self.game_state["current_voting"] = {}  # 重置当前投票状态

        # 收集所有玩家的投票
        for agent_id in alive_voters:
            agent = next(a for a in self.agents if a.agent_id == agent_id)
            vote_targets = [target_id for target_id in vote_session.eligible_targets if target_id != agent_id]
            execution = self._call_agent_tool(
                agent,
                intent="day_vote",
                eligible_targets=vote_targets,
                eligible_targets_by_tool={"vote_day": vote_targets, "abstain": []},
                allowed_tool_names=["vote_day"] if vote_targets else ["abstain"],
            )
            action = execution.action
            vote_target = action.get("target") if action.get("type") == "vote" else None
            if vote_session.cast(agent_id, vote_target, action.get("explain", "day_elimination")) and vote_target is not None:
                self.game_state["current_voting"][agent_id] = vote_target
                self.logger.log_agent_action("day", agent_id, action)
            else:
                self.logger.log_agent_action("day", agent_id, {
                    "type": "abstain",
                    "target": None,
                    "explain": action.get("explain", f"Player {agent_id} abstained or produced an invalid vote")
                })

        day_resolution = vote_session.resolve()
        self.game_state["vote_history"].append(day_resolution.to_dict())
        self.logger.log_system("day", {"day_vote_resolution": day_resolution.to_dict()})

        # 白天结算
        self._settle_day(day_resolution)

    def _process_hunter_last_shot(self, hunter, phase: str):
        """Process hunter's last shot when eliminated."""
        if not self.game_state["alive_agents"]:
            self.logger.log_system(phase, f"Hunter {hunter.agent_id} has no alive targets, cannot shoot")
            return

        # Only the hunter decides; no VoteSession needed for a solo action
        execution = self._call_agent_tool(
            hunter,
            intent="hunter_shot",
            eligible_targets=list(self.game_state["alive_agents"]),
        )
        action = execution.action
        target = action.get("target")
        if target is not None and target in self.game_state["alive_agents"]:
            self.game_state["alive_agents"].remove(target)
            self.game_state["eliminated_agents"].append(target)
            self.logger.log_system(phase, f"Hunter {hunter.agent_id} shot and eliminated player {target}")
            self.logger.log_agent_action(phase, hunter.agent_id, action)
            self._update_agents_environmental_awareness(phase, target)
        else:
            self.logger.log_system(phase, f"Hunter {hunter.agent_id} chose not to shoot")

    def _inject_memory_event(self, phase: str, source: str, content: str, visibility: Visibility,
                             recipients: Optional[List[int]] = None) -> List[int]:
        event = MemoryEvent(
            phase=phase,
            source=source,
            content=content,
            visibility=visibility,
            recipients=recipients,
        )
        injected = MemoryInjector(self.agents, self.game_state).inject(event)
        self.logger.log_system(phase, {
            "memory_injection": {
                "source": source,
                "visibility": visibility.value,
                "recipients": injected,
            }
        })
        return injected

    def _call_agent_tool(
        self,
        agent,
        intent: str,
        eligible_targets: Optional[List[int]] = None,
        extra_context: Optional[Dict[str, Any]] = None,
        eligible_targets_by_tool: Optional[Dict[str, List[int]]] = None,
        allowed_tool_names: Optional[List[str]] = None,
    ):
        """
        MCP 风格的按需工具调用入口：引擎按阶段暴露工具，Agent 只返回 tool_call。
        """
        runtime = AgentToolRuntime(self.agents)
        tools = runtime.available_tools(
            agent,
            intent,
            eligible_targets,
            allowed_tool_names=allowed_tool_names,
        )
        prompt = runtime.build_prompt(
            agent=agent,
            intent=intent,
            game_state=self.game_state,
            tools=tools,
            eligible_targets=eligible_targets,
            extra_context=extra_context,
            eligible_targets_by_tool=eligible_targets_by_tool,
        )
        response_text = agent.model_adapter.call_model(
            prompt,
            system_prompt=getattr(agent, "system_prompt", None),
        )
        tool_call = runtime.parse_tool_call(
            response_text,
            tools=tools,
            eligible_targets=eligible_targets,
            eligible_targets_by_tool=eligible_targets_by_tool,
            agent=agent,
        )
        execution = runtime.execute(
            agent=agent,
            tool_call=tool_call,
            tools=tools,
            eligible_targets=eligible_targets,
            eligible_targets_by_tool=eligible_targets_by_tool,
        )
        self.logger.log("tool", agent.agent_id, "tool_call", {
            "intent": intent,
            "requested": {"name": tool_call.name, "arguments": tool_call.arguments},
            "execution": {
                "tool_name": execution.tool_name,
                "action": execution.action,
                "valid": execution.valid,
                "error": execution.error,
            }
        })
        return execution

    def _settle_day(self, resolution):
        """
        白天结算。

        Args:
            resolution: VoteSession.resolve() 返回的投票决议
        """
        target = resolution.target
        eliminated_player = None
        if target is not None and target in self.game_state["alive_agents"]:
            self.game_state["alive_agents"].remove(target)
            self.game_state["eliminated_agents"].append(target)
            eliminated_player = target
            self.logger.log_system("day", f"Agent {target} was eliminated by voting")
        else:
            self.logger.log_system("day", f"No player was eliminated by voting: {resolution.reason}")

        # Hunter last shot if the eliminated player is a hunter
        if eliminated_player is not None:
            hunter = next((a for a in self.agents if a.agent_id == eliminated_player and a.role == "hunter"), None)
            if hunter:
                self.logger.log_system("day", f"Hunter {eliminated_player} is eliminated, triggering last shot")
                self._process_hunter_last_shot(hunter, "day")

        self.logger.log_system("day", "Day settlement completed")
        self._update_agents_environmental_awareness("day", eliminated_player)

    def _update_agents_environmental_awareness(self, phase: str, eliminated_player: Optional[int]):
        """
        更新所有Agent的环境感知
        
        Args:
            phase: 阶段 ("night" 或 "day")
            eliminated_player: 被淘汰的玩家ID，如果没有则为None
        """
        if eliminated_player is not None:
            # 构造环境变化信息
            environment_change = f"在{phase}阶段，{eliminated_player}号玩家被淘汰"
            
            # 为每个存活的Agent创建记忆更新信息
            memory_update_info = {
                "memory_updates": {
                    "short_memory_add": [environment_change],
                    "prediction_adjust": []
                }
            }
            
            # 更新所有存活Agent的记忆
            for agent in self.agents:
                if agent.agent_id in self.game_state["alive_agents"]:
                    agent.update_memory(memory_update_info, phase)

    def check_victory_condition(self) -> Optional[str]:
        """
        检查胜利条件
        
        Returns:
            胜利方名称，如果游戏继续则返回None
        """
        alive_agents = [a for a in self.agents if a.agent_id in self.game_state["alive_agents"]]
        werewolves = [a for a in alive_agents if a.role == "werewolf"]
        villagers = [a for a in alive_agents if a.role != "werewolf"]
        
        # 记录当前游戏状态
        game_status = {
            "day": self.game_state["day"],
            "alive_players": len(alive_agents),
            "werewolves_count": len(werewolves),
            "villagers_count": len(villagers),
            "werewolves": [w.agent_id for w in werewolves],
            "villagers": [v.agent_id for v in villagers]
        }
        
        self.logger.log_system("end", f"Checking victory condition: {game_status}")
        
        # 狼人数量大于等于村民数量，狼人胜利
        if len(werewolves) >= len(villagers):
            self.logger.log_system("end", "Werewolves win - equal or more werewolves than villagers")
            return "werewolves"
        
        # 没有狼人，村民胜利
        if len(werewolves) == 0:
            self.logger.log_system("end", "Villagers win - no werewolves left")
            return "villagers"
        
        # 达到最大天数，平局
        if self.game_state["day"] >= self.config["game"].get("max_days", 30):
            self.logger.log_system("end", "Draw - reached maximum days")
            return "draw"
        
        # 游戏继续
        self.logger.log_system("game", "Game continues - no victory condition met")
        return None

    def run_game(self):
        """
        运行完整游戏
        """
        print()
        print('='*196)
        print()
        print('='*91, 'WEREWOLF GAME', '='*90)
        print()
        print('='*91, 'WRITEN BY SAM', '='*90)
        print()
        print('='*196)
        print()

        self.initialize_game()
        
        while True:
            # 夜间阶段
            self.run_night_phase()
            
            # 检查胜利条件
            winner = self.check_victory_condition()
            if winner:
                self.logger.log_system("end", f"Game ended. Winner: {winner}")
                break
            
            # 白天阶段
            self.run_day_phase()
            
            # 检查胜利条件
            winner = self.check_victory_condition()
            if winner:
                self.logger.log_system("end", f"Game ended. Winner: {winner}")
                break
        
        self.logger.log_system("end", "Game finished")

    def _update_seer_check_info(self, seer_check_result: Dict[str, Any]):
        """
        更新预言家查验信息到预言家的记忆中
        
        Args:
            seer_check_result: 预言家查验结果
        """
        check_info = f"第{self.game_state['day']}天查验{seer_check_result['target']}号，他的身份是{seer_check_result['role']}"
        
        # 仅为预言家创建记忆更新信息
        memory_update_info = {
            "memory_updates": {
                "short_memory_add": [check_info],
                "prediction_adjust": []
            }
        }
        
        # 更新预言家的记忆
        for agent in self.agents:
            if agent.role == "seer" and agent.agent_id in self.game_state["alive_agents"]:
                agent.update_memory(memory_update_info, "night")
                break

    def _update_witch_skill_info(self, witch_actions: List[Dict[str, Any]]):
        """
        更新女巫技能使用情况到女巫的记忆中
        
        Args:
            witch_actions: 女巫行动列表
        """
        skill_info_parts = []
        for action in witch_actions:
            if action["type"] == "witch_save":
                skill_info_parts.append(f"第{self.game_state['day']}天使用解药救治{action['target']}号")
            elif action["type"] == "witch_poison":
                skill_info_parts.append(f"第{self.game_state['day']}天使用毒药毒杀{action['target']}号")
        
        if skill_info_parts:
            skill_info = "女巫技能使用情况: " + "; ".join(skill_info_parts)
            
            # 仅为女巫创建记忆更新信息
            memory_update_info = {
                "memory_updates": {
                    "short_memory_add": [skill_info],
                    "prediction_adjust": []
                }
            }
            
            # 更新女巫的记忆
            for agent in self.agents:
                if agent.role == "witch" and agent.agent_id in self.game_state["alive_agents"]:
                    agent.update_memory(memory_update_info, "night")
                    break
