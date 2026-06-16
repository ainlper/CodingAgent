"""Search-and-replace file editing (Claude Code's key innovation).

The core idea: instead of sending whole-file rewrites or line-number patches,
the LLM specifies an *exact* substring to find and its replacement. The
substring must appear exactly once in the file, which eliminates ambiguity
and makes edits safe and reviewable.
"""
# 学习导读：edit_file 采用“精确旧文本 -> 新文本”的乐观编辑协议。唯一匹配
# 既避免行号漂移，也让模型必须提供足够上下文来证明修改位置明确。

import difflib
from pathlib import Path

from .base import Tool

# track files changed this session for /diff
# 进程级集合供 CLI /diff 使用；它记录路径而非真实 Git Diff。
_changed_files: set[str] = set()


class EditFileTool(Tool):
    """仅在 old_string 唯一出现时执行一次替换，并返回统一 Diff。"""
    name = "edit_file"
    description = (
        "Edit a file by replacing an exact string match. "
        "old_string must appear exactly once in the file for safety. "
        "Include enough surrounding context to ensure uniqueness."
    )
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path to the file to edit",
            },
            "old_string": {
                "type": "string",
                "description": "Exact text to find (must be unique in file)",
            },
            "new_string": {
                "type": "string",
                "description": "Replacement text",
            },
        },
        "required": ["file_path", "old_string", "new_string"],
    }

    def execute(self, file_path: str, old_string: str, new_string: str) -> str:
        """检查文件与匹配数量，写回替换结果并登记修改。"""
        try:
            p = Path(file_path).expanduser().resolve()
            if not p.exists():
                return f"Error: {file_path} not found"

            # 先读取完整旧内容，后续既用于唯一性检查，也用于生成前后 Diff。
            content = p.read_text()
            occurrences = content.count(old_string)

            # 零匹配时返回文件开头，帮助模型重新读取并修正 old_string。
            if occurrences == 0:
                preview = content[:500] + ("..." if len(content) > 500 else "")
                return (
                    f"Error: old_string not found in {file_path}.\n"
                    f"File starts with:\n{preview}"
                )
            # 多匹配时拒绝猜测，要求模型增加上下文使目标片段唯一。
            if occurrences > 1:
                return (
                    f"Error: old_string appears {occurrences} times in {file_path}. "
                    f"Include more surrounding lines to make it unique."
                )

            # count=1 是额外保险；理论上前面的唯一性检查已保证只有一处。
            new_content = content.replace(old_string, new_string, 1)
            p.write_text(new_content)
            _changed_files.add(str(p))

            # generate a unified diff so the user/LLM can see exactly what changed
            diff = _unified_diff(content, new_content, str(p))
            return f"Edited {file_path}\n{diff}"
        except Exception as e:
            return f"Error: {e}"


# Diff 仅用于反馈和审查，真正写入已在调用该函数之前完成。
def _unified_diff(old: str, new: str, filename: str, context: int = 3) -> str:
    """Generate a compact unified diff between old and new file content."""
    # keepends=True 保留换行符，使 difflib 输出标准统一 Diff 格式。
    old_lines = old.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)
    diff = difflib.unified_diff(
        old_lines, new_lines,
        fromfile=f"a/{filename}", tofile=f"b/{filename}",
        n=context,
    )
    result = "".join(diff)
    # truncate enormous diffs
    # 限制返回给模型的内容，避免一次大改动快速占满上下文。
    if len(result) > 3000:
        result = result[:2500] + "\n... (diff truncated)\n"
    return result
