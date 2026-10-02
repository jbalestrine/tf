import json
import os
import subprocess
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request, send_file


echo_runtime_bp = Blueprint('echo_runtime_bp', __name__)


def _root() -> Path:
    return Path(current_app.root_path).resolve()


def _echo_outputs_dir() -> Path:
    return _root() / 'data' / 'echo_chat_outputs'


def _echo_images_dir() -> Path:
    p = _root() / 'data' / 'echo_images'
    p.mkdir(parents=True, exist_ok=True)
    return p


def _image_cache() -> dict:
    cache = current_app.config.get('_image_cache')
    if cache is None:
        cache = {}
        current_app.config['_image_cache'] = cache
    return cache


def _image_rate() -> dict:
    rate = current_app.config.get('_image_rate')
    if rate is None:
        rate = {}
        current_app.config['_image_rate'] = rate
    return rate


def _image_jobs() -> dict:
    jobs = current_app.config.get('_image_jobs')
    if jobs is None:
        jobs = {}
        current_app.config['_image_jobs'] = jobs
    return jobs


def _train_jobs_file() -> Path:
    p = _root() / 'data' / 'train_jobs.json'
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _load_resources_index() -> dict:
    idx_file = _root() / 'data' / 'resources' / 'index.json'
    if not idx_file.exists():
        return {}
    try:
        raw = json.loads(idx_file.read_text(encoding='utf-8'))
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}


def _train_jobs() -> dict:
    jobs = current_app.config.get('_train_jobs')
    if isinstance(jobs, dict):
        return jobs

    jobs = {}
    jf = _train_jobs_file()
    if jf.exists():
        try:
            raw = json.loads(jf.read_text(encoding='utf-8'))
            if isinstance(raw, dict):
                jobs = raw
        except Exception:
            jobs = {}
    current_app.config['_train_jobs'] = jobs
    return jobs


def _save_train_jobs(jobs: dict):
    current_app.config['_train_jobs'] = jobs
    try:
        _train_jobs_file().write_text(json.dumps(jobs, indent=2), encoding='utf-8')
    except Exception:
        current_app.logger.exception('Failed to persist train jobs')


def _start_train_job(job_id: str, cmd: list[str], cwd: str | None = None):
    jobs = _train_jobs()

    def runner():
        job = jobs.get(job_id)
        if not job:
            return

        job['status'] = 'running'
        job['started_at'] = time.time()
        _save_train_jobs(jobs)

        try:
            outdir = _root() / 'data' / 'models_output' / job_id
            outdir.mkdir(parents=True, exist_ok=True)
            log_path = outdir / 'train.log'
            with open(log_path, 'wb') as log_f:
                proc = subprocess.Popen(
                    cmd,
                    cwd=cwd or str(_root()),
                    stdout=log_f,
                    stderr=log_f,
                    shell=isinstance(cmd, str),
                )
                job['pid'] = proc.pid
                proc.wait()
                job['returncode'] = proc.returncode
            job['status'] = 'finished'
        except Exception as exc:
            job['error'] = str(exc)
            job['status'] = 'error'
        finally:
            job['finished_at'] = time.time()
            _save_train_jobs(jobs)

    threading.Thread(target=runner, daemon=True).start()


@echo_runtime_bp.route('/api/echo/image_status')
def api_echo_image_status():
    job_id = request.args.get('job_id')
    if not job_id:
        return jsonify({'error': 'job_id required'}), 400

    image_jobs = _image_jobs()
    job = image_jobs.get(job_id)
    jobs_dir = _root() / 'data' / 'image_jobs'
    job_file = jobs_dir / (job_id + '.json')
    if job_file.exists():
        try:
            job = json.loads(job_file.read_text(encoding='utf-8'))
        except Exception:
            pass
    if not job:
        return jsonify({'error': 'not found'}), 404

    res = dict(job)
    if job.get('path'):
        res['url'] = '/' + job['path']
    return jsonify(res)


