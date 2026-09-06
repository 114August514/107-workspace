from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS_ROOT))

from tasks import project  # noqa: E402
from tasks.common import TaskError  # noqa: E402
from tasks.dotenv_file import apply_auth_env_aliases, parse_env_file  # noqa: E402


class DotenvFileTests(unittest.TestCase):
    def test_parse_env_file_strips_quotes_and_comments(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text(
                "# comment\n"
                "export WORKSPACE107_AUTH_MODE=ustc\n"
                "WORKSPACE107_AUTH_SECRET_KEY='s3cret'\n"
                "EMPTY=\n",
                encoding="utf-8",
            )
            values = parse_env_file(path)

        self.assertEqual(values["WORKSPACE107_AUTH_MODE"], "ustc")
        self.assertEqual(values["WORKSPACE107_AUTH_SECRET_KEY"], "s3cret")
        self.assertEqual(values["EMPTY"], "")

    def test_apply_auth_env_aliases_fills_flask_names(self) -> None:
        merged = apply_auth_env_aliases(
            {
                "WORKSPACE107_AUTH_SECRET_KEY": "from-prefix",
                "WORKSPACE107_PUBLIC_ORIGIN": "http://127.0.0.1:5174",
            }
        )
        self.assertEqual(merged["SECRET_KEY"], "from-prefix")
        self.assertEqual(merged["PUBLIC_ORIGIN"], "http://127.0.0.1:5174")


class DevLoginStackTests(unittest.TestCase):
    def test_ustc_without_secret_fails(self) -> None:
        env = {"WORKSPACE107_AUTH_MODE": "ustc", "PATH": os.environ.get("PATH", "")}
        with (
            mock.patch.object(project, "load_local_env_files", return_value={}),
            mock.patch.dict(os.environ, env, clear=True),
            self.assertRaisesRegex(TaskError, "AUTH_SECRET_KEY"),
        ):
            project._prepare_dev_environment()

    def test_ustc_starts_auth_backend_and_vite(self) -> None:
        env = {
            "WORKSPACE107_AUTH_MODE": "ustc",
            "SECRET_KEY": "test-secret",
            "PUBLIC_ORIGIN": "http://127.0.0.1:5174",
            "PATH": os.environ.get("PATH", ""),
        }
        process = mock.Mock()
        process.poll.return_value = 0
        with (
            mock.patch.object(project, "load_local_env_files", return_value={}),
            mock.patch.object(project, "ensure_backend_dependencies"),
            mock.patch.object(project, "ensure_frontend_dependencies"),
            mock.patch.object(project, "_backend_python_executable", return_value="/py"),
            mock.patch.object(project, "resolve_executable", side_effect=lambda name: name),
            mock.patch.dict(os.environ, env, clear=True),
            mock.patch("subprocess.Popen", return_value=process) as popen,
        ):
            project.run_dev("all")

        commands = [call.args[0] for call in popen.call_args_list]
        self.assertEqual(len(commands), 3)
        self.assertIn("uvicorn", commands[0])
        self.assertIn("flask", commands[1])
        self.assertEqual(commands[2][:2], ["pnpm", "run"])
        self.assertIn("auth.auth_server:create_app", commands[1])
