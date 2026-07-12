"""
MAWS Backend - Multi-Agent Werewolf Simulator Web Service

Connects the React frontend to the real game engine and LLM models.
Provides WebSocket for real-time game state updates.
"""

import argparse
import asyncio
import json
import os
import sys
import threading
import time
from queue import Queue
from typing import Any, Dict, List, Optional
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Add project root and src to path (src files import each other without prefix)
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(project_root, 'src'))
sys.path.insert(0, project_root)

from game_engine import GameEngine

# ---------------------------------------------------------------------------
# Pre-defined visual data for up to 8 players (seat-number-indexed)
# ---------------------------------------------------------------------------

PLAYER_NAMES = [
    "",  # index 0 unused, seat numbers are 1-based
    "林间邮差", "磨坊学徒", "溪边药师", "钟楼守望",
    "北坡猎人", "南瓜店主", "铁匠老陈", "旅店老板娘",
]

PLAYER_POSITIONS = [
    None,
    {"x": 20, "y": 43},
    {"x": 48, "y": 35},
    {"x": 78, "y": 44},
    {"x": 22, "y": 79},
    {"x": 53, "y": 82},
    {"x": 82, "y": 80},
    {"x": 12, "y": 12},
    {"x": 86, "y": 14},
]

PLAYER_HOUSES = [
    None,
    {"x": 8, "y": 18, "width": 22, "height": 24, "roof": "#9b4e36", "wall": "#d99a5f", "yard": "#84b95f", "crop": "#e7b95c"},
    {"x": 36, "y": 10, "width": 24, "height": 25, "roof": "#7b3b55", "wall": "#b87857", "yard": "#7cae62", "crop": "#c66b5e"},
    {"x": 68, "y": 19, "width": 23, "height": 25, "roof": "#4f6d84", "wall": "#c88d63", "yard": "#79b866", "crop": "#8ed47a"},
    {"x": 9, "y": 59, "width": 24, "height": 25, "roof": "#d0a14d", "wall": "#bd7a4d", "yard": "#74aa61", "crop": "#6f86c9"},
    {"x": 40, "y": 60, "width": 25, "height": 25, "roof": "#5d6e44", "wall": "#c1834e", "yard": "#7eb45f", "crop": "#d69b4b"},
    {"x": 70, "y": 59, "width": 23, "height": 25, "roof": "#9d5838", "wall": "#bb7350", "yard": "#6f9f58", "crop": "#ef9049"},
    {"x": 2, "y": 40, "width": 22, "height": 24, "roof": "#6f4a3a", "wall": "#b88a5f", "yard": "#75a860", "crop": "#d4a84e"},
    {"x": 74, "y": 38, "width": 22, "height": 24, "roof": "#5a4d6a", "wall": "#c4926a", "yard": "#7bb462", "crop": "#c6d47a"},
]

PLAYER_AVATARS = [
    None,
    {"body": "#f3bf7a", "vest": "#5b8f54", "accent": "#f7df8a", "hair": "#7a4a2a"},
    {"body": "#c9825b", "vest": "#7c3f58", "accent": "#d96b72", "hair": "#3d2a22"},
    {"body": "#d99b6f", "vest": "#527c8f", "accent": "#b6e089", "hair": "#2c3f55"},
    {"body": "#c88a65", "vest": "#f0b65a", "accent": "#6f74bd", "hair": "#5a3823"},
    {"body": "#b97854", "vest": "#496a46", "accent": "#d7a34f", "hair": "#2f241d"},
    {"body": "#cc8a5d", "vest": "#9d5838", "accent": "#ef9049", "hair": "#3a2217"},
    {"body": "#dfa87a", "vest": "#6f4a3a", "accent": "#f0c86e", "hair": "#4a3020"},
    {"body": "#c4926a", "vest": "#5a4d6a", "accent": "#c6d47a", "hair": "#3a2a3a"},
]

ROLE_FACTION: Dict[str, str] = {
    "werewolf": "wolves",
    "villager": "town",
    "seer": "town",
    "witch": "town",
    "hunter": "town",
}

FRONTEND_PHASES = {
    "init": "daybreak",
    "night": "nightfall",
    "day": "discussion",
}

FRONTEND_PHASE_MOON: Dict[str, int] = {
    "daybreak": 8,
    "discussion": 12,
    "voting": 16,
    "nightfall": 92,
    "hunt": 88,
    "settlement": 20,
}

DIALOGUE_TONE_MAP: Dict[str, str] = {
    "system": "system",
    "init": "system",
    "night": "night",
    "day": "public",
    "vote": "vote",
    "action": "private",
    "private_chat": "werewolf",
}

# ---------------------------------------------------------------------------
# Game Runner with WebSocket broadcast
# ---------------------------------------------------------------------------

message_queue: Queue = Queue()


class LiveGameEngine(GameEngine):
    """GameEngine that broadcasts state snapshots via a thread-safe queue."""

    def __init__(self, config_path: str, queue: Queue):
        super().__init__(config_path)
        self._queue = queue
        self._dialogue_seq = 0
        self._event_seq = 0
        self._accumulated_dialogues: List[Dict] = []
        self._accumulated_votes: List[Dict] = []
        self._accumulated_events: List[Dict] = []
        self._last_speaker: Optional[int] = None
        self._marked_target: Optional[int] = None

        # Intercept the logger
        original_log = self.logger.log

        def intercepted_log(phase: str, agent_id: Optional[int], log_type: str, content: Any):
            original_log(phase, agent_id, log_type, content)
            self._on_game_log(phase, agent_id, log_type, content)

        self.logger.log = intercepted_log

    # ------------------------------------------------------------------
    # Log interceptor – builds dialogue / vote / event entries
    # ------------------------------------------------------------------

    def _on_game_log(self, phase: str, agent_id: Optional[int], log_type: str, content: Any):
        if log_type == "speech" and isinstance(content, str) and agent_id is not None:
            tone = DIALOGUE_TONE_MAP.get(phase, "public")
            self._dialogue_seq += 1
            entry = {
                "id": f"d{self._dialogue_seq}",
                "speakerId": agent_id,
                "tone": tone,
                "text": content,
                "timestamp": f"Day {self.game_state.get('day', 1)} {datetime.now().strftime('%H:%M')}",
            }
            self._accumulated_dialogues.append(entry)
            self._last_speaker = agent_id
            self._queue.put({"type": "dialogue", "data": entry})

        elif log_type == "private_chat" and isinstance(content, str) and agent_id is not None:
            self._dialogue_seq += 1
            entry = {
                "id": f"d{self._dialogue_seq}",
                "speakerId": agent_id,
                "tone": "werewolf",
                "text": content,
                "timestamp": f"Day {self.game_state.get('day', 1)} {datetime.now().strftime('%H:%M')}",
            }
            self._accumulated_dialogues.append(entry)
            self._queue.put({"type": "dialogue", "data": entry})

        elif log_type == "action" and isinstance(content, dict) and agent_id is not None:
            action = content
            action_type = action.get("type", "")
            if action_type == "vote":
                target = action.get("target")
                explain = action.get("explain") or action.get("reason", "")
                if target and agent_id:
                    vote_entry = {
                        "voterId": agent_id,
                        "targetId": target,
                        "reason": explain,
                    }
                    self._accumulated_votes.append(vote_entry)
                    self._queue.put({"type": "vote", "data": vote_entry})

                    # Push vote reason as dialogue
                    if explain:
                        self._dialogue_seq += 1
                        speaker_name = PLAYER_NAMES[agent_id] if agent_id < len(PLAYER_NAMES) else f"玩家{agent_id}"
                        target_name = PLAYER_NAMES[target] if target < len(PLAYER_NAMES) else f"玩家{target}"
                        dialogue_entry = {
                            "id": f"d{self._dialogue_seq}",
                            "speakerId": agent_id,
                            "tone": "vote",
                            "text": f"{speaker_name} 投票给 {target_name}：{explain}",
                            "timestamp": f"Day {self.game_state.get('day', 1)} {datetime.now().strftime('%H:%M')}",
                        }
                        self._accumulated_dialogues.append(dialogue_entry)
                        self._queue.put({"type": "dialogue", "data": dialogue_entry})
            elif action_type in ("night_kill", "seer_check", "witch_save", "witch_poison"):
                target = action.get("target")
                explain = action.get("explain") or action.get("reason", "")
                if target and agent_id:
                    vote_entry = {
                        "voterId": agent_id,
                        "targetId": target,
                        "reason": explain,
                    }
                    self._accumulated_votes.append(vote_entry)
                    self._queue.put({"type": "vote", "data": vote_entry})

                    # Generate readable night-action dialogue
                    self._dialogue_seq += 1
                    speaker_name = PLAYER_NAMES[agent_id] if agent_id < len(PLAYER_NAMES) else f"玩家{agent_id}"
                    target_name = PLAYER_NAMES[target] if target < len(PLAYER_NAMES) else f"玩家{target}"
                    action_labels = {
                        "night_kill": "狼人夜袭",
                        "seer_check": "预言家查验",
                        "witch_save": "女巫救药",
                        "witch_poison": "女巫毒药",
                    }
                    action_text = f"{speaker_name} {action_labels.get(action_type, '夜间行动')}: {target_name}"
                    if explain and "abstain" not in explain:
                        action_text += f"（{explain}）"
                    dialogue_entry = {
                        "id": f"d{self._dialogue_seq}",
                        "speakerId": agent_id,
                        "tone": "night",
                        "text": action_text,
                        "timestamp": f"Day {self.game_state.get('day', 1)} {datetime.now().strftime('%H:%M')}",
                    }
                    self._accumulated_dialogues.append(dialogue_entry)
                    self._queue.put({"type": "dialogue", "data": dialogue_entry})

                    # Track speaker so frontend animates the active night actor
                    self._last_speaker = agent_id
                    self._broadcast_snapshot("hunt")

            elif action_type == "hunter_shot":
                target = action.get("target")
                explain = action.get("explain") or action.get("reason", "")
                if target and agent_id:
                    vote_entry = {
                        "voterId": agent_id,
                        "targetId": target,
                        "reason": explain,
                    }
                    self._accumulated_votes.append(vote_entry)
                    self._queue.put({"type": "vote", "data": vote_entry})

                    # System announcement of hunter's last shot
                    self._dialogue_seq += 1
                    speaker_name = PLAYER_NAMES[agent_id] if agent_id < len(PLAYER_NAMES) else f"玩家{agent_id}"
                    target_name = PLAYER_NAMES[target] if target < len(PLAYER_NAMES) else f"玩家{target}"
                    text = f"猎人 {speaker_name} 开枪带走 {target_name}"
                    if explain and "abstain" not in explain:
                        text += f"（{explain}）"
                    dialogue_entry = {
                        "id": f"d{self._dialogue_seq}",
                        "speakerId": "system",
                        "tone": "system",
                        "text": text,
                        "timestamp": f"Day {self.game_state.get('day', 1)} {datetime.now().strftime('%H:%M')}",
                    }
                    self._accumulated_dialogues.append(dialogue_entry)
                    self._queue.put({"type": "dialogue", "data": dialogue_entry})

        elif log_type == "system" and isinstance(content, str):
            self._dialogue_seq += 1
            entry = {
                "id": f"d{self._dialogue_seq}",
                "speakerId": "system",
                "tone": "system",
                "text": content,
                "timestamp": f"Day {self.game_state.get('day', 1)} {datetime.now().strftime('%H:%M')}",
            }
            self._accumulated_dialogues.append(entry)
            self._queue.put({"type": "dialogue", "data": entry})

        elif log_type == "system" and isinstance(content, dict):
            # Format dict-type system messages as Chinese dialogue
            text = None
            if "resolution" in content:
                resolution = content["resolution"]
                text = f"系统：投票结果 — {resolution}"
            if text:
                self._dialogue_seq += 1
                entry = {
                    "id": f"d{self._dialogue_seq}",
                    "speakerId": "system",
                    "tone": "system",
                    "text": text,
                    "timestamp": f"Day {self.game_state.get('day', 1)} {datetime.now().strftime('%H:%M')}",
                }
                self._accumulated_dialogues.append(entry)
                self._queue.put({"type": "dialogue", "data": entry})

    # ------------------------------------------------------------------
    # Game phase hooks
    # ------------------------------------------------------------------

    def initialize_game(self):
        super().initialize_game()
        self._queue.put({"type": "log", "data": "游戏初始化完成，角色已分配"})
        self._broadcast_snapshot("daybreak")

    def run_night_phase(self):
        self._queue.put({"type": "log", "data": f"第{self.game_state['day'] + 1}夜来临"})
        self._broadcast_snapshot("nightfall")
        super().run_night_phase()
        self._queue.put({"type": "log", "data": "天亮了"})
        self._broadcast_snapshot("daybreak")

    def run_day_phase(self):
        self._broadcast_snapshot("discussion")
        super().run_day_phase()
        self._broadcast_snapshot("settlement")

    def _settle_night(self, *args, **kwargs):
        super()._settle_night(*args, **kwargs)
        self._broadcast_snapshot("nightfall")

    def _settle_day(self, resolution):
        super()._settle_day(resolution)
        self._broadcast_snapshot("settlement")

    def check_victory_condition(self):
        winner = super().check_victory_condition()
        if winner:
            snapshot = self._build_snapshot("settlement")
            snapshot["winner"] = winner
            self._queue.put({"type": "game_over", "data": snapshot})
        return winner

    # ------------------------------------------------------------------
    # Snapshot builder
    # ------------------------------------------------------------------

    def _broadcast_snapshot(self, phase_label: str):
        snapshot = self._build_snapshot(phase_label)
        self._queue.put({"type": "game_snapshot", "data": snapshot})

    def _build_snapshot(self, phase_label: str) -> Dict:
        frontend_phase = phase_label
        alive_ids = set(self.game_state.get("alive_agents", []))
        eliminated_ids = set(self.game_state.get("eliminated_agents", []))

        # Determine marked target (the one with most votes or night target)
        current_voting = self.game_state.get("current_voting", {})
        vote_counts: Dict[int, int] = {}
        for voter_id, target_id in (current_voting or {}).items():
            if isinstance(target_id, int):
                vote_counts[target_id] = vote_counts.get(target_id, 0) + 1
        marked = max(vote_counts, key=vote_counts.get) if vote_counts else None

        players = []
        for agent in self.agents:
            aid = agent.agent_id
            role_name = agent.role
            faction = ROLE_FACTION.get(role_name, "town")

            # Determine status
            if aid in eliminated_ids:
                status = "eliminated"
            elif marked and aid == marked:
                status = "targeted"
            else:
                status = "alive"

            vote_target = None
            if aid in current_voting and isinstance(current_voting.get(aid), int):
                vote_target = current_voting[aid]

            # Build last action from dialogues
            last_action = ""
            agent_dialogues = [
                d for d in self._accumulated_dialogues
                if d.get("speakerId") == aid
            ]
            if agent_dialogues:
                last_action = agent_dialogues[-1]["text"][:50]

            player = {
                "id": aid,
                "name": PLAYER_NAMES[aid] if aid < len(PLAYER_NAMES) else f"玩家{aid}",
                "role": role_name,
                "faction": faction,
                "status": status,
                "position": PLAYER_POSITIONS[aid] if aid < len(PLAYER_POSITIONS) else {"x": 50, "y": 50},
                "house": PLAYER_HOUSES[aid] if aid < len(PLAYER_HOUSES) else {"x": 40, "y": 40, "width": 20, "height": 20, "roof": "#666", "wall": "#888", "yard": "#999", "crop": "#aaa"},
                "avatar": PLAYER_AVATARS[aid] if aid < len(PLAYER_AVATARS) else {"body": "#ccc", "vest": "#999", "accent": "#bbb", "hair": "#555"},
                "suspicion": 0,
                "voteTarget": vote_target,
                "lastAction": last_action,
            }
            players.append(player)

        dialogues = list(self._accumulated_dialogues)
        votes = list(self._accumulated_votes)

        events = [
            {"id": "e1", "phase": "daybreak", "label": "天亮公告", "detail": "聚集到中心广场，公开昨夜结果。"},
            {"id": "e2", "phase": "discussion", "label": "轮流发言", "detail": "公开发言注入所有存活玩家记忆。"},
            {"id": "e3", "phase": "voting", "label": "投票撮合", "detail": "最高票放逐，平票无人出局。"},
            {"id": "e4", "phase": "hunt", "label": "夜间行动", "detail": "狼人私聊、神职行动，结果仅注入本人。"},
        ]

        moon = FRONTEND_PHASE_MOON.get(frontend_phase, 20)
        current_speaker = self._last_speaker or (players[0]["id"] if players else 1)

        return {
            "day": self.game_state.get("day", 1),
            "phase": frontend_phase,
            "moon": moon,
            "currentSpeakerId": current_speaker,
            "markedTargetId": marked,
            "players": players,
            "dialogues": dialogues,
            "votes": votes,
            "events": events,
        }


