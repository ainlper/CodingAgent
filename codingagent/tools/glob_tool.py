"""File pattern matching."""
# 学习导读：Glob 只根据路径模式发现候选文件，不读取文件内容；它通常是 Agent
# 探索仓库时的第一步，之后再交给 read_file 或 grep 缩小范围。

from pathlib import Path
from .base import Tool


class GlobTool(Tool):
    """在指定目录下执行 pathlib glob，并限制返回结果数量。"""
    name = "glob"
    description = (
        "Find files matching a glob pattern. "
        "Supports ** for recursive matching (e.g. '**/*.py')."
    )
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Glob pattern, e.g. '**/*.py' or 'src/**/*.ts'",
            },
            "path": {
                "type": "string",
                "description": "Directory to search in (default: cwd)",
            },
        },
        "required": ["pattern"],
    }

    def execute(self, pattern: str, path: str = ".") -> str:
        """解析搜索根目录、匹配路径、按修改时间排序并格式化结果。"""
        try:
            # resolve 后使用该目录作为模式匹配根；当前允许搜索项目目录之外。
            base = Path(path).expanduser().resolve()
            if not base.is_dir():
                return f"Error: {path} is not a directory"

            # Path.glob 原生支持 ** 递归语法，返回文件和目录两种 Path。
            hits = list(base.glob(pattern))
            # sort by mtime, newest first
            # 新修改文件优先，通常更可能与当前任务相关。
            hits.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)

            total = len(hits)
            # 硬上限防止大型仓库一次返回数千路径占满上下文。
            shown = hits[:100]
            lines = [str(h) for h in shown]
            result = "\n".join(lines)

            if total > 100:
                result += f"\n... ({total} matches, showing first 100)"
            return result or "No files matched."
        except Exception as e:
            return f"Error: {e}"
