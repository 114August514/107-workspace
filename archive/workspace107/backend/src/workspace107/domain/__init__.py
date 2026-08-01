"""领域层。

只包含领域对象、枚举、规则和端口定义。
不依赖 Web 框架、ORM 或任何 infrastructure 模块——依赖方向是

    application -> domain ports <- infrastructure

违反这一点的 import 会被 ruff 的 flake8-tidy-imports 规则拦下。
"""
