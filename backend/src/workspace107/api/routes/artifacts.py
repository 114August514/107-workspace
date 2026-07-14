from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from workspace107.api.dependencies import ArtifactServiceDependency, IdentityDependency
from workspace107.api.schemas.runs import ArtifactResponse

router = APIRouter(tags=["artifacts"])


@router.get("/runs/{run_id}/artifacts", response_model=list[ArtifactResponse])
async def list_artifacts(
    run_id: UUID,
    actor_id: IdentityDependency,
    service: ArtifactServiceDependency,
) -> list[ArtifactResponse]:
    artifacts = await service.list(actor_id=actor_id, run_id=run_id)
    return [ArtifactResponse.model_validate(artifact) for artifact in artifacts]


@router.get("/artifacts/{artifact_id}/download")
async def download_artifact(
    artifact_id: UUID,
    actor_id: IdentityDependency,
    service: ArtifactServiceDependency,
) -> StreamingResponse:
    artifact, chunks = await service.open(actor_id=actor_id, artifact_id=artifact_id)
    return StreamingResponse(
        chunks,
        media_type=artifact.media_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(artifact.name, safe='')}",
            "Content-Length": str(artifact.size_bytes),
        },
    )
