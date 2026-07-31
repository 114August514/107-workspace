"""调度适配器。"""

from .mock import MockScheduler
from .slurm import SlurmRestScheduler

__all__ = ["MockScheduler", "SlurmRestScheduler"]
