"""Core agent loop.

This is the heart of CoreCoder.  The pattern is simple:

    user message -> LLM (with tools) -> tool calls? -> execute -> loop
                                      -> text reply? -> return to user

It keeps looping until the LLM responds with plain text (no tool calls),
which means it's done working and ready to report back.
"""
# 学习导读：Agent 是编排层，不负责具体模型协议或工具实现。它维护消息历史，
# 在 LLM 和 Tool 之间搬运结构化消息，直到模型不再请求工具或达到轮次上限。

import concurrent.futures
from .llm import LLM
from .tools import ALL_TOOLS, get_tool
from .tools.base import Tool
from .tools.agent import AgentTool
from .prompt import system_prompt
from .context import ContextManager


class Agent:
    """有状态的单 Agent 运行器；一个实例对应一段可持续多轮的会话。"""
    def __init__(
        self,
        llm: LLM,
        tools: list[Tool] | None = None,
        max_context_tokens: int = 128_000,
        max_rounds: int = 50,
    ):
        """装配模型、工具、消息历史、上下文管理器和轮次预算。"""
        # 依赖通过构造函数注入，便于替换模型实现和测试替身。
        self.llm = llm
        self.tools = tools if tools is not None else ALL_TOOLS
        # 这里只保存 user/assistant/tool 历史；system prompt 每轮动态加在最前面。
        self.messages: list[dict] = []
        # ContextManager 会原地修改 messages，以控制发送给模型的上下文规模。
        self.context = ContextManager(max_tokens=max_context_tokens)
        self.max_rounds = max_rounds
        self._system = system_prompt(self.tools)

        # wire up sub-agent capability
        # 子 Agent 工具需要反向引用父 Agent，才能复用其 LLM、工具和上下文配置。
        for t in self.tools:
            if isinstance(t, AgentTool):
                t._parent_agent = self

    def _full_messages(self) -> list[dict]:
        """构造本轮模型请求；不把 system 消息永久写入会话历史。"""
        return [{"role": "system", "content": self._system}] + self.messages

    def _tool_schemas(self) -> list[dict]:
        """把 Python 工具对象转换为 OpenAI function-calling Schema。"""
        return [t.schema() for t in self.tools]

    def chat(self, user_input: str, on_token=None, on_tool=None) -> str:
        """Process one user message. May involve multiple LLM/tool rounds."""
        # 新用户消息先进入历史，再检查是否需要压缩旧上下文。
        self.messages.append({"role": "user", "content": user_input})
        self.context.maybe_compress(self.messages, self.llm)

        # 每轮最多产生一次模型响应；工具结果会触发下一轮模型推理。
        for _ in range(self.max_rounds):
            # 发送完整历史和当前实例声明的工具 Schema，并透传流式 token 回调。
            resp = self.llm.chat(
                messages=self._full_messages(),
                tools=self._tool_schemas(),
                on_token=on_token,
            )

            # no tool calls -> LLM is done, return text
            if not resp.tool_calls:
                self.messages.append(resp.message)
                return resp.content

            # tool calls -> execute (parallel when multiple, like Claude Code's
            # StreamingToolExecutor which runs independent tools concurrently)
            # assistant 的 Tool Call 必须先入历史，随后对应的 tool 消息才能引用 call id。
            self.messages.append(resp.message)

            if len(resp.tool_calls) == 1:
                tc = resp.tool_calls[0]
                if on_tool:
                    on_tool(tc.name, tc.arguments)
                result = self._exec_tool(tc)
                self.messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                })
            else:
                # parallel execution for multiple tool calls
                # 返回结果保持原 Tool Call 顺序，确保 zip 后的 tool_call_id 不错配。
                results = self._exec_tools_parallel(resp.tool_calls, on_tool)
                for tc, result in zip(resp.tool_calls, results):
                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    })

            # compress if tool outputs are big
            self.context.maybe_compress(self.messages, self.llm)

        # 轮次上限是最小终止保护，避免模型持续调用工具形成无限循环。
        return "(reached maximum tool-call rounds)"

    def _exec_tool(self, tc) -> str:
        """Execute a single tool call, returning the result string."""
        # 注意：当前实现从全局 ALL_TOOLS 查找，而不是从 self.tools 查找。
        # 因此自定义工具可能被展示给模型，却无法在这里执行；这是后续重构重点。
        tool = get_tool(tc.name)
        if tool is None:
            return f"Error: unknown tool '{tc.name}'"
        try:
            return tool.execute(**tc.arguments)
        except TypeError as e:
            return f"Error: bad arguments for {tc.name}: {e}"
        except Exception as e:
            return f"Error executing {tc.name}: {e}"

    def _exec_tools_parallel(self, tool_calls, on_tool=None) -> list[str]:
        """Run multiple tool calls concurrently using threads.

        This is inspired by Claude Code's StreamingToolExecutor which starts
        executing tools while the model is still generating.  We simplify to:
        when the model returns N tool calls at once, run them in parallel.
        """
        for tc in tool_calls:
            if on_tool:
                on_tool(tc.name, tc.arguments)

        # 线程池适合 I/O 型工具；当前实现没有区分只读与有副作用工具。
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            futures = [pool.submit(self._exec_tool, tc) for tc in tool_calls]
            return [f.result() for f in futures]

    # reset 只清空对话，不重置 LLM token 计数、Bash cwd 或已修改文件集合。
    def reset(self):
        """Clear conversation history."""
        self.messages.clear()
