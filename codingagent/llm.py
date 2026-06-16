"""LLM provider layer - thin wrapper over OpenAI-compatible APIs.

Since most providers (DeepSeek, Qwen, Kimi, GLM, Ollama, etc.) expose an
OpenAI-compatible endpoint, we just use the openai SDK directly.  Switch
provider by changing OPENAI_BASE_URL + OPENAI_API_KEY. That's it.

For providers that are NOT OpenAI-compatible (AWS Bedrock, Google Vertex,
etc.), use the LiteLLM backend which routes to 100+ providers through a
single unified interface. Set CORECODER_PROVIDER=litellm.
"""
# 学习导读：Provider 层把不同模型服务统一成 LLMResponse。上层 Agent 不接触
# SDK 的流式 Chunk，而只处理完整文本、ToolCall 列表和 token 使用量。

import json
import time
from dataclasses import dataclass, field

from openai import OpenAI, APIError, RateLimitError, APITimeoutError, APIConnectionError


@dataclass
class ToolCall:
    """模型请求执行一次工具所需的最小结构。"""
    id: str
    name: str
    arguments: dict


@dataclass
class LLMResponse:
    """一次完整模型响应；由多个流式 Chunk 聚合而成。"""
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0

    # Agent 会把该属性返回的字典直接追加到 OpenAI 风格消息历史中。
    @property
    def message(self) -> dict:
        """Convert to OpenAI message format for appending to history."""
        msg: dict = {"role": "assistant", "content": self.content or None}
        if self.tool_calls:
            msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments),
                    },
                }
                for tc in self.tool_calls
            ]
        return msg


# pricing per million tokens: (input, output)
# sources: openai.com/api/pricing, api-docs.deepseek.com, platform.claude.com,
#          platform.moonshot.ai, alibabacloud.com/help/en/model-studio
_PRICING = {
    # OpenAI - current flagships
    "gpt-5.4": (2.5, 15),
    "gpt-5.4-mini": (0.75, 4.5),
    "gpt-5.4-nano": (0.2, 1.25),
    "o4-mini": (1.1, 4.4),
    # OpenAI - previous gen (still widely used)
    "gpt-4.1": (2, 8),
    "gpt-4.1-mini": (0.4, 1.6),
    "gpt-4.1-nano": (0.1, 0.4),
    "gpt-4o": (2.5, 10),
    "gpt-4o-mini": (0.15, 0.6),
    # DeepSeek
    "deepseek-chat": (0.27, 1.10),
    "deepseek-reasoner": (0.55, 2.19),
    # Anthropic Claude
    "claude-opus-4-6": (5, 25),
    "claude-sonnet-4-6": (3, 15),
    "claude-haiku-4-5": (1, 5),
    # Alibaba Qwen
    "qwen3-max": (0.78, 3.9),
    "qwen3-plus": (0.26, 0.78),
    "qwen-max": (0.78, 3.9),
    # Moonshot Kimi
    "kimi-k2.5": (0.6, 3),
}


