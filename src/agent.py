from typing import Dict, List, Any, Optional

try:
    from rulebook import build_agent_system_prompt
except ImportError:
    from .rulebook import build_agent_system_prompt
try:
    from loguru import logger
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)


class WerewolfAgent:
    """
    狼人杀游戏中的智能体基类
    
    Attributes:
        agent_id: Agent的座位号（从1开始）
        role: Agent的角色名称
        team: Agent所属阵营
        model_config: 模型配置字典
        prompt_template: 提示词模板
        short_memory: 短期记忆列表
        prediction_memory: 预测/信念内存字典
        system_memory: 系统内存，存储固定信息
        game_engine_ref: 对游戏引擎的引用，用于获取游戏状态
    """
    
    def __init__(
        self,
        agent_id: int,
        role: str,
        team: str,
        model_config: Dict[str, Any],
        prompt_template: str,
        role_allocation: Optional[Dict[str, int]] = None,
    ):
        self.agent_id = agent_id
        self.role = role
        self.team = team
        self.model_config = model_config
        self.prompt_template = prompt_template
        self.short_memory: List[str] = []
        self.prediction_memory: Dict[str, Any] = {}
        self.system_memory: Dict[str, Any] = {
            "role": role,
            "team": team,
            "role_allocation": role_allocation or {},
        }
        self.system_prompt = build_agent_system_prompt(
            agent_id=agent_id,
            role=role,
            team=team,
            role_allocation=role_allocation or {},
        )
        self.game_engine_ref = None

    def update_memory(self, settlement_info: Dict[str, Any], when: str):
        """
        系统在夜/日结算后调用，用来更新short_memory与prediction_memory
        
        Args:
            settlement_info: 结算信息
            when: "night" 或 "day"
        """
        try:
            # 更新短期记忆
            if "memory_updates" in settlement_info:
                memory_updates = settlement_info["memory_updates"]
                if "short_memory_add" in memory_updates:
                    for item in memory_updates["short_memory_add"]:
                        self.short_memory.append(item)
                
                # 更新预测区
                if "prediction_adjust" in memory_updates:
                    for adjust in memory_updates["prediction_adjust"]:
                        player = adjust["player"]
                        role = adjust["role"]
                        delta_confidence = adjust["delta_confidence"]
                        
                        if player in self.prediction_memory:
                            if self.prediction_memory[player]["role"] == role:
                                self.prediction_memory[player]["confidence"] += delta_confidence
                        else:
                            self.prediction_memory[player] = {
                                "role": role,
                                "confidence": delta_confidence
                            }
        except Exception as e:
            logger.error(f"Error updating memory for agent {self.agent_id}: {e}")

    def serialize(self) -> Dict[str, Any]:
        """
        序列化Agent状态用于日志或持久化
        
        Returns:
            包含Agent状态的字典
        """
        return {
            "id": self.agent_id,
            "role": self.role,
            "team": self.team,
            "system_memory": self.system_memory,
            "short_memory": self.short_memory,
            "prediction_memory": self.prediction_memory
        }

    def to_dict(self) -> Dict[str, Any]:
        """
        序列化Agent状态用于日志或持久化
        
        Returns:
            包含Agent状态的字典
        """
        return self.serialize()