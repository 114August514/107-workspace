# Repository workflow

`workspace.py` is the only task implementation. `Makefile` is a thin convenience wrapper;
contributors who do not have Make, including native Windows users, run the CLI directly:

```powershell
uv run --no-project python scripts/workspace.py check
```

The frontend toolchain is Node.js 24 LTS with pnpm 11. The checked-in
`frontend/pnpm-lock.yaml` is the only frontend dependency lock file. The adjacent
`pnpm-workspace.yaml` allows only esbuild's required install script.

The main commands are:

```text
setup                 install locked backend and frontend dependencies
check [target]        run format, lint, type, test, build, and contract checks
contract sync|check   regenerate or verify OpenAPI and frontend types
dev                    start backend and frontend development servers
demo / smoke           exercise an isolated Project-to-Artifact workflow
migrate / migrate-down apply or roll back one database revision
journal / audit        expose work in progress and review-sensitive changes
doctor                 inspect the local engineering baseline
```

`target` can be `all`, `backend`, `frontend`, or, for `check`, `contract`.

The task implementation is organized by responsibility:

```text
scripts/
├── workspace.py
├── tasks/
│   ├── common.py
│   ├── check.py
│   ├── contract.py
│   └── project.py
└── platform/
    ├── windows/bootstrap.ps1
    └── posix/bootstrap.sh
```

Platform bootstrap files only validate prerequisites and enter the common Python workflow. No
quality, contract, migration, or demo behavior is duplicated in shell or PowerShell.

The common CLI avoids platform-specific task logic. CI exercises the Make-free command on Windows
so the portable entry point cannot silently regress; real Windows behavior is reported from that
runner rather than inferred from a Linux host.
