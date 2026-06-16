"""Content search with regex support."""
# 学习导读：Grep 在 Python 中递归枚举文本文件并逐行应用正则；它返回
# ``路径:行号:内容``，让模型可以继续用 read_file 精读命中位置。

import re
from pathlib import Path
from .base import Tool

# skip these dirs to avoid noise
# 跳过依赖、缓存、构建和版本库目录，减少噪声与无意义 I/O。
_SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".tox", "dist", "build"}


class GrepTool(Tool):
    """在单文件或目录树中执行正则内容搜索。"""
    name = "grep"
    description = (
        "Search file contents with regex. "
        "Returns matching lines with file path and line number."
    )
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Regex pattern to search for",
            },
            "path": {
                "type": "string",
                "description": "File or directory to search (default: cwd)",
            },
            "include": {
                "type": "string",
                "description": "Only search files matching this glob (e.g. '*.py')",
            },
        },
        "required": ["pattern"],
    }

    def execute(self, pattern: str, path: str = ".", include: str | None = None) -> str:
        """编译正则、收集候选文件并返回最多 200 条逐行匹配。"""
        # 先编译正则，把语法错误作为工具结果反馈给模型，而不是抛出异常。
        try:
            regex = re.compile(pattern)
        except re.error as e:
            return f"Invalid regex: {e}"

        base = Path(path).expanduser().resolve()
        if not base.exists():
            return f"Error: {path} not found"

        # 文件路径直接搜索；目录路径则调用 _walk 枚举候选文件。
        if base.is_file():
            files = [base]
        else:
            files = self._walk(base, include)

        # 单个不可读或非文本文件不会终止整次仓库搜索。
        matches = []
        for fp in files:
            try:
                text = fp.read_text(errors="ignore")
            except OSError:
                continue
            for lineno, line in enumerate(text.splitlines(), 1):
                if regex.search(line):
                    matches.append(f"{fp}:{lineno}: {line.rstrip()}")
                    # 匹配数上限控制 Tool Message 大小和搜索耗时。
                    if len(matches) >= 200:
                        matches.append("... (200 match limit reached)")
                        return "\n".join(matches)

        return "\n".join(matches) if matches else "No matches found."

    @staticmethod
    def _walk(root: Path, include: str | None) -> list[Path]:
        """递归枚举最多 5000 个文件，并过滤已知噪声目录。"""
        results = []
        # include 同时充当 pathlib glob，例如 *.py；为空时枚举所有条目。
        for item in root.rglob(include or "*"):
            # skip hidden/junk directories
            if any(part in _SKIP_DIRS for part in item.parts):
                continue
            if item.is_file():
                results.append(item)
            if len(results) >= 5000:
                break
        return results
