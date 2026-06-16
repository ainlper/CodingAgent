"""File creation / overwrite."""
# 学习导读：写入工具适合创建文件或整文件覆盖；它不计算补丁，也不验证旧内容，
# 因此小范围修改应优先使用 edit_file。

from pathlib import Path
from .base import Tool
from .edit import _changed_files


class WriteFileTool(Tool):
    """创建父目录并一次性写入完整文本内容。"""
    name = "write_file"
    description = (
        "Create a new file or completely overwrite an existing one. "
        "For small edits to existing files, prefer edit_file instead."
    )
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path for the file",
            },
            "content": {
                "type": "string",
                "description": "Full file content to write",
            },
        },
        "required": ["file_path", "content"],
    }

    def execute(self, file_path: str, content: str) -> str:
        """完成路径规范化、目录创建、写入和变更文件登记。"""
        try:
            # 当前路径可解析到项目外；后续安全化应在统一 Workspace Policy 中限制。
            p = Path(file_path).expanduser().resolve()
            # parents=True 允许一次创建多级目录，exist_ok=True 保持重复调用幂等。
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
            # 使用绝对路径登记，供 CLI 的 /diff 命令展示本会话修改范围。
            _changed_files.add(str(p))
            # 无结尾换行的最后一行也需要计入，因此不能只统计换行符。
            n_lines = content.count("\n") + (1 if content and not content.endswith("\n") else 0)
            return f"Wrote {n_lines} lines to {file_path}"
        except Exception as e:
            return f"Error: {e}"