@echo_runtime_bp.route('/api/echo/generate_image', methods=['POST'])
def api_echo_generate_image():
    """Generate an image from a prompt using local diffusers when available."""
    try:
        payload = request.get_json() or {}
        prompt = payload.get('prompt') or payload.get('message')
        session_id = payload.get('session_id') or request.remote_addr or 'anon'
        size = payload.get('size') or '512x512'
        style = payload.get('style') or ''
        if not prompt:
            return jsonify({'error': 'prompt required'}), 400

        now_ts = time.time()
        rl_key = str(session_id)
        window = 60
        rate = _image_rate()
        timestamps = rate.get(rl_key, [])
        timestamps = [t for t in timestamps if now_ts - t < window]
        if len(timestamps) >= current_app.config.get('IMAGE_RATE_LIMIT_PER_MIN', 6):
            return jsonify({'error': 'rate limit exceeded'}), 429
        timestamps.append(now_ts)
        rate[rl_key] = timestamps

        cache_key = f"{prompt}||{size}||{style}"
        cache = _image_cache()
        cached = cache.get(cache_key)
        if cached and (now_ts - cached.get('ts', 0) < current_app.config.get('IMAGE_CACHE_TTL', 86400)):
            return jsonify({'ok': True, 'url': '/' + cached['path']})

        provider = current_app.config.get('IMAGE_PROVIDER', 'local')
        if provider != 'local':
            return jsonify({'error': 'Only local CPU generation is enabled in this demo. Set IMAGE_PROVIDER=local.'}), 501

        try:
            import torch  # noqa: F401
            from diffusers import StableDiffusionPipeline
        except Exception:
            return jsonify({'error': 'diffusers or torch not installed (pip install diffusers[torch] transformers)'}), 501

        try:
            model_id = os.environ.get('IMAGE_LOCAL_MODEL', 'runwayml/stable-diffusion-v1-5')
            try:
                pipe = StableDiffusionPipeline.from_pretrained(model_id, device_map='cpu')
            except Exception:
                pipe = StableDiffusionPipeline.from_pretrained(model_id)

            width, height = (512, 512)
            try:
                parts = size.split('x')
                if len(parts) == 2:
                    width = int(parts[0])
                    height = int(parts[1])
            except Exception:
                pass

            image = pipe(prompt, height=height, width=width, num_inference_steps=20).images[0]
            fname = f"img_{int(time.time()*1000)}_{uuid.uuid4().hex}.png"
            fpath = _echo_images_dir() / fname
            image.save(str(fpath))
            rel = fpath.relative_to(_root()).as_posix()
            cache[cache_key] = {'path': rel, 'ts': time.time()}
            return jsonify({'ok': True, 'url': '/' + rel})
        except Exception as exc:
            current_app.logger.exception('Local image generation failed')
            return jsonify({'error': f'local generation failed: {exc}'}), 500
    except Exception as exc:
        current_app.logger.exception('Generate image failed')
        return jsonify({'error': str(exc)}), 500


@echo_runtime_bp.route('/data/echo_images/<path:fname>')
def serve_echo_image(fname):
    try:
        outdir = _echo_images_dir()
        fpath = (outdir / fname).resolve()
        if not str(fpath).startswith(str(outdir.resolve())):
            return 'invalid path', 400
        if not fpath.exists():
            return 'not found', 404
        return send_file(str(fpath), as_attachment=False)
    except Exception as exc:
        current_app.logger.exception('Failed to serve echo image')
        return jsonify({'error': str(exc)}), 500


