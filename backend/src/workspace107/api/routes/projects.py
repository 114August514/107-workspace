"""Project、文件、版本与运行方案路由。"""

from __future__ import annotations

from fastapi import APIRouter, File, Query, UploadFile, status
from fastapi.responses import Response

from ...application.run_configuration_service import RunConfigurationInput
from ...domain.enums import ProjectStatus
from .. import presenters as p
from .. import schemas as s
from ..deps import CurrentUser, PageDep, ServicesDep

router = APIRouter(tags=["project"])

MAX_TEXT_PREVIEW = 256 * 1024


@router.get("/projects/{project_id}", response_model=s.ProjectOut)
async def get_project(project_id: str, user: CurrentUser, services: ServicesDep) -> s.ProjectOut:
    access = await services.projects.get(user.id, project_id)
    return p.project_out(access.project)


@router.patch("/projects/{project_id}", response_model=s.ProjectOut)
async def update_project(
    project_id: str, payload: s.ProjectUpdateIn, user: CurrentUser, services: ServicesDep
) -> s.ProjectOut:
    project = await services.projects.update(
        user.id,
        project_id,
        name=payload.name,
        description=payload.description,
        environment_version_id=payload.environment_version_id,
        inherit_workspace_environment=bool(payload.inherit_workspace_environment),
        default_run_configuration_id=payload.default_run_configuration_id,
    )
    if payload.status is not None:
        project = await services.projects.set_status(
            user.id, project_id, ProjectStatus(payload.status)
        )
    return p.project_out(project)


# -- 文件 -------------------------------------------------------------------


@router.get("/projects/{project_id}/files", response_model=list[s.ProjectFileOut])
async def list_files(
    project_id: str, user: CurrentUser, services: ServicesDep
) -> list[s.ProjectFileOut]:
    files = await services.projects.list_files(user.id, project_id)
    return [p.project_file_out(f) for f in files]


@router.get("/projects/{project_id}/files/content", response_model=s.FileContentOut)
async def read_file(
    project_id: str,
    user: CurrentUser,
    services: ServicesDep,
    path: str = Query(min_length=1),
) -> s.FileContentOut:
    data = await services.projects.read_file(user.id, project_id, path)
    truncated = len(data) > MAX_TEXT_PREVIEW
    text = data[:MAX_TEXT_PREVIEW].decode("utf-8", errors="replace")
    return s.FileContentOut(path=path, content=text, truncated=truncated)


@router.put("/projects/{project_id}/files", response_model=s.ProjectFileOut)
async def write_file(
    project_id: str, payload: s.FileWriteIn, user: CurrentUser, services: ServicesDep
) -> s.ProjectFileOut:
    record = await services.projects.write_file(
        user.id, project_id, payload.path, payload.content.encode("utf-8")
    )
    return p.project_file_out(record)


@router.post("/projects/{project_id}/files/upload", response_model=list[s.ProjectFileOut])
async def upload_files(
    project_id: str,
    user: CurrentUser,
    services: ServicesDep,
    files: list[UploadFile] = File(...),
    prefix: str = Query(default=""),
) -> list[s.ProjectFileOut]:
    uploaded: list[s.ProjectFileOut] = []
    for upload in files:
        name = upload.filename or "unnamed"
        target = f"{prefix.rstrip('/')}/{name}" if prefix else name
        record = await services.projects.write_file(
            user.id, project_id, target, await upload.read()
        )
        uploaded.append(p.project_file_out(record))
    return uploaded


@router.delete("/projects/{project_id}/files", status_code=status.HTTP_204_NO_CONTENT)
async def delete_path(
    project_id: str,
    user: CurrentUser,
    services: ServicesDep,
    path: str = Query(min_length=1),
) -> None:
    await services.projects.delete_path(user.id, project_id, path)


@router.post("/projects/{project_id}/files/move", response_model=list[s.ProjectFileOut])
async def move_path(
    project_id: str, payload: s.FileMoveIn, user: CurrentUser, services: ServicesDep
) -> list[s.ProjectFileOut]:
    moved = await services.projects.move_path(
        user.id, project_id, payload.source, payload.destination
    )
    return [p.project_file_out(f) for f in moved]


@router.get("/projects/{project_id}/changes", response_model=list[s.WorkingChangeOut])
async def working_changes(
    project_id: str, user: CurrentUser, services: ServicesDep
) -> list[s.WorkingChangeOut]:
    changes = await services.projects.working_changes(user.id, project_id)
    return [s.WorkingChangeOut(path=c.path, change=c.change) for c in changes]


# -- 版本 -------------------------------------------------------------------


@router.get("/projects/{project_id}/versions", response_model=s.PageOut[s.ProjectVersionOut])
async def list_versions(
    project_id: str, user: CurrentUser, services: ServicesDep, page: PageDep
) -> s.PageOut[s.ProjectVersionOut]:
    result = await services.projects.list_versions(user.id, project_id, page)
    return p.page_out(result, p.version_out)


@router.post(
    "/projects/{project_id}/versions",
    response_model=s.ProjectVersionOut,
    status_code=status.HTTP_201_CREATED,
)
async def save_version(
    project_id: str, payload: s.VersionCreateIn, user: CurrentUser, services: ServicesDep
) -> s.ProjectVersionOut:
    version = await services.projects.save_version(user.id, project_id, payload.message)
    return p.version_out(version)


