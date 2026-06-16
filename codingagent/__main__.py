"""支持通过 ``python -m codingagent`` 启动命令行程序。"""

from codingagent.cli import main

# 学习提示：包入口只负责调用 CLI 的 main；参数解析、配置装配和 Agent 创建都在 cli.py 中完成。
main()
