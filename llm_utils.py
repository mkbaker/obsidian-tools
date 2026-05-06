#!/usr/bin/env python3
"""Shared LLM tier logic: ollama -> Haiku -> Sonnet."""

import json
import sys
import urllib.request

SONNET_MODEL = "claude-sonnet-4-6"
HAIKU_MODEL = "claude-haiku-4-5-20251001"
TOKEN_THRESHOLD = 60_000
OLLAMA_URL = "http://localhost:11434"

_cache = {}


def _check_ollama():
    if 'available' not in _cache:
        try:
            urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=2)
            _cache['available'] = True
        except Exception:
            _cache['available'] = False
    return _cache['available']


def _get_ollama_models():
    if 'models' not in _cache:
        try:
            resp = urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=2)
            data = json.loads(resp.read())
            _cache['models'] = [m['name'] for m in data.get('models', [])]
        except Exception:
            _cache['models'] = []
    return _cache['models']


def _call_ollama(prompt, model):
    payload = json.dumps({'model': model, 'prompt': prompt, 'stream': False}).encode()
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate",
        data=payload,
        headers={'Content-Type': 'application/json'}
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read())['response'].strip()


def _call_claude(prompt, model):
    try:
        import anthropic
    except ImportError:
        print("Error: anthropic package not installed. Run: pip install anthropic")
        sys.exit(1)
    client = anthropic.Anthropic()
    msg = client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )
    return msg.content[0].text.strip()


def call_llm(prompt, use_claude=False, use_sonnet=False, ollama_model=None):
    """Call LLM with automatic tier selection. Returns (text, model_label)."""
    tokens = len(prompt) // 4

    if use_sonnet:
        label = f"claude/{SONNET_MODEL}"
        print(f"  Using {label}")
        return _call_claude(prompt, SONNET_MODEL), label

    if use_claude:
        label = f"claude/{HAIKU_MODEL}"
        print(f"  Using {label}")
        return _call_claude(prompt, HAIKU_MODEL), label

    if _check_ollama():
        models = _get_ollama_models()
        if models:
            if tokens > TOKEN_THRESHOLD:
                print(f"  Content large (~{tokens:,} tokens), escalating to Claude Sonnet")
                label = f"claude/{SONNET_MODEL}"
                return _call_claude(prompt, SONNET_MODEL), label
            model = ollama_model or models[0]
            label = f"ollama/{model}"
            print(f"  Using {label}")
            return _call_ollama(prompt, model), label
        print("  Ollama running but no models found, falling back to Claude Haiku")
    else:
        print("  Ollama unavailable, using Claude Haiku")

    if tokens > TOKEN_THRESHOLD:
        print(f"  Content large (~{tokens:,} tokens), using Claude Sonnet")
        label = f"claude/{SONNET_MODEL}"
        return _call_claude(prompt, SONNET_MODEL), label

    label = f"claude/{HAIKU_MODEL}"
    print(f"  Using {label}")
    return _call_claude(prompt, HAIKU_MODEL), label
