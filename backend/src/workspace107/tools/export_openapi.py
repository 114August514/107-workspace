"""导出 OpenAPI Contract。

    uv run python -m workspace107.tools.export_openapi ../docs/api/openapi.json

CI 会重新生成并检查是否存在未提交差异，所以改了 DTO 或路由之后
必须执行 ``scripts/sync-api-contract.sh`` 并提交结果。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from ..config import Settings
from ..main import create_app


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("用法: python -m workspace107.tools.export_openapi <输出路径>", file=sys.stderr)
        return 2

    output = Path(argv[1])
    output.parent.mkdir(parents=True, exist_ok=True)

    # 导出只需要路由和 schema，不连接数据库和调度系统。
    app = create_app(Settings(env="export", run_sync_interval_seconds=0))
    schema = app.openapi()

    output.write_text(
        json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