@echo_runtime_bp.route('/api/echo/generate_image_async', methods=['POST'])
def api_echo_generate_image_async():
    """Enqueue an image generation job by writing a job file for the worker."""
    try:
        payload = request.get_json() or {}
        prompt = payload.get('prompt') or payload.get('message')
        session_id = payload.get('session_id') or request.remote_addr or 'anon'
        size = payload.get('size') or '512x512'
        style = payload.get('style') or ''
        if not prompt:
            return jsonify({'error': 'prompt required'}), 400

        now_ts = time.time()
        rl_key = str(session_id)
        window = 60
        rate = _image_rate()
        timestamps = rate.get(rl_key, [])
        timestamps = [t for t in timestamps if now_ts - t < window]
        if len(timestamps) >= current_app.config.get('IMAGE_RATE_LIMIT_PER_MIN', 6):
            return jsonify({'error': 'rate limit exceeded'}), 429
        timestamps.append(now_ts)
        rate[rl_key] = timestamps

        cache_key = f"{prompt}||{size}||{style}"
        cache = _image_cache()
        cached = cache.get(cache_key)
        if cached and (now_ts - cached.get('ts', 0) < current_app.config.get('IMAGE_CACHE_TTL', 86400)):
            return jsonify({'ok': True, 'url': '/' + cached['path']})

        job_id = uuid.uuid4().hex
        job = {
            'id': job_id,
            'prompt': prompt,
            'size': size,
            'style': style,
            'status': 'queued',
            'progress': 0,
            'path': None,
            'error': None,
            'created': now_ts,
        }
        jobs = _image_jobs()
        jobs[job_id] = job

        jobs_dir = _root() / 'data' / 'image_jobs'
        jobs_dir.mkdir(parents=True, exist_ok=True)
        job_path = jobs_dir / (job_id + '.json')
        tmp_path = jobs_dir / (job_id + '.json.tmp')
        tmp_path.write_text(json.dumps(job), encoding='utf-8')
        try:
            tmp_path.replace(job_path)
        except Exception:
            job_path.write_text(json.dumps(job), encoding='utf-8')

        app_logger = current_app.logger

        def _run_image_job(jpath):
            try:
                import importlib.util

                worker_path = str(_root() / 'image_worker.py')
                spec = importlib.util.spec_from_file_location('image_worker', worker_path)
                iw = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(iw)
                iw.process_job(jpath)
                try:
                    updated = json.loads(jpath.read_text(encoding='utf-8'))
                    jobs[updated.get('id', '')] = updated
                    if updated.get('path') and updated.get('status') == 'done':
                        ck = f"{updated.get('prompt','')}||{updated.get('size','')}||{updated.get('style','')}"
                        cache[ck] = {'path': updated['path'], 'ts': time.time()}
                except Exception:
                    pass
            except Exception as thread_exc:
                app_logger.exception('Image job thread error: %s', thread_exc)

        import threading

        threading.Thread(target=_run_image_job, args=(job_path,), daemon=True).start()
        return jsonify({'ok': True, 'job_id': job_id})
    except Exception as exc:
        current_app.logger.exception('Enqueue image job failed')
        return jsonify({'error': str(exc)}), 500


@echo_runtime_bp.route('/api/echo/outputs')
def api_echo_outputs():
    try:
        outdir = _echo_outputs_dir()
        files = []
        if outdir.exists():
            for p in sorted(outdir.glob('*.txt')):
                try:
                    files.append(
                        {
                            'name': p.name,
                            'size': p.stat().st_size,
                            'modified': datetime.fromtimestamp(p.stat().st_mtime).isoformat(),
                            'path': str(p.relative_to(_root())),
                        }
                    )
                except Exception:
                    files.append({'name': p.name})
        return jsonify({'files': files})
    except Exception as exc:
        current_app.logger.exception('List echo outputs failed')
        return jsonify({'error': str(exc)}), 500


@echo_runtime_bp.route('/data/echo_chat_outputs/<path:fname>')
def serve_echo_output(fname):
    try:
        outdir = _echo_outputs_dir()
        fpath = (outdir / fname).resolve()
        if not str(fpath).startswith(str(outdir.resolve())):
            return 'invalid path', 400
        if not fpath.exists():
            return 'not found', 404
        return send_file(str(fpath), as_attachment=True)
    except Exception as exc:
        current_app.logger.exception('Failed to serve echo output')
        return jsonify({'error': str(exc)}), 500


@echo_runtime_bp.route('/api/echo/outputs/delete', methods=['POST'])
def api_echo_outputs_delete():
    try:
        data = request.get_json() or {}
        name = data.get('name')
        if not name:
            return jsonify({'error': 'name required'}), 400

        outdir = _echo_outputs_dir()
        fpath = (outdir / name).resolve()
        if not str(fpath).startswith(str(outdir.resolve())):
            return jsonify({'error': 'invalid path'}), 400
        if not fpath.exists():
            return jsonify({'error': 'not found'}), 404

        try:
            fpath.unlink()
        except Exception:
            current_app.logger.exception('Failed to delete echo output %s', fpath)
            return jsonify({'error': 'delete failed'}), 500

        return jsonify({'ok': True})
    except Exception as exc:
        current_app.logger.exception('Delete echo output failed')
        return jsonify({'error': str(exc)}), 500


