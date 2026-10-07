from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
import json
import threading
import uuid

import yaml
from flask import jsonify, make_response, request
from werkzeug.utils import secure_filename
import subprocess


PIPELINE_RUNS = {}
PIPELINE_APPROVAL_EVENTS = {}
_ALLOWED_STEP_TYPES = {
    "script",
    "docker_build",
    "terraform_apply",
    "terraform_plan",
    "test_run",
    "deploy",
    "custom_command",
}

class PipelineManager:
    def __init__(self, db_path, runs_path):
        self.db_path = Path(db_path)
        self.runs_path = Path(runs_path)
        self._ensure_db()

    def _ensure_db(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        for p, default in [(self.db_path, {'pipelines': []}), (self.runs_path, {'runs': []})]:
            if not p.exists():
                p.write_text(json.dumps(default, indent=2), encoding='utf-8')

    def _load(self):
        try:
            return json.loads(self.db_path.read_text(encoding='utf-8'))
        except Exception:
            return {'pipelines': []}

    def _save(self, data):
        self.db_path.write_text(json.dumps(data, indent=2), encoding='utf-8')

    def _load_runs(self):
        try:
            return json.loads(self.runs_path.read_text(encoding='utf-8'))
        except Exception:
            return {'runs': []}

    def _save_runs(self, data):
        self.runs_path.write_text(json.dumps(data, indent=2), encoding='utf-8')

    def list_pipelines(self):
        return self._load().get('pipelines', [])

    def get_pipeline(self, pid):
        for p in self._load().get('pipelines', []):
            if p['id'] == pid:
                return p
        raise ValueError('Pipeline not found')

    def create_pipeline(self, name, description=''):
        d = self._load()
        pipeline = {
            'id': str(uuid.uuid4()), 'name': name, 'description': description,
            'stages': [], 'created': datetime.now().isoformat(),
            'updated': datetime.now().isoformat()
        }
        d.setdefault('pipelines', []).append(pipeline)
        self._save(d)
        return pipeline

    def import_pipeline(self, definition):
        if not isinstance(definition, dict):
            raise ValueError("Pipeline definition must be a YAML or JSON object.")
        name = definition.get("name")
        description = definition.get("description", "")
        stages = definition.get("stages", [])
        if not isinstance(name, str) or not name.strip() or len(name) > 120:
            raise ValueError("Pipeline name must contain 1 to 120 characters.")
        if not isinstance(description, str) or len(description) > 2000:
            raise ValueError("Pipeline description must be 2000 characters or fewer.")
        if not isinstance(stages, list) or len(stages) > 50:
            raise ValueError("Pipeline stages must be a list of at most 50 stages.")

        normalized_stages = []
        for stage_index, stage in enumerate(stages):
            if not isinstance(stage, dict):
                raise ValueError(f"Stage {stage_index + 1} must be an object.")
            stage_name = stage.get("name", f"Stage {stage_index + 1}")
            steps = stage.get("steps", [])
            if not isinstance(stage_name, str) or not stage_name.strip() or len(stage_name) > 120:
                raise ValueError(f"Stage {stage_index + 1} needs a name of 1 to 120 characters.")
            if not isinstance(steps, list) or len(steps) > 100:
                raise ValueError(f"Stage {stage_index + 1} must have at most 100 steps.")

            normalized_steps = []
            for step_index, step in enumerate(steps):
                if not isinstance(step, dict):
                    raise ValueError(f"Step {step_index + 1} in stage {stage_index + 1} must be an object.")
                step_type = step.get("type", "custom_command")
                step_name = step.get("name", f"Step {step_index + 1}")
                config = step.get("config", {})
                if not isinstance(step_type, str) or step_type not in _ALLOWED_STEP_TYPES:
                    raise ValueError(f"Unsupported step type in stage {stage_index + 1}: {step_type}.")
                if not isinstance(step_name, str) or not step_name.strip() or len(step_name) > 120:
                    raise ValueError(f"Step {step_index + 1} in stage {stage_index + 1} needs a valid name.")
                if not isinstance(config, dict):
                    raise ValueError(f"Step {step_index + 1} in stage {stage_index + 1} config must be an object.")
                normalized_steps.append({
                    "id": str(uuid.uuid4()),
                    "name": step_name.strip(),
                    "type": step_type,
                    "config": config,
                })

            normalized_stages.append({
                "id": str(uuid.uuid4()),
                "name": stage_name.strip(),
                "order": stage_index,
                "parallel": bool(stage.get("parallel", False)),
                "approval_required": bool(stage.get("approval_required", False)),
                "steps": normalized_steps,
            })

        pipeline = self.create_pipeline(name.strip(), description)
        return self.update_pipeline(pipeline["id"], {"stages": normalized_stages})

    def update_pipeline(self, pid, updates):
        d = self._load()
        for p in d.get('pipelines', []):
            if p['id'] == pid:
                for k, v in updates.items():
                    if k not in ('id', 'created'):
                        p[k] = v
                p['updated'] = datetime.now().isoformat()
                self._save(d)
                return p
        raise ValueError('Pipeline not found')

    def delete_pipeline(self, pid):
        d = self._load()
        d['pipelines'] = [p for p in d.get('pipelines', []) if p['id'] != pid]
        self._save(d)

    def execute_pipeline(self, pid):
        pipeline = self.get_pipeline(pid)
        run = {
            'id': str(uuid.uuid4()), 'pipeline_id': pid,
            'pipeline_name': pipeline['name'], 'status': 'running',
            'started': datetime.now().isoformat(), 'finished': None,
            'stages': [], 'log': []
        }
        PIPELINE_RUNS[run['id']] = run
        t = threading.Thread(target=self._run_pipeline, args=(run, pipeline), daemon=True)
        t.start()
        return run

    def _run_pipeline(self, run, pipeline):
        try:
            for stage in sorted(pipeline.get('stages', []), key=lambda s: s.get('order', 0)):
                if run.get("status") == "cancelled":
                    self._persist_run(run)
                    return
                stage_name = stage.get("name", "Stage")
                stage_id = stage.get("id") or str(uuid.uuid4())
                stage_run = {
                    'stage_id': stage_id, 'name': stage_name,
                    'status': 'pending', 'started': None,
                    'finished': None, 'steps': []
                }
                run['stages'].append(stage_run)
                run['log'].append(f"[{datetime.now().isoformat()}] Starting stage: {stage_name}")
                steps = stage.get('steps', [])
                requires_approval = stage.get("approval_required") or any(
                    step.get("type") == "terraform_apply" for step in steps
                )
                if requires_approval:
                    approval_event = threading.Event()
                    PIPELINE_APPROVAL_EVENTS[run["id"]] = approval_event
                    stage_run["status"] = "waiting_for_approval"
                    run["status"] = "waiting_for_approval"
                    run["approval"] = {
                        "stage_id": stage_id,
                        "stage_name": stage_name,
                        "decision": None,
                        "requested_at": datetime.now().isoformat(),
                    }
                    run["log"].append(
                        f"[{datetime.now().isoformat()}] Approval required before stage: {stage_name}"
                    )
                    self._persist_run(run)
                    if not approval_event.wait(timeout=24 * 60 * 60):
                        run["approval"]["decision"] = "timed_out"
                    PIPELINE_APPROVAL_EVENTS.pop(run["id"], None)
                    if run.get("status") == "cancelled":
                        self._persist_run(run)
                        return
                    if run["approval"].get("decision") != "approved":
                        stage_run["status"] = "failed"
                        stage_run["finished"] = datetime.now().isoformat()
                        run["status"] = "failed"
                        run["finished"] = datetime.now().isoformat()
                        run["log"].append(
                            f"[{datetime.now().isoformat()}] Approval was not granted for stage: {stage_name}"
                        )
                        self._persist_run(run)
                        return

                stage_run["status"] = "running"
                stage_run["started"] = datetime.now().isoformat()
                run["status"] = "running"
                if stage.get("parallel") and len(steps) > 1:
                    with ThreadPoolExecutor(max_workers=min(len(steps), 8)) as executor:
                        step_runs = list(executor.map(lambda step: self._execute_step(step, run), steps))
                else:
                    step_runs = [self._execute_step(step, run) for step in steps]

                stage_run["steps"].extend(step_runs)
                failed_step = next((step for step in step_runs if step["status"] == "failed"), None)
                if failed_step:
                    stage_run['status'] = 'failed'
                    stage_run['finished'] = datetime.now().isoformat()
                    run['status'] = 'failed'
                    run['finished'] = datetime.now().isoformat()
                    run['log'].append(f"[{datetime.now().isoformat()}] Pipeline FAILED at stage: {stage_name}")
                    self._persist_run(run)
                    return
                if run.get("status") == "cancelled":
                    stage_run["status"] = "cancelled"
                    stage_run["finished"] = datetime.now().isoformat()
                    self._persist_run(run)
                    return
                stage_run['status'] = 'completed'
                stage_run['finished'] = datetime.now().isoformat()
            run['status'] = 'completed'
            run['finished'] = datetime.now().isoformat()
            run['log'].append(f"[{datetime.now().isoformat()}] Pipeline completed successfully")
        except Exception as e:
            run['status'] = 'failed'
            run['finished'] = datetime.now().isoformat()
            run['log'].append(f"[{datetime.now().isoformat()}] Pipeline error: {str(e)}")
        finally:
            PIPELINE_APPROVAL_EVENTS.pop(run["id"], None)
        self._persist_run(run)

    def _execute_step(self, step, run):
        step_run = {
            'step_id': step.get('id', str(uuid.uuid4())),
            'name': step.get('name', 'Step'), 'type': step.get('type', 'custom_command'),
            'status': 'running', 'started': datetime.now().isoformat(),
            'output': '', 'finished': None
        }
        run['log'].append(f"[{datetime.now().isoformat()}] Running step: {step.get('name')} (type={step.get('type')})")
        try:
            cfg = step.get('config', {})
            cmd = None
            cwd = cfg.get('working_dir') or None
            if step.get('type') == 'script':
                cmd = f"{cfg.get('script_path', '')} {cfg.get('args', '')}".strip()
            elif step.get('type') == 'docker_build':
                cmd = f"docker build -t {cfg.get('image_tag', 'latest')} -f {cfg.get('dockerfile_path', 'Dockerfile')} {cfg.get('context_dir', '.')}"
            elif step.get('type') in ('terraform_apply', 'terraform_plan'):
                action = 'apply -auto-approve' if step['type'] == 'terraform_apply' else 'plan'
                var_file = f"-var-file={cfg['var_file']}" if cfg.get('var_file') else ''
                cmd = f"terraform {action} {var_file}".strip()
            elif step.get('type') == 'test_run':
                cmd = cfg.get('test_command', 'echo No test command')
            elif step.get('type') == 'deploy':
                cmd = f"echo Deploying to {cfg.get('target', 'unknown')} with strategy {cfg.get('strategy', 'rolling')}"
            elif step.get('type') == 'custom_command':
                cmd = cfg.get('command', 'echo hello')
            else:
                cmd = f"echo Unknown step type: {step.get('type')}"
            if cmd:
                result = subprocess.run(
                    cmd, shell=True, capture_output=True, text=True,
                    timeout=int(cfg.get('timeout', 300)), cwd=cwd
                )
                step_run['output'] = result.stdout + result.stderr
                step_run['status'] = 'completed' if result.returncode == 0 else 'failed'
            else:
                step_run['status'] = 'completed'
                step_run['output'] = 'No command to run'
        except subprocess.TimeoutExpired:
            step_run['status'] = 'failed'
            step_run['output'] = 'Step timed out'
        except Exception as e:
            step_run['status'] = 'failed'
            step_run['output'] = str(e)
        step_run['finished'] = datetime.now().isoformat()
        return step_run

    def _persist_run(self, run):
        d = self._load_runs()
        runs = d.setdefault('runs', [])
        for index, existing in enumerate(runs):
            if existing.get("id") == run.get("id"):
                runs[index] = run
                break
        else:
            runs.insert(0, run)
        if len(runs) > 100:
            d['runs'] = runs[:100]
        self._save_runs(d)

    def get_run(self, rid):
        if rid in PIPELINE_RUNS:
            return PIPELINE_RUNS[rid]
        d = self._load_runs()
        for r in d.get('runs', []):
            if r['id'] == rid:
                return r
        raise ValueError('Run not found')

    def get_runs(self, pipeline_id=None, limit=50):
        runs = list(PIPELINE_RUNS.values())
        d = self._load_runs()
        for r in d.get('runs', []):
            if r['id'] not in PIPELINE_RUNS:
                runs.append(r)
        if pipeline_id:
            runs = [r for r in runs if r.get('pipeline_id') == pipeline_id]
        runs.sort(key=lambda r: r.get('started', ''), reverse=True)
        return runs[:limit]

    def cancel_run(self, rid):
        if rid in PIPELINE_RUNS:
            run = PIPELINE_RUNS[rid]
            if run.get("status") not in {"running", "waiting_for_approval"}:
                raise ValueError("Run is not active.")
            run['status'] = 'cancelled'
            run['finished'] = datetime.now().isoformat()
            approval_event = PIPELINE_APPROVAL_EVENTS.get(rid)
            if approval_event:
                approval_event.set()
            self._persist_run(run)
            return run
        raise ValueError('Run not found or already finished')

    def resolve_approval(self, rid, decision, comment=""):
        if decision not in {"approved", "rejected"}:
            raise ValueError("Decision must be approved or rejected.")
        run = PIPELINE_RUNS.get(rid)
        if not run or run.get("status") != "waiting_for_approval":
            raise ValueError("Run is not waiting for approval.")
        approval_event = PIPELINE_APPROVAL_EVENTS.get(rid)
        if not approval_event:
            raise ValueError("The approval request is no longer active.")

        run["approval"]["decision"] = decision
        run["approval"]["comment"] = comment.strip()[:500] if isinstance(comment, str) else ""
        run["approval"]["decided_at"] = datetime.now().isoformat()
        run["log"].append(
            f"[{datetime.now().isoformat()}] Stage {decision}: {run['approval']['stage_name']}"
        )
        approval_event.set()
        return run


def register_pipeline_module(app, db_path='data/pipelines.json', runs_path='data/pipeline_runs.json'):
    pipeline_mgr = PipelineManager(db_path, runs_path)

    @app.route('/api/pipelines', methods=['GET'])
    def api_pipelines_list():
        try:
            return jsonify({'ok': True, 'result': pipeline_mgr.list_pipelines()})
        except Exception as e:
            return jsonify({'ok': False, 'error': str(e)}), 500

    @app.route('/api/pipelines', methods=['POST'])
    def api_pipelines_create():
        try:
            d = request.get_json(silent=True) or {}
            pipeline = pipeline_mgr.create_pipeline(d.get('name', 'New Pipeline'), d.get('description', ''))
            return jsonify({'ok': True, 'result': pipeline})
        except Exception as e:
            return jsonify({'ok': False, 'error': str(e)}), 400

    @app.route('/api/pipelines/<pid>', methods=['GET'])
    def api_pipelines_get(pid):
        try:
            return jsonify({'ok': True, 'result': pipeline_mgr.get_pipeline(pid)})
        except Exception as e:
            return jsonify({'ok': False, 'error': str(e)}), 404

    @app.route('/api/pipelines/<pid>', methods=['PUT'])
    def api_pipelines_update(pid):
        try:
            d = request.get_json(silent=True) or {}
            pipeline = pipeline_mgr.update_pipeline(pid, d)
            return jsonify({'ok': True, 'result': pipeline})
        except Exception as e:
            return jsonify({'ok': False, 'error': str(e)}), 400

    @app.route('/api/pipelines/<pid>', methods=['DELETE'])
    def api_pipelines_delete(pid):
        try:
            pipeline_mgr.delete_pipeline(pid)
            return jsonify({'ok': True})
        except Exception as e:
            return jsonify({'ok': False, 'error': str(e)}), 500

    @app.route('/api/pipelines/<pid>/execute', methods=['POST'])
    def api_pipelines_execute(pid):
        try:
            run = pipeline_mgr.execute_pipeline(pid)
            return jsonify({'ok': True, 'result': run})
        except Exception as e:
            return jsonify({'ok': False, 'error': str(e)}), 400

    @app.route('/api/pipelines/runs', methods=['GET'])
    def api_pipeline_runs_list():
        try:
            pid = request.args.get('pipeline_id')
            return jsonify({'ok': True, 'result': pipeline_mgr.get_runs(pipeline_id=pid)})
        except Exception as e:
            return jsonify({'ok': False, 'error': str(e)}), 500

    @app.route('/api/pipelines/runs/<rid>', methods=['GET'])
    def api_pipeline_runs_get(rid):
        try:
            return jsonify({'ok': True, 'result': pipeline_mgr.get_run(rid)})
        except Exception as e:
            return jsonify({'ok': False, 'error': str(e)}), 404

    @app.route('/api/pipelines/runs/<rid>/cancel', methods=['POST'])
    def api_pipeline_runs_cancel(rid):
        try:
            run = pipeline_mgr.cancel_run(rid)
            return jsonify({'ok': True, 'result': run})
        except Exception as e:
            return jsonify({'ok': False, 'error': str(e)}), 400

    @app.route('/api/pipelines/runs/<rid>/approval', methods=['POST'])
    def api_pipeline_runs_approval(rid):
        try:
            d = request.get_json(silent=True) or {}
            run = pipeline_mgr.resolve_approval(
                rid,
                d.get("decision"),
                d.get("comment", ""),
            )
            return jsonify({'ok': True, 'result': run})
        except Exception as e:
            return jsonify({'ok': False, 'error': str(e)}), 400

    @app.route('/api/pipelines/import', methods=['POST'])
    def api_pipelines_import():
        try:
            d = request.get_json(silent=True) or {}
            pipeline = pipeline_mgr.import_pipeline(d)
            return jsonify({'ok': True, 'result': pipeline})
        except Exception as e:
            return jsonify({'ok': False, 'error': str(e)}), 400

    @app.route('/api/pipelines/import-yaml', methods=['POST'])
    def api_pipelines_import_yaml():
        body = request.get_json(silent=True) or {}
        raw_yaml = body.get("yaml")
        if not isinstance(raw_yaml, str) or not raw_yaml.strip():
            return jsonify({'ok': False, 'error': 'Provide a MasterChief pipeline YAML definition.'}), 400
        if len(raw_yaml) > 200_000:
            return jsonify({'ok': False, 'error': 'Pipeline YAML must be 200 KB or smaller.'}), 413
        try:
            definition = yaml.safe_load(raw_yaml)
            pipeline = pipeline_mgr.import_pipeline(definition)
            return jsonify({'ok': True, 'result': pipeline})
        except (yaml.YAMLError, ValueError) as e:
            return jsonify({'ok': False, 'error': str(e)}), 400

    @app.route('/api/pipelines/<pid>/export', methods=['GET'])
    def api_pipelines_export(pid):
        try:
            return jsonify({'ok': True, 'result': pipeline_mgr.get_pipeline(pid)})
        except Exception as e:
            return jsonify({'ok': False, 'error': str(e)}), 404

    @app.route('/api/pipelines/<pid>/export.yaml', methods=['GET'])
    def api_pipelines_export_yaml(pid):
        try:
            pipeline = pipeline_mgr.get_pipeline(pid)
            response = make_response(yaml.safe_dump(pipeline, sort_keys=False, allow_unicode=True))
            response.headers["Content-Type"] = "application/yaml; charset=utf-8"
            filename = secure_filename(pipeline.get("name", "pipeline")) or "pipeline"
            response.headers["Content-Disposition"] = f'attachment; filename="{filename}.yaml"'
            return response
        except Exception as e:
            return jsonify({'ok': False, 'error': str(e)}), 404

    return pipeline_mgr