$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../../..")).Path
Set-Location $RepoRoot

foreach ($Command in @("uv", "node", "pnpm")) {
    if (-not (Get-Command $Command -ErrorAction SilentlyContinue)) {
        throw "Missing required command: $Command"
    }
}

& uv run --no-project python scripts/workspace.py setup
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
