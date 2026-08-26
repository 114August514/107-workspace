"""应用配置。

所有配置通过环境变量注入，变量清单见仓库根目录的 .env.example。
凭据类配置只从环境读取，不写入代码，也不落库。
"""

from __future__ import annotations

import os
import stat
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
        env_ignore_empty=True,
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
    storage_gid: int | None = None
    shared_gid: int | None = None

    scheduler: SchedulerKind = "mock"
    slurm_api_base_url: str = ""
    slurm_api_user: str = ""
    slurm_jwt: str = Field(default="", repr=False)

    auth_mode: AuthMode = "dev"

    worker_poll_seconds: float = 1.0
    worker_idle_seconds: float = 0.5

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

    @model_validator(mode="after")
    def validate_common_settings(self) -> Self:
        for name, value in (
            ("WORKSPACE107_STORAGE_GID", self.storage_gid),
            ("WORKSPACE107_SHARED_GID", self.shared_gid),
        ):
            if value is not None and value < 0:
                raise ValueError(f"{name} must be non-negative")
        if (
            self.storage_gid is not None
            and self.shared_gid is not None
            and self.storage_gid != self.shared_gid
        ):
            raise ValueError("WORKSPACE107_STORAGE_GID and WORKSPACE107_SHARED_GID must match")
        return self

    def ensure_worker_configuration(self) -> None:
        """Fail before the Worker acquires its lock or constructs external adapters."""
        if os.name != "posix":
            raise ValueError("Independent Worker requires a POSIX host; use Linux or WSL2")
        if self.scheduler == "slurm":
            raise ValueError(
                "Slurm execution is disabled until per-Run filesystem isolation prevents "
                "compute jobs from accessing other Runs and service-private stores"
            )
        if self.env not in {"local", "test", "export"}:
            raise ValueError("Mock scheduler is only allowed in local/test environments")
        if not self.database_url.startswith("postgresql+"):
            raise ValueError("Independent Worker 必须使用 PostgreSQL 数据库")

    @property
    def resolved_shared_gid(self) -> int:
        if os.name != "posix":
            raise ValueError("Independent Worker shared GID requires a POSIX host")
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
        """Create and validate the service-owned canonical storage namespace."""
        if os.name != "posix":
            raise ValueError("Canonical storage requires a POSIX host")

        canonical = Path(os.path.abspath(self.storage_root))
        self._ensure_trusted_storage_ancestors(canonical.parent)
        self.storage_root = canonical
        if canonical.is_symlink():
            raise ValueError("WORKSPACE107_STORAGE_ROOT cannot be a symbolic link")

        created = not canonical.exists()
        if created:
            canonical.mkdir(mode=0o700)
            if self.storage_gid is not None:
                os.chown(canonical, -1, self.storage_gid)
            canonical.chmod(0o750)
        info = canonical.stat(follow_symlinks=False)
        if not stat.S_ISDIR(info.st_mode):
            raise ValueError("WORKSPACE107_STORAGE_ROOT must be a directory")
        if info.st_uid != os.geteuid():
            raise ValueError("WORKSPACE107_STORAGE_ROOT must be owned by the service UID")
        expected_gid = self.storage_gid if self.storage_gid is not None else os.getegid()
        if info.st_gid != expected_gid:
            raise ValueError(
                "WORKSPACE107_STORAGE_ROOT GID does not match WORKSPACE107_STORAGE_GID"
            )
        mode = stat.S_IMODE(info.st_mode)
        if mode == 0o755:
            canonical.chmod(0o750)
            mode = stat.S_IMODE(canonical.stat(follow_symlinks=False).st_mode)
        if mode != 0o750:
            raise ValueError("WORKSPACE107_STORAGE_ROOT mode must be exactly 0o750")

        sqlite_file = self.sqlite_file
        if sqlite_file is not None:
            sqlite_file.parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _ensure_trusted_storage_ancestors(parent: Path) -> None:
        current = Path(parent.anchor)
        for part in parent.parts[1:]:
            current /= part
            try:
                info = current.lstat()
            except FileNotFoundError:
                current.mkdir(mode=0o700)
                info = current.lstat()
            if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
                raise ValueError("WORKSPACE107_STORAGE_ROOT ancestors must be real directories")
            mode = stat.S_IMODE(info.st_mode)
            sticky = bool(mode & stat.S_ISVTX)
            if mode & 0o022 and not sticky:
                raise ValueError(
                    "WORKSPACE107_STORAGE_ROOT ancestor is writable by an untrusted group"
                )
            if info.st_uid not in {0, os.geteuid()} and mode & stat.S_IWUSR and not sticky:
                raise ValueError("WORKSPACE107_STORAGE_ROOT ancestor owner is not trusted")

    def __str__(self) -> str:  # pragma: no cover - 仅用于日志
        return (
            f"Settings(env={self.env}, scheduler={self.scheduler}, "
            f"auth_mode={self.auth_mode}, storage_root={self.storage_root})"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