class LLM:
    """OpenAI 兼容 Provider：负责请求、流式聚合、重试和用量统计。"""
    def __init__(
        self,
        model: str,
        api_key: str,
        base_url: str | None = None,
        **kwargs,
    ):
        """保存 Provider 配置，并初始化跨请求累计的 token 计数。"""
        # Provider 保存长期累计计数；单次请求用量则放在 LLMResponse 中。
        self.model = model
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.extra = kwargs  # temperature, max_tokens, etc.
        # 累计计数服务于 CLI 的 /tokens 和费用估算。
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0

    # 费用表按每百万 token 计价；未知模型返回 None，避免给出错误估算。
    @property
    def estimated_cost(self) -> float | None:
        """Rough cost estimate in USD. Returns None if model not in pricing table."""
        pricing = _PRICING.get(self.model)
        if not pricing:
            return None
        input_rate, output_rate = pricing
        return (
            self.total_prompt_tokens * input_rate / 1_000_000
            + self.total_completion_tokens * output_rate / 1_000_000
        )

    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        on_token=None,
    ) -> LLMResponse:
        """Send messages, stream back response, handle tool calls."""
        # extra 允许透传 temperature、max_tokens 等供应商兼容参数。
        params: dict = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            **self.extra,
        }
        if tools:
            params["tools"] = tools

        # stream_options is an OpenAI extension; not all providers support it
        # 先请求 usage 扩展；部分兼容服务不支持时，去掉该参数后重试。
        try:
            params["stream_options"] = {"include_usage": True}
            stream = self._call_with_retry(params)
        except Exception:
            params.pop("stream_options", None)
            stream = self._call_with_retry(params)

        # 文本和 Tool Call 都可能被拆散在多个 Chunk 中，需要按索引累计。
        content_parts: list[str] = []
        tc_map: dict[int, dict] = {}  # index -> {id, name, arguments_str}
        prompt_tok = 0
        completion_tok = 0

        # 流同时承担两件事：即时回调文本，以及重建最终结构化响应。
        for chunk in stream:
            # usage info comes in the final chunk
            if chunk.usage:
                prompt_tok = chunk.usage.prompt_tokens
                completion_tok = chunk.usage.completion_tokens

            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta

            # accumulate text
            if delta.content:
                content_parts.append(delta.content)
                if on_token:
                    on_token(delta.content)

            # accumulate tool calls across chunks
            if delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index
                    # 同一个 Tool Call 的 id、name、arguments 可能分别出现在不同 Chunk。
                    if idx not in tc_map:
                        tc_map[idx] = {"id": "", "name": "", "args": ""}
                    if tc_delta.id:
                        tc_map[idx]["id"] = tc_delta.id
                    if tc_delta.function:
                        if tc_delta.function.name:
                            tc_map[idx]["name"] = tc_delta.function.name
                        if tc_delta.function.arguments:
                            tc_map[idx]["args"] += tc_delta.function.arguments

        # parse accumulated tool calls
        # arguments 是逐片段拼接的 JSON 字符串，只能在流结束后统一解析。
        parsed: list[ToolCall] = []
        for idx in sorted(tc_map):
            raw = tc_map[idx]
            try:
                args = json.loads(raw["args"])
            except (json.JSONDecodeError, KeyError):
                args = {}
            parsed.append(ToolCall(id=raw["id"], name=raw["name"], arguments=args))

        # 累计计数服务于 CLI 的 /tokens 和费用估算。
        self.total_prompt_tokens += prompt_tok
        self.total_completion_tokens += completion_tok

        return LLMResponse(
            content="".join(content_parts),
            tool_calls=parsed,
            prompt_tokens=prompt_tok,
            completion_tokens=completion_tok,
        )

    def _call_with_retry(self, params: dict, max_retries: int = 3):
        """Retry on transient errors with exponential backoff."""
        # 指数退避仅处理限流、超时、连接和服务端错误；客户端参数错误直接抛出。
        for attempt in range(max_retries):
            try:
                return self.client.chat.completions.create(**params)
            except (RateLimitError, APITimeoutError, APIConnectionError) as e:
                if attempt == max_retries - 1:
                    raise
                wait = 2 ** attempt
                time.sleep(wait)
            except APIError as e:
                # 5xx = server error, retry; 4xx = client error, don't
                if e.status_code and e.status_code >= 500 and attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise


