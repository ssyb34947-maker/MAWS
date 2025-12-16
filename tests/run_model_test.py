#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
模型调用测试脚本
用于验证各种大模型是否能正常调用
"""

import sys
import os

# 添加src目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from models_adapter import ModelsAdapter
from utils import load_config


def run_model_test(model_config, model_name):
    """测试单个模型调用"""
    print(f"\n=== 测试 {model_name} ===")
    print(f"模型类型: {model_config.get('type')}")
    print(f"模型名称: {model_config.get('model')}")
    print(f"API地址: {model_config.get('api_base')}")
    
    try:
        adapter = ModelsAdapter(model_config)
        prompt = "请用中文简短回答：1+1等于多少？"
        
        print(f"发送提示词: {prompt}")
        response = adapter.call_model(prompt)
        
        # 检查是否为模拟响应
        if "模拟" in response or "这是一个模拟的发言" in response:
            print(f"❌ {model_name} 返回了模拟响应:")
            print(f"   {response}")
            return False
        else:
            print(f"✅ {model_name} 成功返回响应:")
            print(f"   {response}")
            return True
            
    except Exception as e:
        print(f"❌ {model_name} 调用出错: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    print("开始测试大模型调用...")
    
    # 加载配置文件
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config.yaml')
    try:
        config = load_config(config_path)
        model_adapters = config.get("models", {}).get("adapters", {})
    except Exception as e:
        print(f"❌ 无法加载配置文件: {e}")
        return
    
    # 执行测试
    results = []
    for model_name, model_config in model_adapters.items():
        # 检查是否有API密钥
        api_key = model_config.get("api_key", "")
        if not api_key or api_key.startswith("YOUR_"):
            print(f"\n跳过 {model_name} 测试（未设置有效的API密钥）")
            continue
            
        result = run_model_test(model_config, model_name)
        results.append((model_name, result))
    
    # 输出总结
    print("\n" + "="*50)
    print("测试总结:")
    for name, success in results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"  {name}: {status}")
    
    successful_tests = sum(1 for _, success in results if success)
    print(f"\n成功: {successful_tests}/{len(results)} 个模型测试")


if __name__ == "__main__":
    main()