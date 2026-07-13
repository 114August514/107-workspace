from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="WORKSPACE107_", env_file=".env")

    database_url: str = "sqlite+aiosqlite:///./var/workspace107.db"
    storage_root: Path = Path("var/storage")
    transfer_roots: dict[str, Path] = Field(
        default_factory=lambda: {
            "source": Path("var/transfer/source"),
            "cluster": Path("var/transfer/cluster"),
            "downloads": Path("var/transfer/downloads"),
        }
    )
    mock_cluster_root: Path = Path("var/mock-cluster")
    cluster_adapter: Literal["mock", "slurm"] = "mock"
    cluster_transport: Literal["local", "ssh"] = "local"
    reconcile_interval_seconds: float = 0.2


@lru_cache
def get_settings() -> Settings:
    return Settings()
