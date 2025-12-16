from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import json
import random
import asyncio
import threading
import sys
import os
import importlib.util
from queue import Queue

# 确保项目根目录在Python路径中
project_root = os.path.dirname(os.path.dirname(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
    print(f"Added project root to sys.path: {project_root}")
    print(f"Current sys.path: {sys.path}")

app = FastAPI()

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 创建消息队列用于游戏引擎和WebSocket之间的通信
message_queue = Queue()

# 确保src目录在Python路径中
src_dir = os.path.join(project_root, 'src')
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)
    print(f"Added src directory to sys.path: {src_dir}")
    
# 验证必要的文件存在
required_files = [
    os.path.join(src_dir, 'agent.py'),
    os.path.join(src_dir, 'game_engine.py'),
    os.path.join(src_dir, 'logger.py')
]
for file_path in required_files:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Required file not found: {file_path}")
    else:
        print(f"Found required file: {file_path}")
        
# 手动导入agent模块
agent_spec = importlib.util.spec_from_file_location("agent", os.path.join(src_dir, "agent.py"))
agent_module = importlib.util.module_from_spec(agent_spec)
agent_spec.loader.exec_module(agent_module)

# 手动导入game_engine模块
game_engine_spec = importlib.util.spec_from_file_location("game_engine", os.path.join(src_dir, "game_engine.py"))
game_engine_module = importlib.util.module_from_spec(game_engine_spec)
game_engine_spec.loader.exec_module(game_engine_module)
GameEngine = game_engine_module.GameEngine

# 创建GameRunner类
class GameRunner:
    def __init__(self, message_queue):
        self.message_queue = message_queue
        self.engine = None
        
    def run_game(self):
        """
        在独立线程中运行游戏引擎，将日志输出通过消息队列发送给WebSocket
        """
        try:
            print(f"Current working directory: {os.getcwd()}")
            print(f"Project root: {project_root}")
            print(f"sys.path: {sys.path}")
            
            # 创建游戏引擎实例，使用正确的配置文件路径
            config_path = os.path.join(project_root, "config.yaml")
            print(f"Using config file path: {config_path}")
            if not os.path.exists(config_path):
                raise FileNotFoundError(f"Config file not found: {config_path}")
            # 传递project_root给GameEngine
            self.engine = GameEngine(config_path)
            # 确保project_root指向正确的项目根目录
            self.engine.project_root = os.path.join(project_root, '狼人杀')
            
            # 重写logger的log方法，将日志推送到前端
            original_log = self.engine.logger.log
            
            def intercepted_log(phase: str, agent_id: int, log_type: str, content: any):
                # 调用原始日志记录
                original_log(phase, agent_id, log_type, content)
                
                # 将日志信息发送到前端
                message = {
                    "type": "game_log",
                    "phase": phase,
                    "agent_id": agent_id,
                    "log_type": log_type,
                    "content": content
                }
                self.message_queue.put(message)
            
            # 替换日志方法
            self.engine.logger.log = intercepted_log
            
            # 运行游戏
            self.engine.run_game()
            
            # 游戏结束后发送结束消息
            self.message_queue.put({
                "type": "status_update",
                "message": "游戏已结束"
            })
        except Exception as e:
            error_msg = f"Error in GameRunner.run_game: {str(e)}"
            print(error_msg)
            import traceback
            traceback.print_exc()
            self.message_queue.put({
                "type": "status_update",
                "message": error_msg
            })

# 创建GameRunner实例
game_runner = GameRunner(message_queue)

# 启动日志处理循环
@app.on_event("startup")
async def startup_event():
    # 启动后台任务来处理消息队列
    asyncio.create_task(process_message_queue())

async def process_message_queue():
    """
    后台任务：从消息队列中获取游戏日志并推送到所有WebSocket客户端
    """
    while True:
        try:
            # 从队列获取消息（非阻塞）
            if not message_queue.empty():
                message = message_queue.get_nowait()
                await manager.broadcast(message)
            
            # 短暂休眠以避免高CPU占用
            await asyncio.sleep(0.1)
        except Exception as e:
            print(f"Error in message queue processing: {e}")
            await asyncio.sleep(1)

# 挂载前端静态文件到 /static 路径，避免与WebSocket端点冲突
app.mount("/static", StaticFiles(directory="../frontend"), name="static")

# 根路径路由，用于返回前端主页面
@app.get("/")
async def get_home():
    with open("../frontend/index.html", "r", encoding="utf-8") as f:
        return f.read()

# 游戏状态管理
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self.game_state = {}
        self.engine = None  # 存储游戏引擎实例
        self.game_thread = None  # 存储游戏线程

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message))
            except Exception:
                disconnected.append(connection)
        
        # 清理断开的连接
        for conn in disconnected:
            self.disconnect(conn)

manager = ConnectionManager()

# 角色列表
ROLES = ["村民", "村民", "村民", "村民", "狼人", "狼人", "预言家", "女巫"]

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message["type"] == "start_game":
                # 启动游戏线程
                if manager.game_thread is None or not manager.game_thread.is_alive():
                    manager.game_thread = threading.Thread(target=game_runner.run_game)
                    manager.game_thread.daemon = True
                    manager.game_thread.start()
                    await manager.broadcast({
                        "type": "status_update",
                        "message": "游戏引擎已启动..."
                    })
                else:
                    await manager.broadcast({
                        "type": "status_update",
                        "message": "游戏已在运行中..."
                    })
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"Error: {e}")
        await manager.broadcast({
            "type": "status_update",
            "message": f"服务器错误: {str(e)}"
        })

async def start_new_game():
    # 重置游戏状态
    manager.game_state = {
        "game_id": random.randint(1000, 9999),
        "players": list(range(1, 9)),
        "roles": {}
    }
    
    # 广播游戏开始
    await manager.broadcast({
        "type": "game_started",
        "game_id": manager.game_state["game_id"]
    })
    
    # 更新状态
    await manager.broadcast({
        "type": "status_update",
        "message": "游戏开始，正在分配角色..."
    })
    
    # 随机打乱角色
    shuffled_roles = ROLES.copy()
    random.shuffle(shuffled_roles)
    
    # 分配角色并广播
    for i, player_id in enumerate(manager.game_state["players"]):
        role = shuffled_roles[i]
        manager.game_state["roles"][player_id] = role
        
        # 给所有客户端发送角色分配消息
        await manager.broadcast({
            "type": "role_assigned",
            "player_id": player_id,
            "role": role
        })
        
        # 添加延迟使分配过程更真实
        await asyncio.sleep(0.5)
    
    # 最终状态更新
    await manager.broadcast({
        "type": "status_update",
        "message": f"角色分配完成！游戏正式开始"
    })
    
    # 发送示例聊天消息
    example_messages = [
        ("系统", "天黑请闭眼..."),
        ("系统", "狼人请睁眼，互相确认身份..."),
        ("系统", "狼人请选择要击杀的目标..."),
        ("系统", "狼人请闭眼..."),
        ("系统", "预言家请睁眼，选择查验对象..."),
        ("系统", "预言家请闭眼..."),
        ("系统", "女巫请睁眼，是否使用解药或毒药..."),
        ("系统", "女巫请闭眼..."),
        ("系统", "天亮了，昨晚是平安夜。大家依次发言讨论...")
    ]
    
    for sender, content in example_messages:
        await manager.broadcast({
            "type": "chat_message",
            "sender": sender,
            "content": content
        })
        await asyncio.sleep(1.5)