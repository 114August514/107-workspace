"""Project、文件、版本与运行方案路由。"""

from __future__ import annotations

from fastapi import APIRouter, File, Query, UploadFile, status
from fastapi.responses import Response

from ...application.run_configuration_service import RunConfigurationInput
from ...domain.enums import ProjectStatus
from ...domain.ownership import OwnerReference
from .. import presenters as p
from .. import schemas as s
from ..deps import CurrentUser, PageDep, ServicesDep

router = APIRouter(tags=["project"])

MAX_TEXT_PREVIEW = 256 * 1024


@router.get(
    "/projects", response_model=s.PageOut[s.ProjectOut], summary="列出当前用户可发现的 Project"
)
async def list_discoverable_projects(
    user: CurrentUser, services: ServicesDep, page: PageDep
) -> s.PageOut[s.ProjectOut]:
    """列出当前用户可发现的 Project：自己 / 所属 User Group 拥有的，以及 PUBLIC Project。"""
    result = await services.projects.list_discoverable_for_user(user.id, page)
    summaries = await services.projects.owner_summaries(result.items)
    return p.page_out(
        result,
        lambda project: p.project_out(
            project,
            owner=summaries[(project.owner.kind, project.owner.id)],
            owner_scope=False,
        ),
    )


@router.post(
    "/projects",
    response_model=s.ProjectOut,
    status_code=status.HTTP_201_CREATED,
    summary="为 User 或 User Group 创建 Project",
)
async def create_owned_project(
    payload: s.ProjectCreateOwnedIn, user: CurrentUser, services: ServicesDep
) -> s.ProjectOut:
    project = await services.projects.create_owned(
        user.id,
        OwnerReference(kind=payload.owner.kind, id=payload.owner.id),
        payload.name,
        payload.description,
        visibility=payload.visibility,
    )
    access = await services.projects.get(user.id, project.id)
    return p.project_out(
        project,
        owner=await services.projects.owner_summary(project),
        capabilities=access.capabilities,
    )


@router.get(
    "/projects/{project_id}",
    response_model=s.ProjectOut,
    summary="获取 Project 详情",
)
async def get_project(project_id: str, user: CurrentUser, services: ServicesDep) -> s.ProjectOut:
    """校验当前用户可查看该 Project 后，返回项目设置与当前状态。"""
    access = await services.projects.get(user.id, project_id)
    return p.project_out(
        access.project,
        owner=await services.projects.owner_summary(access.project),
        owner_scope=access.owner_scope,
        capabilities=access.capabilities,
    )


@router.patch(
    "/projects/{project_id}",
    response_model=s.ProjectOut,
    summary="更新 Project 设置",
)
async def update_project(
    project_id: str, payload: s.ProjectUpdateIn, user: CurrentUser, services: ServicesDep
) -> s.ProjectOut:
    """要求 Project 更新权限，修改基本信息、环境、默认运行方案或状态。

    更新项目设置会刷新修改时间并记录项目更新活动。
    """
    project = await services.projects.update(
        user.id,
        project_id,
        name=payload.name,
        description=payload.description,
        environment_version_id=payload.environment_version_id,
        update_environment_version="environment_version_id" in payload.model_fields_set,
        default_run_configuration_id=payload.default_run_configuration_id,
        visibility=payload.visibility,
    )
    if payload.status is not None:
        project = await services.projects.set_status(
            user.id, project_id, ProjectStatus(payload.status)
        )
    access = await services.projects.get(user.id, project.id)
    return p.project_out(
        project,
        owner=await services.projects.owner_summary(project),
        capabilities=access.capabilities,
    )


# -- 文件 -------------------------------------------------------------------


@router.get(
    "/projects/{project_id}/files",
    response_model=list[s.ProjectFileOut],
    summary="列出 Project 文件",
)
async def list_files(
    project_id: str, user: CurrentUser, services: ServicesDep
) -> list[s.ProjectFileOut]:
    """校验 Project 查看权限后，按路径排序返回当前工作区的文件元数据。"""
    files = await services.projects.list_files(user.id, project_id)
    return [p.project_file_out(f) for f in files]


@router.get(
    "/projects/{project_id}/files/content",
    response_model=s.FileContentOut,
    summary="读取 Project 文件内容",
)
async def read_file(
    project_id: str,
    user: CurrentUser,
    services: ServicesDep,
    path: str = Query(min_length=1),
) -> s.FileContentOut:
    """校验 Project 查看权限后读取文本预览，最多返回前 256 KiB。

    非 UTF-8 字节以替代字符解码；内容超出预览上限时 ``truncated`` 为真。
    """
    data = await services.projects.read_file(user.id, project_id, path)
    truncated = len(data) > MAX_TEXT_PREVIEW
    text = data[:MAX_TEXT_PREVIEW].decode("utf-8", errors="replace")
    return s.FileContentOut(path=path, content=text, truncated=truncated)


