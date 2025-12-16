# 测试目录说明

本目录包含用于测试项目功能的各种测试脚本。

## 测试文件说明

1. [test_models_adapter.py](file://d:\桌面\work\狼人杀\tests\test_models_adapter.py) - 测试模型适配器的基本功能和创建
2. [test_real_model_calls.py](file://d:\桌面\work\狼人杀\tests\test_real_model_calls.py) - 测试真实模型调用
3. [run_model_test.py](file://d:\桌面\work\狼人杀\tests\run_model_test.py) - 简单的模型调用测试脚本

## 如何运行测试

### 运行单元测试

```bash
# 在项目根目录下运行
python -m pytest tests/test_models_adapter.py tests/test_real_model_calls.py

# 或者运行特定测试文件
python -m pytest tests/test_models_adapter.py
python -m pytest tests/test_real_model_calls.py
```

### 运行模型调用测试

测试脚本会自动从 `config.yaml` 文件中读取模型配置。要测试真实的大模型调用，您需要在 `config.yaml` 中填写实际的API密钥：

```yaml
models:
  adapters:
    deepseek:
      api_key: "your_actual_deepseek_key"
    qwen_bailian:
      api_key: "your_actual_dashscope_key"
    kimi_bailian:
      api_key: "your_actual_kimi_key"
    GLM_bailian:
      api_key: "your_actual_glm_key"
```

然后运行测试脚本：

```bash
python tests/run_model_test.py
```

## 测试说明

测试脚本会检查模型返回的内容是否为模拟响应。如果返回包含"模拟"或"这是一个模拟的发言"等字样，则说明模型调用未正常工作，仍在返回模拟数据。