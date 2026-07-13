from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from workspace107.api.errors import (
    ApiProblem,
    api_problem_handler,
    domain_error_handler,
    request_validation_handler,
)
from workspace107.api.router import router
from workspace107.config import get_settings
from workspace107.domain.errors import DomainError
from workspace107.domain.ports.repositories import UnitOfWorkFactory
from workspace107.infrastructure.db.session import create_engine, create_session_factory
from workspace107.infrastructure.db.uow import SqlAlchemyUnitOfWork


def create_app(*, uow_factory: UnitOfWorkFactory | None = None) -> FastAPI:
    app = FastAPI(title="107 Workspace API", version="0.1.0")
    if uow_factory is None:
        engine = create_engine(get_settings().database_url)
        session_factory = create_session_factory(engine)

        def configured_uow_factory() -> SqlAlchemyUnitOfWork:
            return SqlAlchemyUnitOfWork(session_factory)

        uow_factory = configured_uow_factory
        app.state.database_engine = engine
    app.state.uow_factory = uow_factory

    app.add_exception_handler(ApiProblem, api_problem_handler)
    app.add_exception_handler(DomainError, domain_error_handler)
    app.add_exception_handler(RequestValidationError, request_validation_handler)
    app.include_router(router)
    return app
