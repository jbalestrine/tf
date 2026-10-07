import time

from flask import Flask
import yaml

from managers.pipeline import register_pipeline_module


def _build_pipeline_app(tmp_path):
    app = Flask(__name__)
    manager = register_pipeline_module(
        app,
        db_path=tmp_path / "pipelines.json",
        runs_path=tmp_path / "pipeline_runs.json",
    )
    return app.test_client(), manager


def _wait_for_status(manager, run_id, expected_status, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        run = manager.get_run(run_id)
        if run["status"] == expected_status:
            return run
        time.sleep(0.01)
    raise AssertionError(f"Run {run_id} did not reach status {expected_status!r}.")


def test_terraform_apply_waits_for_explicit_approval(tmp_path):
    client, manager = _build_pipeline_app(tmp_path)
    pipeline = manager.create_pipeline("Protected deployment")
    manager.update_pipeline(pipeline["id"], {
        "stages": [{
            "name": "Deploy",
            "steps": [{
                "name": "Apply infrastructure",
                "type": "terraform_apply",
                "config": {"working_dir": str(tmp_path)},
            }],
        }],
    })

    run = manager.execute_pipeline(pipeline["id"])
    waiting = _wait_for_status(manager, run["id"], "waiting_for_approval")
    assert waiting["stages"][0]["status"] == "waiting_for_approval"
    assert waiting["stages"][0]["steps"] == []

    response = client.post(
        f"/api/pipelines/runs/{run['id']}/approval",
        json={"decision": "rejected", "comment": "Do not deploy in this test."},
    )

    assert response.status_code == 200
    failed = _wait_for_status(manager, run["id"], "failed")
    assert failed["approval"]["decision"] == "rejected"
    assert failed["stages"][0]["steps"] == []


def test_yaml_pipeline_import_export_round_trip(tmp_path):
    client, _manager = _build_pipeline_app(tmp_path)
    imported = client.post(
        "/api/pipelines/import-yaml",
        json={
            "yaml": """
name: Build and test
description: Validate the application before release.
stages:
  - name: Build
    parallel: false
    steps:
      - name: Unit tests
        type: test_run
        config:
          test_command: pytest -q
          working_dir: .
""",
        },
    )

    assert imported.status_code == 200
    pipeline = imported.get_json()["result"]
    exported = client.get(f"/api/pipelines/{pipeline['id']}/export.yaml")

    assert exported.status_code == 200
    definition = yaml.safe_load(exported.get_data(as_text=True))
    assert definition["name"] == "Build and test"
    assert definition["stages"][0]["steps"][0]["config"]["test_command"] == "pytest -q"


def test_yaml_import_rejects_unsupported_step_types(tmp_path):
    client, _manager = _build_pipeline_app(tmp_path)

    response = client.post(
        "/api/pipelines/import-yaml",
        json={
            "yaml": """
name: Invalid
stages:
  - name: Build
    steps:
      - name: Unknown task
        type: arbitrary_shell
""",
        },
    )

    assert response.status_code == 400
    assert "Unsupported step type" in response.get_json()["error"]
