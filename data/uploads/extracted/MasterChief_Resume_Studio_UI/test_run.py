import hashlib
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import run


class BootstrapTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = self.root / ".venv"
        self.requirements = self.root / "requirements.txt"
        self.requirements.write_text("example>=1\n", encoding="utf-8")
        self.marker = self.env / ".masterchief-requirements"
        for name, value in (
            ("BASE_DIR", self.root), ("ENV_DIR", self.env),
            ("REQUIREMENTS", self.requirements), ("MARKER", self.marker),
        ):
            patch = mock.patch.object(run, name, value)
            patch.start()
            self.addCleanup(patch.stop)

    def create_fake_environment(self, path, with_pip):
        self.assertTrue(with_pip)
        python = run.environment_python()
        python.parent.mkdir(parents=True)
        python.touch()

    def execute_fake(self, args, **kwargs):
        if "-c" in args:
            return subprocess.CompletedProcess(args, 0, stdout=str(self.env), stderr="")
        return subprocess.CompletedProcess(args, 0)

    def test_create_install_reuse_and_requirements_change(self):
        with mock.patch.object(run.venv, "create", side_effect=self.create_fake_environment) as create, \
                mock.patch.object(run.subprocess, "run", side_effect=self.execute_fake) as execute:
            python = run.prepare_environment()
            self.assertEqual(python, run.environment_python())
            create.assert_called_once_with(self.env, with_pip=True)
            self.assertEqual(self.marker.read_text().strip(), hashlib.sha256(self.requirements.read_bytes()).hexdigest())
            self.assertEqual(execute.call_count, 2)
            run.prepare_environment()
            self.assertEqual(execute.call_count, 3)
            self.requirements.write_text("example>=2\n", encoding="utf-8")
            run.prepare_environment()
            self.assertEqual(execute.call_count, 5)

    def test_failed_install_does_not_write_marker(self):
        def execute(args, **kwargs):
            if "-c" in args:
                return self.execute_fake(args, **kwargs)
            raise subprocess.CalledProcessError(1, args)
        with mock.patch.object(run.venv, "create", side_effect=self.create_fake_environment), \
                mock.patch.object(run.subprocess, "run", side_effect=execute):
            with self.assertRaises(subprocess.CalledProcessError):
                run.prepare_environment()
        self.assertFalse(self.marker.exists())

    def test_invalid_existing_environment_is_reported(self):
        self.env.mkdir()
        with self.assertRaisesRegex(RuntimeError, "Recreate .venv"):
            run.prepare_environment()

    def test_main_starts_uvicorn_from_app_directory(self):
        process = mock.Mock()
        process.wait.return_value = 0
        worker = mock.Mock()
        with mock.patch.object(run, "prepare_environment", return_value=Path("python")), \
                mock.patch.object(run.subprocess, "Popen", return_value=process) as popen, \
                mock.patch.object(run.threading, "Thread", return_value=worker) as thread:
            self.assertEqual(run.main(), 0)
        popen.assert_called_once_with(
            ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"],
            cwd=self.root,
        )
        thread.assert_called_once_with(target=run.open_when_ready, args=(process,), daemon=True)
        worker.start.assert_called_once()

    def test_ready_server_opens_local_browser(self):
        process = mock.Mock()
        process.poll.return_value = None
        connection = mock.MagicMock()
        with mock.patch.object(run.socket, "create_connection", return_value=connection), \
                mock.patch.object(run.webbrowser, "open", return_value=True) as browser:
            run.open_when_ready(process)
        browser.assert_called_once_with("http://127.0.0.1:8080/")


if __name__ == "__main__":
    unittest.main()
