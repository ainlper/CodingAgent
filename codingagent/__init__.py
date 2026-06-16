"""CodingAgent - Minimal AI coding agent inspired by Claude Code's architecture."""

__version__ = "0.3.0"
# 学习导读：这里定义包的稳定公开 API。外部用户无需了解内部文件布局，
# 只需从 codingagent 导入 Agent、LLM、Config 和默认工具集合。

# 重新导出核心类型，使 ``from codingagent import Agent`` 成为稳定用法。
from codingagent.agent import Agent
from codingagent.llm import LLM
from codingagent.config import Config
from codingagent.tools import ALL_TOOLS

# ``__all__`` 同时服务于文档工具和 ``from codingagent import *``。
__all__ = ["Agent", "LLM", "Config", "ALL_TOOLS", "__version__"]
