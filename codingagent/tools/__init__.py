"""Tool registry."""
# 学习导读：模块导入时即创建全部默认工具单例。Agent 默认复用这些对象，
# 因此 Bash cwd、修改文件集合和 AgentTool 父引用等状态会跨调用保留。

from .bash import BashTool
from .read import ReadFileTool
from .write import WriteFileTool
from .edit import EditFileTool
from .glob_tool import GlobTool
from .grep import GrepTool
from .agent import AgentTool

# 顺序同时决定 System Prompt 中工具列表和发送给模型的 Schema 顺序。
ALL_TOOLS = [
    BashTool(),
    ReadFileTool(),
    WriteFileTool(),
    EditFileTool(),
    GlobTool(),
    GrepTool(),
    AgentTool(),
]


# 当前查找固定遍历全局列表，而不是某个 Agent 实例的 self.tools。
def get_tool(name: str):
    """按模型返回的工具名查找默认工具单例，找不到时返回 None。"""
    for t in ALL_TOOLS:
        if t.name == name:
            return t
    return None