# ---------------------------------------------------------------------------
# FastAPI app with lifespan
# ---------------------------------------------------------------------------

from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app_instance):
    # Startup: start queue processor
    queue_task = asyncio.create_task(process_message_queue())
    yield
    # Shutdown: cancel queue processor
    queue_task.cancel()
    try:
        await queue_task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="MAWS - Multi-Agent Werewolf Simulator", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Resolve frontend dist path
frontend_dist = os.path.join(project_root, "app", "dist")
frontend_index = os.path.join(frontend_dist, "index.html")

# Mount static files if dist exists
if os.path.isdir(frontend_dist):
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="assets")

    @app.get("/")
    async def serve_frontend():
        return FileResponse(frontend_index)

    @app.exception_handler(404)
    async def spa_fallback(req, exc):
        if os.path.isfile(frontend_index):
            return FileResponse(frontend_index)
        from fastapi.responses import JSONResponse
        return JSONResponse({"detail": "Not Found"}, status_code=404)
else:
    @app.get("/")
    async def root():
        return {"status": "ok", "message": "MAWS Backend. Build frontend first: cd app && npm run build"}


# ---------------------------------------------------------------------------
# WebSocket manager
# ---------------------------------------------------------------------------

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.game_thread: Optional[threading.Thread] = None
        self.engine: Optional[LiveGameEngine] = None
        self.game_running = False

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active_connections.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active_connections:
            self.active_connections.remove(ws)

    async def broadcast(self, message: dict):
        dead = []
        for conn in self.active_connections:
            try:
                await conn.send_json(message)
            except Exception:
                dead.append(conn)
        for conn in dead:
            self.disconnect(conn)

    def start_game(self, config_path: str):
        if self.game_running:
            return False
        self.game_running = True
        self.engine = LiveGameEngine(config_path, message_queue)
        self.game_thread = threading.Thread(target=self._run_engine, daemon=True)
        self.game_thread.start()
        return True

    def stop_game(self):
        """Stop the game and send reset signal to all clients."""
        self.game_running = False
        self.engine = None
        self.game_thread = None
        # Flush stale messages from the queue
        while not message_queue.empty():
            try:
                message_queue.get_nowait()
            except:
                break
        message_queue.put({"type": "game_reset", "data": {}})

    def _run_engine(self):
        try:
            message_queue.put({"type": "log", "data": "游戏引擎启动..."})
            self.engine.run_game()
        except Exception as e:
            import traceback
            traceback.print_exc()
            message_queue.put({"type": "log", "data": f"引擎错误: {e}"})
        finally:
            self.game_running = False


