from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DatasetCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    description: str = Field(default="", max_length=5000)


class DatasetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    name: str
    slug: str
    description: str
    created_by: UUID
    created_at: datetime
    archived_at: datetime | None


class DatasetVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    dataset_id: UUID
    version: str
    storage_key: str
    size_bytes: int
    sha256: str
    created_by: UUID
    created_at: datetime
