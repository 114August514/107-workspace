from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from workspace107.domain.enums import WorkspaceKind, WorkspaceRole


class WorkspaceCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: WorkspaceKind
    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    description: str = Field(default="", max_length=5000)
    parent_id: UUID | None = None


class WorkspaceUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    slug: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )
    description: str | None = Field(default=None, max_length=5000)


class WorkspaceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    kind: WorkspaceKind
    name: str
    slug: str
    description: str
    parent_id: UUID | None
    created_by: UUID
    created_at: datetime
    archived_at: datetime | None


class MemberCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: UUID
    role: WorkspaceRole


class MemberUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: WorkspaceRole


class MemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    workspace_id: UUID
    user_id: UUID
    role: WorkspaceRole
    joined_at: datetime
