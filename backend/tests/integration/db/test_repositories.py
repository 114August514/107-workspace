from dataclasses import replace

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from workspace107.domain.enums import ArtifactKind, RunStatus, WorkspaceKind, WorkspaceRole
from workspace107.domain.models import (
    FileSignature,
    NewArtifact,
    NewDataset,
    NewDatasetVersion,
    NewProject,
    NewProjectSync,
    NewRun,
    NewRunEvent,
    NewRunTemplate,
    NewUser,
    NewWorkspace,
    NewWorkspaceMember,
    ResourceSpec,
    RunDataset,
    utc_now,
)
from workspace107.infrastructure.db.uow import SqlAlchemyUnitOfWork


async def seed_content(uow: SqlAlchemyUnitOfWork):
    user = await uow.users.add(NewUser(username="alice", display_name="Alice"))
    workspace = await uow.workspaces.add(
        NewWorkspace(
            kind=WorkspaceKind.COURSE,
            name="AI 101",
            slug="ai-101",
            created_by=user.id,
        )
    )
    member = await uow.members.add(
        NewWorkspaceMember(
            workspace_id=workspace.id,
            user_id=user.id,
            role=WorkspaceRole.OWNER,
        )
    )
    project = await uow.projects.add(
        NewProject(
            workspace_id=workspace.id,
            name="Demo",
            slug="demo",
            storage_key="projects/demo",
            created_by=user.id,
        )
    )
    dataset = await uow.datasets.add(
        NewDataset(
            workspace_id=workspace.id,
            name="Images",
            slug="images",
            created_by=user.id,
        )
    )
    version = await uow.datasets.add_version(
        NewDatasetVersion(
            dataset_id=dataset.id,
            version="v1",
            storage_key="sha256/aa/" + "a" * 64,
            size_bytes=7,
            sha256="a" * 64,
            created_by=user.id,
        )
    )
    template = await uow.templates.add(
        NewRunTemplate(
            workspace_id=workspace.id,
            name="Train",
            entrypoint="train.py",
            environment_spec={"kind": "uv"},
            resource_spec=ResourceSpec(
                cpus=2,
                memory_mb=4096,
                gpus=0,
                walltime_seconds=600,
            ),
            output_spec=("results",),
            created_by=user.id,
        )
    )
    return user, workspace, member, project, dataset, version, template


async def test_content_repositories_round_trip_and_list(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        user, workspace, member, project, dataset, version, template = await seed_content(uow)
        await uow.commit()

    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        assert await uow.users.get_by_username("alice") == user
        assert await uow.workspaces.get_by_slug("ai-101") == workspace
        assert await uow.workspaces.list_for_user(user.id, limit=10, offset=0) == (workspace,)
        assert await uow.members.get(workspace.id, user.id) == member
        assert await uow.members.list_for_workspace(workspace.id) == (member,)
        assert await uow.members.count_owners(workspace.id) == 1
        assert await uow.projects.get(project.id) == project
        assert await uow.projects.get_by_slug(workspace.id, "demo") == project
        assert await uow.projects.list_for_workspace(workspace.id, limit=10, offset=0) == (project,)
        assert await uow.datasets.get(dataset.id) == dataset
        assert await uow.datasets.get_by_slug(workspace.id, "images") == dataset
        assert await uow.datasets.list_for_workspace(workspace.id, limit=10, offset=0) == (dataset,)
        assert await uow.datasets.get_version(version.id) == version
        assert await uow.datasets.get_version_by_name(dataset.id, "v1") == version
        assert await uow.datasets.list_versions(dataset.id) == (version,)
        assert await uow.datasets.count_versions_by_storage_key(version.storage_key) == 1
        assert await uow.templates.get(template.id) == template
        assert await uow.templates.list_for_workspace(workspace.id, limit=10, offset=0) == (
            template,
        )


async def test_save_role_removal_and_sync_upsert(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        user, workspace, _, project, dataset, _, _ = await seed_content(uow)
        workspace = await uow.workspaces.save(replace(workspace, name="Advanced AI"))
        project = await uow.projects.save(replace(project, description="updated"))
        dataset = await uow.datasets.save(replace(dataset, description="updated"))
        changed = await uow.members.set_role(workspace.id, user.id, WorkspaceRole.MANAGER)
        sync = await uow.syncs.upsert(
            NewProjectSync(
                project_id=project.id,
                transport="local",
                target_uri="file:///target",
                manifest={"train.py": FileSignature(path="train.py", size_bytes=10, mtime_ns=1)},
                last_synced_at=utc_now(),
            )
        )
        await uow.commit()

    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        assert (await uow.workspaces.get(workspace.id)) == workspace
        assert (await uow.projects.get(project.id)) == project
        assert (await uow.datasets.get(dataset.id)) == dataset
        assert changed is not None and changed.role is WorkspaceRole.MANAGER
        assert await uow.members.count_owners(workspace.id) == 0
        assert await uow.syncs.get(project.id, "local", "file:///target") == sync
        assert await uow.syncs.get_latest(project.id, "local") == sync

        updated_sync = await uow.syncs.upsert(
            NewProjectSync(
                project_id=project.id,
                transport="local",
                target_uri="file:///target",
                manifest={},
                last_synced_at=utc_now(),
            )
        )
        assert updated_sync.id == sync.id
        assert updated_sync.manifest == {}
        assert await uow.members.remove(workspace.id, user.id)
        assert not await uow.members.remove(workspace.id, user.id)
        await uow.commit()


async def test_run_history_artifacts_and_compare_and_set(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        user, workspace, _, project, _, version, template = await seed_content(uow)
        new_run = NewRun(
            workspace_id=workspace.id,
            project_id=project.id,
            template_id=template.id,
            submitted_by=user.id,
            submission_snapshot={"entrypoint": "train.py"},
        )
        mount = RunDataset(
            run_id=new_run.id,
            dataset_version_id=version.id,
            mount_path="input/data",
        )
        run = await uow.runs.add(new_run, (mount,))
        event = await uow.events.add(
            NewRunEvent(
                run_id=run.id,
                event_type="created",
                to_status=RunStatus.SUBMITTING,
            )
        )
        artifact = await uow.artifacts.add(
            NewArtifact(
                run_id=run.id,
                kind=ArtifactKind.RESULT,
                name="result.json",
                storage_key="sha256/bb/" + "b" * 64,
                media_type="application/json",
                size_bytes=10,
                sha256="b" * 64,
            )
        )
        await uow.commit()

    queued = replace(
        run,
        status=RunStatus.QUEUED,
        external_job_id="job-1",
        submitted_at=utc_now(),
        updated_at=utc_now(),
    )
    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        assert await uow.runs.compare_and_set_status(RunStatus.SUBMITTING, queued)
        assert not await uow.runs.compare_and_set_status(RunStatus.SUBMITTING, queued)
        await uow.commit()

    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        assert await uow.runs.get(run.id) == queued
        assert await uow.runs.list_for_workspace(workspace.id, limit=10, offset=0) == (queued,)
        assert await uow.runs.list_non_terminal() == (queued,)
        assert await uow.runs.list_datasets(run.id) == (mount,)
        assert await uow.events.list_for_run(run.id) == (event,)
        assert await uow.artifacts.get(artifact.id) == artifact
        assert await uow.artifacts.list_for_run(run.id) == (artifact,)
        assert await uow.artifacts.exists_for_run_and_storage_key(run.id, artifact.storage_key)
