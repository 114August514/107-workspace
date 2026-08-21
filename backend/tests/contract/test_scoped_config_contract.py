import json
from pathlib import Path


def test_scoped_config_routes_are_explicit_and_secret_safe() -> None:
    document = json.loads(Path("../contracts/openapi.json").read_text())
    paths = document["paths"]
    ids = {"users": "user_id", "user-groups": "user_group_id", "projects": "project_id"}
    for owner, identifier in ids.items():
        variable_path = f"/api/v1/{owner}/{{{identifier}}}/variables"
        secret_path = f"/api/v1/{owner}/{{{identifier}}}/secrets"
        assert variable_path in paths
        assert secret_path in paths
        assert "value" not in json.dumps(paths[secret_path])
    assert not any(path.startswith("/api/v1/config/") for path in paths)
