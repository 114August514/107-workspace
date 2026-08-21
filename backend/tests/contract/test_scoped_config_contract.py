import json
from pathlib import Path


def test_scoped_config_routes_are_explicit_and_secret_safe() -> None:
    document = json.loads(Path("../contracts/openapi.json").read_text())
    paths = document["paths"]
    for owner in ("users", "user-groups", "projects"):
        assert f"/api/v1/{owner}/{{{'user_id' if owner == 'users' else 'user_group_id' if owner == 'user-groups' else 'project_id'}}}/variables" in paths
        secret_path = f"/api/v1/{owner}/{{{'user_id' if owner == 'users' else 'user_group_id' if owner == 'user-groups' else 'project_id'}}}/secrets"
        assert secret_path in paths
        assert "value" not in json.dumps(paths[secret_path])
    assert not any(path.startswith("/api/v1/config/") for path in paths)
