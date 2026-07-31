"""测试包。

分层：

    unit/         领域规则与不变量，不碰数据库
    integration/  端到端闭环，真实 SQLite + 真实子进程执行
    security/     GR-304 Secret 不落明文、无发现权限即不存在
    contract/     API 契约与错误码映射
"""
