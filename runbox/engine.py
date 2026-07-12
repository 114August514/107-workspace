"""Async-friendly wrapper over the synchronous ``hpc_helper.api`` engine.

The engine is pure blocking SSH/subprocess calls. FastAPI runs on an event
loop, so every call is shipped to a worker thread via ``anyio.to_thread``.
This module is the *only* place that knows about the engine; the route
handlers depend on it, not on ``hpc_helper`` directly.

Errors raised by the engine (``EngineError`` subclasses) carry a ``kind``
that maps to a friendly category the frontend can translate.
"""
from __future__ import annotations

from typing import Any, Callable, List, Optional

import anyio

import hpc_helper.api as engine
from hpc_helper.api import (
    AllocError,
    AuthError,
    ConfigError,
    EngineError,
    SyncError,
)

# Re-export the error types so the web layer imports everything from here.
__all__ = [
    "EngineError",
    "ConfigError",
    "AuthError",
    "AllocError",
    "SyncError",
    "call",
    "engine",
]


async def call(func: Callable[..., Any], *args, **kwargs) -> Any:
    """Run a blocking engine function in a worker thread and await it.

    Use this for every engine call from a route handler so the event loop
    (and thus SSE streaming for other clients) never blocks on SSH.
    """
    return await anyio.to_thread.run_sync(lambda: func(*args, **kwargs))
