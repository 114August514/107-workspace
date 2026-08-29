"""应用配置。

所有配置通过环境变量注入，变量清单见仓库根目录的 .env.example。
凭据类配置只从环境读取，不写入代码，也不落库。
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

SchedulerKind = Literal["mock", "slurm"]
AuthMode = Literal["dev", "ustc"]
LogFormat = Literal["auto", "json", "text"]


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
    # 压缩包展开预算：解压后总大小与条目数，防止 zip 炸弹
    max_archive_total_bytes: int = 128 * 1024 * 1024
    max_archive_entries: int = 500

    database_url: str = "sqlite+aiosqlite:///./var/workspace107.db"
    storage_root: Path = Path("./var/storage")

    scheduler: SchedulerKind = "mock"
    slurm_api_base_url: str = ""
    slurm_api_user: str = ""
    slurm_jwt: str = Field(default="", repr=False)

    auth_mode: AuthMode = "dev"

    # 后台状态同步间隔（秒）。设为 0 表示不启动后台同步，由调用方显式触发。
    run_sync_interval_seconds: float = 1.0
    # Shared Resource publication uses its own durable processor boundary.
    shared_resource_publication_interval_seconds: float = 1.0
    shared_resource_publication_recovery_seconds: float = 300.0

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