@router.get("/versions/{version_id}", response_model=s.ProjectVersionDetailOut)
async def get_version(
    version_id: str, user: CurrentUser, services: ServicesDep
) -> s.ProjectVersionDetailOut:
    version = await services.projects.get_version(user.id, version_id)
    return p.version_detail_out(version)


@router.get("/versions/{version_id}/diff", response_model=list[s.VersionDiffOut])
async def diff_versions(
    version_id: str,
    user: CurrentUser,
    services: ServicesDep,
    base: str = Query(min_length=1),
) -> list[s.VersionDiffOut]:
    entries = await services.projects.diff_versions(user.id, base, version_id)
    return [s.VersionDiffOut(path=e.path, change=e.change) for e in entries]


@router.get("/versions/{version_id}/files/content", response_model=s.FileContentOut)
async def read_version_file(
    version_id: str,
    user: CurrentUser,
    services: ServicesDep,
    path: str = Query(min_length=1),
) -> s.FileContentOut:
    data = await services.projects.read_version_file(user.id, version_id, path)
    truncated = len(data) > MAX_TEXT_PREVIEW
    return s.FileContentOut(
        path=path,
        content=data[:MAX_TEXT_PREVIEW].decode("utf-8", errors="replace"),
        truncated=truncated,
    )


@router.post(
    "/versions/{version_id}/fork",
    response_model=s.ProjectOut,
    status_code=status.HTTP_201_CREATED,
    summary="从这个版本派生一个新 Project",
)
async def fork_version(
    version_id: str,
    payload: s.ForkIn,
    user: CurrentUser,
    services: ServicesDep,
) -> s.ProjectOut:
    """两侧都会校验：源版本可读、目标空间可写。

    复制内容、运行方案和环境选择；**不复制**权益、凭据、成员权限和 Run 历史
    （GR-503）。Secret 只复制引用表达式，目标空间缺同名 Secret 时
    提交前检查会拦下（GR-407）。
    """
    project = await services.projects.fork(
        user.id,
        version_id,
        payload.target_workspace_id,
        name=payload.name,
        description=payload.description,
    )
    return p.project_out(project)


@router.get(
    "/projects/{project_id}/fork-source",
    response_model=s.ForkSourceOut | None,
    summary="这个 Project 从哪儿来的",
)
async def fork_source(
    project_id: str, user: CurrentUser, services: ServicesDep
) -> s.ForkSourceOut | None:
    relation = await services.projects.fork_source(user.id, project_id)
    return p.fork_source_out(relation) if relation else None


@router.post("/versions/{version_id}/restore", response_model=list[s.ProjectFileOut])
async def restore_version(
    version_id: str, user: CurrentUser, services: ServicesDep
) -> list[s.ProjectFileOut]:
    restored = await services.projects.restore_version(user.id, version_id)
    return [p.project_file_out(f) for f in restored]


# -- 运行方案 ---------------------------------------------------------------


@router.get("/projects/{project_id}/run-configurations", response_model=list[s.RunConfigurationOut])
async def list_run_configurations(
    project_id: str, user: CurrentUser, services: ServicesDep
) -> list[s.RunConfigurationOut]:
    configurations = await services.run_configurations.list_for_project(user.id, project_id)
    return [p.run_configuration_out(c) for c in configurations]


@router.post(
    "/projects/{project_id}/run-configurations",
    response_model=s.RunConfigurationOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_run_configuration(
    project_id: str, payload: s.RunConfigurationIn, user: CurrentUser, services: ServicesDep
) -> s.RunConfigurationOut:
    configuration = await services.run_configurations.create(
        user.id, project_id, _to_input(payload)
    )
    return p.run_configuration_out(configuration)


@router.put("/run-configurations/{configuration_id}", response_model=s.RunConfigurationOut)
async def update_run_configuration(
    configuration_id: str,
    payload: s.RunConfigurationIn,
    user: CurrentUser,
    services: ServicesDep,
) -> s.RunConfigurationOut:
    configuration = await services.run_configurations.update(
        user.id, configuration_id, _to_input(payload)
    )
    return p.run_configuration_out(configuration)


@router.delete("/run-configurations/{configuration_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_run_configuration(
    configuration_id: str, user: CurrentUser, services: ServicesDep
) -> Response:
    await services.run_configurations.delete(user.id, configuration_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _to_input(payload: s.RunConfigurationIn) -> RunConfigurationInput:
    return RunConfigurationInput(
        name=payload.name,
        command=payload.command,
        compute_plan_id=payload.compute_plan_id,
        working_directory=payload.working_directory,
        description=payload.description,
        environment_version_id=payload.environment_version_id,
        environment_variables=dict(payload.environment_variables),
        input_bindings=[b.model_dump() for b in payload.input_bindings],
        compute_request=(payload.compute_request.model_dump() if payload.compute_request else None),
        artifact_rules=[r.model_dump() for r in payload.artifact_rules],
    )


@router.get(
    "/projects/{project_id}/activities",
    response_model=s.PageOut[s.ActivityOut],
    summary="Project 近期活动",
)
async def list_project_activities(
    project_id: str, user: CurrentUser, services: ServicesDep, page: PageDep
) -> s.PageOut[s.ActivityOut]:
    result = await services.activities.list_for_project(user.id, project_id, page)
    return p.page_out(result, p.activity_out)
