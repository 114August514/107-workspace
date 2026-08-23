"""领域对象 -> API 响应模型。

Secret 只输出名称和引用关系，任何路径都不输出值（docs/product/design.md 第 3.1.4 节）。
"""

from __future__ import annotations

from collections.abc import Callable

from ..application.catalog_service import EnvironmentView
from ..application.entitlement_service import EntitlementView
from ..application.grant_service import GrantView
from ..application.ownership import OwnerSummary
from ..application.shared_resource_service import SharedResourceAccessView, SharedResourceView
from ..application.user_group_service import InvitationView, MemberView, UserGroupView
from ..application.workspace_service import LegacyWorkspaceView
from ..domain.compute import ComputePlan, ComputeRequest
from ..domain.models import (
    Activity,
    Artifact,
    EnvironmentVersion,
    ForkRelation,
    InputBinding,
    Notification,
    Project,
    ProjectFile,
    ProjectVersion,
    Run,
    RunConfiguration,
    RunEvent,
    SharedResourceVersion,
    User,
)
from ..domain.pagination import Page
from ..domain.run_snapshot import RunSnapshot
from . import schemas as s


def page_out[TIn, TOut](page: Page[TIn], convert: Callable[[TIn], TOut]) -> s.PageOut[TOut]:
    """把领域分页结果转成响应模型。"""
    return s.PageOut[TOut](
        items=[convert(item) for item in page.items],
        page=page.page,
        page_size=page.page_size,
        total=page.total,
        has_more=page.has_more,
    )


def user_out(user: User) -> s.UserOut:
    return s.UserOut(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        email=user.email,
    )


def user_group_out(view: UserGroupView) -> s.UserGroupOut:
    group = view.user_group
    return s.UserGroupOut(
        id=group.id,
        name=group.name,
        description=group.description,
        created_by_id=group.created_by_id,
        created_at=group.created_at,
        role=view.role,
        capabilities=sorted(view.capabilities),
    )


def legacy_workspace_context_out(
    view: LegacyWorkspaceView,
) -> s.LegacyWorkspaceContextOut:
    workspace = view.workspace
    return s.LegacyWorkspaceContextOut(
        id=workspace.id,
        kind=workspace.kind,
        name=workspace.name,
        owner_id=workspace.owner_id,
        default_environment_version_id=workspace.default_environment_version_id,
        role=view.role,
        capabilities=sorted(view.capabilities),
    )


def member_out(view: MemberView) -> s.MemberOut:
    return s.MemberOut(
        user_id=view.user.id,
        username=view.user.username,
        display_name=view.user.display_name,
        role=view.membership.role.value,
        status=view.membership.status.value,
    )


def entitlement_out(view: EntitlementView) -> s.EntitlementOut:
    return s.EntitlementOut(
        id=view.entitlement.id,
        compute_plan_id=view.plan.id,
        compute_plan_name=view.plan.name,
        max_concurrent_runs=view.entitlement.max_concurrent_runs,
        expires_at=view.entitlement.expires_at,
    )


