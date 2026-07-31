"""分层与依赖注入的可执行约定。

    api  ->  application  ->  domain ports  <-  infrastructure

这些规则光写在 README 里会慢慢烂掉。放成测试，违反了当场就红。

用 AST 静态分析而不是真的 import，这样即使某个模块有导入副作用也不影响检查。
"""

from __future__ import annotations

import ast
from dataclasses import fields
from pathlib import Path
from typing import get_type_hints

import pytest

from workspace107.api.deps import Services

SRC = Path(__file__).resolve().parents[2] / "src" / "workspace107"

# 唯一允许把具体实现接到用例上的地方：组合根。
COMPOSITION_ROOTS = {"main.py", "api/deps.py"}


def module_imports(path: Path) -> set[str]:
    """取出一个模块 import 的所有顶层模块名和包内相对目标。"""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                names.add(node.module)
            elif node.module:
                # 相对导入：用 ".." * level + module 表达，够判断层级了
                names.add("." * node.level + node.module)
    return names


def layer_modules(layer: str) -> list[Path]:
    return sorted(p for p in (SRC / layer).rglob("*.py") if p.name != "__init__.py")


def relative(path: Path) -> str:
    return str(path.relative_to(SRC))


def imports_layer(names: set[str], layer: str) -> bool:
    """判断这组 import 里有没有指向某一层的。"""
    return any(
        name == f"workspace107.{layer}"
        or name.startswith(f"workspace107.{layer}.")
        # 相对导入形如 ..infrastructure.db.tables 或 ...domain.models
        or (name.lstrip(".").split(".")[0] == layer and name.startswith("."))
        for name in names
    )


@pytest.mark.parametrize("path", layer_modules("domain"), ids=relative)
def test_domain_层不依赖框架和基础设施(path: Path) -> None:
    names = module_imports(path)
    for banned in ("fastapi", "sqlalchemy", "httpx", "pydantic"):
        assert not any(n == banned or n.startswith(f"{banned}.") for n in names), (
            f"{relative(path)} 依赖了 {banned}。领域层必须能脱离框架单独理解和测试。"
        )
    assert not imports_layer(names, "infrastructure"), (
        f"{relative(path)} 依赖了 infrastructure。依赖方向应当反过来。"
    )
    assert not imports_layer(names, "api"), f"{relative(path)} 依赖了 api 层。"


@pytest.mark.parametrize("path", layer_modules("application"), ids=relative)
def test_application_层只依赖领域端口(path: Path) -> None:
    names = module_imports(path)
    for banned in ("fastapi", "sqlalchemy"):
        assert not any(n == banned or n.startswith(f"{banned}.") for n in names), (
            f"{relative(path)} 依赖了 {banned}。用例层只认 domain/ports 里的协议。"
        )
    assert not imports_layer(names, "infrastructure"), (
        f"{relative(path)} 直接依赖了 infrastructure。"
        "需要什么能力就在 domain/ports 里定义端口，由组合根注入具体实现。"
    )
    assert not imports_layer(names, "api"), f"{relative(path)} 依赖了 api 层。"


@pytest.mark.parametrize("path", layer_modules("api"), ids=relative)
def test_api_层不直接依赖基础设施(path: Path) -> None:
    """路由只做请求解析和响应序列化，具体实现由组合根注入。"""
    if relative(path) in COMPOSITION_ROOTS:
        return
    names = module_imports(path)
    assert not imports_layer(names, "infrastructure"), (
        f"{relative(path)} 直接依赖了 infrastructure。"
        "只有 api/deps.py 和 main.py 这两个组合根可以接具体实现。"
    )


def test_services_容器只暴露用例服务() -> None:
    """路由拿不到仓储、存储和调度器，就没办法绕过用例层。

    绕过用例层等于绕过权限校验、事务边界和领域规则——
    所以这不是洁癖，是一条安全边界。
    """
    # deps.py 用了 from __future__ import annotations，字段类型是字符串，
    # 这里解析回真正的类再判断它来自哪一层。
    resolved = get_type_hints(Services)
    leaked = [
        f.name
        for f in fields(Services)
        if not getattr(resolved[f.name], "__module__", "").startswith("workspace107.application")
    ]
    assert leaked == [], (
        f"Services 暴露了非用例层的依赖：{leaked}。"
        "需要新能力时请新增用例服务或给现有服务加方法，不要往容器里塞端口。"
    )


def test_组合根只有两个() -> None:
    """具体实现被接到用例上的地方越少越好，换实现时才只改一处。"""
    constructors = {"SqlRepositories(", "DatabaseSecretVault(", "LocalStorage(", "MockScheduler("}
    offenders: list[str] = []
    for path in sorted(SRC.rglob("*.py")):
        name = relative(path)
        if name in COMPOSITION_ROOTS or name.startswith("tools/"):
            continue
        source = path.read_text(encoding="utf-8")
        if any(ctor in source for ctor in constructors):
            offenders.append(name)
    assert offenders == [], (
        f"这些模块里直接构造了具体实现：{offenders}。装配只应发生在 {sorted(COMPOSITION_ROOTS)}。"
    )
