"""活动代码和文档引用必须指向当前仓库中的事实源。"""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path
from urllib.parse import unquote, urlsplit

BACKEND = Path(__file__).resolve().parents[2]
REPO = BACKEND.parent
DESIGN = REPO / "docs" / "product" / "design.md"
DECISIONS = REPO / "docs" / "decisions"

_GR_DEFINITION = re.compile(r"^##### \*\*(GR-\d{3})\s+—", re.MULTILINE)
_GR_REFERENCE = re.compile(r"\bGR-\d{3}[a-z]?\b")
_ADR_REFERENCE = re.compile(r"\bADR-(\d{4})\b")
_DOC_REFERENCE = re.compile(r"(?<![A-Za-z0-9_/'\"])((?:\.\./)*docs/[A-Za-z0-9_./-]+\.md)")
_MARKDOWN_LINK = re.compile(r"(?<!!)\[[^]]+\]\(([^)]+)\)")

_GENERATED = REPO / "frontend" / "src" / "api" / "schema.d.ts"
_HISTORICAL_DOC_DIRS = frozenset({"archive", "references"})


def _excluded(path: Path) -> bool:
    relative = path.relative_to(REPO)
    if path == _GENERATED or relative.parts[0] == "archive":
        return True
    if relative.parts[:2] == ("backend", "migrations"):
        return True
    return (
        len(relative.parts) > 1
        and relative.parts[0] == "docs"
        and relative.parts[1] in _HISTORICAL_DOC_DIRS
    )


def _files_under(root: Path, suffixes: set[str]) -> Iterable[Path]:
    if not root.exists():
        return
    for path in root.rglob("*"):
        if path.is_file() and path.suffix in suffixes and not _excluded(path):
            yield path


def _active_files() -> list[Path]:
    files = [
        *_files_under(BACKEND / "src", {".py"}),
        *_files_under(BACKEND / "tests", {".py"}),
        *_files_under(REPO / "frontend" / "src", {".ts", ".tsx"}),
        *_files_under(REPO / "scripts", {".py", ".sh", ".ps1", ".md"}),
    ]
    files.extend(
        path
        for path in (
            REPO / "README.md",
            REPO / "AGENTS.md",
            REPO / "CONTRIBUTING.md",
            BACKEND / "README.md",
            BACKEND / "Dockerfile",
            BACKEND / "docker-entrypoint.sh",
            REPO / "frontend" / "README.md",
            REPO / "frontend" / "Dockerfile",
            REPO / "frontend" / "nginx.conf",
            REPO / "deploy" / "README.md",
            REPO / "deploy" / "compose.yaml",
        )
        if path.exists()
    )
    return sorted(set(files))


def _maintained_documents() -> list[Path]:
    files = [
        path
        for path in (
            REPO / "AGENTS.md",
            REPO / "CONTRIBUTING.md",
            REPO / "docs" / "README.md",
            REPO / "docs" / "product" / "design.md",
            REPO / "docs" / "product" / "deferred.md",
            REPO / "docs" / "contributing" / "git-workflow.md",
            REPO / "docs" / "operations" / "deployment.md",
            REPO / "docs" / "journal" / "README.md",
        )
        if path.exists()
    ]
    files.extend(_files_under(DECISIONS, {".md"}))
    files.extend(_files_under(REPO / "docs" / "journal", {".md"}))
    return sorted(set(files))


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _label(path: Path) -> str:
    return str(path.relative_to(REPO))


def test_活动代码引用的_GR_存在于现行设计() -> None:
    definitions = _GR_DEFINITION.findall(_read(DESIGN))
    assert definitions, "docs/product/design.md 中没有解析到 GR 定义，请检查标题格式"
    assert len(definitions) == len(set(definitions)), "docs/product/design.md 中存在重复的 GR 编号"

    valid = set(definitions)
    invalid: list[str] = []
    for path in _active_files():
        for rule_id in sorted(set(_GR_REFERENCE.findall(_read(path))) - valid):
            invalid.append(f"{_label(path)}: {rule_id}")

    assert invalid == [], "这些活动文件引用了非现行 GR：\n" + "\n".join(invalid)


def test_活动文件引用的_ADR_已经存在() -> None:
    available = {
        match.group(1)
        for path in DECISIONS.glob("[0-9][0-9][0-9][0-9]-*.md")
        if (match := re.match(r"^(\d{4})-", path.name))
    }
    missing: list[str] = []
    for path in [*_active_files(), *_maintained_documents()]:
        for decision_id in sorted(set(_ADR_REFERENCE.findall(_read(path))) - available):
            missing.append(f"{_label(path)}: ADR-{decision_id}")

    assert missing == [], "这些活动文件引用了不存在的 ADR：\n" + "\n".join(missing)


def _resolve_doc_reference(source: Path, reference: str) -> Path:
    if reference.startswith("docs/"):
        return (REPO / reference).resolve()
    return (source.parent / reference).resolve()


def test_活动文件引用的_docs_路径已经存在() -> None:
    missing: list[str] = []
    for path in [*_active_files(), *_maintained_documents()]:
        for reference in sorted(set(_DOC_REFERENCE.findall(_read(path)))):
            target = _resolve_doc_reference(path, reference)
            if not target.is_relative_to(REPO) or not target.is_file():
                missing.append(f"{_label(path)}: {reference}")

    assert missing == [], "这些活动文件引用了不存在的 docs 路径：\n" + "\n".join(missing)


def test_活动_Markdown_中的本地链接可以解析() -> None:
    markdown_files = {path for path in _active_files() if path.suffix == ".md"}
    markdown_files.update(
        path
        for path in (REPO / "docs").rglob("*.md")
        if path.relative_to(REPO / "docs").parts[0] != "archive"
    )

    missing: list[str] = []
    for source in sorted(markdown_files):
        for reference in _MARKDOWN_LINK.findall(_read(source)):
            parsed = urlsplit(reference)
            if parsed.scheme or reference.startswith(("#", "mailto:")):
                continue
            relative = unquote(parsed.path)
            if not relative:
                continue
            target = (source.parent / relative).resolve()
            if not target.is_relative_to(REPO) or not target.exists():
                missing.append(f"{_label(source)}: {reference}")

    assert missing == [], "这些活动 Markdown 链接无法解析：\n" + "\n".join(missing)
