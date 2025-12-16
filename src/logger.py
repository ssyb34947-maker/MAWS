import os
import json
from datetime import datetime
from typing import Dict, Any, Optional

try:
    from loguru import logger
except ImportError:
    # 如果loguru不可用，使用标准库logging
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    # 模拟loguru的add方法
    logger.add = lambda *args, **kwargs: None


class GameLogger:
    """
    游戏日志记录器
    """

    def __init__(self, log_file_pattern: str):
        """
        初始化日志记录器
        
        Args:
            log_file_pattern: 日志文件路径模式
        """
        # 创建logs目录（如果不存在）
        os.makedirs("logs", exist_ok=True)
        
        # 格式化日志文件路径
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file_path = log_file_pattern.format(timestamp=timestamp)
        
        # 配置loguru
        logger.add(log_file_path, rotation="10 MB", encoding="utf-8")
        
        self.log_file_path = log_file_path

    def log(self, phase: str, agent_id: Optional[int], log_type: str, content: Any):
        """
        记录日志条目
        
        Args:
            phase: 阶段 ("night"/"day"/"settlement"/"init"/"end")
            agent_id: Agent ID（可选）
            log_type: 日志类型 ("speech"/"action"/"system")
            content: 日志内容（文本或JSON）
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "phase": phase,
            "agent_id": agent_id,
            "type": log_type,
            "content": content
        }
        
        # 控制台输出
        #print(json.dumps(log_entry, ensure_ascii=False, indent=2))
        
        # 文件记录
        logger.info(json.dumps(log_entry, ensure_ascii=False))

    def log_system(self, phase: str, content: Any):
        """
        记录系统日志
        
        Args:
            phase: 阶段
            content: 日志内容
        """
        self.log(phase, None, "system", content)

    def log_agent_action(self, phase: str, agent_id: int, action: Dict[str, Any]):
        """
        记录Agent行为日志
        
        Args:
            phase: 阶段
            agent_id: Agent ID
            action: 行为内容
        """
        self.log(phase, agent_id, "action", action)

    def log_agent_speech(self, phase: str, agent_id: int, speech: str):
        """
        记录Agent发言日志
        
        Args:
            phase: 阶段
            agent_id: Agent ID
            speech: 发言内容
        """
        self.log(phase, agent_id, "speech", speech)