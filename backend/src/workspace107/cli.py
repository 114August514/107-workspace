"""面向本地用户的 107 命令行入口。"""

from __future__ import annotations

import argparse
import fnmatch
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import httpx
from pathspec import GitIgnoreSpec

DEFAULT_API_URL = "http://127.0.0.1:8107/api/v1"
DEFAULT_EXCLUDED_DIRS = (
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
)
DEFAULT_EXCLUDED_FILES = ("*.pyc", "*.pyo")
PROGRESS_RE = re.compile(
    r"^\s*(?P<bytes>[\d,.]+(?:[KMGTPE]i?)?)\s+"
    r"(?P<percent>\d+)%\s+(?P<rate>\S+)\s+(?P<eta>\d+:\d+:\d+)"
)
SSH_TARGET_RE = re.compile(r"^(?:[A-Za-z0-9._-]+@)?[A-Za-z0-9._-]+$")


class CliError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ScanResult:
    file_count: int
    total_bytes: int
    excluded_paths: tuple[str, ...]


def _human_bytes(value: int) -> str:
    units = ("B", "KiB", "MiB", "GiB", "TiB")
    amount = float(value)
    for unit in units:
        if amount < 1024 or unit == units[-1]:
            return f"{amount:.0f} {unit}" if unit == "B" else f"{amount:.1f} {unit}"
        amount /= 1024
    raise AssertionError("unreachable")


def _read_ignore(source: Path) -> GitIgnoreSpec:
    ignore = source / ".107ignore"
    if not ignore.exists():
        return GitIgnoreSpec.from_lines([])
    if not ignore.is_file() or ignore.is_symlink():
        raise CliError(".107ignore 必须是普通文件")
    try:
        return GitIgnoreSpec.from_lines(ignore.read_text(encoding="utf-8").splitlines())
    except (OSError, UnicodeError, ValueError) as error:
        raise CliError(f"无法读取 .107ignore：{error}") from error


def _scan_source(source: Path) -> ScanResult:
    spec = _read_ignore(source)
    excluded: list[str] = []
    count = 0
    total = 0

    for directory, dirnames, filenames in os.walk(source, followlinks=False):
        parent = Path(directory)
        kept_dirs: list[str] = []
        for name in sorted(dirnames):
            candidate = parent / name
            relative = candidate.relative_to(source).as_posix()
            if candidate.is_symlink():
                raise CliError(f"本地目录包含不支持的符号链接：{relative}")
            if name in DEFAULT_EXCLUDED_DIRS:
                continue
            kept_dirs.append(name)
        dirnames[:] = kept_dirs

        for name in sorted(filenames):
            candidate = parent / name
            relative = candidate.relative_to(source).as_posix()
            if "\n" in relative or "\r" in relative:
                raise CliError(f"文件名不能包含换行符：{relative!r}")
            mode = candidate.lstat().st_mode
            if stat.S_ISLNK(mode):
                raise CliError(f"本地目录包含不支持的符号链接：{relative}")
            if not stat.S_ISREG(mode):
                raise CliError(f"本地目录包含不支持的特殊文件：{relative}")
            if any(fnmatch.fnmatch(name, pattern) for pattern in DEFAULT_EXCLUDED_FILES):
                continue
            if spec.match_file(relative):
                excluded.append(relative)
                continue
            count += 1
            total += candidate.stat().st_size

    return ScanResult(count, total, tuple(sorted(excluded)))


def _escape_rsync_pattern(path: str) -> str:
    escaped: list[str] = []
    for character in path:
        escaped.append("\\" + character if character in "\\*?[" else character)
    return "".join(escaped)


def _write_filter_file(excluded_paths: tuple[str, ...]) -> Path:
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", prefix="workspace107-sync-", suffix=".filter", delete=False
    ) as handle:
        for path in excluded_paths:
            handle.write(f"- /{_escape_rsync_pattern(path)}\n")
    return Path(handle.name)


def _build_rsync_command(
    source: Path, ssh_target: str, remote_path: str, filter_file: Path
) -> list[str]:
    if SSH_TARGET_RE.fullmatch(ssh_target) is None:
        raise CliError("服务端返回了无效的 SSH 同步目标")
    remote = PurePosixPath(remote_path)
    if not remote.is_absolute() or ".." in remote.parts or "\n" in remote_path:
        raise CliError("服务端返回了无效的同步暂存路径")

    command = [
        "rsync",
        "--archive",
        "--partial",
        "--delete",
        "--delete-excluded",
        "--prune-empty-dirs",
        "--human-readable",
        "--info=progress2",
        "--protect-args",
        "--filter",
        f"merge {filter_file}",
    ]
    for name in DEFAULT_EXCLUDED_DIRS:
        command.extend(("--exclude", f"{name}/"))
    for pattern in DEFAULT_EXCLUDED_FILES:
        command.extend(("--exclude", pattern))
    command.extend(("--", f"{source}/", f"{ssh_target}:{remote.as_posix().rstrip('/')}/"))
    return command


