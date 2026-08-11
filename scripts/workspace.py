#!/usr/bin/env python3
"""Cross-platform repository workflow entry point.

Run directly on every supported development platform:

    uv run --no-project python scripts/workspace.py check
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable

from tasks import check as quality
from tasks import contract, project
from tasks.common import TaskError

TARGETS = ("all", "backend", "frontend", "contract")
CODE_TARGETS = ("all", "backend", "frontend")


def _target_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    name: str,
    help_text: str,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(name, help=help_text)
    parser.add_argument("target", nargs="?", choices=CODE_TARGETS, default="all")
    return parser


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="107 Workspace development, verification, contract, and demo tasks."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    _target_parser(subparsers, "setup", "install locked backend/frontend dependencies")
    _target_parser(subparsers, "fmt", "format backend/frontend source")
    _target_parser(subparsers, "fmt-check", "check formatting without changing files")
    _target_parser(subparsers, "lint", "run static lint checks")
    _target_parser(subparsers, "typecheck", "run configured type checks")
    _target_parser(subparsers, "test", "run backend/frontend tests")
    _target_parser(subparsers, "build", "build backend/frontend artifacts")

    check_parser = subparsers.add_parser("check", help="run the canonical repository checks")
    check_parser.add_argument("target", nargs="?", choices=TARGETS, default="all")

    dev_parser = subparsers.add_parser("dev", help="start local development servers")
    dev_parser.add_argument("component", nargs="?", choices=CODE_TARGETS, default="all")

    subparsers.add_parser("migrate", help="upgrade the database to the latest revision")
    subparsers.add_parser("migrate-down", help="downgrade the database by one revision")
    subparsers.add_parser("coverage", help="report backend test coverage without a global gate")
    subparsers.add_parser("demo", help="run the isolated core Run demonstration")
    smoke_parser = subparsers.add_parser("smoke", help="run the HTTP core Run smoke test")
    smoke_parser.add_argument(
        "--base-url",
        help="exercise an already-running API stack instead of starting an isolated stack",
    )
    subparsers.add_parser("ship", help="deploy the application when a production target exists")
    subparsers.add_parser("hooks", help="enable repository-owned Git hooks for this clone")
    subparsers.add_parser("doctor", help="inspect the local engineering baseline")
    subparsers.add_parser("review", help="report whole-repository milestone review signals")

    contract_parser = subparsers.add_parser("contract", help="manage generated API contracts")
    contract_parser.add_argument("action", choices=("sync", "check"), nargs="?", default="sync")

    compose_parser = subparsers.add_parser("compose", help="operate the local Compose topology")
    compose_parser.add_argument("action", choices=("config", "build", "up", "down"))

    audit_parser = subparsers.add_parser("audit", help="report incremental human-review gates")
    audit_parser.add_argument("--base")
    audit_parser.add_argument("--max-lines", type=int, default=400)

    journal_parser = subparsers.add_parser("journal", help="inspect or create work journal entries")
    journal_parser.add_argument("--all", action="store_true", dest="include_all")
    journal_parser.add_argument("--new", metavar="SLUG")
    journal_parser.add_argument("--context", default="未指定")
    return parser


def dispatch(args: argparse.Namespace) -> None:
    target_commands: dict[str, Callable[[str], None]] = {
        "setup": quality.setup,
        "fmt": quality.format_code,
        "fmt-check": lambda target: quality.format_code(target, check_only=True),
        "lint": quality.lint,
        "typecheck": quality.typecheck,
        "test": quality.test,
        "build": quality.build,
        "check": quality.run_check,
    }
    if args.command in target_commands:
        target_commands[args.command](args.target)
    elif args.command == "dev":
        project.run_dev(args.component)
    elif args.command == "migrate":
        project.migrate("up")
    elif args.command == "migrate-down":
        project.migrate("down")
    elif args.command == "coverage":
        project.coverage()
    elif args.command == "demo":
        project.demo()
    elif args.command == "smoke":
        if args.base_url is None:
            project.demo(smoke=True)
        else:
            project.external_smoke(args.base_url)
    elif args.command == "ship":
        project.ship()
    elif args.command == "hooks":
        project.install_hooks()
    elif args.command == "doctor":
        project.doctor()
    elif args.command == "review":
        project.review()
    elif args.command == "audit":
        project.audit(base=args.base, max_lines=args.max_lines)
    elif args.command == "journal":
        project.journal(include_all=args.include_all, new_slug=args.new, context=args.context)
    elif args.command == "contract":
        contract.sync_contract() if args.action == "sync" else contract.check_contract()
    elif args.command == "compose":
        project.compose(args.action)
    else:  # pragma: no cover - argparse guarantees the command set
        raise AssertionError(f"Unhandled command: {args.command}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        dispatch(args)
    except TaskError as error:
        print(f"error: {error}", file=sys.stderr)
        return error.exit_code
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
