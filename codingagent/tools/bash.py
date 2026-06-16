"""Shell command execution with safety checks.

Claude Code's BashTool is 1,143 lines. This is the distilled version:
- Output capture with truncation (head+tail preserved)
- Timeout support
- Dangerous command detection
- Working directory tracking (cd awareness)
"""
# 学习导读：BashTool 是能力最强也风险最高的工具。当前安全层是命令字符串
# 正则黑名单，只能拦截典型危险形式，不能替代沙箱、权限隔离或命令解析器。

import os
import re
import subprocess
from .base import Tool

# track cwd across commands (Claude Code does this too)
# 模块级 cwd 让多次命令看起来处于同一个终端会话，也意味着多个 Agent 会共享状态。
_cwd: str | None = None

# patterns that could wreck the filesystem or leak secrets
# 每个元组保存“检测正则 + 用户可读原因”；该列表不是完整 Shell 语法分析。
_DANGEROUS_PATTERNS = [
    (r"\brm\s+(-\w*)?-r\w*\s+(/|~|\$HOME)", "recursive delete on home/root"),
    (r"\brm\s+(-\w*)?-rf\s", "force recursive delete"),
    (r"\bmkfs\b", "format filesystem"),
    (r"\bdd\s+.*of=/dev/", "raw disk write"),
    (r">\s*/dev/sd[a-z]", "overwrite block device"),
    (r"\bchmod\s+(-R\s+)?777\s+/", "chmod 777 on root"),
    (r":\(\)\s*\{.*:\|:.*\}", "fork bomb"),
    (r"\bcurl\b.*\|\s*(sudo\s+)?bash", "pipe curl to bash"),
    (r"\bwget\b.*\|\s*(sudo\s+)?bash", "pipe wget to bash"),
]


class BashTool(Tool):
    """在跟踪的工作目录中执行 Shell 命令，并做基础风险检查与截断。"""
    name = "bash"
    description = (
        "Execute a shell command. Returns stdout, stderr, and exit code. "
        "Use this for running tests, installing packages, git operations, etc."
    )
    parameters = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The shell command to run",
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout in seconds (default 120)",
            },
        },
        "required": ["command"],
    }

    def execute(self, command: str, timeout: int = 120) -> str:
        """检查危险模式，运行命令，更新 cwd，并格式化进程输出。"""
        # global 允许本次成功的 cd 影响下一次 execute 调用。
        global _cwd
        # safety check
        # 黑名单在启动子进程前执行；命中时命令完全不会运行。
        warning = _check_dangerous(command)
        if warning:
            return f"⚠ Blocked: {warning}\nCommand: {command}\nIf intentional, modify the command to be more specific."

        # use tracked working directory
        # 首次调用使用进程 cwd，之后优先使用工具自己跟踪的目录。
        cwd = _cwd or os.getcwd()

        try:
            # shell=True 支持管道和重定向，但也扩大注入与解析风险。
            proc = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd,
            )

            # track cd commands so next command runs in the right place
            # 只有成功命令才更新目录，避免失败 cd 污染后续工作路径。
            if proc.returncode == 0:
                _update_cwd(command, cwd)
            out = proc.stdout
            if proc.stderr:
                out += f"\n[stderr]\n{proc.stderr}"
            if proc.returncode != 0:
                out += f"\n[exit code: {proc.returncode}]"
            # keep head + tail to preserve the most useful info
            # 同时保留头尾：开头常含命令上下文，结尾常含测试失败摘要。
            if len(out) > 15_000:
                out = (
                    out[:6000]
                    + f"\n\n... truncated ({len(out)} chars total) ...\n\n"
                    + out[-3000:]
                )
            return out.strip() or "(no output)"
        except subprocess.TimeoutExpired:
            return f"Error: timed out after {timeout}s"
        except Exception as e:
            return f"Error running command: {e}"


# 安全检查返回原因而非布尔值，便于把阻止依据反馈给用户和模型。
def _check_dangerous(cmd: str) -> str | None:
    """Return a warning string if the command looks destructive, else None."""
    for pattern, reason in _DANGEROUS_PATTERNS:
        if re.search(pattern, cmd):
            return reason
    return None


# 这里只识别简单 cd 和 && 链，不模拟子 Shell、分号、变量或复杂脚本语义。
def _update_cwd(command: str, current_cwd: str):
    """Track directory changes from cd commands."""
    global _cwd
    # simple heuristic: look for cd at the end of a && chain or standalone
    parts = command.split("&&")
    for part in parts:
        part = part.strip()
        if part.startswith("cd "):
            target = part[3:].strip().strip("'\"")
            if target:
                new_dir = os.path.normpath(os.path.join(current_cwd, os.path.expanduser(target)))
                if os.path.isdir(new_dir):
                    _cwd = new_dir
