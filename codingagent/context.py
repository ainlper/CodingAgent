"""Multi-layer context compression.

Claude Code uses a 4-layer strategy:
  1. HISTORY_SNIP   - trim old tool outputs to a one-line summary
  2. Microcompact   - LLM-powered summary of old turns (cached)
  3. CONTEXT_COLLAPSE - aggressive compression when nearing hard limit
  4. Autocompact    - periodic background compaction

CoreCoder implements the same idea in 3 layers:
  Layer 1 (tool_snip)   - replace verbose tool results with truncated versions
  Layer 2 (summarize)   - LLM-powered summary of old conversation
  Layer 3 (hard_collapse) - last resort: drop everything except summary + recent
"""
# 学习导读：该模块接收 Agent 的可变消息列表并直接原地压缩。三层策略从
# 无损伤较小的工具输出截断，逐步升级到摘要和紧急折叠，以换取可继续推理的空间。

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .llm import LLM


def _approx_tokens(text: str) -> int:
    """Rough token count. ~3.5 chars/token for mixed en/zh content."""
    return len(text) // 3


def estimate_tokens(messages: list[dict]) -> int:
    """估算整段消息历史的 token 数；同时计入文本和 Tool Call 参数。"""
    total = 0
    for m in messages:
        if m.get("content"):
            total += _approx_tokens(m["content"])
        if m.get("tool_calls"):
            total += _approx_tokens(str(m["tool_calls"]))
    return total


class ContextManager:
    """根据上下文占用率按层触发压缩策略。"""
    def __init__(self, max_tokens: int = 128_000):
        """由模型上下文上限派生三档阈值，统一管理压缩时机。"""
        self.max_tokens = max_tokens
        # layer thresholds (fraction of max_tokens)
        self._snip_at = int(max_tokens * 0.50)    # 50% -> snip tool outputs
        self._summarize_at = int(max_tokens * 0.70)  # 70% -> LLM summarize
        self._collapse_at = int(max_tokens * 0.90)   # 90% -> hard collapse

    def maybe_compress(self, messages: list[dict], llm: LLM | None = None) -> bool:
        """Apply compression layers as needed. Returns True if any compression happened."""
        # 每次调用都重新估算，因为前一层压缩会改变是否需要执行后一层。
        current = estimate_tokens(messages)
        compressed = False

        # Layer 1: snip verbose tool outputs
        if current > self._snip_at:
            if self._snip_tool_outputs(messages):
                compressed = True
                current = estimate_tokens(messages)

        # Layer 2: LLM-powered summarization of old turns
        if current > self._summarize_at and len(messages) > 10:
            if self._summarize_old(messages, llm, keep_recent=8):
                compressed = True
                current = estimate_tokens(messages)

        # Layer 3: hard collapse - last resort
        if current > self._collapse_at and len(messages) > 4:
            self._hard_collapse(messages, llm)
            compressed = True

        return compressed

    @staticmethod
    def _snip_tool_outputs(messages: list[dict]) -> bool:
        """Layer 1: Truncate tool results over 1500 chars to their first/last lines.

        This mirrors Claude Code's HISTORY_SNIP which replaces old tool outputs
        with a one-line summary to reclaim context space.
        """
        changed = False
        for m in messages:
            if m.get("role") != "tool":
                continue
            content = m.get("content", "")
            if len(content) <= 1500:
                continue
            lines = content.splitlines()
            if len(lines) <= 6:
                continue
            # keep first 3 + last 3 lines
            snipped = (
                "\n".join(lines[:3])
                + f"\n... ({len(lines)} lines, snipped to save context) ...\n"
                + "\n".join(lines[-3:])
            )
            m["content"] = snipped
            changed = True
        return changed

    def _summarize_old(self, messages: list[dict], llm: LLM | None,
                       keep_recent: int = 8) -> bool:
        """Layer 2: Summarize old conversation, keep recent messages intact."""
        if len(messages) <= keep_recent:
            return False

        # 旧消息用于生成摘要，最近消息保持原始精度，避免丢失当前工作状态。
        old = messages[:-keep_recent]
        tail = messages[-keep_recent:]

        summary = self._get_summary(old, llm)

        # 原地替换而非返回新列表，确保 Agent 持有的同一个 messages 对象立即生效。
        messages.clear()
        messages.append({
            "role": "user",
            "content": f"[Context compressed - conversation summary]\n{summary}",
        })
        messages.append({
            "role": "assistant",
            "content": "Got it, I have the context from our earlier conversation.",
        })
        messages.extend(tail)
        return True

    def _hard_collapse(self, messages: list[dict], llm: LLM | None):
        """Layer 3: Emergency compression. Keep only last 4 messages + summary."""
        # 紧急折叠只保留极少近期消息，其余全部收敛为一段摘要。
        tail = messages[-4:] if len(messages) > 4 else messages[-2:]
        summary = self._get_summary(messages[:-len(tail)], llm)

        # 原地替换而非返回新列表，确保 Agent 持有的同一个 messages 对象立即生效。
        messages.clear()
        messages.append({
            "role": "user",
            "content": f"[Hard context reset]\n{summary}",
        })
        messages.append({
            "role": "assistant",
            "content": "Context restored. Continuing from where we left off.",
        })
        messages.extend(tail)

    def _get_summary(self, messages: list[dict], llm: LLM | None) -> str:
        """Generate summary via LLM or fallback to extraction."""
        # 先把多角色消息转成带角色标签的纯文本，供摘要模型阅读。
        flat = self._flatten(messages)

        # llm 为可选依赖：在线时生成语义摘要，离线或失败时执行规则提取。
        if llm:
            try:
                # 摘要请求不提供 tools，避免压缩过程再次触发工具调用。
                resp = llm.chat(
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "Compress this conversation into a brief summary. "
                                "Preserve: file paths edited, key decisions made, "
                                "errors encountered, current task state. "
                                "Drop: verbose command output, code listings, "
                                "redundant back-and-forth."
                            ),
                        },
                        {"role": "user", "content": flat[:15000]},
                    ],
                )
                return resp.content
            except Exception:
                pass

        # 降级路径保证模型服务异常时，主 Agent 仍能回收上下文。
        # fallback: extract key lines
        return self._extract_key_info(messages)

    @staticmethod
    def _flatten(messages: list[dict]) -> str:
        """将多角色消息压平成带角色标签且限制长度的摘要输入。"""
        # 每条消息最多保留 400 字，防止摘要输入本身再次膨胀。
        parts = []
        for m in messages:
            role = m.get("role", "?")
            text = m.get("content", "") or ""
            if text:
                parts.append(f"[{role}] {text[:400]}")
        return "\n".join(parts)

    @staticmethod
    def _extract_key_info(messages: list[dict]) -> str:
        """Fallback: extract file paths, errors, and decisions without LLM."""
        import re
        # 规则摘要重点保留恢复任务最有价值的文件路径和错误线索。
        files_seen = set()
        errors = []
        decisions = []

        for m in messages:
            text = m.get("content", "") or ""
            # extract file paths
            for match in re.finditer(r'[\w./\-]+\.\w{1,5}', text):
                files_seen.add(match.group())
            # extract error lines
            for line in text.splitlines():
                if 'error' in line.lower() or 'Error' in line:
                    errors.append(line.strip()[:150])

        # 将规则提取结果重新组织为紧凑摘要，并限制文件与错误条目数量。
        parts = []
        if files_seen:
            parts.append(f"Files touched: {', '.join(sorted(files_seen)[:20])}")
        if errors:
            parts.append(f"Errors seen: {'; '.join(errors[:5])}")
        return "\n".join(parts) or "(no extractable context)"
