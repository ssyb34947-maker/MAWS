from typing import Dict, List, Any, Optional
from agent import WerewolfAgent
from logger import GameLogger
from utils import load_config, assign_roles, parse_llm_response
import random
import json
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
            "current_speaker": None,  # 当前发言人
            "speaking_order": [],  # 发言顺序
            "last_night_result": None,  # 昨晚结果
            "current_voting": {}  # 当前投票情况
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
        from utils import parse_llm_response
        
        class RealAgent(WerewolfAgent):
            def __init__(self, agent_id: int, role: str, team: str, 
                         model_config: Dict[str, Any], prompt_template: str):
                super().__init__(agent_id, role, team, model_config, prompt_template)
                self.model_adapter = ModelsAdapter(model_config)
                #self.system_prompt = self._build_prompt
            
            def think(self, night_or_day: str, game_state: Dict[str, Any]) -> Dict[str, Any]:
                # 构建提示词
                prompt = self._build_prompt(night_or_day, game_state)
                
                # 记录提示词用于调试
                # logger.debug(f"Agent {self.agent_id} prompt:\n{prompt}")
                
                # 调用模型
                response_text = self.model_adapter.call_model(prompt)
                
                # 记录模型响应用于调试
                # logger.debug(f"Agent {self.agent_id} response:\n{response_text}")
                
                # 解析响应
                try:
                    return parse_llm_response(response_text)
                except Exception as e:
                    logger.error(f"Error parsing LLM response for agent {self.agent_id}: {e}")
                    # 返回默认响应
                    return {
                        "agent_id": self.agent_id,
                        "role_claim": None,
                        "prediction": {},
                        "memory_updates": {
                            "short_memory_add": [],
                            "prediction_adjust": []
                        },
                        "speech": f"我是{self.agent_id}号玩家",
                        "action": {
                            "type": "none",
                            "target": None
                        }
                    }
                
            def speak(self, thought: Dict[str, Any], game_state: Dict[str, Any]) -> str:
                return thought.get("speech", "")
                
            def act(self, thought: Dict[str, Any]) -> Dict[str, Any]:
                return thought.get("action", {"type": "none", "target": None})
                
            def _generate_role_allocation_info(self) -> str:
                """
                动态生成本局游戏的角色分配信息
                
                Returns:
                    格式化后的角色分配信息字符串
                """
                # 统计各角色数量
                role_counts = {}
                for agent in self.game_engine_ref.agents:
                    role = agent.role
                    role_counts[role] = role_counts.get(role, 0) + 1
                
                # 生成描述文本
                role_descriptions = []
                role_description_map = {
                    "werewolf": "狼人",
                    "villager": "平民",
                    "seer": "预言家",
                    "witch": "女巫",
                    "hunter": "猎人"
                }
                
                for role, count in role_counts.items():
                    chinese_role = role_description_map.get(role, role)
                    role_descriptions.append(f"{count}个{chinese_role}")
                
                return "、".join(role_descriptions)
                
            def _generate_night_action_order(self) -> str:
                """
                生成夜晚行动顺序信息
                
                Returns:
                    格式化后的夜晚行动顺序信息字符串
                """
                action_order = [
                    "1. 狼人：互相确认身份并选择击杀目标",
                    "2. 预言家：查验一名玩家身份，可以知道对方是好人还是狼人",
                    "3. 女巫：选择是否使用解药救人或使用毒药杀人",
                    "4. 猎人：无夜间行动"
                ]
                return "\n".join(action_order)
                
            def _build_prompt(self, night_or_day: str, game_state: Dict[str, Any]) -> str:
                # 根据角色加载对应的提示词模板
                role_template_file = os.path.join(self.project_root, "prompts", f"{self.role}_role.txt")
                try:
                    with open(role_template_file, "r", encoding="utf-8") as f:
                        prompt = f.read()
                except FileNotFoundError:
                    # 如果找不到角色特定的模板，则使用通用模板
                    template_file = os.path.join(self.project_root, self.config["prompt"]["template_file"])
                    if not os.path.exists(template_file):
                        # fallback to default location
                        template_file = os.path.join(self.project_root, "prompts", "agent_template.txt")
                    with open(template_file, "r", encoding="utf-8") as f:
                        prompt = f.read()
                
                # 替换模板中的变量
                prompt = prompt.replace("agent_id", str(self.agent_id))
                prompt = prompt.replace("role", self.role)
                prompt = prompt.replace("team", self.team)
                prompt = prompt.replace("seat", str(self.agent_id))
                
                # 添加游戏状态信息
                visible_game_state = f"当前阶段: {night_or_day}\n存活玩家: {game_state['alive_agents']}\n已淘汰玩家: {game_state.get('eliminated_agents', [])}"
                prompt = prompt.replace("visible_game_state", visible_game_state)
                
                # 添加记忆信息
                short_memory_str = "\n".join(self.short_memory[-5:]) if self.short_memory else "无"
                prompt = prompt.replace("short_memory", short_memory_str)
                
                prediction_memory_str = json.dumps(self.prediction_memory, ensure_ascii=False, indent=2) if self.prediction_memory else "无"
                prompt = prompt.replace("prediction_memory", prediction_memory_str)
                
                # 如果是狼人，添加队友信息
                if self.role == "werewolf":
                    werewolf_teammates = [a.agent_id for a in self.game_engine_ref.agents 
                                          if a.role == "werewolf" and a.agent_id != self.agent_id 
                                          and a.agent_id in self.game_engine_ref.game_state["alive_agents"]]
                    teammates_str = ", ".join(map(str, werewolf_teammates)) if werewolf_teammates else "无"
                    prompt = prompt.replace("known_teammates", teammates_str)
                else:
                    prompt = prompt.replace("known_teammates", "无")
                
                # 动态生成本局游戏的角色分配信息
                role_allocation_info = self._generate_role_allocation_info()
                prompt = prompt.replace("role_allocation_info", role_allocation_info)
                
                # 生成夜晚行动顺序信息
                night_action_order = self._generate_night_action_order()
                prompt = prompt.replace("night_action_order", night_action_order)
                
                return prompt
        
        # 获取模型配置
        # 根据agent_id选择模型，实现每个模型2个Agent
        model_names = list(self.config["models"]["adapters"].keys())
        model_index = (agent_info["agent_id"] - 1) % len(model_names)
        selected_model = model_names[model_index]
        model_config = self.config["models"]["adapters"][selected_model]
        
        agent = RealAgent(
            agent_id=agent_info["agent_id"],
            role=agent_info["role"],
            team=agent_info["team"],
            model_config=model_config,
            prompt_template=""  # 不使用这个参数，因为我们直接在_build_prompt中加载模板
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
            
            # 每个狼人都参与讨论
            for werewolf in werewolves:
                # 构建特殊的狼人私聊提示词
                private_prompt = self._build_werewolf_private_prompt(werewolf, private_context)
                logger.debug(f"Werewolf {werewolf.agent_id} private chat prompt:\n{private_prompt}")
                private_response = werewolf.model_adapter.call_model(private_prompt)
                #logger.debug(f"Werewolf {werewolf.agent_id} private chat response:\n{private_response}")
                
                # 解析狼人的响应以提取发言和解释
                try:
                    parsed_response = json.loads(private_response)
                    message_content = f"{parsed_response.get('speech', '')}。原因是：{parsed_response.get('action', {}).get('explain', '')}"
                except json.JSONDecodeError:
                    # 如果解析失败，使用原始响应
                    message_content = private_response
                
                # 将私聊内容添加到记录中
                private_message = {
                    "sender": werewolf.agent_id,
                    "message": message_content,
                    "timestamp": self.game_state["day"]
                }
                self.game_state["werewolf_private_chat"].append(private_message)
                self.logger.log("night", werewolf.agent_id, "private_chat", private_response)
        
        # 狼人集体决策 - 基于私聊信息做出最终决策
        werewolf_actions = []
        if len(werewolves) >= 1:
            # 构建狼人决策上下文
            decision_context = {
                "private_chat_history": self.game_state["werewolf_private_chat"],
                "alive_agents": self.game_state["alive_agents"],
                "eliminated_agents": self.game_state["eliminated_agents"],
                "day": self.game_state["day"]
            }
            
            # 收集所有狼人的决策
            wolf_votes = {}  # target -> vote count
            first_wolf_target = None
            
            for i, werewolf in enumerate(werewolves):
                # 构建决策提示词
                decision_prompt = self._build_werewolf_decision_prompt(werewolf, decision_context)
                #logger.debug(f"Werewolf {werewolf.agent_id} decision prompt:\n{decision_prompt}")
                decision_response = werewolf.model_adapter.call_model(decision_prompt)
                #logger.debug(f"Werewolf {werewolf.agent_id} decision response:\n{decision_response}")
                
                # 解析简单的数字投票
                try:
                    # 尝试提取数字
                    target = int(''.join(filter(str.isdigit, decision_response)))
                    if target not in self.game_state["alive_agents"]:
                        raise ValueError(f"Target {target} is not in alive agents")
                        
                    # 记录第一个狼人的选择
                    if i == 0:
                        first_wolf_target = target
                        
                    # 记录投票
                    wolf_votes[target] = wolf_votes.get(target, 0) + 1
                    
                    # 构造标准动作格式
                    action = {
                        "type": "night_kill",
                        "target": target,
                        "explain": f"Werewolf {werewolf.agent_id} voted to kill player {target}"
                    }
                    werewolf_actions.append(action)
                    self.logger.log_agent_action("night", werewolf.agent_id, action)
                    
                except Exception as e:
                    logger.error(f"Error parsing werewolf {werewolf.agent_id} decision: {e}")
                    # 使用默认动作
                    action = {"type": "none", "target": None}
                    werewolf_actions.append(action)
                    self.logger.log_agent_action("night", werewolf.agent_id, action)
            
            # 处理平票情况，选择第一个狼人的目标
            if wolf_votes and len(wolf_votes) > 1:
                max_votes = max(wolf_votes.values())
                targets_with_max_votes = [target for target, votes in wolf_votes.items() if votes == max_votes]
                
                if len(targets_with_max_votes) > 1 and first_wolf_target is not None:
                    # 平票情况，使用第一个狼人的选择
                    logger.info(f"Werewolf voting tie resolved using first werewolf's choice: {first_wolf_target}")
                    # 更新所有狼人的动作为第一个狼人的选择
                    for i in range(len(werewolf_actions)):
                        werewolf_actions[i] = {
                            "type": "night_kill",
                            "target": first_wolf_target,
                            "explain": f"Werewolf {werewolves[i].agent_id} voted to kill player {first_wolf_target} (tie resolved)"
                        }
        
        # 2. 预言家
        seers = [agent for agent in self.agents if agent.role == "seer" and agent.agent_id in self.game_state["alive_agents"]]
        seer_actions = []
        for seer in seers:
            thought = seer.think("night", self.game_state)
            action = seer.act(thought)
            seer_actions.append(action)
            self.logger.log_agent_action("night", seer.agent_id, action)
        
        # 3. 女巫
        witches = [agent for agent in self.agents if agent.role == "witch" and agent.agent_id in self.game_state["alive_agents"]]
        witch_actions = []
        for witch in witches:
            thought = witch.think("night", self.game_state)
            action = witch.act(thought)
            witch_actions.append(action)
            self.logger.log_agent_action("night", witch.agent_id, action)
        
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
        witch_poison_target = None
        if witch_actions:
            for action in witch_actions:
                if action["type"] == "witch_save" and action["target"] is not None:
                    witch_save_target = action["target"]
                elif action["type"] == "witch_poison" and action["target"] is not None:
                    witch_poison_target = action["target"]
        
        # 应用技能效果
        eliminated_players = []
        
        # 女巫救人（如果选择救人且目标是被狼人击杀的玩家）
        final_wolf_target = wolf_target
        if witch_save_target is not None and witch_save_target == wolf_target:
            final_wolf_target = None  # 救下被击杀的玩家
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
            self.logger.log_system("night", f"Agent {witch_poison_target} was poisoned by witch")
        
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
            thought = agent.think("day", self.game_state)
            speech = agent.speak(thought, self.game_state)
            speeches[agent_id] = speech
            
            # 添加到公共交流列表
            speech_record = {
                "speaker": agent_id,
                "content": speech,
                "timestamp": self.game_state['day']
            }
            self.game_state["public_speeches"].append(speech_record)
            self.logger.log_agent_speech("day", agent_id, speech)
        
        # 将本轮发言添加到所有存活Agent的短期记忆中
        self._update_agents_short_term_memory_after_speech()
        
        # 投票
        votes = {}
        self.game_state["current_voting"] = {}  # 重置当前投票状态
        
        # 收集所有玩家的投票
        for agent_id in sorted(self.game_state["alive_agents"]):
            agent = next(a for a in self.agents if a.agent_id == agent_id)
            vote_target = self._get_player_vote(agent, "day")
            if vote_target is not None:
                votes[agent_id] = vote_target
                self.game_state["current_voting"][agent_id] = vote_target
                self.logger.log_agent_action("day", agent_id, {
                    "type": "vote",
                    "target": vote_target,
                    "explain": f"Player {agent_id} voted to eliminate player {vote_target}"
                })
        
        # 白天结算
        self._settle_day(votes)

    def _get_player_vote(self, agent, phase: str):
        """
        获取玩家投票
        
        Args:
            agent: 投票的Agent
            phase: 投票阶段 ("day" 或 "night")
            
        Returns:
            投票目标玩家ID，如果无法解析则返回None
        """
        # 构建投票提示词
        vote_prompt = self._build_vote_prompt(agent, phase)
        # logger.debug(f"Agent {agent.agent_id} vote prompt:\n{vote_prompt}")
        
        # 获取投票响应
        vote_response = agent.model_adapter.call_model(vote_prompt)
        # logger.debug(f"Agent {agent.agent_id} vote response:\n{vote_response}")
        
        # 解析简单的数字投票
        try:
            # 尝试提取数字
            target = int(''.join(filter(str.isdigit, vote_response)))
            if target not in self.game_state["alive_agents"]:
                raise ValueError(f"Target {target} is not in alive agents")
            return target
        except Exception as e:
            logger.error(f"Error parsing vote from agent {agent.agent_id}: {e}")
            return None

    def _build_vote_prompt(self, agent, phase: str):
        """
        构建投票提示词
        
        Args:
            agent: 投票的Agent
            phase: 投票阶段
            
        Returns:
            构建好的提示词
        """
        prompt = f"""
你是{agent.agent_id}号玩家。
当前是{self.game_state['day']}天的{phase}阶段。
存活玩家: {self.game_state['alive_agents']}
已淘汰玩家: {self.game_state.get('eliminated_agents', [])}

请根据游戏情况，选择一个你认为是狼人的玩家进行投票。现在你不是和队友讨论，而是做决策。
请只输出一个数字，代表你要投票的玩家编号，不要包含其他任何文字。
例如，如果你想投票给3号玩家，只需输出：3
可选择的玩家编号：{self.game_state['alive_agents']}
"""
        
        # 添加白天特有的信息
        if phase == "day":
            # 添加白天的发言记录
            prompt += "\n近期发言记录:\n"
            for speech_record in self.game_state["public_speeches"]:
                prompt += f"{speech_record['speaker']}号玩家: {speech_record['content']}\n"
        
        return prompt

    def _update_agents_short_term_memory_after_speech(self):
        """
        在白天发言结束后，将本轮发言添加到所有存活Agent的短期记忆中
        """
        # 构造本轮发言的总结
        speech_summary = "最近一轮发言内容:\n"
        for speech_record in self.game_state["public_speeches"]:
            speech_summary += f"{speech_record['speaker']}号玩家: {speech_record['content']}\n"
        
        # 为每个存活的Agent创建记忆更新信息
        memory_update_info = {
            "memory_updates": {
                "short_memory_add": [speech_summary],
                "prediction_adjust": []
            }
        }
        
        # 更新所有存活Agent的记忆
        for agent in self.agents:
            if agent.agent_id in self.game_state["alive_agents"]:
                agent.update_memory(memory_update_info, "day")

    def _settle_day(self, votes: Dict[int, int]):
        """
        白天结算
        
        Args:
            votes: 投票结果字典
        """
        # 统计投票
        vote_count = {}
        for target in votes.values():
            vote_count[target] = vote_count.get(target, 0) + 1
        
        # 确定最高票数目标
        target = None
        max_votes = 0
        if vote_count:
            target, max_votes = max(vote_count.items(), key=lambda x: x[1])
        
        # 淘汰最高票数玩家
        eliminated_player = None
        if target is not None and target in self.game_state["alive_agents"]:
            self.game_state["alive_agents"].remove(target)
            self.game_state["eliminated_agents"].append(target)
            eliminated_player = target
            self.logger.log_system("day", f"Agent {target} was eliminated by voting")
        
        self.logger.log_system("day", "Day settlement completed")
        
        # 更新所有Agent的环境感知
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

    def _generate_role_allocation_info_for_agent(self, agent) -> str:
        """
        为指定Agent生成本局游戏的角色分配信息
        
        Args:
            agent: Agent实例
            
        Returns:
            格式化后的角色分配信息字符串
        """
        # 统计各角色数量
        role_counts = {}
        for a in self.agents:
            role = a.role
            role_counts[role] = role_counts.get(role, 0) + 1
        
        # 生成描述文本
        role_descriptions = []
        role_description_map = {
            "werewolf": "狼人",
            "villager": "平民",
            "seer": "预言家",
            "witch": "女巫",
            "hunter": "猎人"
        }
        
        for role, count in role_counts.items():
            chinese_role = role_description_map.get(role, role)
            role_descriptions.append(f"{count}个{chinese_role}")
        
        return "本局初始化角色配置:"+"、".join(role_descriptions)
        
    def _generate_night_action_order_for_agent(self, agent) -> str:
        """
        为指定Agent生成夜晚行动顺序信息
        
        Args:
            agent: Agent实例
            
        Returns:
            格式化后的夜晚行动顺序信息字符串
        """
        action_order = [
            "1. 狼人：互相确认身份并选择击杀目标",
            "2. 预言家：查验一名玩家身份，可以知道对方是好人还是狼人",
            "3. 女巫：选择是否使用解药救人或使用毒药杀人",
            "4. 猎人：无夜间行动"
        ]
        return "\n".join(action_order)

    def _build_werewolf_private_prompt(self, werewolf_agent, context):
        """
        构建狼人私聊提示词
        
        Args:
            werewolf_agent: 狼人Agent
            context: 上下文信息
            
        Returns:
            构建好的提示词
        """
        # 加载狼人角色提示词模板
        role_template_file = os.path.join(werewolf_agent.project_root, "prompts", f"{werewolf_agent.role}_role.txt")
        try:
            with open(role_template_file, "r", encoding="utf-8") as f:
                base_prompt = f.read()
        except FileNotFoundError:
            # 如果找不到角色特定的模板，则使用通用模板
            template_file = os.path.join(werewolf_agent.project_root, werewolf_agent.config["prompt"]["template_file"])
            if not os.path.exists(template_file):
                # fallback to default location
                template_file = os.path.join(werewolf_agent.project_root, "prompts", "agent_template.txt")
            with open(template_file, "r", encoding="utf-8") as f:
                base_prompt = f.read()
        
        # 添加私聊专用内容
        private_discussion_prompt = f"""

你们需要讨论今晚要击杀的目标。

当前游戏信息：
- 第{context['day']}天夜晚
- 存活玩家: {context['alive_agents']}
- 已淘汰玩家: {context['eliminated_agents']}

狼人团队成员之间可以进行私聊讨论，请与其他狼人协商决定今晚的击杀目标。

历史私聊记录：
"""
        for msg in context['private_chat_history']:
            private_discussion_prompt += f"{msg['sender']}号玩家: {msg['message']}\n"
        
        # 合并基础提示词和私聊专用内容
        prompt = base_prompt + private_discussion_prompt
        
        # 替换模板中的变量
        prompt = prompt.replace("agent_id", str(werewolf_agent.agent_id))
        prompt = prompt.replace("role", werewolf_agent.role)
        prompt = prompt.replace("team", werewolf_agent.team)
        prompt = prompt.replace("seat", str(werewolf_agent.agent_id))
        
        # 添加游戏状态信息
        visible_game_state = f"当前阶段: night\n存活玩家: {context['alive_agents']}\n已淘汰玩家: {context.get('eliminated_agents', [])}"
        prompt = prompt.replace("visible_game_state", visible_game_state)
        
        # 添加记忆信息
        short_memory_str = "\n".join(werewolf_agent.short_memory[-5:]) if werewolf_agent.short_memory else "无"
        prompt = prompt.replace("short_memory", short_memory_str)
        
        prediction_memory_str = json.dumps(werewolf_agent.prediction_memory, ensure_ascii=False, indent=2) if werewolf_agent.prediction_memory else "无"
        prompt = prompt.replace("prediction_memory", prediction_memory_str)
        
        # 添加狼人队友信息
        werewolf_teammates = [a.agent_id for a in werewolf_agent.game_engine_ref.agents 
                              if a.role == "werewolf" and a.agent_id != werewolf_agent.agent_id 
                              and a.agent_id in werewolf_agent.game_engine_ref.game_state["alive_agents"]]
        teammates_str = ", ".join(map(str, werewolf_teammates)) if werewolf_teammates else "无"
        prompt = prompt.replace("known_teammates", teammates_str)
        
        # 动态生成本局游戏的角色分配信息
        role_allocation_info = self._generate_role_allocation_info_for_agent(werewolf_agent)
        
        prompt = prompt.replace("werewolf_allocation_info", role_allocation_info)
        
        # 生成夜晚行动顺序信息
        night_action_order = self._generate_night_action_order_for_agent(werewolf_agent)
        prompt = prompt.replace("night_action_order", night_action_order)
        
        return prompt

    def _build_werewolf_decision_prompt(self, werewolf_agent, context):
        """
        构建狼人决策提示词
        
        Args:
            werewolf_agent: 狼人Agent
            context: 上下文信息
            
        Returns:
            构建好的提示词
        """
        # 加载狼人角色提示词模板
        role_template_file = os.path.join(werewolf_agent.project_root, "prompts", f"{werewolf_agent.role}_role.txt")
        try:
            with open(role_template_file, "r", encoding="utf-8") as f:
                base_prompt = f.read()
        except FileNotFoundError:
            # 如果找不到角色特定的模板，则使用通用模板
            template_file = os.path.join(werewolf_agent.project_root, werewolf_agent.config["prompt"]["template_file"])
            if not os.path.exists(template_file):
                # fallback to default location
                template_file = os.path.join(werewolf_agent.project_root, "prompts", "agent_template.txt")
            with open(template_file, "r", encoding="utf-8") as f:
                base_prompt = f.read()
        
        # 添加决策专用内容
        decision_prompt = f"""

你们已经完成了内部讨论，现在需要基于讨论结果做出最终的击杀决策。

当前游戏信息：
- 第{context['day']}天夜晚
- 存活玩家: {context['alive_agents']}
- 已淘汰玩家: {context['eliminated_agents']}

狼人私聊讨论记录：
"""
        for msg in context['private_chat_history']:
            decision_prompt += f"{msg['sender']}号玩家: {msg['message']}\n"
        
        decision_prompt += f"""
请基于以上讨论内容，选择一个玩家进行击杀。
请只输出一个数字，代表你要击杀的玩家编号，不要包含其他任何文字。
例如，如果你想击杀3号玩家，只需输出：3
可选择的玩家编号：{context['alive_agents']}
"""
        
        # 合并基础提示词和决策专用内容
        prompt = base_prompt + decision_prompt
        
        # 替换模板中的变量
        prompt = prompt.replace("agent_id", str(werewolf_agent.agent_id))
        prompt = prompt.replace("role", werewolf_agent.role)
        prompt = prompt.replace("team", werewolf_agent.team)
        prompt = prompt.replace("seat", str(werewolf_agent.agent_id))
        
        # 添加游戏状态信息
        visible_game_state = f"当前阶段: night\n存活玩家: {context['alive_agents']}\n已淘汰玩家: {context.get('eliminated_agents', [])}"
        prompt = prompt.replace("visible_game_state", visible_game_state)
        
        # 添加记忆信息
        short_memory_str = "\n".join(werewolf_agent.short_memory[-5:]) if werewolf_agent.short_memory else "无"
        prompt = prompt.replace("short_memory", short_memory_str)
        
        prediction_memory_str = json.dumps(werewolf_agent.prediction_memory, ensure_ascii=False, indent=2) if werewolf_agent.prediction_memory else "无"
        prompt = prompt.replace("prediction_memory", prediction_memory_str)
        
        # 添加狼人队友信息
        werewolf_teammates = [a.agent_id for a in werewolf_agent.game_engine_ref.agents 
                              if a.role == "werewolf" and a.agent_id != werewolf_agent.agent_id 
                              and a.agent_id in werewolf_agent.game_engine_ref.game_state["alive_agents"]]
        teammates_str = ", ".join(map(str, werewolf_teammates)) if werewolf_teammates else "无"
        prompt = prompt.replace("known_teammates", teammates_str)
        
        # 动态生成本局游戏的角色分配信息
        role_allocation_info = self._generate_role_allocation_info_for_agent(werewolf_agent)
        prompt = prompt.replace("role_allocation_info", role_allocation_info)
        
        # 生成夜晚行动顺序信息
        night_action_order = self._generate_night_action_order_for_agent(werewolf_agent)
        prompt = prompt.replace("night_action_order", night_action_order)
        
        return prompt

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
