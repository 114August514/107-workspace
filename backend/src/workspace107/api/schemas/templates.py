from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from workspace107.domain.errors import InvalidRelativePath
from workspace107.domain.models import ResourceSpec
from workspace107.domain.values import relative_posix_path


class EnvironmentSpecRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    kind: Literal["uv", "conda", "system"]
    conda_env: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$",
    )

    @model_validator(mode="after")
    def validate_conda_environment(self) -> Self:
        if self.kind == "conda" and self.conda_env is None:
            raise ValueError("conda_env is required for a conda environment")
        if self.kind != "conda" and self.conda_env is not None:
            raise ValueError("conda_env is only valid for a conda environment")
        return self

    def as_mapping(self) -> dict[str, object]:
        result: dict[str, object] = {"kind": self.kind}
        if self.conda_env is not None:
            result["conda_env"] = self.conda_env
        return result


class ResourceSpecRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    cpus: int = Field(ge=1, le=256)
    memory_mb: int = Field(ge=256)
    gpus: int = Field(ge=0, le=16)
    walltime_seconds: int = Field(ge=60)
    account: str = Field(default="stu", min_length=1, max_length=100)
    partition: str = Field(default="Students", min_length=1, max_length=100)
    qos: str = Field(default="qos_stu_default", min_length=1, max_length=100)

    def as_domain(self) -> ResourceSpec:
        return ResourceSpec(
            cpus=self.cpus,
            memory_mb=self.memory_mb,
            gpus=self.gpus,
            walltime_seconds=self.walltime_seconds,
            account=self.account,
            partition=self.partition,
            qos=self.qos,
        )


def _relative_path(value: str) -> str:
    try:
        return str(relative_posix_path(value))
    except InvalidRelativePath as exc:
        raise ValueError("must be a safe relative POSIX path") from exc


class TemplateCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=5000)
    entrypoint: str = Field(max_length=500)
    environment_spec: EnvironmentSpecRequest
    resource_spec: ResourceSpecRequest
    output_spec: tuple[str, ...] = ()

    @field_validator("entrypoint")
    @classmethod
    def validate_entrypoint(cls, value: str) -> str:
        return _relative_path(value)

    @field_validator("output_spec")
    @classmethod
    def validate_outputs(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_relative_path(value) for value in values)


class TemplateUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    entrypoint: str | None = Field(default=None, max_length=500)
    environment_spec: EnvironmentSpecRequest | None = None
    resource_spec: ResourceSpecRequest | None = None
    output_spec: tuple[str, ...] | None = None

    @field_validator("entrypoint")
    @classmethod
    def validate_entrypoint(cls, value: str | None) -> str | None:
        return _relative_path(value) if value is not None else None

    @field_validator("output_spec")
    @classmethod
    def validate_outputs(cls, values: tuple[str, ...] | None) -> tuple[str, ...] | None:
        if values is None:
            return None
        return tuple(_relative_path(value) for value in values)


class TemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    name: str
    description: str
    entrypoint: str
    environment_spec: EnvironmentSpecRequest
    resource_spec: ResourceSpecRequest
    output_spec: tuple[str, ...]
    created_by: UUID
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None
