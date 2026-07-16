from typing import Dict, Any, List, Optional
import json
import requests
from loguru import logger

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    httpx = None
    HTTPX_AVAILABLE = False

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("OpenAI library not available, will use HTTP requests for all models")


class ModelsAdapter:
    """
    模型适配器类，用于统一不同模型的调用接口
    """

    def __init__(self, model_config: Dict[str, Any]):
        """
        初始化模型适配器
        
        Args:
            model_config: 模型配置字典
        """
        self.model_config = model_config

    def _build_messages(self, prompt_text: str, system_prompt: Optional[str] = None) -> List[Dict[str, str]]:
        messages: List[Dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt_text})
        return messages

    def _print_raw_tool_response(self, message: Any, provider: str) -> None:
        try:
            if hasattr(message, "model_dump"):
                raw_message = message.model_dump(mode="json")
            elif isinstance(message, dict):
                raw_message = message
            else:
                raw_message = {"repr": repr(message)}
            debug_payload = {
                "provider": provider,
                "model": self.model_config.get("model"),
                "content": raw_message.get("content"),
                "reasoning_content": raw_message.get("reasoning_content"),
                "tool_calls": raw_message.get("tool_calls"),
                "raw_message": raw_message,
            }
            print("\n========== RAW LLM TOOL RESPONSE ==========")
            print(json.dumps(debug_payload, ensure_ascii=False, indent=2, default=str))
            print("======== END RAW LLM TOOL RESPONSE ========\n", flush=True)
        except Exception as exc:
            print(f"[raw-llm-tool-response-print-failed] {exc}; message={message!r}", flush=True)

    def call_model(self, prompt_text: str, system_prompt: Optional[str] = None) -> str:
        """
        调用模型并返回原始字符串输出
        
        Args:
            prompt_text: 提示词文本
            
        Returns:
            模型的原始字符串输出
        """
        model_type = self.model_config.get("type", "openai")
        
        try:
            if model_type == "openai":
                return self._call_openai_model(prompt_text, system_prompt)
            elif model_type == "http":
                return self._call_http_model(prompt_text, system_prompt)
            elif model_type == "bailian":
                return self._call_bailian_model(prompt_text, system_prompt)
            else:
                raise ValueError(f"Unsupported model type: {model_type}")
        except Exception as e:
            logger.error(f"Error calling model: {e}")
            return self._mock_response()  # 返回模拟响应作为默认值

    def call_tool(
        self,
        prompt_text: str,
        tools: List[Dict[str, Any]],
        system_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        调用模型原生 tool calling，返回模型选择的工具名和参数。
        不再要求模型在普通文本中手写 JSON。
        """
        model_type = self.model_config.get("type", "openai")
        try:
            if model_type == "openai" and OPENAI_AVAILABLE:
                return self._call_openai_tool(prompt_text, tools, system_prompt)
            return self._call_http_tool(prompt_text, tools, system_prompt)
        except Exception as e:
            logger.error(f"Error calling model tool: {e}")
            return self._deterministic_tool_fallback(tools, "模型工具调用失败，系统按合法工具兜底")

    def _call_openai_tool(
        self,
        prompt_text: str,
        tools: List[Dict[str, Any]],
        system_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        http_client = None
        if HTTPX_AVAILABLE and not self.model_config.get("trust_env_proxy", False):
            http_client = httpx.Client(trust_env=False, timeout=self.model_config.get("timeout", 60))

        client = OpenAI(
            api_key=self.model_config.get("api_key"),
            base_url=self.model_config.get("api_base"),
            http_client=http_client,
        )
        request_payload = {
            "model": self.model_config.get("model"),
            "messages": self._build_messages(prompt_text, system_prompt),
            "temperature": self.model_config.get("temperature", 0.7),
            "max_tokens": self.model_config.get("max_tokens", 500),
            "tools": tools,
        }
        if self.model_config.get("force_tool_choice", False):
            request_payload["tool_choice"] = "required"
        response = client.chat.completions.create(**request_payload)
        message = response.choices[0].message
        self._print_raw_tool_response(message, "openai-compatible-sdk")
        tool_calls = getattr(message, "tool_calls", None) or []
        if not tool_calls:
            return self._deterministic_tool_fallback(tools, "模型未返回原生工具调用")
        call = tool_calls[0]
        function = call.function
        return {
            "name": function.name,
            "arguments": self._load_tool_arguments(function.arguments),
        }

    def _call_http_tool(
        self,
        prompt_text: str,
        tools: List[Dict[str, Any]],
        system_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.model_config.get('api_key')}",
            "Content-Type": "application/json",
        }
        api_base = self.model_config.get("api_base", "").rstrip("/")
        if not api_base.startswith("http"):
            api_base = "https://" + api_base
        if "deepseek" in api_base and not api_base.endswith("/v1"):
            url = api_base + "/v1/chat/completions"
        elif "dashscope" in api_base or "volces.com" in api_base:
            url = api_base + "/chat/completions"
        elif api_base.endswith("/v1"):
            url = api_base + "/chat/completions"
        else:
            url = api_base + "/v1/chat/completions"

        data = {
            "model": self.model_config.get("model"),
            "messages": self._build_messages(prompt_text, system_prompt),
            "temperature": self.model_config.get("temperature", 0.7),
            "max_tokens": self.model_config.get("max_tokens", 500),
            "tools": tools,
        }
        if self.model_config.get("force_tool_choice", False):
            data["tool_choice"] = "required"
        response = requests.post(url, headers=headers, json=data, timeout=self.model_config.get("timeout", 60))
        response.raise_for_status()
        result = response.json()
        choices = result.get("choices") or []
        if not choices:
            raise ValueError("Tool call response has no choices")
        message = choices[0].get("message") or {}
        self._print_raw_tool_response(message, "openai-compatible-http")
        tool_calls = message.get("tool_calls") or []
        if not tool_calls:
            return self._deterministic_tool_fallback(tools, "模型未返回原生工具调用")
        function = tool_calls[0].get("function") or {}
        return {
            "name": function.get("name"),
            "arguments": self._load_tool_arguments(function.get("arguments")),
        }

    def _load_tool_arguments(self, raw_arguments: Any) -> Dict[str, Any]:
        if isinstance(raw_arguments, dict):
            return raw_arguments
        if raw_arguments in (None, ""):
            return {}
        try:
            payload = json.loads(raw_arguments)
        except (TypeError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {"value": payload}

    def _deterministic_tool_fallback(self, tools: List[Dict[str, Any]], reason: str) -> Dict[str, Any]:
        if not tools:
            return {
                "name": "abstain",
                "arguments": {"reason": "本轮我不投票"},
                "fallback_reason": reason,
            }

        function = tools[0].get("function") or {}
        name = function.get("name") or "abstain"
        schema = function.get("parameters") or {}
        properties = schema.get("properties") or {}

        if "speech" in properties:
            return {
                "name": name,
                "arguments": {"speech": "本轮我不发言"},
                "fallback_reason": reason,
            }

        return {
            "name": "abstain",
            "arguments": {"reason": "本轮我不投票"},
            "fallback_reason": reason,
        }

    def _call_openai_model(self, prompt_text: str, system_prompt: Optional[str] = None) -> str:
        """
        调用OpenAI风格的模型
        
        Args:
            prompt_text: 提示词文本
            
        Returns:
            模型的原始字符串输出
        """
        if not OPENAI_AVAILABLE:
            logger.warning("OpenAI library not available, falling back to HTTP request")
            return self._call_http_model(prompt_text, system_prompt)
        
        try:
            # OpenAI/httpx will otherwise read ALL_PROXY/HTTP_PROXY from the shell.
            # Some local proxy tools export socks://, which httpx does not accept.
            # Default to an explicit no-env client; opt back in with trust_env_proxy: true.
            http_client = None
            if HTTPX_AVAILABLE and not self.model_config.get("trust_env_proxy", False):
                http_client = httpx.Client(trust_env=False, timeout=self.model_config.get("timeout", 60))

            client = OpenAI(
                api_key=self.model_config.get("api_key"),
                base_url=self.model_config.get("api_base"),
                http_client=http_client
            )
            
            response = client.chat.completions.create(
                model=self.model_config.get("model"),
                messages=self._build_messages(prompt_text, system_prompt),
                temperature=self.model_config.get("temperature", 0.7),
                max_tokens=self.model_config.get("max_tokens", 500)
            )
            
            content = response.choices[0].message.content
            if not content:
                logger.warning(f"Empty response from model, retrying once...")
                response = client.chat.completions.create(
                    model=self.model_config.get("model"),
                    messages=self._build_messages(prompt_text, system_prompt),
                    temperature=self.model_config.get("temperature", 0.7),
                    max_tokens=self.model_config.get("max_tokens", 500),
                )
                content = response.choices[0].message.content
                if not content:
                    raise ValueError("Model returned empty response after retry")
            return content
        except Exception as e:
            logger.error(f"Error calling OpenAI model: {e}")
            raise  # 重新抛出异常而不是返回模拟响应

    def _call_http_model(self, prompt_text: str, system_prompt: Optional[str] = None) -> str:
        """
        调用HTTP接口的模型
        
        Args:
            prompt_text: 提示词文本
            
        Returns:
            模型的原始字符串输出
        """
        try:
            headers = {
                "Authorization": f"Bearer {self.model_config.get('api_key')}"
            }
            
            api_base = self.model_config.get("api_base", "")
            if "deepseek" in api_base:
                headers["Content-Type"] = "application/json"
                data = {
                    "model": self.model_config.get("model"),
                    "messages": self._build_messages(prompt_text, system_prompt),
                    "temperature": self.model_config.get("temperature", 0.7),
                    "max_tokens": self.model_config.get("max_tokens", 500)
                }
                
                api_base = api_base.rstrip('/')
                if not api_base.startswith("http"):
                    api_base = "https://" + api_base
                
                # 确保URL格式正确
                if not api_base.endswith("/v1"):
                    url = api_base.rstrip('/') + "/v1/chat/completions"
                else:
                    url = api_base.rstrip('/') + "/chat/completions"
                
                response = requests.post(
                    url,
                    headers=headers,
                    json=data,
                    timeout=30
                )
                
                response.raise_for_status()
                result = response.json()
                if "choices" in result and len(result["choices"]) > 0:
                    return result["choices"][0]["message"]["content"]
                else:
                    logger.warning(f"Unexpected response format from DeepSeek: {result}")
                    raise ValueError("Unexpected response format from DeepSeek")
            elif "volces.com" in api_base:
                # 豆包(Doubao) API处理
                headers["Content-Type"] = "application/json"
                data = {
                    "model": self.model_config.get("model"),
                    "messages": self._build_messages(prompt_text, system_prompt),
                    "temperature": self.model_config.get("temperature", 0.7),
                    "max_tokens": self.model_config.get("max_tokens", 500)
                }
                
                if not api_base.startswith("http"):
                    api_base = "https://" + api_base
                    
                url = api_base.rstrip('/') + "/chat/completions"
                
                response = requests.post(
                    url,
                    headers=headers,
                    json=data,
                    timeout=30
                )
                
                response.raise_for_status()
                result = response.json()
                if "choices" in result and len(result["choices"]) > 0:
                    return result["choices"][0]["message"]["content"]
                else:
                    logger.warning(f"Unexpected response format from Doubao: {result}")
                    raise ValueError("Unexpected response format from Doubao")
            else:
                # 默认的HTTP调用方式
                return self._call_openai_compatible_model(prompt_text, system_prompt)
        except Exception as e:
            logger.error(f"Error calling HTTP model: {e}")
            raise  # 重新抛出异常而不是返回模拟响应

    def _call_bailian_model(self, prompt_text: str, system_prompt: Optional[str] = None) -> str:
        """
        调用百炼平台的模型
        
        Args:
            prompt_text: 提示词文本
            
        Returns:
            模型的原始字符串输出
        """
        return self._call_openai_compatible_model(prompt_text, system_prompt)

    def _call_openai_compatible_model(self, prompt_text: str, system_prompt: Optional[str] = None) -> str:
        """
        调用OpenAI兼容的模型
        
        Args:
            prompt_text: 提示词文本
            
        Returns:
            模型的原始字符串输出
        """
        try:
            headers = {
                "Authorization": f"Bearer {self.model_config.get('api_key')}"
            }
            
            # 检查是否是阿里云百炼平台
            if "dashscope" in self.model_config.get("api_base", ""):
                headers["Content-Type"] = "application/json"
                headers["X-DashScope-SSE"] = "enable"
                data = {
                    "model": self.model_config.get("model"),
                    "messages": self._build_messages(prompt_text, system_prompt),
                    "temperature": self.model_config.get("temperature", 0.2),
                    "max_tokens": self.model_config.get("max_tokens", 500)
                }
                
                api_base = self.model_config.get("api_base", "").rstrip('/')
                if not api_base.startswith("http"):
                    api_base = "https://" + api_base
                
                # 百炼平台使用标准的/chat/completions端点
                url = api_base + "/chat/completions"
                
                response = requests.post(
                    url,
                    headers=headers,
                    json=data,
                    timeout=60
                )
                
                response.raise_for_status()
                result = response.json()
                if "choices" in result and len(result["choices"]) > 0 and "message" in result["choices"][0]:
                    return result["choices"][0]["message"]["content"]
                else:
                    logger.warning(f"Unexpected response format from DashScope: {result}")
                    raise ValueError("Unexpected response format from DashScope")
            else:
                # 标准的OpenAI兼容API
                headers["Content-Type"] = "application/json"
                data = {
                    "model": self.model_config.get("model"),
                    "messages": self._build_messages(prompt_text, system_prompt),
                    "temperature": self.model_config.get("temperature", 0.7),
                    "max_tokens": self.model_config.get("max_tokens", 500)
                }
                
                api_base = self.model_config.get("api_base", "").rstrip('/')
                if not api_base.startswith("http"):
                    api_base = "https://" + api_base
                    
                # 确保URL格式正确
                url = api_base.rstrip('/') + "/v1/chat/completions"
                
                response = requests.post(
                    url,
                    headers=headers,
                    json=data,
                    timeout=30
                )
                
                response.raise_for_status()
                result = response.json()
                if "choices" in result and len(result["choices"]) > 0:
                    return result["choices"][0]["message"]["content"]
                else:
                    logger.warning(f"Unexpected response format from OpenAI-compatible API: {result}")
                    raise ValueError("Unexpected response format from OpenAI-compatible API")
        except Exception as e:
            logger.error(f"Error calling OpenAI compatible model: {e}")
            raise  # 重新抛出异常而不是返回模拟响应
    
    def _mock_response(self) -> str:
        """
        返回符合单轮工具调用协议的降级响应。
        """
        response = {
            "tool_call": {
                "name": "abstain",
                "arguments": {
                    "reason": "模型调用失败，系统降级为弃权"
                }
            }
        }
        return json.dumps(response, ensure_ascii=False)

    def batch_call_model(self, prompts: List[str]) -> List[str]:
        """
        批量调用模型接口（用于狼人内部协商）
        
        Args:
            prompts: 提示词文本列表
            
        Returns:
            模型的原始字符串输出列表
        """
        results = []
        for prompt in prompts:
            results.append(self.call_model(prompt))
        return results