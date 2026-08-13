from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS_ROOT))

import workspace  # noqa: E402
from tasks import check as quality  # noqa: E402
from tasks import common, contract, project  # noqa: E402
from tasks.common import REPO_ROOT, TaskError  # noqa: E402


class WorkspaceCliTests(unittest.TestCase):
    def test_check_defaults_to_all(self) -> None:
        with mock.patch.object(workspace.quality, "run_check") as run_check:
            result = workspace.main(["check"])

        self.assertEqual(result, 0)
        run_check.assert_called_once_with("all")

    def test_frontend_check_target_is_forwarded(self) -> None:
        with mock.patch.object(workspace.quality, "run_check") as run_check:
            result = workspace.main(["check", "frontend"])

        self.assertEqual(result, 0)
        run_check.assert_called_once_with("frontend")

    def test_frontend_tests_pass_run_without_an_extra_separator(self) -> None:
        with (
            mock.patch.object(quality, "_prepare"),
            mock.patch.object(quality, "frontend_pnpm") as frontend_pnpm,
        ):
            quality.test("frontend")

        frontend_pnpm.assert_called_once_with("run", "test", "--run")

        with (
            mock.patch.object(quality, "_prepare"),
            mock.patch.object(quality, "frontend_pnpm") as frontend_pnpm,
        ):
            quality.run_check("frontend")

        self.assertIn(mock.call("run", "test", "--run"), frontend_pnpm.call_args_list)
        self.assertNotIn(mock.call("run", "test", "--", "--run"), frontend_pnpm.call_args_list)

    def test_contract_check_target_is_forwarded(self) -> None:
        with mock.patch.object(workspace.quality, "run_check") as run_check:
            result = workspace.main(["check", "contract"])

        self.assertEqual(result, 0)
        run_check.assert_called_once_with("contract")

    def test_contract_artifacts_have_explicit_owners(self) -> None:
        self.assertEqual(contract.OPENAPI_PATH, REPO_ROOT / "contracts" / "openapi.json")
        self.assertEqual(
            contract.SCHEMA_PATH,
            REPO_ROOT / "frontend" / "src" / "api" / "schema.d.ts",
        )

    def test_task_error_becomes_stable_exit_code(self) -> None:
        error = TaskError("expected failure", exit_code=7)
        stderr = io.StringIO()
        with (
            mock.patch.object(workspace.quality, "run_check", side_effect=error),
            contextlib.redirect_stderr(stderr),
        ):
            result = workspace.main(["check"])

        self.assertEqual(result, 7)
        self.assertIn("expected failure", stderr.getvalue())

    def test_contract_check_refuses_missing_generated_file(self) -> None:
        missing = REPO_ROOT / "does-not-exist" / "openapi.json"
        with (
            mock.patch.object(contract, "OPENAPI_PATH", missing),
            self.assertRaisesRegex(TaskError, "Missing generated contract"),
        ):
            contract.check_contract()

    def test_contract_comparison_normalizes_windows_line_endings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            lf = Path(directory) / "lf.txt"
            crlf = Path(directory) / "crlf.txt"
            lf.write_bytes(b'{"ok": true}\n')
            crlf.write_bytes(b'{"ok": true}\r\n')

            self.assertEqual(contract._normalized_text(lf), contract._normalized_text(crlf))

    def test_tool_version_parser_accepts_node_and_pnpm_versions(self) -> None:
        self.assertEqual(common._major_version("v24.18.0"), 24)
        self.assertEqual(common._major_version("11.3.0"), 11)

    def test_tool_version_parser_rejects_unexpected_output(self) -> None:
        with self.assertRaisesRegex(TaskError, "Could not parse tool version"):
            common._major_version("unknown")

    def test_backend_python_executable_is_resolved_by_uv(self) -> None:
        expected = r"C:\workspace\backend\.venv\Scripts\python.exe"
        with mock.patch.object(project, "backend_uv") as backend_uv:
            backend_uv.return_value.stdout = f"{expected}\n"
            executable = project._backend_python_executable()

        self.assertEqual(executable, expected)
        backend_uv.assert_called_once_with(
            "run",
            "--no-sync",
            "python",
            "-c",
            "import sys; print(sys.executable)",
            capture=True,
            quiet=True,
        )

    def test_demo_command_quotes_posix_python_paths(self) -> None:
        self.assertEqual(
            project._demo_command(r"C:\workspace\backend\.venv\Scripts\python.exe"),
            r"'C:\workspace\backend\.venv\Scripts\python.exe' train.py",
        )

    def test_demo_command_quotes_windows_python_paths(self) -> None:
        with mock.patch.object(project.os, "name", "nt"):
            self.assertEqual(
                project._demo_command(r"C:\Program Files\Python\python.exe"),
                r'"C:\Program Files\Python\python.exe" train.py',
            )

    def test_smoke_dispatches_the_isolated_demo(self) -> None:
        with mock.patch.object(project, "demo") as demo:
            result = workspace.main(["smoke"])

        self.assertEqual(result, 0)
        demo.assert_called_once_with(smoke=True)

    def test_backend_dev_reload_only_watches_source(self) -> None:
        process = mock.Mock()
        process.poll.return_value = 0
        with (
            mock.patch.object(project, "ensure_backend_dependencies"),
            mock.patch.object(project, "_backend_python_executable", return_value="python"),
            mock.patch.object(project.subprocess, "Popen", return_value=process) as popen,
        ):
            project.run_dev("backend")

        command = popen.call_args.args[0]
        self.assertIn("--reload-dir", command)
        self.assertEqual(command[command.index("--reload-dir") + 1], "src")

    def test_coverage_reports_without_a_global_gate(self) -> None:
        with (
            mock.patch.object(project, "ensure_backend_dependencies"),
            mock.patch.object(project, "backend_uv") as backend_uv,
        ):
            project.coverage()

        arguments = backend_uv.call_args.args
        self.assertEqual(arguments[:2], ("run", "pytest"))
        self.assertIn("--cov=workspace107", arguments)
        self.assertFalse(any(str(value).startswith("--cov-fail-under") for value in arguments))

    def test_compose_uses_deploy_manifest(self) -> None:
        with (
            mock.patch.object(project, "require_commands") as require_commands,
            mock.patch.object(project, "run") as run,
        ):
            project.compose("config")

        require_commands.assert_called_once_with("docker")
        run.assert_called_once_with(
            [
                "docker",
                "compose",
                "--project-directory",
                REPO_ROOT,
                "--file",
                REPO_ROOT / "deploy" / "compose.yaml",
                "config",
            ]
        )

    def test_journal_listing_ignores_directory_readme(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            journal_dir = Path(directory) / "docs" / "journal"
            journal_dir.mkdir(parents=True)
            (journal_dir / "README.md").write_text("# Journal index\n", encoding="utf-8")
            stdout = io.StringIO()

            with (
                mock.patch.object(project, "REPO_ROOT", Path(directory)),
                contextlib.redirect_stdout(stdout),
            ):
                project.journal()

        self.assertIn("No journal entries.", stdout.getvalue())
        self.assertNotIn("Journal index", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
