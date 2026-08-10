"""领域端口。

application 层只依赖这里定义的协议，具体实现在 infrastructure 层。
这样调度系统、存储后端和数据库都可以替换，而不需要改动用例代码。
"""

from .clock import Clock
from .scheduler import (
    SchedulerCorrelatedJob,
    SchedulerCorrelationResult,
    SchedulerJobState,
    SchedulerPort,
    SchedulerState,
    SchedulerSubmission,
)
from .secret_vault import SecretVault
from .storage import ArtifactContent, RunPaths, StoragePort

__all__ = [
    "ArtifactContent",
    "Clock",
    "RunPaths",
    "SchedulerCorrelatedJob",
    "SchedulerCorrelationResult",
    "SchedulerJobState",
    "SchedulerPort",
    "SchedulerState",
    "SchedulerSubmission",
    "SecretVault",
    "StoragePort",
]