manager = ConnectionManager()


# ---------------------------------------------------------------------------
# Background queue processor
# ---------------------------------------------------------------------------


async def process_message_queue():
    while True:
        try:
            while not message_queue.empty():
                msg = message_queue.get_nowait()
                await manager.broadcast(msg)
            await asyncio.sleep(0.05)
        except Exception as e:
            print(f"Queue error: {e}")
            await asyncio.sleep(1)


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------

@app.get("/api/status")
async def api_status():
    return {
        "running": manager.game_running,
        "connections": len(manager.active_connections),
    }


@app.post("/api/start")
async def api_start():
    """Start a new game with config_ds.yaml"""
    config_path = os.path.join(project_root, "config", "config_ds.yaml")
    if not os.path.exists(config_path):
        # Try alternate paths
        config_path = os.path.join(project_root, "config.yaml")
    if not os.path.exists(config_path):
        return {"success": False, "message": f"配置文件不存在: {config_path}"}

    ok = manager.start_game(config_path)
    return {
        "success": ok,
        "message": "游戏已启动" if ok else "游戏已在运行中",
    }


@app.post("/api/stop")
async def api_stop():
    """Stop the current game and reset."""
    if not manager.game_running:
        return {"success": False, "message": "当前没有运行中的游戏"}
    manager.stop_game()
    return {"success": True, "message": "游戏已终止"}


