"""Secret 存取端口。

GR-304 及设计稿 §3.1.4：Secret 明文不进入领域对象、Run Snapshot、日志和 API 响应。

因此这个端口的读取入口只有 ``resolve``，它只在执行边界上被调用一次，
用来把值注入子进程环境；其余路径只能拿到名称列表。
"""

from typing import Protocol

from ..config_scope import ConfigScope, SecretReference


class SecretVault(Protocol):
    async def set_secret(self, scope: ConfigScope, name: str, value: str) -> None: ...

    async def delete_secret(self, scope: ConfigScope, name: str) -> None: ...

    async def list_names(self, scope: ConfigScope) -> set[str]:
        """列出一个明确 scope 的 Secret 名称，不返回值。"""
        ...

    async def resolve(self, references: list[SecretReference]) -> dict[SecretReference, str]:
        """Resolve exact references only at execution boundary."""
        ...
