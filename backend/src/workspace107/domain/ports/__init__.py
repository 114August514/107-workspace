"""领域端口。

application 层只依赖这里定义的协议，具体实现在 infrastructure 层。
这样调度系统、存储后端和数据库都可以替换，而不需要改动用例代码。
"""

from .clock import Clock
from .execution import ExecutionContextPort, ExecutionStore, RunInputUnavailable
from .run_workspace import (
    RunArtifactEvidence,
    RunWorkspace,
    RunWorkspaceConflict,
    RunWorkspaceError,
    RunWorkspaceIdentity,
    RunWorkspacePort,
    UnsafeRunWorkspacePath,
)
from .scheduler import (
    SchedulerCorrelationResult,
    SchedulerJobState,
    SchedulerPort,
    SchedulerState,
    SchedulerSubmission,
)
from .secret_vault import SecretVault
from .storage import StoragePort

__all__ = [
    "Clock",
    "ExecutionContextPort",
    "ExecutionStore",
    "RunArtifactEvidence",
    "RunInputUnavailable",
    "RunWorkspace",
    "RunWorkspaceConflict",
    "RunWorkspaceError",
    "RunWorkspaceIdentity",
    "RunWorkspacePort",
    "SchedulerCorrelationResult",
    "SchedulerJobState",
    "SchedulerPort",
    "SchedulerState",
    "SchedulerSubmission",
    "SecretVault",
    "StoragePort",
    "UnsafeRunWorkspacePath",
]
