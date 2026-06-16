"""Sub-agent spawning (inspired by Claude Code's AgentTool, 1397 lines).

The idea: for complex sub-tasks, spawn an independent agent with its own
conversation history and tool access. This lets the main agent delegate
work like "go research this codebase and report back" without polluting
its own context window.

The sub-agent runs to completion and returns a text summary.
"""
# 学习导读：AgentTool 创建一段独立消息历史来隔离复杂子任务，但复用父 Agent
# 的同一个 LLM 对象和工具对象；因此上下文隔离不等于资源或状态完全隔离。

from .base import Tool


class AgentTool(Tool):
    """把子任务交给临时 Agent，并将其最终文本摘要返回父会话。"""
    name = "agent"
    description = (
        "Spawn a sub-agent to handle a complex sub-task independently. "
        "The sub-agent has its own context and tool access. Use this for: "
        "researching a codebase, implementing a multi-step change in isolation, "
        "or any task that would benefit from a fresh context window."
    )
    parameters = {
        "type": "object",
        "properties": {
            "task": {
                "type": "string",
                "description": "What the sub-agent should accomplish",
            },
        },
        "required": ["task"],
    }

    # set by Agent.__init__ after construction
    # 父引用在 Agent 初始化时注入；默认全局 AgentTool 单例会保存最后一次注入值。
    _parent_agent = None

    def execute(self, task: str) -> str:
        """构造禁止递归委派的子 Agent，并同步等待其运行结束。"""
        if self._parent_agent is None:
            return "Error: agent tool not initialized (no parent agent)"

        # import here to avoid circular dep
        # 延迟导入打破 agent.py 与 tools/agent.py 之间的循环依赖。
        from ..agent import Agent

        # 子 Agent 使用新 messages 和 ContextManager，但共享父 LLM 的 token 计数与客户端。
        parent = self._parent_agent
        sub = Agent(
            llm=parent.llm,
            # 排除 agent 工具，避免子 Agent 无限递归创建下一层 Agent。
            tools=[t for t in parent.tools if t.name != "agent"],  # no recursive agents
            max_context_tokens=parent.context.max_tokens,
            max_rounds=20,
        )

        try:
            # 当前调用是同步的：父 Agent 在子任务完成前不会进入下一轮。
            result = sub.chat(task)
            # trim long results to avoid blowing up parent's context
            # 子任务只向父上下文返回最终结论，且继续限制最大文本长度。
            if len(result) > 5000:
                result = result[:4500] + "\n... (sub-agent output truncated)"
            return f"[Sub-agent completed]\n{result}"
        except Exception as e:
            return f"Sub-agent error: {e}"
