"""Run workspace 分配端口与 prepared identity。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True, slots=True)
class RunWorkspaceIdentity:
    """一个已准备 workspace 不可更换的四元 identity。"""

    run_id: str
    snapshot_id: str
    project_version_id: str
    commit_oid: str


@dataclass(frozen=True, slots=True)
class RunWorkspace:
    """Worker 与计算节点共同看到的一次 Run 的绝对 POSIX 路径。"""

    root: Path
    work: Path
    inputs: Path
    logs: Path
    artifact_staging: Path
    identity_marker: Path

    @property
    def stdout(self) -> Path:
        return self.logs / "stdout.log"

    @property
    def stderr(self) -> Path:
        return self.logs / "stderr.log"


class RunWorkspaceError(RuntimeError):
    """Run workspace 无法安全准备或恢复。"""


class UnsafeRunWorkspacePath(RunWorkspaceError):
    """路径、符号链接或权限不能满足 POSIX workspace 安全边界。"""


class RunWorkspaceConflict(RunWorkspaceError):
    """已有目录没有可恢复的相同 prepared identity。"""


class RunWorkspacePort(Protocol):
    async def prepare(
        self,
        identity: RunWorkspaceIdentity,
        *,
        inputs: tuple[()] = (),
    ) -> RunWorkspace:
        """创建或恢复相同 identity 的 workspace；M1 只接受显式空 inputs。"""
        ...