@router.put(
    "/projects/{project_id}/files",
    response_model=s.ProjectFileOut,
    summary="写入 Project 文本文件",
)
async def write_file(
    project_id: str, payload: s.FileWriteIn, user: CurrentUser, services: ServicesDep
) -> s.ProjectFileOut:
    """要求内容写入权限，以 UTF-8 创建或覆盖指定文件并刷新项目修改时间。"""
    record = await services.projects.write_file(
        user.id, project_id, payload.path, payload.content.encode("utf-8")
    )
    return p.project_file_out(record)


@router.post(
    "/projects/{project_id}/files/upload",
    response_model=list[s.ProjectFileOut],
    summary="上传 Project 文件",
)
async def upload_files(
    project_id: str,
    user: CurrentUser,
    services: ServicesDep,
    files: list[UploadFile] = File(...),
    prefix: str = Query(default=""),
) -> list[s.ProjectFileOut]:
    """要求内容写入权限，将多个上传文件写入可选路径前缀并返回文件元数据。

    同路径文件会被覆盖，每个文件均受服务端单文件大小限制。
    """
    uploaded: list[s.ProjectFileOut] = []
    for upload in files:
        name = upload.filename or "unnamed"
        target = f"{prefix.rstrip('/')}/{name}" if prefix else name
        record = await services.projects.write_file(
            user.id, project_id, target, await upload.read()
        )
        uploaded.append(p.project_file_out(record))
    return uploaded


@router.delete(
    "/projects/{project_id}/files",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除 Project 文件或目录",
)
async def delete_path(
    project_id: str,
    user: CurrentUser,
    services: ServicesDep,
    path: str = Query(min_length=1),
) -> None:
    """要求内容写入权限，删除指定文件或递归删除目录并刷新项目修改时间。"""
    await services.projects.delete_path(user.id, project_id, path)


@router.post(
    "/projects/{project_id}/files/move",
    response_model=list[s.ProjectFileOut],
    summary="移动 Project 文件或目录",
)
async def move_path(
    project_id: str, payload: s.FileMoveIn, user: CurrentUser, services: ServicesDep
) -> list[s.ProjectFileOut]:
    """要求内容写入权限，重命名文件或递归移动目录并返回移动后的文件。"""
    moved = await services.projects.move_path(
        user.id, project_id, payload.source, payload.destination
    )
    return [p.project_file_out(f) for f in moved]


@router.get(
    "/projects/{project_id}/changes",
    response_model=list[s.WorkingChangeOut],
    summary="查看 Project 未保存变更",
)
async def working_changes(
    project_id: str, user: CurrentUser, services: ServicesDep
) -> list[s.WorkingChangeOut]:
    """校验 Project 查看权限后，比较当前文件与最近保存版本的内容摘要。

    尚无历史版本时以空内容为基线，结果只表示新增、修改或删除，不写入数据。
    """
    changes = await services.projects.working_changes(user.id, project_id)
    return [s.WorkingChangeOut(path=c.path, change=c.change) for c in changes]


# -- 版本 -------------------------------------------------------------------


@router.get(
    "/projects/{project_id}/versions",
    response_model=s.PageOut[s.ProjectVersionOut],
    summary="列出 Project 历史版本",
)
async def list_versions(
    project_id: str, user: CurrentUser, services: ServicesDep, page: PageDep
) -> s.PageOut[s.ProjectVersionOut]:
    """校验 Project 查看权限后，分页返回已保存的不可变历史版本。"""
    result = await services.projects.list_versions(user.id, project_id, page)
    return p.page_out(result, p.version_out)


@router.post(
    "/projects/{project_id}/versions",
    response_model=s.ProjectVersionOut,
    status_code=status.HTTP_201_CREATED,
    summary="保存 Project 新版本",
)
async def save_version(
    project_id: str, payload: s.VersionCreateIn, user: CurrentUser, services: ServicesDep
) -> s.ProjectVersionOut:
    """要求内容写入权限，将当前全部文件保存为新的不可变版本并记录活动。

    空 Project 或与最近版本内容完全相同时不会创建新版本。
    """
    version = await services.projects.save_version(user.id, project_id, payload.message)
    return p.version_out(version)


@router.get(
    "/versions/{version_id}",
    response_model=s.ProjectVersionDetailOut,
    summary="获取 Project 版本详情",
)
async def get_version(
    version_id: str, user: CurrentUser, services: ServicesDep
) -> s.ProjectVersionDetailOut:
    """校验所属 Project 的查看权限后，返回版本信息及完整文件清单。"""
    version = await services.projects.get_version(user.id, version_id)
    return p.version_detail_out(version)


@router.get(
    "/versions/{version_id}/diff",
    response_model=list[s.VersionDiffOut],
    summary="比较 Project 历史版本",
)
async def diff_versions(
    version_id: str,
    user: CurrentUser,
    services: ServicesDep,
    base: str = Query(min_length=1),
) -> list[s.VersionDiffOut]:
    """校验两个版本均可查看，返回从 ``base`` 到目标版本的文件级差异。

    仅允许比较同一个 Project 的版本，不读取或返回文件正文。
    """
    entries = await services.projects.diff_versions(user.id, base, version_id)
    return [s.VersionDiffOut(path=e.path, change=e.change) for e in entries]


