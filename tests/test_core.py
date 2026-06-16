"""Tests for core modules: config, context, session, imports."""
# 学习导读：本文件用小而直接的断言锁定公开 API、配置、上下文压缩、
# 会话持久化、费用计算和变更跟踪。测试名本身描述行为，注释重点解释夹具与隔离。

import os
import pathlib

from codingagent import Agent, LLM, Config, ALL_TOOLS, __version__
from codingagent.context import ContextManager, estimate_tokens
from codingagent.session import save_session, load_session, list_sessions
from codingagent.tools import get_tool


def test_version():
    assert __version__ == "0.3.0"


def test_public_api_exports():
    """Users should be able to import key classes from the top-level package."""
    assert Agent is not None
    assert LLM is not None
    assert Config is not None
    assert len(ALL_TOOLS) == 7


# 环境变量测试手动保存或删除状态，避免一个用例污染下一个用例。
def test_config_from_env():
    os.environ["CODINGAGENT_MODEL"] = "test-model"
    c = Config.from_env()
    assert c.model == "test-model"
    del os.environ["CODINGAGENT_MODEL"]


def test_config_defaults():
    # temporarily clear relevant env vars
    saved = {}
    for k in ["CODINGAGENT_MODEL", "CODINGAGENT_MAX_TOKENS"]:
        if k in os.environ:
            saved[k] = os.environ.pop(k)

    c = Config.from_env()
    assert c.model == "gpt-4o"
    assert c.max_tokens == 4096
    assert c.temperature == 0.0

    os.environ.update(saved)


# --- Context ---
# 这里有意直接测试私有压缩层，以便精确定位哪一层发生回归。

def test_estimate_tokens():
    msgs = [{"role": "user", "content": "hello world"}]
    t = estimate_tokens(msgs)
    assert t > 0
    assert t < 100


def test_context_snip():
    ctx = ContextManager(max_tokens=3000)
    msgs = [
        {"role": "tool", "tool_call_id": "t1", "content": "x\n" * 1000},
    ]
    # 使用前后 token 估值比较效果，而不是依赖具体摘要文本。
    before = estimate_tokens(msgs)
    ctx._snip_tool_outputs(msgs)
    after = estimate_tokens(msgs)
    assert after < before


def test_context_compress():
    ctx = ContextManager(max_tokens=2000)
    msgs = []
    for i in range(20):
        msgs.append({"role": "user", "content": f"msg {i} " + "a" * 200})
        msgs.append({"role": "tool", "tool_call_id": f"t{i}", "content": "b" * 2000})
    # 使用前后 token 估值比较效果，而不是依赖具体摘要文本。
    before = estimate_tokens(msgs)
    ctx.maybe_compress(msgs, None)
    after = estimate_tokens(msgs)
    assert after < before
    assert len(msgs) < 40  # should be compressed


# --- Session ---
# 会话测试会落盘到用户目录，因此每个创建文件的用例都负责清理。

def test_session_save_load():
    msgs = [{"role": "user", "content": "test message"}]
    sid = save_session(msgs, "test-model", "pytest_test_session")
    loaded = load_session("pytest_test_session")
    assert loaded is not None
    assert loaded[0] == msgs
    assert loaded[1] == "test-model"
    # cleanup
    pathlib.Path.home().joinpath(".codingagent/sessions/pytest_test_session.json").unlink()


def test_session_name_is_sanitized():
    msgs = [{"role": "user", "content": "test message"}]
    sid = save_session(msgs, "test-model", "../Research Notes!")

    assert sid == "Research-Notes"
    path = pathlib.Path.home().joinpath(".codingagent/sessions/Research-Notes.json")
    assert path.exists()
    assert load_session("../Research Notes!") is not None
    path.unlink()


def test_session_not_found():
    assert load_session("nonexistent_session_id") is None


def test_list_sessions():
    sessions = list_sessions()
    assert isinstance(sessions, list)


# --- Cost estimation ---

def test_cost_estimation_known_model():
    from codingagent.llm import LLM
    # 绕过 __init__，避免测试纯费用公式时创建真实 OpenAI 客户端。
    llm = LLM.__new__(LLM)
    llm.model = "gpt-5.4"
    llm.total_prompt_tokens = 1_000_000
    llm.total_completion_tokens = 500_000
    cost = llm.estimated_cost
    assert cost is not None
    assert cost == 2.5 + 7.5  # $2.5/M in + $15/M out * 0.5M

def test_cost_estimation_unknown_model():
    from codingagent.llm import LLM
    # 绕过 __init__，避免测试纯费用公式时创建真实 OpenAI 客户端。
    llm = LLM.__new__(LLM)
    llm.model = "some-custom-model"
    llm.total_prompt_tokens = 1000
    llm.total_completion_tokens = 500
    assert llm.estimated_cost is None


# --- Changed files tracking ---

def test_edit_tracks_changed_files(tmp_path):
    from codingagent.tools.edit import _changed_files
    # _changed_files 是模块级共享集合；测试前后清空以保持用例独立。
    _changed_files.clear()
    edit = get_tool("edit_file")
    path = tmp_path / "sample.py"
    path.write_text("aaa\nbbb\n")
    edit.execute(file_path=str(path), old_string="aaa", new_string="zzz")
    assert any(str(path) in p for p in _changed_files)
    # _changed_files 是模块级共享集合；测试前后清空以保持用例独立。
    _changed_files.clear()


def test_write_tracks_changed_files(tmp_path):
    from codingagent.tools.edit import _changed_files
    # _changed_files 是模块级共享集合；测试前后清空以保持用例独立。
    _changed_files.clear()
    write = get_tool("write_file")
    path = tmp_path / "tracked.txt"
    write.execute(file_path=str(path), content="tracked\n")
    assert any("tracked" not in p and path.name in p for p in _changed_files) or len(_changed_files) > 0
    # _changed_files 是模块级共享集合；测试前后清空以保持用例独立。
    _changed_files.clear()
