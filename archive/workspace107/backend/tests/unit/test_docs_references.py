"""文档里指的文件必须真的存在。

`docs/domain/invariants.md` 的价值在于「这条规则由哪段代码保证、由哪个测试守住」。
一旦重构把文件挪了而文档没跟上，这张表就从索引变成误导——
照着去找的人会先浪费时间，然后不再相信它。

这个检查在写下来的时候就抓到了一处：GR-011 指向的
`infrastructure/execution/workspace_layout.py` 是 M0 阶段预写的路径，
实际实现在 `infrastructure/storage/local.py`。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[2]
REPO = BACKEND.parent
DOCS = REPO / "docs"

# 反引号里形如 xxx/yyy.py 的引用
_PY_REFERENCE = re.compile(r"`([A-Za-z0-9_./]+\.py)(?:::[^`]+)?`")

# 这些是示例或占位，不指向真实文件
_ALLOWED_PLACEHOLDERS = frozenset({"train.py", "main.py", "produce.py", "consume.py"})


def _documents() -> list[Path]:
    return sorted(DOCS.rglob("*.md"))


def _resolve(reference: str) -> Path | None:
    """解析文档里的文件引用。

    完整路径按 backend/ 或后端包目录解析；只写了文件名的（正文里常这么写，
    比如「改 script.py 里的渲染」）退化成按文件名查找。
    退化查找仍然能抓住真正的问题：文件整个不存在。
    """
    for base in (BACKEND, BACKEND / "src" / "workspace107"):
        candidate = base / reference
        if candidate.exists():
            return candidate

    if "/" not in reference:
        for root in (BACKEND / "src", BACKEND / "tests"):
            if next(root.rglob(reference), None) is not None:
                return root
    return None


@pytest.mark.parametrize("document", _documents(), ids=lambda p: str(p.relative_to(REPO)))
def test_文档引用的_python_文件都存在(document: Path) -> None:
    text = document.read_text(encoding="utf-8")
    missing = [
        reference
        for reference in _PY_REFERENCE.findall(text)
        if reference not in _ALLOWED_PLACEHOLDERS and _resolve(reference) is None
    ]
    assert missing == [], (
        f"{document.relative_to(REPO)} 指向了不存在的文件：{missing}。"
        "重构挪了文件就要同步改文档，否则这张表会从索引变成误导。"
    )


_GR_RULE_REFERENCE = re.compile(r"(GR-\d{3}[a-z]?) 规则 ([0-9、\s]+)")
"""形如「GR-012 规则 4」或「GR-012 规则 6、7」。"""


def _numbered_rules(section: str) -> set[int]:
    """数一个 GR 小节里编号列表有几条。

    小节形如：

        ### GR-012 Secret 不落明文

        ```text
        1. ...
        2. ...
        ```
    """
    return {int(m) for m in re.findall(r"^\s*(\d+)\.\s", section, re.MULTILINE)}


def test_引用的_GR_规则编号必须真的存在() -> None:
    """「GR-012 规则 6、7」这种引用，编号得对得上源头。

    真出过：invariants.md 里 GR-012 只有 4 条，而 ADR-0001 和 M2 里程碑
    都引用了并不存在的「规则 6、7」。读的人照着去找，找不到，
    只能猜作者到底指的是哪条——**编号错的引用比没有引用更糟**。
    """
    invariants = (REPO / "docs" / "domain" / "invariants.md").read_text(encoding="utf-8")
    # 按 "### GR-xxx" 切成小节
    sections: dict[str, str] = {}
    for chunk in re.split(r"^### ", invariants, flags=re.MULTILINE)[1:]:
        for name in re.findall(r"GR-\d{3}[a-z]?", chunk.split("\n", 1)[0]):
            sections[name] = chunk

    problems: list[str] = []
    for document in _documents():
        text = document.read_text(encoding="utf-8")
        for rule_id, numbers in _GR_RULE_REFERENCE.findall(text):
            available = _numbered_rules(sections.get(rule_id, ""))
            cited = {int(n) for n in re.findall(r"\d+", numbers)}
            unknown = sorted(cited - available)
            if unknown:
                problems.append(
                    f"{document.relative_to(REPO)} 引用了 {rule_id} 规则 {unknown}，"
                    f"但那一节只有 {sorted(available) or '（没有编号列表）'}"
                )

    assert problems == [], "\n".join(problems)
