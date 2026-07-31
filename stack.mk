# The Makefile contains no task logic. This is the single command it forwards to.
# Override from the environment only when uv itself has a non-standard location.
UV ?= uv
WORKSPACE_CLI ?= $(UV) run --no-project python scripts/workspace.py
