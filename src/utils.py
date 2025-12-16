import yaml
import json
from typing import Dict, Any, List
import random
import logger


def load_config(config_path: str) -> Dict[str, Any]:
    """
    加载配置文件
    
    Args:
        config_path: 配置文件路径
        
    Returns:
        配置字典
    """
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def parse_llm_response(response_text: str) -> Dict[str, Any]:
    """
    解析LLM响应文本为JSON对象
    
    Args:
        response_text: LLM响应文本
        
    Returns:
        解析后的JSON对象
    """
    try:
        # 移除可能的额外文本，只保留JSON部分
        # 查找第一个 '{' 和最后一个 '}'
        start = response_text.find('{')
        end = response_text.rfind('}') + 1
        
        if start != -1 and end > start:
            json_text = response_text[start:end]
            #logger.debug(f"Parsing JSON: {json_text}")
            return json.loads(json_text)
        else:
            raise ValueError("No valid JSON found in response")
    except json.JSONDecodeError as e:
        #logger.error(f"Failed to parse JSON: {e}")
        #logger.error(f"Response text: {response_text}")
        raise ValueError(f"Failed to parse JSON: {e}")


def assign_roles(roles_config: List[Dict[str, Any]], total_agents: int) -> List[Dict[str, Any]]:
    """
    根据配置分配角色给Agent
    
    Args:
        roles_config: 角色配置列表
        total_agents: 总Agent数
        
    Returns:
        分配好角色的Agent列表
    """
    agents = []
    role_pool = []
    
    # 构建角色池
    for role_config in roles_config:
        role_name = role_config["name"]
        count = role_config["count"]
        abilities = role_config.get("abilities", [])
        
        for _ in range(count):
            role_pool.append({
                "role": role_name,
                "abilities": abilities
            })
    
    # 检查角色总数是否匹配
    if len(role_pool) != total_agents:
        raise ValueError(f"Role count mismatch: expected {total_agents}, got {len(role_pool)}")
    
    # 随机分配座位
    random.shuffle(role_pool)
    
    # 创建Agent列表
    for i, role_info in enumerate(role_pool):
        agent = {
            "agent_id": i + 1,
            "role": role_info["role"],
            "abilities": role_info["abilities"],
            "seat": i + 1
        }
        
        # 设置阵营
        if role_info["role"] == "werewolf":
            agent["team"] = "werewolves"
        else:
            agent["team"] = "villagers"
            
        agents.append(agent)
    
    return agents