@app.get("/api/config")
async def api_config():
    """Return current game config info."""
    config_path = os.path.join(project_root, "config", "config_ds.yaml")
    if not os.path.exists(config_path):
        config_path = os.path.join(project_root, "config.yaml")
    if os.path.exists(config_path):
        import yaml
        with open(config_path) as f:
            cfg = yaml.safe_load(f)
        return {
            "model": cfg.get("models", {}).get("default"),
            "roles": cfg.get("roles", {}).get("default_setup", {}).get("roles", []),
            "total_agents": cfg.get("roles", {}).get("default_setup", {}).get("total_agents", 0),
        }
    return {"error": "No config found"}


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    await ws.send_json({"type": "connected", "data": {"message": "已连接到游戏服务器"}})

    try:
        while True:
            data = await ws.receive_text()
            msg = json.loads(data)
            if msg.get("type") == "ping":
                await ws.send_json({"type": "pong"})
            elif msg.get("type") == "start":
                config_path = os.path.join(project_root, "config", "config_ds.yaml")
                if not os.path.exists(config_path):
                    config_path = os.path.join(project_root, "config.yaml")
                ok = manager.start_game(config_path)
                await ws.send_json({
                    "type": "log",
                    "data": "游戏已启动" if ok else "游戏已在运行",
                })
            elif msg.get("type") == "stop":
                manager.stop_game()
    except WebSocketDisconnect:
        manager.disconnect(ws)
    except Exception as e:
        print(f"WS error: {e}")
        manager.disconnect(ws)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="MAWS Backend Server")
    parser.add_argument("--host", default="0.0.0.0", help="监听地址")
    parser.add_argument("--port", type=int, default=8000, help="监听端口")
    args = parser.parse_args()

    print(f"  MAWS Backend starting on http://{args.host}:{args.port}")
    print(f"  Frontend dist: {frontend_dist}")
    print(f"  Config: config/config_ds.yaml")
    print()

    os.chdir(project_root)
    import uvicorn
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
