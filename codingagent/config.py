"""Configuration - env vars and defaults."""

# 学习导读：配置流为 ``.env -> 系统环境变量 -> Config``；CLI 参数会在 cli.py 中
# 最后覆盖这里得到的值。配置对象只保存数据，不直接创建模型客户端。
import os
from dataclasses import dataclass
from pathlib import Path


# 该辅助函数把 dotenv 作为可选依赖，未安装时仍可使用纯环境变量。
def _load_dotenv():
    """Load .env from cwd, walking up to home dir. No-op if python-dotenv missing."""
    try:
        from dotenv import load_dotenv
        # search cwd first, then parent dirs up to ~
        env_path = Path(".env")
        if not env_path.exists():
            cur = Path.cwd()
            home = Path.home()
            while cur != home and cur != cur.parent:
                candidate = cur / ".env"
                if candidate.exists():
                    env_path = candidate
                    break
                cur = cur.parent
        load_dotenv(env_path, override=False)
    except ImportError:
        pass  # python-dotenv not installed, silently skip


@dataclass
class Config:
    """运行期配置的数据载体；默认值保证最小启动参数清晰可见。"""
    model: str = "gpt-4o"
    api_key: str = ""
    base_url: str | None = None
    max_tokens: int = 4096
    temperature: float = 0.0
    max_context_tokens: int = 128_000
    provider: str = "openai"

    @classmethod
    def from_env(cls) -> "Config":
        """按优先级读取环境变量并完成字符串到数值类型的转换。"""
        # load .env if present (won't override existing env vars)
        _load_dotenv()
        # pick up common env vars automatically
        api_key = (
            os.getenv("CODINGAGENT_API_KEY")
            or
            os.getenv("CORECODER_API_KEY")
            or os.getenv("OPENAI_API_KEY")
            or os.getenv("DEEPSEEK_API_KEY")
            or ""
        )
        return cls(
            model=os.getenv("CODINGAGENT_MODEL") or os.getenv("CORECODER_MODEL", "gpt-4o"),
            api_key=api_key,
            base_url=os.getenv("OPENAI_BASE_URL") or os.getenv("CODINGAGENT_BASE_URL") or os.getenv("CORECODER_BASE_URL"),
            max_tokens=int(os.getenv("CODINGAGENT_MAX_TOKENS") or os.getenv("CORECODER_MAX_TOKENS", "4096")),
            temperature=float(os.getenv("CODINGAGENT_TEMPERATURE") or os.getenv("CORECODER_TEMPERATURE", "0")),
            max_context_tokens=int(os.getenv("CODINGAGENT_MAX_CONTEXT") or os.getenv("CORECODER_MAX_CONTEXT", "128000")),
            provider=os.getenv("CODINGAGENT_PROVIDER") or os.getenv("CORECODER_PROVIDER", "openai"),
        )
