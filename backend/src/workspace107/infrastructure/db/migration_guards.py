"""M1 migration 的数据保留边界；不猜测 execution intent 或重复 Artifact。"""

from __future__ import annotations

from sqlalchemy import Connection, text


def guard_worker_upgrade(connection: Connection) -> None:
    unfinished = connection.execute(
        text("SELECT COUNT(*) FROM runs WHERE status IN ('queued','running')")
    ).scalar_one()
    if unfinished:
        raise RuntimeError(
            "Independent Worker migration 发现既有非终态 Run；无法猜测 execution intent，"
            "请确认开发数据可丢弃后重建 schema"
        )
    duplicate_artifacts = connection.execute(
        text(
            "SELECT COUNT(*) FROM ("
            "SELECT 1 FROM artifacts GROUP BY run_id, source_path HAVING COUNT(*) > 1"
            ") AS duplicates"
        )
    ).scalar_one()
    if duplicate_artifacts:
        raise RuntimeError(
            "Independent Worker migration 发现重复 (run_id, source_path) Artifact；"
            "不得自动选择记录，请重建开发 schema"
        )


def guard_worker_downgrade(connection: Connection) -> None:
    unfinished_intents = connection.execute(
        text(
            "SELECT COUNT(*) FROM run_execution_intents "
            "WHERE phase <> 'complete' OR completed_at IS NULL"
        )
    ).scalar_one()
    unfinished_runs = connection.execute(
        text("SELECT COUNT(*) FROM runs WHERE status IN ('queued','running')")
    ).scalar_one()
    unresolved_attempts = connection.execute(
        text(
            "SELECT COUNT(*) FROM run_submission_attempts "
            "WHERE resolved_at IS NULL OR outcome IN ('armed','uncertain','reconciled_multiple')"
        )
    ).scalar_one()
    if unfinished_intents or unfinished_runs or unresolved_attempts:
        raise RuntimeError(
            "Independent Worker downgrade 被拒绝：仍有未完成 intent、非终态 Run "
            "或 unresolved submission attempt"
        )