@echo_runtime_bp.route('/api/gguf/models')
def api_gguf_models():
    try:
        from echo.chat_bot import get_chat_bot

        models_dir = _root() / 'models'
        models = []
        if models_dir.exists():
            for f in models_dir.glob('*.gguf'):
                models.append(str(f.relative_to(_root())))

        bot = get_chat_bot()
        current = None
        if hasattr(bot, '_model_path') and bot._model_path:
            model_path = Path(bot._model_path)
            current = str(model_path.relative_to(_root())) if model_path.is_relative_to(_root()) else bot._model_path
        return jsonify({'models': models, 'current': current})
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500


@echo_runtime_bp.route('/api/gguf/select', methods=['POST'])
def api_gguf_select():
    try:
        from echo.chat_bot import get_chat_bot

        data = request.get_json() or {}
        model = data.get('model', '')
        bot = get_chat_bot()
        if model:
            success = bot.reload_model(model_name=model)
            model_path = Path(bot._model_path)
            current = str(model_path.relative_to(_root())) if model_path.is_relative_to(_root()) else bot._model_path
            return jsonify({'success': success, 'current': current})

        bot._model_path = None
        return jsonify({'success': True, 'current': None})
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500


@echo_runtime_bp.route('/api/echo/debug_image_provider')
def api_echo_debug_image_provider():
    try:
        import importlib.util

        has_torch = importlib.util.find_spec('torch') is not None
        has_diffusers = importlib.util.find_spec('diffusers') is not None
    except Exception:
        has_torch = False
        has_diffusers = False

    return jsonify(
        {
            'IMAGE_PROVIDER': current_app.config.get('IMAGE_PROVIDER'),
            'torch_installed': bool(has_torch),
            'diffusers_installed': bool(has_diffusers),
        }
    )


@echo_runtime_bp.route('/api/echo/training_files')
def api_echo_training_files():
    try:
        base = _root() / 'data' / 'echo_training'
        files = []
        if base.exists():
            for p in sorted(base.glob('*')):
                if p.is_file():
                    files.append(
                        {
                            'name': p.name,
                            'size': p.stat().st_size,
                            'modified': datetime.fromtimestamp(p.stat().st_mtime).isoformat(),
                        }
                    )
        return jsonify({'files': files})
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500


@echo_runtime_bp.route('/api/echo/youtube_search', methods=['GET'])
def api_echo_youtube_search():
    """Resolve a search query to a real YouTube video ID."""
    import re as _re2
    import requests as _req

    q = (request.args.get('q') or '').strip()
    if not q:
        return jsonify({'error': 'no query'}), 400

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
    }

    try:
        url = 'https://www.youtube.com/results?search_query=' + _req.utils.quote(q) + '&sp=EgIQAQ%3D%3D'
        resp = _req.get(url, headers=headers, timeout=6)
        if resp.status_code == 200:
            match = _re2.search(r'"videoId":"([A-Za-z0-9_-]{11})"', resp.text)
            if match:
                vid = match.group(1)
                title_match = _re2.search(r'"title":\{"runs":\[\{"text":"([^"]+)"', resp.text)
                title = title_match.group(1) if title_match else q
                return jsonify({'videoId': vid, 'title': title, 'source': 'youtube'})
    except Exception:
        pass

    piped_instances = [
        'https://pipedapi.kavin.rocks',
        'https://pipedapi.adminforge.de',
        'https://piped-api.garudalinux.org',
    ]
    for base in piped_instances:
        try:
            resp = _req.get(f'{base}/search?q={_req.utils.quote(q)}&filter=videos', headers=headers, timeout=4)
            if resp.status_code == 200:
                for item in (resp.json().get('items') or []):
                    vid = item.get('url', '')
                    vid = vid.replace('/watch?v=', '').replace('https://www.youtube.com/watch?v=', '')
                    if vid and len(vid) == 11:
                        return jsonify({'videoId': vid, 'title': item.get('title', q), 'source': base})
        except Exception:
            continue

    return jsonify({'videoId': 'jfKfPfyJRdk', 'title': 'Lofi Hip Hop Radio - Beats to Relax/Study To', 'source': 'fallback'})


@echo_runtime_bp.route('/api/echo/model', methods=['GET'])
def api_echo_model():
    try:
        from echo.chat_bot import get_chat_bot

        bot = get_chat_bot()
        model = getattr(bot, '_local_model_path', None)
        return jsonify({'model': model if model else None})
    except Exception as exc:
        current_app.logger.exception('Get model failed')
        return jsonify({'error': str(exc)}), 500


