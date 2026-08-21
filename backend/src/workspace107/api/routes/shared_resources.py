"""Shared Resource routes.

Canonical ownership is User/UserGroup:

- ``GET    /shared-resources``                              —— actor-discoverable resources
- ``POST   /shared-resources``                             —— create with explicit owner
- ``GET    /shared-resources/{id}``                        —— resource detail and versions
- ``PATCH  /shared-resources/{id}``                        —— resource metadata
- ``POST   /shared-resources/{id}/versions``               —— upload immutable version
- ``GET    /shared-resource-versions/{id}``                —— version detail
- ``GET    /shared-resource-versions/{id}/files/content``  —— read version text file
- ``GET    /shared-resource-versions/{id}/files/download`` —— read original bytes

File uploads use ``multipart/form-data``, matching Project file uploads.
"""

from __future__ import annotations

import mimetypes
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, File, Form, Query, UploadFile, status
from fastapi.responses import PlainTextResponse, Response

from ...application.shared_resource_service import SharedResourceUpload
from ...domain.ownership import OwnerReference
from .. import presenters as p
from .. import schemas as s
from ..deps import CurrentUser, ServicesDep

router = APIRouter(tags=["shared-resource"])


# -- Canonical actor-owned resources ---------------------------------------


@router.get(
    "/shared-resources",
    response_model=list[s.SharedResourceOut],
    summary="列出当前用户可发现的共享资源",
)
async def list_shared_resources(
    user: CurrentUser, services: ServicesDep
) -> list[s.SharedResourceOut]:
    """Return resources owned by the actor or by an owning UserGroup with active membership."""
    views = await services.shared_resources.list_discoverable(user.id)
    return [p.shared_resource_out(view) for view in views]


@router.post(
    "/shared-resources",
    response_model=s.SharedResourceOut,
    status_code=status.HTTP_201_CREATED,
    summary="创建 Shared Resource",
)
async def create_canonical_shared_resource(
    payload: s.CanonicalSharedResourceCreateIn,
    user: CurrentUser,
    services: ServicesDep,
) -> s.SharedResourceOut:
    """Create with explicit User/UserGroup owner.

    User owner must be the actor; UserGroup owner requires active membership with
    Shared Resource management capability. Cross-owner attempts are concealed.
    """
    view = await services.shared_resources.create(
        user.id,
        owner=OwnerReference(payload.owner.kind, payload.owner.id),
        name=payload.name,
        description=payload.description,
    )
    return p.shared_resource_out(view)


# -- 单资源 ----------------------------------------------------------------


@router.get(
    "/shared-resources/{resource_id}",
    response_model=s.SharedResourceDetailOut,
    summary="获取 Shared Resource 详情",
)
async def get_shared_resource(
    resource_id: str, user: CurrentUser, services: ServicesDep
) -> s.SharedResourceDetailOut:
    """校验可见性后返回资源信息及其全部版本（按 sequence 倒序）。"""
    view = await services.shared_resources.get(user.id, resource_id)
    versions = await services.shared_resources.list_versions(user.id, resource_id)
    return p.shared_resource_detail_out(view, versions)


@router.patch(
    "/shared-resources/{resource_id}",
    response_model=s.SharedResourceOut,
    summary="更新 Shared Resource 元信息",
)
async def update_shared_resource(
    resource_id: str,
    payload: s.SharedResourceUpdateIn,
    user: CurrentUser,
    services: ServicesDep,
) -> s.SharedResourceOut:
    """需要 Shared Resource 管理权限；仅修改当前 actor 可发现资源的名称与说明。"""
    view = await services.shared_resources.update(
        user.id,
        resource_id,
        name=payload.name,
        description=payload.description,
    )
    return p.shared_resource_out(view)


@router.post(
    "/shared-resources/{resource_id}/versions",
    response_model=s.SharedResourceVersionOut,
    status_code=status.HTTP_201_CREATED,
    summary="上传 Shared Resource 新版本",
)
async def publish_shared_resource_version(
    resource_id: str,
    user: CurrentUser,
    services: ServicesDep,
    files: list[UploadFile] = File(...),
    description: str = Form(default=""),
    prefix: str = Query(default=""),
) -> s.SharedResourceVersionOut:
    """需要 Shared Resource 版本创建权限；上传文件形成新的不可变版本。

    上传的文件按 ``prefix/<filename>`` 写入资源；同路径文件会被视为重复路径
    导致版本发布失败。版本发布后内容不可修改。
    """
    uploads: list[SharedResourceUpload] = []
    for upload in files:
        name = upload.filename or "unnamed"
        target = f"{prefix.rstrip('/')}/{name}" if prefix else name
        uploads.append(SharedResourceUpload(path=target, content=await upload.read()))
    version = await services.shared_resources.publish_version(
        user.id,
        resource_id,
        description=description,
        uploads=uploads,
    )
    return p.shared_resource_version_out(version)


# -- 版本 ------------------------------------------------------------------


@router.get(
    "/shared-resource-versions/{version_id}",
    response_model=s.SharedResourceVersionDetailOut,
    summary="获取 Shared Resource 版本详情",
)
async def get_shared_resource_version(
    version_id: str, user: CurrentUser, services: ServicesDep
) -> s.SharedResourceVersionDetailOut:
    """校验所属资源的可见性后，返回版本信息及完整文件清单。"""
    version, _ = await services.shared_resources.get_version(user.id, version_id)
    return p.shared_resource_version_detail_out(version)


@router.get(
    "/shared-resource-versions/{version_id}/files/content",
    response_class=PlainTextResponse,
    summary="读取 Shared Resource 版本中的文件",
)
async def read_shared_resource_version_file(
    version_id: str,
    path: Annotated[str, Query(description="版本内的相对路径")],
    user: CurrentUser,
    services: ServicesDep,
) -> PlainTextResponse:
    """按可见性校验后返回版本内指定文件的内容。

    用 ``text/plain`` 直返字节，前端拿到字符串即可预览或下载；
    二进制文件请改走 ``files/download``，经本接口会被损坏。
    """
    data = await services.shared_resources.read_version_file(user.id, version_id, path)
    filename = path.rsplit("/", 1)[-1]
    return PlainTextResponse(
        content=data,
        media_type="text/plain",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.get(
    "/shared-resource-versions/{version_id}/files/download",
    summary="下载 Shared Resource 版本中的文件",
    responses={200: {"content": {"application/octet-stream": {}}}},
)
async def download_shared_resource_version_file(
    version_id: str,
    path: Annotated[str, Query(description="版本内的相对路径")],
    user: CurrentUser,
    services: ServicesDep,
) -> Response:
    """按可见性校验后返回版本内指定文件的原始字节。

    按扩展名推断 MIME 并以 ``inline`` 返回：图片等浏览器能直接渲染的类型
    供前端内联预览，其余类型前端仍按不可预览处理。``files/content`` 走
    ``text/plain`` 直出，二进制文件经它会损坏，只能由本接口取原始字节。
    """
    data = await services.shared_resources.read_version_file(user.id, version_id, path)
    filename = path.rsplit("/", 1)[-1]
    media_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    fallback = filename.encode("ascii", errors="replace").decode("ascii").replace('"', "_")
    quoted = quote(filename, safe="")
    return Response(
        content=data,
        media_type=media_type,
        headers={
            "Content-Disposition": f"inline; filename=\"{fallback}\"; filename*=UTF-8''{quoted}"
        },
    )
