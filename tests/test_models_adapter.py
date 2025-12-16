import unittest
import os
import sys

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from models_adapter import ModelsAdapter
from utils import load_config


class TestModelsAdapter(unittest.TestCase):
    """测试模型适配器是否能正确调用大模型"""

    def setUp(self):
        """设置测试环境"""
        # 加载配置文件
        config_path = os.path.join(os.path.dirname(__file__), '..', 'config.yaml')
        try:
            config = load_config(config_path)
            self.model_adapters = config.get("models", {}).get("adapters", {})
        except Exception as e:
            self.model_adapters = {}
            print(f"警告：无法加载配置文件: {e}")
            
        # 如果无法加载配置文件，使用默认配置
        if not self.model_adapters:
            self.model_adapters = {
                "openai": {
                    "type": "openai",
                    "model": "gpt-4o-mini",
                    "api_key": "test-key",
                    "api_base": "https://api.openai.com/v1",
                    "temperature": 0.7,
                    "max_tokens": 100
                },
                "deepseek": {
                    "type": "http",
                    "model": "deepseek-chat",
                    "api_key": "test-key",
                    "api_base": "https://api.deepseek.com",
                    "temperature": 0.7,
                    "max_tokens": 100
                },
                "qwen_bailian": {
                    "type": "bailian",
                    "model": "qwen-plus",
                    "api_key": "test-key",
                    "api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                    "temperature": 0.7,
                    "max_tokens": 100
                },
                "kimi_bailian": {
                    "type": "bailian",
                    "model": "moonshot-v1-8k",
                    "api_key": "test-key",
                    "api_base": "https://api.moonshot.cn/v1",
                    "temperature": 0.7,
                    "max_tokens": 100
                }
            }

    def test_openai_adapter_creation(self):
        """测试OpenAI适配器创建"""
        openai_config = self.model_adapters.get("openai", {})
        if openai_config:
            adapter = ModelsAdapter(openai_config)
            self.assertIsNotNone(adapter)
            self.assertEqual(adapter.model_config, openai_config)
        else:
            self.skipTest("未找到OpenAI配置")

    def test_deepseek_adapter_creation(self):
        """测试DeepSeek适配器创建"""
        deepseek_config = self.model_adapters.get("deepseek", {})
        if deepseek_config:
            adapter = ModelsAdapter(deepseek_config)
            self.assertIsNotNone(adapter)
            self.assertEqual(adapter.model_config, deepseek_config)
        else:
            self.skipTest("未找到DeepSeek配置")

    def test_qwen_adapter_creation(self):
        """测试通义千问适配器创建"""
        qwen_config = self.model_adapters.get("qwen_bailian", {})
        if qwen_config:
            adapter = ModelsAdapter(qwen_config)
            self.assertIsNotNone(adapter)
            self.assertEqual(adapter.model_config, qwen_config)
        else:
            self.skipTest("未找到通义千问配置")

    def test_kimi_adapter_creation(self):
        """测试Kimi适配器创建"""
        kimi_config = self.model_adapters.get("kimi_bailian", {})
        if kimi_config:
            adapter = ModelsAdapter(kimi_config)
            self.assertIsNotNone(adapter)
            self.assertEqual(adapter.model_config, kimi_config)
        else:
            self.skipTest("未找到Kimi配置")

    def test_call_model_method_exists(self):
        """测试call_model方法是否存在"""
        # 使用任意一个有效的配置
        config = next(iter(self.model_adapters.values())) if self.model_adapters else {}
        if config:
            adapter = ModelsAdapter(config)
            self.assertTrue(hasattr(adapter, 'call_model'))
            self.assertTrue(callable(getattr(adapter, 'call_model')))
        else:
            self.skipTest("未找到任何模型配置")

    def test_model_routing(self):
        """测试模型路由是否正确"""
        # 测试OpenAI路由
        openai_config = self.model_adapters.get("openai", {})
        if openai_config:
            openai_adapter = ModelsAdapter(openai_config)
            self.assertTrue(hasattr(openai_adapter, '_call_openai_model'))
        
        # 测试HTTP路由
        deepseek_config = self.model_adapters.get("deepseek", {})
        if deepseek_config:
            deepseek_adapter = ModelsAdapter(deepseek_config)
            self.assertTrue(hasattr(deepseek_adapter, '_call_http_model'))
        
        # 测试百炼路由
        qwen_config = self.model_adapters.get("qwen_bailian", {})
        if qwen_config:
            qwen_adapter = ModelsAdapter(qwen_config)
            self.assertTrue(hasattr(qwen_adapter, '_call_bailian_model'))


if __name__ == '__main__':
    unittest.main()