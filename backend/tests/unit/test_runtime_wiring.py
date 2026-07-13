from pathlib import Path
from typing import Literal, cast

import pytest

from workspace107.config import Settings
from workspace107.domain.ports.repositories import UnitOfWorkFactory
from workspace107.infrastructure.cluster.slurm.adapter import SlurmClusterAdapter
from workspace107.infrastructure.storage.local import LocalStorage
from workspace107.infrastructure.transfer.local import LocalProjectTransfer
from workspace107.infrastructure.transfer.ssh import SshProjectTransfer
from workspace107.main import create_app


def settings_for(
    tmp_path: Path,
    *,
    transport: Literal["local", "ssh"],
    ssh_host: str | None = None,
) -> Settings:
    return Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'workspace107.db'}",
        storage_root=tmp_path / "storage",
        transfer_roots={
            "source": tmp_path / "source",
            "cluster": Path("/cluster/projects"),
            "downloads": tmp_path / "downloads",
        },
        mock_cluster_root=tmp_path / "mock",
        cluster_adapter="slurm",
        cluster_transport=transport,
        ssh_host=ssh_host,
        slurm_remote_root=Path("/cluster/workspace107"),
        slurm_log_root=Path("/cluster/logs"),
        slurm_storage_root=Path("/cluster/storage"),
    )


def unused_uow_factory() -> UnitOfWorkFactory:
    return cast(UnitOfWorkFactory, lambda: None)


def test_create_app_wires_local_slurm_and_local_transfer(tmp_path: Path) -> None:
    app = create_app(
        settings=settings_for(tmp_path, transport="local"),
        uow_factory=unused_uow_factory(),
        storage=LocalStorage(tmp_path / "objects"),
        start_reconciler=False,
    )

    assert isinstance(app.state.cluster, SlurmClusterAdapter)
    assert isinstance(app.state.transfer, LocalProjectTransfer)
    assert app.state.project_transport == "local"


def test_create_app_wires_ssh_slurm_and_ssh_transfer(tmp_path: Path) -> None:
    app = create_app(
        settings=settings_for(tmp_path, transport="ssh", ssh_host="ustc-cluster"),
        uow_factory=unused_uow_factory(),
        storage=LocalStorage(tmp_path / "objects"),
        start_reconciler=False,
    )

    assert isinstance(app.state.cluster, SlurmClusterAdapter)
    assert isinstance(app.state.transfer, SshProjectTransfer)
    assert app.state.project_transport == "ssh"


def test_create_app_requires_host_for_ssh_transport(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="SSH host"):
        create_app(
            settings=settings_for(tmp_path, transport="ssh"),
            uow_factory=unused_uow_factory(),
            storage=LocalStorage(tmp_path / "objects"),
            start_reconciler=False,
        )
