import unittest
import os
import sys

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from models_adapter import ModelsAdapter
from utils import load_config


class TestRealModelCalls(unittest.TestCase):
    """测试真实模型调用"""

    def setUp(self):
        """设置测试环境"""
        self.test_prompt = "请用中文回答：1+1等于几？"
        
        # 加载配置文件
        config_path = os.path.join(os.path.dirname(__file__), '..', 'config.yaml')
        try:
            self.config = load_config(config_path)
        except Exception as e:
            self.config = {}
            print(f"警告：无法加载配置文件: {e}")

    def test_model_calls_from_config(self):
        """测试从配置文件中读取的模型配置"""
        if not self.config:
            self.skipTest("无法加载配置文件")
            
        model_adapters = self.config.get("models", {}).get("adapters", {})
        
        # 测试每个配置的模型
        for model_name, model_config in model_adapters.items():
            with self.subTest(model_name=model_name):
                # 检查是否有有效的API密钥
                api_key = model_config.get("api_key", "")
                if not api_key or api_key.startswith("YOUR_"):
                    self.skipTest(f"{model_name} 未设置有效的API密钥")
                
                adapter = ModelsAdapter(model_config)
                response = adapter.call_model(self.test_prompt)
                
                # 检查响应不是模拟响应
                self.assertNotIn("模拟", response)
                self.assertNotIn("这是一个模拟的发言", response)
                self.assertGreater(len(response), 0, f"{model_name} 返回空响应")
                print(f"{model_name} 响应: {response}")


if __name__ == '__main__':
    unittest.main()