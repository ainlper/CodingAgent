"""会话 ID 唯一性与恢复行为测试。

学习导读：monkeypatch 把真实用户会话目录替换成 pytest 临时目录，既避免
污染 ~/.corecoder，也让两个自动生成 ID 的文件副作用可以被直接验证。
"""

from codingagent import session as session_module
from codingagent.session import load_session, save_session


def test_default_session_ids_do_not_collide(tmp_path, monkeypatch):
    # 只替换模块变量；save_session 和 load_session 会自动使用新目录。
    monkeypatch.setattr(session_module, "SESSIONS_DIR", tmp_path)

    # 连续保存模拟同一秒内创建会话，UUID 后缀应保证不碰撞。
    first_id = save_session([{"role": "user", "content": "first"}], "model-a")
    second_id = save_session([{"role": "user", "content": "second"}], "model-b")

    # 除了 ID 不同，还验证每个 ID 能恢复到各自消息和模型。
    assert first_id != second_id
    assert load_session(first_id) == (
        [{"role": "user", "content": "first"}],
        "model-a",
    )
    assert load_session(second_id) == (
        [{"role": "user", "content": "second"}],
        "model-b",
    )
