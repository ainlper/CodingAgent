"""File reading with line numbers."""
# 学习导读：读取工具把任意文本文件转换成带 1-based 行号的模型上下文，
# 并通过 offset/limit 控制单次注入的内容规模。

from pathlib import Path
from .base import Tool


class ReadFileTool(Tool):
    """按行读取文本文件，并返回适合模型定位代码的编号视图。"""
    name = "read_file"
    description = (
        "Read a file's contents with line numbers. "
        "Always read a file before editing it."
    )
    # parameters 会直接暴露给模型，默认值仍由 Python execute 签名提供。
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path to the file",
            },
            "offset": {
                "type": "integer",
                "description": "Start line (1-based). Default 1.",
            },
            "limit": {
                "type": "integer",
                "description": "Max lines to read. Default 2000.",
            },
        },
        "required": ["file_path"],
    }

    def execute(self, file_path: str, offset: int = 1, limit: int = 2000) -> str:
        """规范化路径、切片目标行并生成带行号的字符串结果。"""
        try:
            # expanduser 处理 ~，resolve 生成绝对路径；当前未限制必须位于项目目录。
            p = Path(file_path).expanduser().resolve()
            if not p.exists():
                return f"Error: {file_path} not found"
            if not p.is_file():
                return f"Error: {file_path} is a directory, not a file"

            # errors=replace 允许包含坏编码字节的文件仍被读取和分析。
            text = p.read_text(errors="replace")
            lines = text.splitlines()
            total = len(lines)

            # 外部接口从 1 开始计数，Python 切片从 0 开始，因此需要减一。
            start = max(0, offset - 1)
            chunk = lines[start : start + limit]
            # 返回字符串而非结构化行对象，是为了直接作为 Tool Message 内容。
            numbered = [f"{start + i + 1}\t{ln}" for i, ln in enumerate(chunk)]
            result = "\n".join(numbered)

            if total > start + limit:
                result += f"\n... ({total} lines total, showing {start+1}-{start+len(chunk)})"
            return result or "(empty file)"
        except Exception as e:
            return f"Error: {e}"
