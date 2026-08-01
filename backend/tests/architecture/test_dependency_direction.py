"""用 AST 检查与目标架构一致的稳定依赖方向。"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src" / "workspace107"


def _module_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                names.add(node.module)
            elif node.module:
                names.add("." * node.level + node.module)
    return names


def _layer_modules(layer: str) -> list[Path]:
    return sorted(path for path in (SRC / layer).rglob("*.py") if path.name != "__init__.py")


def _relative(path: Path) -> str:
    return str(path.relative_to(SRC))


def _imports_layer(names: set[str], layer: str) -> bool:
    return any(
        name == f"workspace107.{layer}"
        or name.startswith(f"workspace107.{layer}.")
        or (name.startswith(".") and name.lstrip(".").split(".")[0] == layer)
        for name in names
    )


@pytest.mark.parametrize("path", _layer_modules("domain"), ids=_relative)
def test_domain_does_not_depend_on_frameworks_or_outer_layers(path: Path) -> None:
    names = _module_imports(path)
    for banned in ("fastapi", "sqlalchemy", "httpx", "pydantic"):
        assert not any(name == banned or name.startswith(f"{banned}.") for name in names), (
            f"{_relative(path)} 依赖了 {banned}。领域层必须能脱离框架单独理解和测试。"
        )
    assert not _imports_layer(names, "infrastructure"), (
        f"{_relative(path)} 依赖了 infrastructure。依赖方向应当反过来。"
    )
    assert not _imports_layer(names, "api"), f"{_relative(path)} 依赖了 api 层。"


@pytest.mark.parametrize("path", _layer_modules("application"), ids=_relative)
def test_application_depends_on_domain_ports_not_outer_layers(path: Path) -> None:
    names = _module_imports(path)
    for banned in ("fastapi", "sqlalchemy"):
        assert not any(name == banned or name.startswith(f"{banned}.") for name in names), (
            f"{_relative(path)} 依赖了 {banned}。用例层只认 domain/ports 里的协议。"
        )
    assert not _imports_layer(names, "infrastructure"), (
        f"{_relative(path)} 直接依赖了 infrastructure。"
        "需要什么能力就在 domain/ports 里定义端口，由组合根注入具体实现。"
    )
    assert not _imports_layer(names, "api"), f"{_relative(path)} 依赖了 api 层。"
