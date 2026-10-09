#!/usr/bin/env python3
"""Minimal LLM worker.

Attempts to generate using the local `llama_cpp` binding if available,
otherwise sends the prompt to an Ollama server (if configured).

Reads the prompt from stdin and prints JSON {"text": "..."} on success,
or {"error": "..."} on failure.
"""
import sys
import json
import argparse
import os

# Delay importing llama_cpp until actually needed to avoid importing
# native bindings during pytest/module import time.
import requests


def try_llama(model_path: str, prompt: str, max_tokens: int, temperature: float):
    try:
        # delayed import
        from llama_cpp import Llama as _Llama
    except Exception as e:
        return None, f"llama_cpp import failed: {e}"
    try:
        ctx = os.environ.get('ECHO_LLM_CTX')
        model = _Llama(model_path=model_path, n_ctx=int(ctx)) if ctx else _Llama(model_path=model_path)
    except Exception as e:
        return None, f"Failed to instantiate Llama: {e}"
    try:
        if hasattr(model, 'create'):
            resp = model.create(prompt=prompt, max_tokens=int(max_tokens), temperature=float(temperature))
            if isinstance(resp, dict):
                choices = resp.get('choices') or []
                if choices:
                    text = choices[0].get('text') or choices[0].get('content')
                    return text, None
            if hasattr(resp, 'text'):
                return str(resp.text), None
        # fallback: try callable
        if callable(model):
            out = model(prompt, max_tokens=int(max_tokens), temperature=float(temperature))
            if isinstance(out, dict):
                choices = out.get('choices') or []
                if choices:
                    text = choices[0].get('text') or choices[0].get('content')
                    return text, None
            if isinstance(out, str):
                return out, None
    except Exception as e:
        return None, str(e)
    finally:
        try:
            if hasattr(model, 'close'):
                model.close()
        except Exception:
            pass
    return None, 'No usable generation method on Llama binding'


def try_ollama(model: str, prompt: str, max_tokens: int, temperature: float):
    try:
        ollama_url = os.environ.get('OLLAMA_URL', 'http://localhost:11434')
        resp = requests.post(f"{ollama_url}/api/generate", json={'model': model, 'prompt': prompt, 'max_tokens': max_tokens, 'temperature': temperature}, timeout=20)
        if resp.ok:
            data = resp.json()
            text = data.get('text') or data.get('response') or (data.get('choices') and data['choices'][0].get('text'))
            return text, None
        return None, f'Ollama returned {resp.status_code}'
    except Exception as e:
        return None, f'Ollama request failed: {e}'


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--model', required=True)
    p.add_argument('--max_tokens', type=int, default=256)
    p.add_argument('--temperature', type=float, default=0.7)
    args = p.parse_args()

    prompt = sys.stdin.read() or ''

    # Try llama_cpp binding first (always attempt delayed import)
    text, err_llama = try_llama(args.model, prompt, args.max_tokens, args.temperature)
    if text:
        print(json.dumps({'text': text}))
        return 0

    # Optionally try Ollama only if enabled via env var to avoid silent fallbacks
    allow_ollama = os.environ.get('ECHO_ALLOW_OLLAMA', '0') == '1'
    err_ollama = None
    if allow_ollama:
        text, err_ollama = try_ollama(args.model, prompt, args.max_tokens, args.temperature)
        if text:
            print(json.dumps({'text': text}))
            return 0

    # Report combined errors for diagnostics
    final_err = err_llama or err_ollama or 'No model available'
    print(json.dumps({'error': final_err}))
    return 2


if __name__ == '__main__':
    try:
        rc = main()
        sys.exit(rc)
    except Exception as e:
        print(json.dumps({'error': str(e)}))
        sys.exit(3)
