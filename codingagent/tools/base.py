"""Base class for all tools."""
# 学习导读：Tool 是 Agent 与外部世界之间的协议边界。子类提供元数据和 execute，
# 基类把元数据统一包装成模型能够理解的 function-calling Schema。

from abc import ABC, abstractmethod


class Tool(ABC):
    """Minimal tool interface. Subclass this to add new capabilities."""

    # 这三个类属性由具体工具声明；parameters 使用 JSON Schema 描述参数。
    name: str
    description: str
    parameters: dict  # JSON Schema for the function args

    # execute 的文本结果会被包装成 role=tool 的消息重新发给模型。
    @abstractmethod
    def execute(self, **kwargs) -> str:
        """Run the tool and return a text result."""
        ...

    # Schema 只描述工具，不执行参数校验；当前参数错误在调用阶段捕获。
    def schema(self) -> dict:
        """OpenAI function-calling schema."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }
