"""107 RunBox — FastAPI application.

A thin local web GUI over the ``hpc_helper`` engine. Serves a single-page UI
and a small REST API that maps 1:1 onto engine functions.
"""
from __future__ import annotations

import webbrowser
from pathlib import Path
from typing import Any, Optional

import asyncio

import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import engine
from .engine import EngineError

# RunBox can run in two places:
#  - "local": on the cluster login node (this web shell). Commands run here,
#    /home is a local path — no SSH. Auto-detected by presence of squeue.
#  - "ssh":   on a student laptop, driving the cluster over SSH.
import hpc_helper.api as _engine_api
from shutil import which

if which("squeue") and which("sbatch"):
    _engine_api.set_transport("local")
    TRANSPORT = "local"
else:
    TRANSPORT = "ssh"

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="107 RunBox", version="0.1.0")

# Sensible defaults for this cluster, pre-filled on the setup screen.
CLUSTER_DEFAULTS = {
    "host": "hpc-tunnel",
    "remote_home": "",          # filled from username on the client
    "conda_env": "deep-learning",
    "account": "stu",
    "partition": "Students",
    "qos": "qos_stu_small",
    "cpus": 4,
    "gpus": 1,
    "walltime": 420,            # 7h
}


# ── error handling ────────────────────────────────────────────────────────────


@app.exception_handler(EngineError)
async def engine_error_handler(_request, exc: EngineError) -> JSONResponse:
    """Translate engine errors into a structured JSON body the UI can show.

    ``kind`` drives the friendly message in the frontend (auth/alloc/sync/...).
    """
    return JSONResponse(status_code=400, content={"kind": exc.kind, "message": str(exc)})


# ── session / status ──────────────────────────────────────────────────────────


def _config_summary(cfg) -> Optional[dict]:
    if cfg is None:
        return None
    return {
        "host": cfg.host,
        "user": cfg.user,
        "remote_home": cfg.remote_home,
        "conda_env": cfg.conda_env,
        "account": cfg.account,
        "partition": cfg.partition,
        "qos": cfg.qos,
        "cpus": cfg.cpus,
        "gpus": cfg.gpus,
        "walltime": cfg.walltime,
    }


@app.get("/api/session")
async def get_session() -> dict:
    """Top-of-page status: is the user configured + what node do they hold."""
    cfg = await engine.call(engine.engine.load_config)
    info = await engine.call(engine.engine.get_job_info)
    return {
        "configured": cfg is not None,
        "config": _config_summary(cfg),
        "job": {
            "job_id": info.job_id,
            "node": info.node,
            "state": info.state,
            "minutes_left": info.minutes_left,
        },
    }


# ── config / setup ────────────────────────────────────────────────────────────


@app.get("/api/config/defaults")
async def config_defaults() -> dict:
    """Cluster defaults + current config, for pre-filling the setup screen."""
    cfg = await engine.call(engine.engine.load_config)
    return {"defaults": CLUSTER_DEFAULTS, "config": _config_summary(cfg)}


@app.put("/api/config")
async def save_config(body: dict) -> dict:
    """Persist the setup form to ~/.hpc-helper/config.toml."""
    from hpc_helper.config import Config

    fields = (
        "host", "user", "remote_home", "conda_env", "account",
        "partition", "qos", "cpus", "gpus", "walltime",
    )
    data = {k: body[k] for k in fields if k in body}
    # Coerce numeric fields (form posts strings).
    for k in ("cpus", "gpus", "walltime"):
        if k in data and not isinstance(data[k], int):
            data[k] = int(data[k])
    cfg = Config(**data)
    await engine.call(engine.engine.save_config, cfg)
    return {"ok": True}


@app.post("/api/config/test")
async def test_config(body: dict) -> dict:
    """Test an SSH connection from the submitted form (does not save)."""
    from hpc_helper.config import Config

    data = {k: body[k] for k in (
        "host", "user", "remote_home", "conda_env", "account",
        "partition", "qos", "cpus", "gpus", "walltime",
    ) if k in body}
    for k in ("cpus", "gpus", "walltime"):
        if k in data and not isinstance(data[k], int):
            data[k] = int(data[k])
    cfg = Config(**data)
    # Raises AuthError (-> 400 with kind=auth) on failure; success returns green.
    await engine.call(engine.engine.test_connection, cfg)
    return {"ok": True}


# ── node up / down ────────────────────────────────────────────────────────────


@app.get("/api/node/up")
async def node_up() -> "StreamingResponse":
    """Allocate a GPU node, streaming progress lines as SSE.

    Events: ``status`` (a human progress string), ``done`` (final JobInfo),
    ``error`` (engine error message). The browser shows "waiting for a free
    node…" while polling instead of the request hanging silently.
    """
    import hpc_helper.api as e

    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_running_loop()

    def _run() -> None:
        def on_status(msg: str) -> None:
            loop.call_soon_threadsafe(queue.put_nowait, ("status", msg))
        try:
            info = e.up(on_status=on_status)
            loop.call_soon_threadsafe(queue.put_nowait, ("done", {
                "job_id": info.job_id, "node": info.node, "state": info.state,
            }))
        except e.EngineError as exc:
            loop.call_soon_threadsafe(queue.put_nowait, ("error", str(exc)))
        except Exception as exc:  # pragma: no cover - defensive
            loop.call_soon_threadsafe(queue.put_nowait, ("error", str(exc)))
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, ("_close", None))

    import threading
    threading.Thread(target=_run, daemon=True).start()

    async def event_gen():
        while True:
            kind, payload = await queue.get()
            if kind == "_close":
                break
            yield f"event: {kind}\ndata: {_sse_data(payload)}\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")


def _sse_data(payload) -> str:
    import json
    return json.dumps(payload, ensure_ascii=False)


@app.post("/api/node/down")
async def node_down() -> dict:
    """Release the active node."""
    await engine.call(engine.engine.down)
    return {"ok": True}


# ── project: browse / scan / push ─────────────────────────────────────────────


@app.get("/api/project/browse")
async def project_browse(path: str = "") -> dict:
    """List subdirectories of a path, for the folder picker.

    Constrained to absolute paths so the UI can show a simple browser. Hidden
    dirs (starting with .) are hidden to reduce noise.
    """
    import os
    from pathlib import Path

    base = Path(path).expanduser() if path else Path.home()
    base = base.resolve()
    if not base.is_dir():
        return {"path": str(base), "dirs": [], "error": "not a directory"}
    dirs = []
    try:
        for entry in sorted(base.iterdir(), key=lambda p: p.name.lower()):
            if entry.is_dir() and not entry.name.startswith("."):
                dirs.append(entry.name)
    except PermissionError:
        return {"path": str(base), "dirs": [], "error": "permission denied"}
    return {"path": str(base), "parent": str(base.parent), "dirs": dirs}


@app.post("/api/project/scan")
async def project_scan(body: dict) -> dict:
    """Scan a local project folder: list .py files + total file count."""
    py_files, total = await engine.call(engine.engine.scan_project, body["path"])
    plan = await engine.call(engine.engine.plan_push, body["path"])
    return {
        "path": body["path"],
        "name": Path(body["path"]).name,
        "python_files": py_files,
        "total_files": total,
        "changed_files": plan.changed_files,
        "remote_project": plan.remote_project,
    }


@app.post("/api/project/push")
async def project_push(body: dict) -> dict:
    """Sync the project to the cluster (incremental). Returns what transferred."""
    result = await engine.call(
        engine.engine.push,
        body["path"],
        body.get("remote_subpath"),
        body.get("full", False),
    )
    return {
        "remote_project": result.remote_project,
        "transferred": result.transferred,
        "skipped": result.skipped,
    }


# ── run: launch / stream / stop ───────────────────────────────────────────────
#
# A single active run at a time (MVP). The RunHandle is kept module-global so
# the SSE stream and the stop button share it. Output lines are buffered into
# an asyncio.Queue so a reconnecting client misses only the gap.

_ACTIVE_RUN: dict = {}  # {"handle": RunHandle, "queue": asyncio.Queue, "done": bool}


@app.post("/api/run")
async def run_start(body: dict) -> dict:
    """Launch a script on the active GPU node. Returns the remote command."""
    import hpc_helper.api as e

    if _ACTIVE_RUN.get("handle") is not None and not _ACTIVE_RUN.get("done"):
        raise engine.AllocError("A run is already active. Stop it first.")

    # Clear any previous (finished) run before starting a new one.
    _ACTIVE_RUN.clear()

    script = body.get("script")
    args = body.get("args") or []
    raw = body.get("raw")
    handle = await engine.call(
        e.start_run, script=script, args=args, raw=raw,
        conda_env=body.get("conda_env"), no_conda=body.get("no_conda", False),
    )

    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_running_loop()
    _ACTIVE_RUN.update({"handle": handle, "queue": queue, "done": False})

    def _pump() -> None:
        try:
            for line in handle.stream():
                loop.call_soon_threadsafe(queue.put_nowait, ("line", line))
        finally:
            rc = handle.returncode
            loop.call_soon_threadsafe(queue.put_nowait, ("exit", rc))
            loop.call_soon_threadsafe(queue.put_nowait, ("_close", None))
            # Mark done server-side regardless of whether a client is reading,
            # so a new run can start after the process exits.
            loop.call_soon_threadsafe(lambda: _ACTIVE_RUN.update({"done": True}))

    import threading
    threading.Thread(target=_pump, daemon=True).start()
    return {"command": handle.command, "job_id": handle.job_id}


@app.get("/api/run/stream")
async def run_stream() -> "StreamingResponse":
    """SSE stream of the active run's output (lines) + a final exit code."""
    if not _ACTIVE_RUN.get("handle"):
        return JSONResponse(status_code=409, content={"kind": "run", "message": "No active run."})

    # Each client gets its own view of the queue by snapshotting then tailing.
    # Simplest correct approach for MVP: a shared queue drained by one reader.
    # Since the UI keeps a single tab open, we read the shared queue.
    queue: asyncio.Queue = _ACTIVE_RUN["queue"]

    async def event_gen():
        # If the run already finished, we still want to flush queued lines.
        while True:
            try:
                kind, payload = await asyncio.wait_for(queue.get(), timeout=0.1)
            except asyncio.TimeoutError:
                if _ACTIVE_RUN.get("done"):
                    break
                continue
            if kind == "_close":
                _ACTIVE_RUN["done"] = True
                break
            if kind == "exit":
                _ACTIVE_RUN["done"] = True
                yield f"event: exit\ndata: {payload}\n\n"
            else:
                yield f"event: line\ndata: {_sse_line(payload)}\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")


def _sse_line(text: str) -> str:
    import json
    return json.dumps(text, ensure_ascii=False)


@app.post("/api/run/stop")
async def run_stop() -> dict:
    """Stop the active run."""
    handle = _ACTIVE_RUN.get("handle")
    if handle is None:
        return {"ok": False, "message": "No active run."}
    await engine.call(handle.stop)
    _ACTIVE_RUN["done"] = True
    return {"ok": True}


# ── pull results ──────────────────────────────────────────────────────────────


@app.post("/api/pull")
async def pull_results(body: dict) -> dict:
    """Download results from the cluster into a local dir; returns that dir."""
    local_dest = await engine.call(
        engine.engine.pull,
        body.get("remote_subpath"),
        body.get("local_dest"),
        body.get("project_name"),
    )
    return {"local_dest": local_dest}


# ── static UI ─────────────────────────────────────────────────────────────────

app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")


# ── launcher ──────────────────────────────────────────────────────────────────


def main() -> None:
    """Entry point for the ``runbox`` console script."""
    import os
    import socket

    # Bind 0.0.0.0 so the web shell / container is reachable; on a laptop this
    # is still fine for a single-user local tool.
    host = os.environ.get("RUNBOX_HOST", "0.0.0.0")
    port = int(os.environ.get("RUNBOX_PORT", "8760"))
    url = f"http://{host}:{port}"
    print(f"107 RunBox starting on {url}  (transport: {TRANSPORT})  Ctrl+C to stop")
    # Try to open a browser; in a headless web shell this is a no-op.
    try:
        webbrowser.open(f"http://127.0.0.1:{port}")
    except Exception:
        pass
    uvicorn.run("runbox.app:app", host=host, port=port, reload=False)
