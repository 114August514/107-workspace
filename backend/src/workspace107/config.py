"""应用配置。

所有配置通过环境变量注入，变量清单见仓库根目录的 .env.example。
凭据类配置只从环境读取，不写入代码，也不落库。
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

SchedulerKind = Literal["mock", "slurm"]
AuthMode = Literal["dev", "ustc"]
LogFormat = Literal["auto", "json", "text"]
SlurmRuntimeMode = Literal["native", "apptainer"]


class Settings(BaseSettings):
    """从环境变量读取的运行配置。"""

    model_config = SettingsConfigDict(
        env_prefix="WORKSPACE107_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    env: str = "local"
    log_level: str = "INFO"
    # auto：本地开发用可读文本，其余环境用 JSON 便于采集
    log_format: LogFormat = "auto"

    # 请求体上限，在读进内存之前按 Content-Length 拦掉
    max_request_bytes: int = 128 * 1024 * 1024
    # 单个项目文件上限，由用例层校验（Content-Length 可能缺失或被伪造）
    max_file_bytes: int = 32 * 1024 * 1024

    database_url: str = "sqlite+aiosqlite:///./var/workspace107.db"
    storage_root: Path = Path("./var/storage")
    shared_gid: int | None = None

    scheduler: SchedulerKind = "mock"
    slurm_api_base_url: str = ""
    slurm_api_user: str = ""
    slurm_jwt: str = Field(default="", repr=False)
    slurm_target_cluster_id: str = ""
    slurm_api_version: str = ""
    slurm_api_schema_profile: str = ""
    slurm_submit_path: str = ""
    slurm_job_path_template: str = ""
    slurm_jobs_path: str = ""
    slurm_cancel_path_template: str = ""
    slurm_correlation_field: str = ""
    slurm_correlation_query_parameter: str = ""
    slurm_correlation_query_complete: bool = False
    slurm_correlation_max_bytes: int = 0
    slurm_runtime_mode: SlurmRuntimeMode = "native"
    slurm_timeout_seconds: float = 20.0

    auth_mode: AuthMode = "dev"

    worker_poll_seconds: float = 1.0
    worker_idle_seconds: float = 0.5

    @model_validator(mode="after")
    def validate_common_settings(self) -> Self:
        if self.shared_gid is not None and self.shared_gid < 0:
            raise ValueError("WORKSPACE107_SHARED_GID must be non-negative")
        return self

    def ensure_worker_configuration(self) -> None:
        """Fail before Worker acquires its lock or constructs scheduler adapters."""
        if self.scheduler == "mock":
            if self.env not in {"local", "test", "export"}:
                raise ValueError("Mock scheduler is only allowed in local/test environments")
        else:
            if self.shared_gid is None:
                raise ValueError("Slurm scheduler requires explicit WORKSPACE107_SHARED_GID")
            required = {
                "SLURM_API_BASE_URL": self.slurm_api_base_url,
                "SLURM_API_USER": self.slurm_api_user,
                "SLURM_JWT": self.slurm_jwt,
                "SLURM_TARGET_CLUSTER_ID": self.slurm_target_cluster_id,
                "SLURM_API_VERSION": self.slurm_api_version,
                "SLURM_API_SCHEMA_PROFILE": self.slurm_api_schema_profile,
                "SLURM_SUBMIT_PATH": self.slurm_submit_path,
                "SLURM_JOB_PATH_TEMPLATE": self.slurm_job_path_template,
                "SLURM_JOBS_PATH": self.slurm_jobs_path,
                "SLURM_CANCEL_PATH_TEMPLATE": self.slurm_cancel_path_template,
                "SLURM_CORRELATION_FIELD": self.slurm_correlation_field,
                "SLURM_CORRELATION_QUERY_PARAMETER": self.slurm_correlation_query_parameter,
            }
            missing = [name for name, value in required.items() if not value.strip()]
            if missing:
                names = ", ".join(f"WORKSPACE107_{name}" for name in missing)
                raise ValueError(f"Slurm scheduler requires explicit configuration: {names}")
            if not self.slurm_correlation_query_complete:
                raise ValueError(
                    "WORKSPACE107_SLURM_CORRELATION_QUERY_COMPLETE must be true only after the "
                    "target cluster confirms permission and pagination completeness"
                )
            if self.slurm_correlation_max_bytes < 1:
                raise ValueError("WORKSPACE107_SLURM_CORRELATION_MAX_BYTES must be positive")
            if self.slurm_timeout_seconds <= 0:
                raise ValueError("WORKSPACE107_SLURM_TIMEOUT_SECONDS must be positive")
            if self.slurm_runtime_mode != "native":
                raise ValueError(
                    "Apptainer runtime is not implemented or target-validated; use native only "
                    "after the human runtime gate"
                )
        if not self.database_url.startswith("postgresql+"):
            raise ValueError("Independent Worker 必须使用 PostgreSQL 数据库")

    @property
    def resolved_shared_gid(self) -> int:
        if self.shared_gid is not None:
            return self.shared_gid
        if self.scheduler == "mock" and self.env in {"local", "test", "export"}:
            return os.getegid()
        raise ValueError("WORKSPACE107_SHARED_GID is required for this deployment")

    @property
    def use_json_logs(self) -> bool:
        if self.log_format != "auto":
            return self.log_format == "json"
        return self.env != "local"

    @property
    def sqlite_file(self) -> Path | None:
        """SQLite 数据库文件路径；使用其他数据库时返回 None。"""
        prefix = "sqlite+aiosqlite:///"
        if not self.database_url.startswith(prefix):
            return None
        location = self.database_url[len(prefix) :]
        # sqlite+aiosqlite:///:memory: 之类的特殊地址没有对应文件。
        return None if location.startswith(":") else Path(location)

    def ensure_local_directories(self) -> None:
        """建好本地运行需要的目录。

        存储根目录和 SQLite 文件所在目录都在 .gitignore 里，新克隆的仓库中
        并不存在。不先建出来，``alembic upgrade head`` 会直接报
        「unable to open database file」——那是新成员遇到的第一条命令。
        """
        self.storage_root.mkdir(parents=True, exist_ok=True)
        sqlite_file = self.sqlite_file
        if sqlite_file is not None:
            sqlite_file.parent.mkdir(parents=True, exist_ok=True)

    def __str__(self) -> str:  # pragma: no cover - 仅用于日志
        return (
            f"Settings(env={self.env}, scheduler={self.scheduler}, "
            f"auth_mode={self.auth_mode}, storage_root={self.storage_root})"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
