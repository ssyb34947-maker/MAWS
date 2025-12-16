import argparse
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.game_engine import GameEngine


def main():
    """
    主函数，程序入口
    """
    parser = argparse.ArgumentParser(description='Multi-Agent 狼人杀')
    parser.add_argument('--config', type=str, default='config.yaml', help='配置文件路径')
    
    args = parser.parse_args()
    
    # 创建游戏引擎实例
    # 确保使用绝对路径以正确定位project_root
    config_path = os.path.abspath(args.config)
    engine = GameEngine(config_path)
    
    # 运行游戏
    engine.run_game()


if __name__ == "__main__":
    main()