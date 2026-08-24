"""对象标识生成。

标识带类型前缀，便于在日志、URL 和排障过程中一眼看出对象类型。
"""

from __future__ import annotations

from uuid import uuid4

USER = "usr"
USER_GROUP = "grp"
LEGACY_WORKSPACE = "ws"
MEMBERSHIP = "mbr"
PROJECT = "prj"
PROJECT_VERSION = "pv"
RUN_CONFIGURATION = "rc"
RUN = "run"
RUN_SNAPSHOT = "snap"
ARTIFACT = "art"
ENVIRONMENT = "env"
ENVIRONMENT_VERSION = "ev"
COMPUTE_PLAN = "plan"
ENTITLEMENT = "ent"
EVENT = "evt"
ACTIVITY = "act"
NOTIFICATION = "ntf"
FORK_RELATION = "fork"
SHARED_RESOURCE = "shr"
SHARED_RESOURCE_VERSION = "shrv"
GRANT = "gnt"


def new_id(prefix: str) -> str:
    """生成形如 ``prj_9f2c...`` 的对象标识。"""
    return f"{prefix}_{uuid4().hex[:20]}"