def _run_rsync(command: list[str]) -> None:
    if shutil.which("rsync") is None:
        raise CliError("未找到 rsync；请先在本机安装 rsync")
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    assert process.stdout is not None
    details: list[str] = []
    showed_progress = False
    for raw in process.stdout:
        line = raw.strip()
        match = PROGRESS_RE.match(line)
        if match:
            showed_progress = True
            print(
                f"\r{match['bytes']}  {match['percent']}%  {match['rate']} · ETA {match['eta']}",
                end="",
                flush=True,
            )
        elif line:
            details.append(line)
    return_code = process.wait()
    if showed_progress:
        print()
    if return_code:
        detail = details[-1] if details else f"rsync 退出码 {return_code}"
        raise CliError(f"SSH / rsync 传输失败：{detail}")


def _response_error(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text.strip() or f"HTTP {response.status_code}"
    return str(payload.get("message") or payload.get("detail") or f"HTTP {response.status_code}")


def _resolve_project(client: httpx.Client, selector: str) -> str:
    direct = client.get(f"projects/{selector}")
    if direct.status_code == 200:
        return str(direct.json()["id"])
    if direct.status_code != 404:
        raise CliError(_response_error(direct))

    response = client.get("projects", params={"query": selector, "page_size": 100})
    if response.is_error:
        raise CliError(_response_error(response))
    exact = [item for item in response.json()["items"] if item["name"] == selector]
    if not exact:
        raise CliError(f"找不到 Project「{selector}」")
    if len(exact) > 1:
        identifiers = "、".join(item["id"] for item in exact)
        raise CliError(f"有多个同名 Project，请改用 ID：{identifiers}")
    return str(exact[0]["id"])


def _sync(args: argparse.Namespace) -> None:
    source = Path(args.source).expanduser().resolve()
    if not source.is_dir():
        raise CliError(f"本地同步源不是目录：{source}")

    print("Scanning...", flush=True)
    scan = _scan_source(source)
    print(f"{scan.file_count} files · {_human_bytes(scan.total_bytes)}\n", flush=True)
    if scan.file_count == 0:
        raise CliError("忽略规则生效后没有可同步的文件")

    headers = {"X-User": args.user} if args.user else {}
    try:
        with httpx.Client(
            base_url=args.api_url.rstrip("/") + "/", headers=headers, timeout=args.timeout
        ) as client:
            project_id = _resolve_project(client, args.project)
            prepared = client.post(f"projects/{project_id}/sync")
            if prepared.is_error:
                raise CliError(_response_error(prepared))
            target = prepared.json()

            filter_file = _write_filter_file(scan.excluded_paths)
            try:
                print("Uploading", flush=True)
                _run_rsync(
                    _build_rsync_command(
                        source, target["ssh_target"], target["remote_path"], filter_file
                    )
                )
            finally:
                filter_file.unlink(missing_ok=True)

            print("\nApplying to Project...", flush=True)
            applied = client.post(f"projects/{project_id}/sync/apply")
            if applied.is_error:
                raise CliError(_response_error(applied))
            result = applied.json()
            print(f"Done · {result['changed_files']} files changed", flush=True)
    except httpx.HTTPError as error:
        raise CliError(f"无法连接 107 Workspace：{error}") from error


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="107", description="107 Workspace command line")
    parser.add_argument(
        "--api-url", default=os.environ.get("WORKSPACE107_API_URL", DEFAULT_API_URL)
    )
    parser.add_argument("--user", default=os.environ.get("WORKSPACE107_USER", ""))
    parser.add_argument("--timeout", type=float, default=300.0)
    groups = parser.add_subparsers(dest="group", required=True)
    project = groups.add_parser("project", help="Project operations")
    actions = project.add_subparsers(dest="action", required=True)
    sync = actions.add_parser("sync", help="incrementally sync a local directory")
    sync.add_argument("source")
    sync.add_argument("project", help="Project ID or exact name")
    sync.set_defaults(handler=_sync)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.handler(args)
    except CliError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