@router.get(
    "/versions/{version_id}/files/content",
    response_model=s.FileContentOut,
    summary="读取历史版本文件内容",
)
async def read_version_file(
    version_id: str,
    user: CurrentUser,
    services: ServicesDep,
    path: str = Query(min_length=1),
) -> s.FileContentOut:
    """校验所属 Project 的查看权限后，读取历史版本文件的文本预览。

    最多返回前 256 KiB；非 UTF-8 字节会被替换，且不会修改历史版本。
    """
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
    summary="从历史版本派生新 Project",
)
async def fork_version(
    version_id: str,
    payload: s.ForkIn,
    user: CurrentUser,
    services: ServicesDep,
) -> s.ProjectOut:
    """Validate source visibility and explicit target Owner create authority.

    The fork copies content and eligible configuration references, never entitlement,
    credential values, Membership, or Run history. PUBLIC readers only copy immutable files.
    """
    target_owner = OwnerReference(kind=payload.target_owner.kind, id=payload.target_owner.id)
    project = await services.projects.fork(
        user.id,
        version_id,
        target_owner,
        name=payload.name,
        description=payload.description,
    )
    access = await services.projects.get(user.id, project.id)
    return p.project_out(
        project,
        owner=await services.projects.owner_summary(project),
        capabilities=access.capabilities,
    )


@router.get(
    "/projects/{project_id}/fork-source",
    response_model=s.ForkSourceOut | None,
    summary="这个 Project 从哪儿来的",
)
async def fork_source(
    project_id: str, user: CurrentUser, services: ServicesDep
) -> s.ForkSourceOut | None:
    """校验 Project 查看权限后返回固定的派生来源记录；非派生项目返回空。"""
    relation = await services.projects.fork_source(user.id, project_id)
    return p.fork_source_out(relation) if relation else None


@router.post(
    "/versions/{version_id}/restore",
    response_model=list[s.ProjectFileOut],
    summary="将 Project 恢复到历史版本",
)
async def restore_version(
    version_id: str, user: CurrentUser, services: ServicesDep
) -> list[s.ProjectFileOut]:
    """要求所属 Project 的内容写入权限，以指定版本整体替换当前工作内容。

    历史版本本身保持不变；恢复会刷新项目修改时间并记录恢复活动。
    """
    restored = await services.projects.restore_version(user.id, version_id)
    return [p.project_file_out(f) for f in restored]


# -- 运行方案 ---------------------------------------------------------------


@router.get(
    "/projects/{project_id}/run-configurations",
    response_model=list[s.RunConfigurationOut],
    summary="列出 Project 运行方案",
)
async def list_run_configurations(
    project_id: str, user: CurrentUser, services: ServicesDep
) -> list[s.RunConfigurationOut]:
    """校验 Project 查看权限后，返回项目当前可编辑的全部运行方案。"""
    configurations = await services.run_configurations.list_for_project(user.id, project_id)
    return [p.run_configuration_out(c) for c in configurations]


@router.post(
    "/projects/{project_id}/run-configurations",
    response_model=s.RunConfigurationOut,
    status_code=status.HTTP_201_CREATED,
    summary="创建 Project 运行方案",
)
async def create_run_configuration(
    project_id: str, payload: s.RunConfigurationIn, user: CurrentUser, services: ServicesDep
) -> s.RunConfigurationOut:
    """要求运行方案管理权限，校验算力与运行参数后创建方案。

    Project 尚无默认运行方案时，新建方案会自动成为默认项。
    """
    configuration = await services.run_configurations.create(
        user.id, project_id, _to_input(payload)
    )
    return p.run_configuration_out(configuration)


@router.put(
    "/run-configurations/{configuration_id}",
    response_model=s.RunConfigurationOut,
    summary="更新 Project 运行方案",
)
async def update_run_configuration(
    configuration_id: str,
    payload: s.RunConfigurationIn,
    user: CurrentUser,
    services: ServicesDep,
) -> s.RunConfigurationOut:
    """要求运行方案管理权限，以请求内容更新方案并重新校验运行参数。

    修改只影响之后创建的 Run，已有 Run 使用各自已固定的运行快照。
    """
    configuration = await services.run_configurations.update(
        user.id, configuration_id, _to_input(payload)
    )
    return p.run_configuration_out(configuration)


@router.delete(
    "/run-configurations/{configuration_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除 Project 运行方案",
)
async def delete_run_configuration(
    configuration_id: str, user: CurrentUser, services: ServicesDep
) -> Response:
    """要求运行方案管理权限并删除方案；删除默认项时自动选择剩余方案。"""
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
    """校验 Project 查看权限后，分页返回该项目的近期操作记录。"""
    result = await services.activities.list_for_project(user.id, project_id, page)
    return p.page_out(result, p.activity_out)
