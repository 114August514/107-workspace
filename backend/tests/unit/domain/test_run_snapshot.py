"""纯领域层的 Run Snapshot 序列化与路径约束。"""

from __future__ import annotations

import dataclasses
import json
from datetime import UTC, datetime

import pytest

from workspace107.domain.compute import ComputeRequest, ResolvedSchedulerConfiguration
from workspace107.domain.config_scope import ConfigScope, SecretReference
from workspace107.domain.enums import InputSourceType
from workspace107.domain.errors import ValidationFailed
from workspace107.domain.models import ArtifactCollectionRule, InputBinding
from workspace107.domain.run_snapshot import RunSnapshot, build_snapshot
from workspace107.domain.secrets import ResolvedEnv


def make_snapshot() -> RunSnapshot:
    return build_snapshot(
        snapshot_id="snap_1",
        project_id="prj_1",
        project_version_id="pv_1",
        source_run_configuration_id="rc_1",
        working_directory="src",
        command="python train.py",
        environment_version_id="ev_1",
        environment_image="python:3.12-slim",
        environment_setup_command="pip install -r requirements.txt",
        resolved_env=ResolvedEnv(
            literals={"EPOCHS": "5"},
            secret_refs={"TOKEN": SecretReference(ConfigScope.user("owner"), "HF_TOKEN")},
        ),
        input_bindings=(
            InputBinding(
                source_type=InputSourceType.ARTIFACT,
                source_id="art_1",
                access_path="/inputs/train",
                source_subpath="train",
            ),
        ),
        compute_plan_id="plan_cpu",
        compute_request=ComputeRequest(
            nodes=1, cpus=2, memory_mb=4096, gpus=0, time_limit_minutes=15
        ),
        scheduler=ResolvedSchedulerConfiguration(
            cluster="107",
            account="undergraduate",
            partition="debug",
            qos="normal",
            nodes=1,
            cpus=2,
            memory_mb=4096,
            gpus=0,
            time_limit_minutes=15,
        ),
        artifact_rules=(ArtifactCollectionRule(path="outputs", name="结果", optional=False),),
        created_by="usr_1",
        created_at=datetime(2026, 7, 26, 12, 0, tzinfo=UTC),
    )


def test_snapshot_round_trips_through_json() -> None:
    original = make_snapshot()
    # 走一遍 JSON，确保写进数据库 JSON 列再读出来不会丢信息。
    payload = json.loads(json.dumps(original.to_payload()))
    restored = RunSnapshot.from_payload(original.id, payload)

    assert restored == original


def test_input_access_path_must_be_absolute() -> None:
    from workspace107.domain.errors import ValidationFailed

    with pytest.raises(ValidationFailed):
        InputBinding(
            source_type=InputSourceType.ARTIFACT,
            source_id="art_1",
            access_path="inputs/train",
        )


def test_input_access_path_rejects_parent_components() -> None:
    from workspace107.domain.errors import ValidationFailed

    with pytest.raises(ValidationFailed):
        InputBinding(
            source_type=InputSourceType.ARTIFACT,
            source_id="art_1",
            access_path="/inputs/../../etc",
        )


def test_artifact_collection_path_must_be_relative() -> None:
    from workspace107.domain.errors import ValidationFailed

    with pytest.raises(ValidationFailed):
        ArtifactCollectionRule(path="/etc/passwd")
    with pytest.raises(ValidationFailed):
        ArtifactCollectionRule(path="../outside")


@pytest.mark.parametrize(
    "working_directory",
    ["..", "../..", "../../../etc", "src/../..", "/etc", "/", "sub\\..\\..\\.."],
)
def test_working_directory_cannot_escape_run_directory(working_directory: str) -> None:
    """它会被拼成执行时的 cwd，逃出去就是让用户程序在平台任意目录下运行。

    校验放在快照的构造函数里，不是放在某个用例里——**创建 Run 有多条路径**。
    保存运行方案时 normalize_path 管住了一条，提交时的
    working_directory_override 却绕过了它，审查时被抓出来。
    放进不可变对象的构造函数，任何路径都躲不掉。
    """
    with pytest.raises(ValidationFailed):
        dataclasses.replace(make_snapshot(), working_directory=working_directory)


@pytest.mark.parametrize("working_directory", ["", ".", "src", "a/b/c", "带中文的目录"])
def test_valid_working_directory_is_accepted(working_directory: str) -> None:
    replaced = dataclasses.replace(make_snapshot(), working_directory=working_directory)
    assert replaced.working_directory == working_directory
