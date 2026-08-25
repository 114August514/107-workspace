"""验证 run_out presenter 输出 project_version_id 和 project_version_label。

这两个字段从 Run 领域模型冗余到 RunOut，让 Run History 不用 N+1 查询
就能显示版本标签并链接到版本详情。这里守的是「presenter 确实把字段传出去了」
这条可观察契约——领域模型里有没有字段是编译期保证的，不在这里重复。
"""

from __future__ import annotations

from datetime import UTC, datetime

from workspace107.api import presenters as p
from workspace107.api import schemas as s
from workspace107.domain.enums import RunStatus
from workspace107.domain.models import Run


def _make_run(
    *,
    project_version_id: str = "pv-001",
    project_version_label: str = "v3",
) -> Run:
    return Run(
        id="run-1",
        project_id="proj-1",
        workspace_id="ws-1",
        snapshot_id="snap-1",
        compute_plan_id="plan-1",
        project_version_id=project_version_id,
        project_version_label=project_version_label,
        source_run_configuration_id="rc-1",
        source_run_id=None,
        name="首次运行",
        status=RunStatus.SUCCEEDED,
        scheduler_job_id="job-1",
        exit_code=0,
        failure_reason="",
        initiated_by_user_id="user-1",
        created_at=datetime(2026, 8, 12, 10, 0, tzinfo=UTC),
        submitted_at=datetime(2026, 8, 12, 10, 1, tzinfo=UTC),
        started_at=datetime(2026, 8, 12, 10, 2, tzinfo=UTC),
        finished_at=datetime(2026, 8, 12, 10, 30, tzinfo=UTC),
    )


def test_run_out_includes_project_version_id() -> None:
    """RunOut 必须带上 project_version_id，Run History 才能链接到版本详情。"""
    run = _make_run(project_version_id="pv-abc")
    out = p.run_out(run)
    assert out.project_version_id == "pv-abc"


def test_run_out_includes_project_version_label() -> None:
    """RunOut 必须带上 project_version_label，Run History 才能直接显示 v3 而非 raw id。"""
    run = _make_run(project_version_label="v7")
    out = p.run_out(run)
    assert out.project_version_label == "v7"


def test_run_out_preserves_both_fields_together() -> None:
    """id 和 label 必须一起传，不能只传一个——否则列表里要么没链接要么没文字。"""
    run = _make_run(project_version_id="pv-xyz", project_version_label="v12")
    out = p.run_out(run)
    assert out.project_version_id == "pv-xyz"
    assert out.project_version_label == "v12"
    assert isinstance(out, s.RunOut)
