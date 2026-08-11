# GR 规则—测试追踪矩阵

产品语义以 [`docs/product/design.md`](../product/design.md) 为准。本文件将每条活动 GR 规则映射到长期维护的自动化测试。

验证状态只表示测试覆盖，不表示功能实现进度，也不表示当前 CI 结果：

- `已覆盖`：已有测试完整保护该规则；
- `部分覆盖`：已有测试保护该规则的部分语义；
- `未覆盖`：尚无测试保护该规则；
- `阻塞`：外部前置条件使验证证据暂时无法取得。

| 产品规则 | 对应测试 | 验证状态 |
| --- | --- | --- |
| [GR-101 — Workspace 对象归属](../product/design.md#gr-101--workspace-对象归属) | — | 未覆盖 |
| [GR-102 — Membership 操作边界](../product/design.md#gr-102--membership-操作边界) | — | 未覆盖 |
| [GR-103 — Membership Role 权限](../product/design.md#gr-103--membership-role-权限) | — | 未覆盖 |
| [GR-104 — Collaborative Workspace 所有权](../product/design.md#gr-104--collaborative-workspace-所有权) | — | 未覆盖 |
| [GR-105 — 权限与资源资格分离](../product/design.md#gr-105--权限与资源资格分离) | — | 未覆盖 |
| [GR-106 — 平台管理权限与 Workspace 数据权限分离](../product/design.md#gr-106--平台管理权限与-workspace-数据权限分离) | — | 未覆盖 |
| [GR-201 — 版本内容不可变](../product/design.md#gr-201--版本内容不可变) | `backend/tests/integration/api/test_project_git_versions.py::test_req_m1_a_project_api_version_restore_fork_and_export_exact_commit`<br>`backend/tests/integration/storage/test_git_project_content.py::test_req_m1_a_immutable_ref_survives_branch_changes_and_gc` | 部分覆盖 |
| [GR-202 — Run Snapshot 不可变](../product/design.md#gr-202--run-snapshot-不可变) | `backend/tests/integration/api/test_run_submission.py::test_post_run_commits_snapshot_queued_run_and_intent_without_worker` | 部分覆盖 |
| [GR-203 — Artifact 内容不可变](../product/design.md#gr-203--artifact-内容不可变) | `backend/tests/integration/storage/test_run_artifact_collection.py::test_installed_marker_returns_first_evidence_without_reopening_source` | 部分覆盖 |
| [GR-204 — 历史对象不受后续修改影响](../product/design.md#gr-204--历史对象不受后续修改影响) | `backend/tests/integration/api/test_project_git_versions.py::test_req_m1_a_project_api_version_restore_fork_and_export_exact_commit` | 部分覆盖 |
| [GR-205 — 确定引用不得漂移](../product/design.md#gr-205--确定引用不得漂移) | `backend/tests/integration/storage/test_git_project_content.py::test_req_m1_a_rejects_movable_or_abbreviated_revision`<br>`backend/tests/integration/storage/test_git_project_content.py::test_req_m1_a_immutable_ref_survives_branch_changes_and_gc` | 部分覆盖 |
| [GR-206 — 不可变性与生命周期独立](../product/design.md#gr-206--不可变性与生命周期独立) | — | 未覆盖 |
| [GR-301 — Run 归属](../product/design.md#gr-301--run-归属) | — | 未覆盖 |
| [GR-302 — Run Snapshot 生成](../product/design.md#gr-302--run-snapshot-生成) | `backend/tests/integration/api/test_run_submission.py::test_post_run_commits_snapshot_queued_run_and_intent_without_worker` | 部分覆盖 |
| [GR-303 — Run 执行配置依据](../product/design.md#gr-303--run-执行配置依据) | — | 未覆盖 |
| [GR-304 — Secret 执行规则](../product/design.md#gr-304--secret-执行规则) | `backend/tests/unit/domain/test_secrets.py::test_resolution_inlines_variable_and_preserves_secret_reference` | 部分覆盖 |
| [GR-305 — 执行结果与执行快照分离](../product/design.md#gr-305--执行结果与执行快照分离) | — | 未覆盖 |
| [GR-306 — Run 执行唯一性](../product/design.md#gr-306--run-执行唯一性) | `backend/tests/unit/application/test_run_worker.py::test_arm_then_submit_crash_recovers_without_second_submit` | 部分覆盖 |
| [GR-401 — Environment 与 Shared Resource 使用资格](../product/design.md#gr-401--environment-与-shared-resource-使用资格) | — | 未覆盖 |
| [GR-402 — 资源授权与版本固定分离](../product/design.md#gr-402--资源授权与版本固定分离) | `backend/tests/unit/domain/test_run_snapshot.py::test_snapshot_round_trips_through_json` | 部分覆盖 |
| [GR-403 — Input Binding 内容确定性](../product/design.md#gr-403--input-binding-内容确定性) | `backend/tests/unit/domain/test_run_snapshot.py::test_snapshot_round_trips_through_json` | 部分覆盖 |
| [GR-404 — 输入源只读](../product/design.md#gr-404--输入源只读) | — | 未覆盖 |
| [GR-405 — Artifact Workspace 边界](../product/design.md#gr-405--artifact-workspace-边界) | — | 未覆盖 |
| [GR-406 — Compute Plan 使用资格](../product/design.md#gr-406--compute-plan-使用资格) | `backend/tests/unit/domain/test_compute.py::test_unauthorized_request_is_not_resolved_to_scheduler_config`<br>`backend/tests/unit/domain/test_compute.py::test_entitlement_reports_expiration`<br>`backend/tests/unit/domain/test_compute.py::test_exceeding_plan_limits_reports_each_reason` | 部分覆盖 |
| [GR-407 — Secret 跨 Workspace 隔离](../product/design.md#gr-407--secret-跨-workspace-隔离) | — | 未覆盖 |
| [GR-408 — Ownership 变更后的授权失效](../product/design.md#gr-408--ownership-变更后的授权失效) | — | 未覆盖 |
| [GR-501 — Fork 来源与追踪](../product/design.md#gr-501--fork-来源与追踪) | `backend/tests/integration/api/test_project_git_versions.py::test_req_m1_a_project_api_version_restore_fork_and_export_exact_commit` | 部分覆盖 |
| [GR-502 — Fork 后独立](../product/design.md#gr-502--fork-后独立) | — | 未覆盖 |
| [GR-503 — Fork 权限与历史隔离](../product/design.md#gr-503--fork-权限与历史隔离) | — | 未覆盖 |
| [GR-504 — Template 创建独立性](../product/design.md#gr-504--template-创建独立性) | — | 未覆盖 |
| [GR-505 — Profile Instance 版本固定](../product/design.md#gr-505--profile-instance-版本固定) | — | 未覆盖 |
| [GR-506 — Profile 显式升级](../product/design.md#gr-506--profile-显式升级) | — | 未覆盖 |
| [GR-507 — Profile 扩展边界](../product/design.md#gr-507--profile-扩展边界) | — | 未覆盖 |