class LiteLLM(LLM):
    """LLM backend via LiteLLM, supporting 100+ providers.

    Use this when your target provider is NOT OpenAI-compatible
    (AWS Bedrock, Google Vertex, Cohere, etc.) or when you want
    a single interface to switch between any provider by changing
    the model string.

    Set CORECODER_PROVIDER=litellm and use LiteLLM model strings
    like ``anthropic/claude-3-haiku``, ``bedrock/anthropic.claude-v2``,
    ``vertex_ai/gemini-pro``, etc.
    """

    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        base_url: str | None = None,
        **kwargs,
    ):
        """保存 Provider 配置，并初始化跨请求累计的 token 计数。"""
        # LiteLLM 只复用父类的公共语义，不创建 OpenAI SDK 客户端。
        # skip LLM.__init__ which creates an OpenAI client
        # Provider 保存长期累计计数；单次请求用量则放在 LLMResponse 中。
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.extra = kwargs
        # 累计计数服务于 CLI 的 /tokens 和费用估算。
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0

    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        on_token=None,
    ) -> LLMResponse:
        """Send messages via litellm, stream back response, handle tool calls."""
        # extra 允许透传 temperature、max_tokens 等供应商兼容参数。
        params: dict = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            **self.extra,
        }
        if tools:
            params["tools"] = tools

        # LiteLLM 返回近似 OpenAI 的 Chunk，但访问字段时仍用 getattr 兼容差异。
        stream = self._call_with_retry(params)

        # 文本和 Tool Call 都可能被拆散在多个 Chunk 中，需要按索引累计。
        content_parts: list[str] = []
        tc_map: dict[int, dict] = {}
        prompt_tok = 0
        completion_tok = 0

        # 流同时承担两件事：即时回调文本，以及重建最终结构化响应。
        for chunk in stream:
            usage = getattr(chunk, "usage", None)
            if usage:
                prompt_tok = getattr(usage, "prompt_tokens", 0) or 0
                completion_tok = getattr(usage, "completion_tokens", 0) or 0

            if not getattr(chunk, "choices", None):
                continue
            delta = chunk.choices[0].delta

            if getattr(delta, "content", None):
                content_parts.append(delta.content)
                if on_token:
                    on_token(delta.content)

            if getattr(delta, "tool_calls", None):
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index
                    # 同一个 Tool Call 的 id、name、arguments 可能分别出现在不同 Chunk。
                    if idx not in tc_map:
                        tc_map[idx] = {"id": "", "name": "", "args": ""}
                    if tc_delta.id:
                        tc_map[idx]["id"] = tc_delta.id
                    if tc_delta.function:
                        if tc_delta.function.name:
                            tc_map[idx]["name"] = tc_delta.function.name
                        if tc_delta.function.arguments:
                            tc_map[idx]["args"] += tc_delta.function.arguments

        # arguments 是逐片段拼接的 JSON 字符串，只能在流结束后统一解析。
        parsed: list[ToolCall] = []
        for idx in sorted(tc_map):
            raw = tc_map[idx]
            try:
                args = json.loads(raw["args"])
            except (json.JSONDecodeError, KeyError):
                args = {}
            parsed.append(ToolCall(id=raw["id"], name=raw["name"], arguments=args))

        # 累计计数服务于 CLI 的 /tokens 和费用估算。
        self.total_prompt_tokens += prompt_tok
        self.total_completion_tokens += completion_tok

        return LLMResponse(
            content="".join(content_parts),
            tool_calls=parsed,
            prompt_tokens=prompt_tok,
            completion_tokens=completion_tok,
        )

    def _call_with_retry(self, params: dict, max_retries: int = 3):
        """Retry on transient errors with exponential backoff via litellm."""
        import litellm

        # drop_params 让 LiteLLM 自动丢弃目标 Provider 不支持的可选参数。
        params["drop_params"] = True
        if self.api_key:
            params["api_key"] = self.api_key
        if self.base_url:
            params["api_base"] = self.base_url

        # 指数退避仅处理限流、超时、连接和服务端错误；客户端参数错误直接抛出。
        for attempt in range(max_retries):
            try:
                return litellm.completion(**params)
            except Exception as e:
                err = str(e).lower()
                is_transient = any(
                    kw in err
                    for kw in ["rate_limit", "timeout", "connection", "502", "503", "529"]
                )
                is_server = any(kw in err for kw in ["500", "502", "503", "504"])
                if (is_transient or is_server) and attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise
