from typing import Dict

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