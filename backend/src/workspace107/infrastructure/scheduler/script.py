"""作业脚本渲染。

Mock 和 Slurm 两个适配器共用同一份脚本正文，区别只在于头部指令和提交方式。
把脚本单独渲染出来还有一个好处：用户可以直接看到「平台到底替我写了什么」。
"""

from __future__ import annotations

from ...domain.ports.scheduler import SchedulerSubmission


def render_body(submission: SchedulerSubmission) -> str:
    """先固定共享组写权限，再运行任何 setup 或用户命令。"""
    lines = ["set -euo pipefail", "umask 0007", ""]
    if submission.setup_command.strip():
        lines += [
            "# 运行环境准备命令",
            submission.setup_command.strip(),
            "",
        ]
    lines += ["# 运行方案中的执行命令", submission.command.strip(), ""]
    return "\n".join(lines)


def render_sbatch_script(submission: SchedulerSubmission) -> str:
    """渲染完整的 sbatch 脚本。

    环境变量不写进脚本——Secret 明文只通过进程环境传递，
    不落到任何可被读取的文件里（GR-304）。
    """
    config = submission.configuration
    header = [
        "#!/bin/bash",
        f"#SBATCH --job-name={_sanitize(submission.job_name)}",
        f"#SBATCH --comment={_correlation(submission.correlation)}",
        f"#SBATCH --account={config.account}",
        f"#SBATCH --partition={config.partition}",
        f"#SBATCH --qos={config.qos}",
        f"#SBATCH --nodes={config.nodes}",
        "#SBATCH --ntasks-per-node=1",
        f"#SBATCH --cpus-per-task={config.cpus}",
        f"#SBATCH --mem={config.memory_mb}M",
        f"#SBATCH --time={_minutes_to_walltime(config.time_limit_minutes)}",
        f"#SBATCH --chdir={submission.work_dir}",
        f"#SBATCH --output={submission.stdout_path}",
        f"#SBATCH --error={submission.stderr_path}",
    ]
    if config.gpus > 0:
        header.append(f"#SBATCH --gres=gpu:{config.gpus}")
    header.append("")
    return "\n".join(header) + render_body(submission)


def _minutes_to_walltime(minutes: int) -> str:
    hours, remainder = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    if days:
        return f"{days}-{hours:02d}:{remainder:02d}:00"
    return f"{hours:02d}:{remainder:02d}:00"


def _sanitize(name: str) -> str:
    cleaned = "".join(c if c.isalnum() or c in "-_." else "-" for c in name)
    return cleaned[:64] or "workspace107-run"


def _correlation(value: str) -> str:
    """Keep correlation exact while rejecting sbatch directive injection."""
    safe = all(
        character.isascii() and (character.isalnum() or character in "-_.:") for character in value
    )
    if not value or not safe:
        raise ValueError("correlation contains characters unsafe for an sbatch comment")
    return value
