# 狼人杀游戏模拟器

一个基于LangChain和大型语言模型的狼人杀游戏模拟器，支持完全自动化的游戏流程。

## 功能特点

- 完全自动化的狼人杀游戏流程
- 支持多种角色：平民、狼人、预言家、女巫、猎人等
- 可配置的角色数量和游戏参数
- 多种大语言模型支持（OpenAI、DeepSeek、Qwen、Kimi等）
- 详细的日志记录和游戏过程追踪
- JSON格式的标准化LLM交互协议

## 项目结构

```
werewolf-sim/
├── config.yaml              # 游戏配置文件
├── requirements.txt         # Python依赖
├── README.md               # 项目说明文档
├── prompts/
│   └── agent_template.txt  # Agent提示词模板
├── src/
│   ├── main.py             # 主程序入口
│   ├── game_engine.py      # 游戏引擎
│   ├── agent.py            # Agent类定义
│   ├── models_adapter.py   # 模型适配器
│   ├── logger.py           # 日志系统
│   └── utils.py            # 工具函数
└── logs/                   # 日志文件目录
```

## 安装依赖

建议使用虚拟环境来隔离项目依赖：

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# macOS/Linux:
# source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

## 配置说明

在 `config.yaml` 中配置您的模型和游戏参数：

```yaml
# 示例配置
project:
  name: werewolf-sim
  random_seed: 42
models:
  default: openai
  adapters:
    openai:
      type: openai
      model: gpt-4o
      api_key: "YOUR_OPENAI_KEY"
      api_base: "https://api.openai.com/v1"
      temperature: 0.8
      max_tokens: 1024
```

## 运行游戏

### 后端启动
```bash
# 进入backend目录
cd backend

# 安装完整依赖（包含WebSocket支持）
pip install "uvicorn[standard]" fastapi

# 启动后端服务
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 前端访问
直接打开 frontend/index.html 文件即可访问游戏界面。

### 原有主程序运行
```bash
python src/main.py --config=config.yaml
```

## 扩展说明

### 添加新角色
1. 在 `config.yaml` 中添加角色配置
2. 实现角色相关的特殊能力逻辑

### 添加新模型
1. 在 `config.yaml` 中添加模型配置
2. 在 `models_adapter.py` 中实现适配器

### 修改游戏规则
在 `config.yaml` 中调整相关参数即可。

## 测试

项目包含单元测试，用于验证模型适配器和其他功能是否正常工作。

### 运行测试

```bash
# 运行所有测试
python -m pytest tests/

# 运行特定测试
python -m pytest tests/test_models_adapter.py
```

### 模型调用测试

要测试真实的大模型调用，请参考 `tests/README.md` 文件中的说明。

## 开发指南

### 项目组件说明

#### Agent类 (src/agent.py)
- `WerewolfAgent` 基类定义了所有Agent的接口
- 每个Agent都有自己的身份、阵营、短期记忆和预测区
- 核心方法包括：
  - `think()` - 思考并生成JSON格式的决策
  - `speak()` - 将思考转化为发言
  - `act()` - 执行具体行动
  - `update_memory()` - 更新记忆

#### 游戏引擎 (src/game_engine.py)
- 控制整个游戏流程
- 管理游戏状态
- 执行日夜阶段和结算
- 检查胜利条件

#### 模型适配器 (src/models_adapter.py)
- 统一不同模型的调用接口
- 支持OpenAI、HTTP和百炼平台等多种模型
- 提供批处理功能

#### 日志系统 (src/logger.py)
- 记录游戏过程到控制台和文件
- 支持结构化日志格式

#### 工具函数 (src/utils.py)
- 配置加载
- JSON解析
- 角色分配

### LLM交互协议

Agent与LLM之间的交互严格遵循JSON格式：

```json
{
  "agent_id": 1,
  "role_claim": null,
  "prediction": {
    "player_2": {"role": "werewolf", "confidence": 0.65},
    "player_5": {"role": "villager", "confidence": 0.4}
  },
  "memory_updates": {
    "short_memory_add": [
      "夜间看到 3 号 被淘汰（投票）",
      "2号 昨晚 发言可疑"
    ],
    "prediction_adjust": [
      {"player": 2, "role": "werewolf", "delta_confidence": 0.1}
    ]
  },
  "speech": "我觉得2号有嫌疑，因为……",
  "action": {
    "type": "vote" | "night_kill" | "divine_check" | "save" | "poison" | "final_shot" | "none",
    "target": 3,
    "explain": "理由文本，可选"
  }
}
```

### 游戏流程

1. 初始化：读取配置，分配角色，创建Agent
2. 循环执行：
   - 夜间阶段：特殊角色行动（预言家->狼人->女巫）
   - 夜间结算：处理行动结果
   - 白天阶段：发言和投票
   - 白天结算：处理投票结果
   - 检查胜利条件
3. 游戏结束：记录结果

### 可复现性

通过设置 `config.yaml` 中的 `random_seed` 参数确保游戏的可复现性。