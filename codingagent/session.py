"""Session persistence - save and resume conversations.

Claude Code maintains session state via QueryEngine (1295 lines).
CoreCoder distills this to: JSON dump of messages + model config.
"""
# 学习导读：会话文件是一个 JSON 快照，保存消息历史、模型名和元数据。
# session id 会先规范化，再验证最终路径仍是 sessions 目录的直接子文件，
# 以避免 ``../`` 一类路径穿越。

import json
import re
import time
import uuid
from pathlib import Path

SESSIONS_DIR = Path.home() / ".codingagent" / "sessions"
_SAFE_SESSION_RE = re.compile(r"[^A-Za-z0-9._-]+")


# 将用户输入转成安全文件名；空值则生成带时间和随机后缀的新 ID。
def _normalize_session_id(session_id: str | None) -> str:
    """移除目录信息和危险字符，返回可安全用作文件名的会话 ID。"""
    if not session_id:
        return _new_session_id()

    name = session_id.strip().replace("\\", "/").split("/")[-1]
    name = _SAFE_SESSION_RE.sub("-", name).strip(".-_")
    return name or _new_session_id()


# 时间戳便于人读，UUID 后缀避免同一秒内创建会话时发生碰撞。
def _new_session_id() -> str:
    """生成兼顾可读时间和碰撞安全性的默认会话 ID。"""
    return f"session_{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"


# resolve 后再次检查父目录，形成规范化之外的第二道路径边界。
def _session_path(session_id: str) -> Path:
    """构造会话 JSON 路径，并确认其没有逃离会话目录。"""
    path = (SESSIONS_DIR / f"{_normalize_session_id(session_id)}.json").resolve()
    root = SESSIONS_DIR.resolve()
    if root != path.parent:
        raise ValueError("Invalid session id")
    return path


def save_session(messages: list[dict], model: str, session_id: str | None = None) -> str:
    """Save conversation to disk. Returns the session ID."""
    # 首次保存时惰性创建目录，避免 import 模块就产生磁盘副作用。
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

    session_id = _normalize_session_id(session_id)

    # JSON 数据保持与 OpenAI 消息格式一致，恢复后可直接放回 Agent。
    data = {
        "id": session_id,
        "model": model,
        "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "messages": messages,
    }

    path = _session_path(session_id)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    return session_id


def load_session(session_id: str) -> tuple[list[dict], str] | None:
    """Load a saved session. Returns (messages, model) or None."""
    path = _session_path(session_id)
    if not path.exists():
        return None

    data = json.loads(path.read_text())
    return data["messages"], data["model"]


def list_sessions() -> list[dict]:
    """List available sessions, newest first."""
    if not SESSIONS_DIR.exists():
        return []

    # 单个损坏会话不应阻止其他正常会话被列出。
    sessions = []
    for f in sorted(SESSIONS_DIR.glob("*.json"), reverse=True):
        try:
            data = json.loads(f.read_text())
            # grab first user message as preview
            preview = ""
            for m in data.get("messages", []):
                if m.get("role") == "user" and m.get("content"):
                    preview = m["content"][:80]
                    break
            sessions.append({
                "id": data.get("id", f.stem),
                "model": data.get("model", "?"),
                "saved_at": data.get("saved_at", "?"),
                "preview": preview,
            })
        except (json.JSONDecodeError, KeyError):
            continue

    return sessions[:20]  # cap at 20
