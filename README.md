# 107 Workspace

107 Workspace is a backend-first collaborative computing workspace for
undergraduate teaching, student projects, and competition teams.

The active implementation lives in `backend/`. Frontend, container, and deploy
work are intentionally deferred until the backend acceptance workflow passes.

## Development

```bash
cd backend
uv sync --all-extras
uv run alembic upgrade head
uv run uvicorn workspace107.main:create_app --factory --reload
```

OpenAPI is available at `http://127.0.0.1:8000/docs`.

## References

- `docs/superpowers/specs/2026-07-13-workspace107-backend-design.md`
- `ref.md`
- `foo.md`
- `archive/runbox-v0/`
