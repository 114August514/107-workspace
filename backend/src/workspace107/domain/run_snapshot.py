"""Run Snapshot —— 本次执行不可变的配置事实。

::

    Run Snapshot = Project Version
                 + 已解析并固定的 Run Configuration
                 + Resolved Scheduler Configuration

不变量（GR-202）：创建后不允许修改代码版本、执行命令、工作目录、环境版本、
输入来源、算力请求、最终调度配置和 Artifact 收集规则。需要改变任何一项，
都必须创建新的 Run。

不变量（GR-304）：不保存 Secret 明文，只保存引用关系，执行时由平台注入。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .compute import ComputeRequest, ResolvedSchedulerConfiguration
from .config_scope import SecretReference
from .enums import InputSourceType
from .errors import ValidationFailed
from .models import ArtifactCollectionRule, InputBinding
from .secrets import ResolvedEnv


@dataclass(frozen=True, slots=True)
class RunSnapshot:
    """创建 Run 时固定的完整执行事实。

    这是一个 ``frozen`` dataclass，仓储层对它只有 INSERT。
    """

    id: str
    project_id: str
    project_version_id: str
    source_run_configuration_id: str | None
    working_directory: str
    command: str
    environment_version_id: str
    environment_definition_hash: str
    environment_execution_spec: dict[str, object]
    env_literals: dict[str, str]
    env_secret_refs: dict[str, SecretReference]
    """环境变量名 -> scope-qualified Secret reference; never plaintext."""
    input_bindings: tuple[InputBinding, ...]
    compute_plan_id: str
    compute_request: ComputeRequest
    scheduler: ResolvedSchedulerConfiguration
    artifact_rules: tuple[ArtifactCollectionRule, ...]
    initiated_by_user_id: str
    created_at: datetime

    def __post_init__(self) -> None:
        if any(not isinstance(ref, SecretReference) for ref in self.env_secret_refs.values()):
            raise ValidationFailed("Run Snapshot Secret references must be scope-qualified")
        # 工作目录必须留在 Run 目录里。它会被拼成执行时的 cwd
        # （`paths.work / working_directory`），逃出去就等于让用户程序
        # 在平台任意目录下运行。
        #
        # 校验放在这里而不是放在某个用例里，是因为**创建 Run 有多条路径**：
        # 保存运行方案时 normalize_path 管住了一条，提交时的
        # working_directory_override 却绕过了它，审查时被抓出来。
        # 放进不可变对象的构造函数，任何路径都躲不掉，以后新增入口也一样。
        if self.working_directory in {"", "."}:
            return
        if self.working_directory.startswith("/"):
            raise ValidationFailed(f"工作目录 {self.working_directory!r} 必须相对于项目根目录")
        if ".." in self.working_directory.replace("\\", "/").split("/"):
            raise ValidationFailed(f"工作目录 {self.working_directory!r} 不允许包含 ..")

    # -- 序列化 ---------------------------------------------------------

    def to_payload(self) -> dict[str, Any]:
        """转成可直接写入 JSON 列的结构。"""
        return {
            "project_id": self.project_id,
            "project_version_id": self.project_version_id,
            "source_run_configuration_id": self.source_run_configuration_id,
            "working_directory": self.working_directory,
            "command": self.command,
            "environment": {
                "version_id": self.environment_version_id,
                "definition_hash": self.environment_definition_hash,
                "execution_spec": self.environment_execution_spec,
            },
            "env": {
                "literals": dict(self.env_literals),
                "secret_refs": {name: ref.as_key() for name, ref in self.env_secret_refs.items()},
            },
            "input_bindings": [b.as_payload() for b in self.input_bindings],
            "compute": {
                "plan_id": self.compute_plan_id,
                "request": self.compute_request.as_payload(),
                "scheduler": self.scheduler.as_payload(),
            },
            "artifact_rules": [r.as_payload() for r in self.artifact_rules],
            "initiated_by_user_id": self.initiated_by_user_id,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_payload(cls, snapshot_id: str, payload: dict[str, Any]) -> RunSnapshot:
        environment = payload["environment"]
        compute = payload["compute"]
        env = payload["env"]
        return cls(
            id=snapshot_id,
            project_id=payload["project_id"],
            project_version_id=payload["project_version_id"],
            source_run_configuration_id=payload["source_run_configuration_id"],
            working_directory=payload["working_directory"],
            command=payload["command"],
            environment_version_id=environment["version_id"],
            environment_definition_hash=environment["definition_hash"],
            environment_execution_spec=dict(environment["execution_spec"]),
            env_literals=dict(env["literals"]),
            env_secret_refs={
                name: SecretReference.from_key(value) for name, value in env["secret_refs"].items()
            },
            input_bindings=tuple(
                InputBinding(
                    source_type=InputSourceType(b["source_type"]),
                    source_id=b["source_id"],
                    access_path=b["access_path"],
                    source_subpath=b.get("source_subpath", ""),
                )
                for b in payload["input_bindings"]
            ),
            compute_plan_id=compute["plan_id"],
            compute_request=ComputeRequest(**compute["request"]),
            scheduler=ResolvedSchedulerConfiguration(**compute["scheduler"]),
            artifact_rules=tuple(
                ArtifactCollectionRule(
                    path=r["path"],
                    name=r.get("name", ""),
                    optional=r.get("optional", True),
                )
                for r in payload["artifact_rules"]
            ),
            initiated_by_user_id=payload["initiated_by_user_id"],
            created_at=datetime.fromisoformat(payload["created_at"]),
        )


def build_snapshot(
    *,
    snapshot_id: str,
    project_id: str,
    project_version_id: str,
    source_run_configuration_id: str | None,
    working_directory: str,
    command: str,
    environment_version_id: str,
    environment_definition_hash: str,
    environment_execution_spec: dict[str, object],
    resolved_env: ResolvedEnv,
    input_bindings: tuple[InputBinding, ...],
    compute_plan_id: str,
    compute_request: ComputeRequest,
    scheduler: ResolvedSchedulerConfiguration,
    artifact_rules: tuple[ArtifactCollectionRule, ...],
    initiated_by_user_id: str,
    created_at: datetime,
) -> RunSnapshot:
    """组装 Run Snapshot。

    调用方必须先完成全部校验和解析——到这一步所有可变引用都应该已经
    变成确定版本、确定内容或确定配置（GR-205、GR-302）。
    """
    return RunSnapshot(
        id=snapshot_id,
        project_id=project_id,
        project_version_id=project_version_id,
        source_run_configuration_id=source_run_configuration_id,
        working_directory=working_directory,
        command=command,
        environment_version_id=environment_version_id,
        environment_definition_hash=environment_definition_hash,
        environment_execution_spec=dict(environment_execution_spec),
        env_literals=dict(resolved_env.literals),
        env_secret_refs=dict(resolved_env.secret_refs),
        input_bindings=input_bindings,
        compute_plan_id=compute_plan_id,
        compute_request=compute_request,
        scheduler=scheduler,
        artifact_rules=artifact_rules,
        initiated_by_user_id=initiated_by_user_id,
        created_at=created_at,
    )