@echo_runtime_bp.route('/api/echo/preload_model', methods=['POST', 'GET'])
def api_echo_preload_model():
    """Discover local model and optionally run a tiny warm-up generation."""
    try:
        from echo.chat_bot import get_chat_bot

        bot = get_chat_bot()
        model = None
        warmed = False

        try:
            cfg = _root() / 'data' / 'echo_model.json'
            if cfg.exists():
                try:
                    cfgd = json.loads(cfg.read_text(encoding='utf-8'))
                    if cfgd.get('model'):
                        model = cfgd.get('model')
                except Exception:
                    model = None
        except Exception:
            model = None

        if not model and hasattr(bot, '_find_local_model'):
            try:
                model = bot._find_local_model()
            except Exception:
                model = None

        payload = request.get_json(silent=True) or {}
        do_warm = payload.get('warm', True)

        if model and do_warm and hasattr(bot, '_generate_with_local_llm'):
            try:
                out = bot._generate_with_local_llm('Hello, warmup', max_tokens=8, temperature=0.1)
                warmed = bool(out)
            except Exception as exc:
                current_app.logger.exception('Preload generation failed')
                return jsonify({'model': model, 'warmed': False, 'error': str(exc)}), 500

        return jsonify({'model': model, 'warmed': warmed})
    except Exception as exc:
        current_app.logger.exception('Preload endpoint failed')
        return jsonify({'error': str(exc)}), 500


@echo_runtime_bp.route('/api/echo/train', methods=['POST'])
def api_echo_train():
    try:
        data = request.get_json() or {}
        user_message = data.get('user_message', '')
        bot_response = data.get('bot_response', '')
        quality_str = data.get('quality', 'acceptable')

        from echo.chat_bot import ResponseQuality, get_chat_bot

        quality_map = {
            'excellent': ResponseQuality.EXCELLENT,
            'good': ResponseQuality.GOOD,
            'acceptable': ResponseQuality.ACCEPTABLE,
            'poor': ResponseQuality.POOR,
        }
        quality = quality_map.get(quality_str, ResponseQuality.ACCEPTABLE)

        bot = get_chat_bot()
        success = bot.train(user_message, bot_response, quality)
        return jsonify({'success': success})
    except Exception as exc:
        return jsonify({'error': str(exc), 'success': False}), 500


@echo_runtime_bp.route('/api/echo/stats')
def api_echo_stats():
    try:
        from echo.chat_bot import get_chat_bot

        bot = get_chat_bot()
        stats = bot.get_training_stats()
        return jsonify(stats)
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500


@echo_runtime_bp.route('/api/echo/history')
def api_echo_history():
    try:
        from echo.conversation_storage import get_storage

        session_id = request.args.get('session_id', 'default')
        limit = int(request.args.get('limit', 50))
        storage = get_storage()
        history = storage.get_conversation_history(user='web_user', limit=limit, channel=session_id)
        return jsonify({'history': history})
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500


