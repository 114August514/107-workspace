from fastapi import FastAPI

from workspace107.api.router import router


def create_app() -> FastAPI:
    app = FastAPI(title="107 Workspace API", version="0.1.0")
    app.include_router(router)
    return app