def project_out(project: Project) -> s.ProjectOut:
    return s.ProjectOut(
        id=project.id,
        workspace_id=project.workspace_id,
        name=project.name,
        description=project.description,
        status=project.status.value,
        environment_version_id=project.environment_version_id,
        default_run_configuration_id=project.default_run_configuration_id,
        created_by=project.created_by,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


def project_file_out(file: ProjectFile) -> s.ProjectFileOut:
    return s.ProjectFileOut(
        path=file.path,
        size=file.size,
        content_hash=file.content_hash,
        updated_at=file.updated_at,
    )


def version_out(version: ProjectVersion) -> s.ProjectVersionOut:
    return s.ProjectVersionOut(
        id=version.id,
        project_id=version.project_id,
        sequence=version.sequence,
        label=version.label,
        message=version.message,
        file_count=len(version.files),
        total_size=version.total_size,
        created_by=version.created_by,
        created_at=version.created_at,
    )


def version_detail_out(version: ProjectVersion) -> s.ProjectVersionDetailOut:
    return s.ProjectVersionDetailOut(
        **version_out(version).model_dump(),
        files=[
            s.ProjectVersionFileOut(path=f.path, size=f.size, content_hash=f.content_hash)
            for f in version.files
        ],
    )


def owner_summary_out(owner: OwnerSummary) -> s.OwnerSummaryOut:
    return s.OwnerSummaryOut(
        kind=owner.kind,
        id=owner.id,
        display_name=owner.display_name,
    )


def environment_out(
    view: EnvironmentView,
) -> s.EnvironmentOut:
    return s.EnvironmentOut(
        id=view.environment.id,
        name=view.environment.name,
        description=view.environment.description,
        owner=owner_summary_out(view.owner),
        versions=[environment_version_out(v) for v in view.versions],
    )


def environment_version_out(version: EnvironmentVersion) -> s.EnvironmentVersionOut:
    return s.EnvironmentVersionOut(
        id=version.id,
        environment_id=version.environment_id,
        version=version.version,
        description=version.description,
        image=version.image,
        setup_command=version.setup_command,
        available=version.available,
    )


def compute_plan_out(plan: ComputePlan) -> s.ComputePlanOut:
    return s.ComputePlanOut(
        id=plan.id,
        code=plan.code,
        name=plan.name,
        description=plan.description,
        default_nodes=plan.default_nodes,
        default_cpus=plan.default_cpus,
        default_memory_mb=plan.default_memory_mb,
        default_gpus=plan.default_gpus,
        default_time_limit_minutes=plan.default_time_limit_minutes,
        max_nodes=plan.max_nodes,
        max_cpus=plan.max_cpus,
        max_memory_mb=plan.max_memory_mb,
        max_gpus=plan.max_gpus,
        max_time_limit_minutes=plan.max_time_limit_minutes,
    )


def compute_request_out(request: ComputeRequest | None) -> s.ComputeRequestModel | None:
    if request is None:
        return None
    return s.ComputeRequestModel(**request.as_payload())


def input_binding_out(binding: InputBinding) -> s.InputBindingModel:
    return s.InputBindingModel(**binding.as_payload())


def run_configuration_out(configuration: RunConfiguration) -> s.RunConfigurationOut:
    request = (
        configuration.compute_request
        if isinstance(configuration.compute_request, ComputeRequest)
        else None
    )
    return s.RunConfigurationOut(
        id=configuration.id,
        project_id=configuration.project_id,
        name=configuration.name,
        description=configuration.description,
        working_directory=configuration.working_directory,
        command=configuration.command,
        environment_version_id=configuration.environment_version_id,
        environment_variables={
            name: value.expression for name, value in configuration.environment_variables.items()
        },
        input_bindings=[input_binding_out(b) for b in configuration.input_bindings],
        compute_plan_id=configuration.compute_plan_id,
        compute_request=compute_request_out(request),
        artifact_rules=[
            s.ArtifactRuleModel(path=r.path, name=r.name, optional=r.optional)
            for r in configuration.artifact_rules
        ],
    )


def run_out(run: Run) -> s.RunOut:
    queued_seconds: float | None = None
    running_seconds: float | None = None
    if run.submitted_at and run.started_at:
        queued_seconds = (run.started_at - run.submitted_at).total_seconds()
    if run.started_at and run.finished_at:
        running_seconds = (run.finished_at - run.started_at).total_seconds()

    return s.RunOut(
        id=run.id,
        project_id=run.project_id,
        workspace_id=run.workspace_id,
        snapshot_id=run.snapshot_id,
        project_version_id=run.project_version_id,
        project_version_label=run.project_version_label,
        source_run_configuration_id=run.source_run_configuration_id,
        source_run_id=run.source_run_id,
        name=run.name,
        status=run.status.value,
        scheduler_job_id=run.scheduler_job_id,
        exit_code=run.exit_code,
        failure_reason=run.failure_reason,
        created_by=run.created_by,
        created_at=run.created_at,
        submitted_at=run.submitted_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
        queued_seconds=queued_seconds,
        running_seconds=running_seconds,
    )


def run_event_out(event: RunEvent) -> s.RunEventOut:
    return s.RunEventOut(
        id=event.id,
        type=event.type.value,
        message=event.message,
        created_at=event.created_at,
    )


def artifact_out(artifact: Artifact) -> s.ArtifactOut:
    return s.ArtifactOut(
        id=artifact.id,
        run_id=artifact.run_id,
        name=artifact.name,
        source_path=artifact.source_path,
        size=artifact.size,
        file_count=artifact.file_count,
        status=artifact.status.value,
        description=artifact.description,
        created_at=artifact.created_at,
    )


def snapshot_out(snapshot: RunSnapshot) -> s.RunSnapshotOut:
    return s.RunSnapshotOut(
        id=snapshot.id,
        project_id=snapshot.project_id,
        project_version_id=snapshot.project_version_id,
        source_run_configuration_id=snapshot.source_run_configuration_id,
        working_directory=snapshot.working_directory,
        command=snapshot.command,
        environment_version_id=snapshot.environment_version_id,
        environment_image=snapshot.environment_image,
        environment_setup_command=snapshot.environment_setup_command,
        environment_variables=dict(snapshot.env_literals),
        secret_references={name: ref.as_key() for name, ref in snapshot.env_secret_refs.items()},
        input_bindings=[input_binding_out(b) for b in snapshot.input_bindings],
        compute_plan_id=snapshot.compute_plan_id,
        compute_request=s.ComputeRequestModel(**snapshot.compute_request.as_payload()),
        scheduler=snapshot.scheduler.as_payload(),
        artifact_rules=[
            s.ArtifactRuleModel(path=r.path, name=r.name, optional=r.optional)
            for r in snapshot.artifact_rules
        ],
        created_by=snapshot.created_by,
        created_at=snapshot.created_at,
    )


def activity_out(activity: Activity) -> s.ActivityOut:
    return s.ActivityOut(
        id=activity.id,
        workspace_id=activity.workspace_id,
        project_id=activity.project_id,
        actor_id=activity.actor_id,
        actor_name=activity.actor_name,
        action=activity.action,
        target_type=activity.target_type,
        target_id=activity.target_id,
        target_name=activity.target_name,
        detail=activity.detail,
        created_at=activity.created_at,
    )


def notification_out(notification: Notification) -> s.NotificationOut:
    return s.NotificationOut(
        id=notification.id,
        type=notification.type,
        title=notification.title,
        body=notification.body,
        workspace_id=notification.workspace_id,
        target_type=notification.target_type,
        target_id=notification.target_id,
        mandatory=notification.mandatory,
        created_at=notification.created_at,
        read_at=notification.read_at,
    )


def fork_source_out(relation: ForkRelation) -> s.ForkSourceOut:
    return s.ForkSourceOut(
        source_project_id=relation.source_project_id,
        source_version_id=relation.source_version_id,
        source_workspace_id=relation.source_workspace_id,
        source_project_name=relation.source_project_name,
        source_version_label=relation.source_version_label,
        created_at=relation.created_at,
    )


def invitation_out(view: InvitationView) -> s.InvitationOut:
    return s.InvitationOut(
        user_group_id=view.user_group.id,
        user_group_name=view.user_group.name,
        user_group_description=view.user_group.description,
        role=view.membership.role,
        invited_at=view.membership.created_at,
    )


def shared_resource_out(view: SharedResourceView) -> s.SharedResourceOut:
    return s.SharedResourceOut(
        id=view.resource.id,
        name=view.resource.name,
        description=view.resource.description,
        owner=owner_summary_out(view.owner),
        created_at=view.resource.created_at,
    )


def shared_resource_access_out(view: SharedResourceAccessView) -> s.SharedResourceOut:
    return shared_resource_out(SharedResourceView(resource=view.resource, owner=view.owner))


def shared_resource_detail_out(
    view: SharedResourceAccessView, versions: list[SharedResourceVersion]
) -> s.SharedResourceDetailOut:
    return s.SharedResourceDetailOut(
        **shared_resource_access_out(view).model_dump(),
        versions=[shared_resource_version_out(v) for v in versions],
    )


def shared_resource_version_out(version: SharedResourceVersion) -> s.SharedResourceVersionOut:
    return s.SharedResourceVersionOut(
        id=version.id,
        shared_resource_id=version.shared_resource_id,
        sequence=version.sequence,
        label=version.label,
        description=version.description,
        file_count=version.file_count,
        total_size=version.total_size,
        created_by=version.created_by,
        created_at=version.created_at,
    )


def shared_resource_version_detail_out(
    version: SharedResourceVersion,
) -> s.SharedResourceVersionDetailOut:
    return s.SharedResourceVersionDetailOut(
        **shared_resource_version_out(version).model_dump(),
        files=[
            s.SharedResourceVersionFileOut(path=f.path, size=f.size, content_hash=f.content_hash)
            for f in version.files
        ],
    )


def grant_out(view: GrantView) -> s.GrantOut:
    return s.GrantOut(
        id=view.grant.id,
        grantor=owner_summary_out(view.grantor),
        grantee=owner_summary_out(view.grantee),
        target_kind=view.grant.target_kind.value,
        target_id=view.grant.target_id,
        action=view.grant.action.value,
        granted_by=owner_summary_out(view.granted_by),
        created_at=view.grant.created_at,
    )