@echo_runtime_bp.route('/api/echo/train_model', methods=['POST'])
def api_echo_train_model():
    """Start a training job (runs tools/finetune_stub.py by default)."""
    try:
        data = request.get_json() or {}
        model = data.get('model')
        training_file = data.get('training_file')
        resource_id = data.get('resource_id')
        epochs = int(data.get('epochs', 1))
        batch_size = int(data.get('batch_size', 8))
        lr = float(data.get('lr', 1e-4))
        engine = data.get('engine', 'stub')

        if not model or (not training_file and not resource_id):
            return jsonify({'error': 'model and either training_file or resource_id are required'}), 400

        model_path = Path(model)
        if not model_path.is_absolute():
            model_path = _root() / model_path
        if not model_path.exists():
            return jsonify({'error': 'model not found'}), 404

        if resource_id:
            idx = _load_resources_index()
            entry = idx.get(resource_id)
            if not entry:
                return jsonify({'error': 'resource not found'}), 404

            p = Path(entry.get('path', ''))
            if not p.is_absolute():
                p = _root() / p
            if not p.exists():
                return jsonify({'error': 'resource file not found'}), 404

            from tools.dataset_helper import convert_file_to_jsonl

            tfile = _root() / 'data' / 'echo_training' / f'{resource_id}.jsonl'
            try:
                tfile.parent.mkdir(parents=True, exist_ok=True)
                convert_file_to_jsonl(str(p), str(tfile))
            except Exception as exc:
                return jsonify({'error': f'conversion failed: {exc}'}), 500
        else:
            tfile = _root() / 'data' / 'echo_training' / str(training_file)
            if not tfile.exists():
                return jsonify({'error': 'training file not found'}), 404

        job_id = uuid.uuid4().hex
        outdir = _root() / 'data' / 'models_output' / job_id
        outdir.mkdir(parents=True, exist_ok=True)

        if engine == 'stub':
            worker = _root() / 'tools' / 'finetune_stub.py'
            cmd = [
                os.sys.executable,
                str(worker),
                '--model',
                str(model_path),
                '--data',
                str(tfile),
                '--output',
                str(outdir),
                '--epochs',
                str(epochs),
                '--batch_size',
                str(batch_size),
                '--lr',
                str(lr),
            ]
        elif engine == 'peft':
            try:
                import peft  # noqa: F401
                import transformers  # noqa: F401
            except Exception:
                return jsonify(
                    {
                        'error': 'PEFT/transformers not installed',
                        'install': 'pip install "transformers[sentencepiece]" accelerate peft bitsandbytes --upgrade',
                    }
                ), 400
            worker = _root() / 'tools' / 'finetune_stub.py'
            cmd = [
                os.sys.executable,
                str(worker),
                '--model',
                str(model_path),
                '--data',
                str(tfile),
                '--output',
                str(outdir),
                '--epochs',
                str(epochs),
                '--batch_size',
                str(batch_size),
                '--lr',
                str(lr),
            ]
        else:
            return jsonify({'error': 'unknown engine', 'allowed': ['stub', 'peft']}), 400

        jobs = _train_jobs()
        jobs[job_id] = {
            'id': job_id,
            'status': 'queued',
            'model': str(model_path),
            'training_file': str(tfile),
            'output': str(outdir),
            'engine': engine,
            'pid': None,
            'returncode': None,
            'started_at': None,
            'finished_at': None,
        }
        _save_train_jobs(jobs)
        _start_train_job(job_id, cmd, cwd=str(_root()))
        return jsonify({'ok': True, 'job_id': job_id})
    except Exception as exc:
        current_app.logger.exception('Start train failed')
        return jsonify({'error': str(exc)}), 500


@echo_runtime_bp.route('/api/echo/train_status')
def api_echo_train_status():
    job_id = request.args.get('job_id')
    if not job_id:
        return jsonify({'error': 'job_id required'}), 400

    jobs = _train_jobs()
    job = jobs.get(job_id)
    if not job:
        return jsonify({'error': 'job not found'}), 404

    outdir = _root() / 'data' / 'models_output' / job_id
    log_path = outdir / 'train.log'
    log_tail = ''
    if log_path.exists():
        try:
            log_tail = log_path.read_text(encoding='utf-8', errors='ignore')[-8192:]
        except Exception:
            log_tail = ''

    return jsonify({'job': job, 'log_tail': log_tail})


@echo_runtime_bp.route('/api/echo/train_list')
def api_echo_train_list():
    try:
        return jsonify({'jobs': list(_train_jobs().values())})
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500


@echo_runtime_bp.route('/api/echo/train_cancel', methods=['POST'])
def api_echo_train_cancel():
    try:
        data = request.get_json() or {}
        job_id = data.get('job_id')
        if not job_id:
            return jsonify({'error': 'job_id required'}), 400

        jobs = _train_jobs()
        job = jobs.get(job_id)
        if not job:
            return jsonify({'error': 'job not found'}), 404

        pid = job.get('pid')
        if pid:
            try:
                import psutil

                proc = psutil.Process(int(pid))
                proc.terminate()
                time.sleep(1)
                if proc.is_running():
                    proc.kill()
            except Exception:
                pass

        job['status'] = 'cancelled'
        job['finished_at'] = time.time()
        _save_train_jobs(jobs)
        return jsonify({'ok': True})
    except Exception as exc:
        current_app.logger.exception('Cancel failed')
        return jsonify({'error': str(exc)}), 500
