from fastapi import APIRouter

from workspace107.api.routes.datasets import router as datasets_router
from workspace107.api.routes.health import router as health_router
from workspace107.api.routes.projects import router as projects_router
from workspace107.api.routes.users import router as users_router
from workspace107.api.routes.workspaces import router as workspaces_router

router = APIRouter()
router.include_router(health_router)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(datasets_router)
api_router.include_router(projects_router)
api_router.include_router(users_router)
api_router.include_router(workspaces_router)
router.include_router(api_router)
