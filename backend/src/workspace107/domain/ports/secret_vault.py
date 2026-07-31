"""Secret 存取端口。

GR-012：Secret 明文不进入领域对象、Run Snapshot、日志和 API 响应。

因此这个端口的读取入口只有 ``resolve``，它只在执行边界上被调用一次，
用来把值注入子进程环境；其余路径只能拿到名称列表。
"""

from __future__ import annotations

from typing import Protocol


class SecretVault(Protocol):
    async def set_secret(self, workspace_id: str, name: str, value: str) -> None: ...

    async def delete_secret(self, workspace_id: str, name: str) -> None: ...

    async def list_names(self, workspace_id: str) -> set[str]:
        """列出 Workspace 中已配置的 Secret 名称，不返回值。"""
        ...

    async def resolve(self, workspace_id: str, names: list[str]) -> dict[str, str]:
        """取出指定 Secret 的值，仅供执行阶段注入进程环境使用。

        缺失的名称直接省略，由调用方决定如何处理。
        """
        ...
