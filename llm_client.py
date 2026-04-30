"""K2-Think LLM client for the Insight Platform.

Reads K2_API_KEY / K2_API_BASE / K2_MODEL from environment (or `.env` next to
this file). Provides three call styles:

  ask(prompt, system=..., json_schema=...)  → blocking, returns str or dict
  ask_json(prompt, system=...)              → blocking JSON-only with retry
  stream(prompt, system=...)                → yields chunks (for SSE)

K2-Think emits a chain-of-thought block delimited by `</think>` before the
final answer. We strip everything up to and including that marker. The model
sometimes returns plain text without the marker too, so the strip is best-effort.

Cache: file-based, keyed by sha256(model + messages). Cache hits skip the
network call and are returned instantly. Disk cache lives in `llm_cache/`
(gitignored).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Any, Iterator

import requests


# ─── env loading ──────────────────────────────────────────────────────────
_HERE = Path(__file__).resolve().parent
_ENV_FILE = _HERE / ".env"
if _ENV_FILE.exists():
    for line in _ENV_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

API_KEY = os.environ.get("K2_API_KEY", "")
API_BASE = os.environ.get("K2_API_BASE", "https://api.k2think.ai/v1")
MODEL = os.environ.get("K2_MODEL", "MBZUAI-IFM/K2-Think-v2")

if not API_KEY:
    raise RuntimeError(
        "K2_API_KEY not set. Copy .env.example to .env and fill in the key."
    )

CACHE_DIR = _HERE / "llm_cache"
CACHE_DIR.mkdir(exist_ok=True)


# ─── helpers ──────────────────────────────────────────────────────────────
def _strip_reasoning(text: str) -> str:
    """K2-Think prepends a chain-of-thought block before the answer.

    Format observed: `... reasoning ...\n</think>\nANSWER`. We keep only the
    text after the last `</think>` if present, otherwise return as-is.
    """
    if "</think>" in text:
        return text.split("</think>", 1)[1].strip()
    return text.strip()


def _cache_key(payload: dict) -> str:
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode()).hexdigest()[:24]


def _cache_load(key: str) -> str | None:
    f = CACHE_DIR / f"{key}.txt"
    return f.read_text() if f.exists() else None


def _cache_save(key: str, text: str) -> None:
    (CACHE_DIR / f"{key}.txt").write_text(text)


def _post(payload: dict, stream: bool = False, timeout: int = 120) -> requests.Response:
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    return requests.post(
        f"{API_BASE}/chat/completions",
        headers=headers,
        json=payload,
        stream=stream,
        timeout=timeout,
    )


# ─── public API ───────────────────────────────────────────────────────────
def ask(
    prompt: str,
    system: str | None = None,
    *,
    temperature: float = 0.3,
    max_tokens: int | None = None,
    use_cache: bool = True,
    strip_reasoning: bool = True,
) -> str:
    """One-shot blocking call. Returns the final answer text."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload: dict[str, Any] = {
        "model": MODEL,
        "messages": messages,
        "temperature": temperature,
        "stream": False,
    }
    if max_tokens:
        payload["max_tokens"] = max_tokens

    key = _cache_key(payload)
    if use_cache:
        cached = _cache_load(key)
        if cached is not None:
            return cached

    last_err: Exception | None = None
    for attempt in range(3):
        try:
            r = _post(payload, stream=False)
            if r.status_code != 200:
                last_err = RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
                time.sleep(1 + attempt)
                continue
            data = r.json()
            text = data["choices"][0]["message"]["content"]
            if strip_reasoning:
                text = _strip_reasoning(text)
            if use_cache:
                _cache_save(key, text)
            return text
        except Exception as e:
            last_err = e
            time.sleep(1 + attempt)
    raise RuntimeError(f"K2 call failed after 3 attempts: {last_err}")


_JSON_BLOCK = re.compile(r"\{(?:[^{}]|(?:\{[^{}]*\}))*\}", re.DOTALL)


def ask_json(
    prompt: str,
    system: str | None = None,
    *,
    temperature: float = 0.2,
    use_cache: bool = True,
    max_retries: int = 2,
) -> dict:
    """Blocking call that parses the answer as JSON.

    K2-Think doesn't reliably honor a `response_format` flag, so we add an
    explicit "return JSON only" instruction and extract the largest JSON
    object from the answer. On parse failure we retry with a stricter prompt.
    """
    base_system = (system or "") + (
        "\n\nReturn ONLY valid JSON. No prose, no markdown fences, no commentary."
    )
    cur_prompt = prompt
    last_err: Exception | None = None
    for attempt in range(max_retries + 1):
        text = ask(
            cur_prompt,
            system=base_system,
            temperature=temperature,
            use_cache=use_cache and attempt == 0,
        )
        # Try direct parse first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        # Fall back to extracting the largest JSON-like substring
        candidates = _JSON_BLOCK.findall(text)
        for cand in sorted(candidates, key=len, reverse=True):
            try:
                return json.loads(cand)
            except json.JSONDecodeError as e:
                last_err = e
        cur_prompt = (
            prompt
            + "\n\n(Previous reply was not valid JSON. Return ONLY a single "
              "JSON object, with no surrounding text.)"
        )
    raise RuntimeError(f"Failed to parse JSON after {max_retries+1} tries: {last_err}")


def stream(
    prompt: str,
    system: str | None = None,
    *,
    temperature: float = 0.3,
    strip_reasoning: bool = True,
) -> Iterator[str]:
    """SSE stream. Yields content deltas. Reasoning tokens are skipped if
    `strip_reasoning` is True (we don't yield anything until we cross
    `</think>`)."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": temperature,
        "stream": True,
    }
    r = _post(payload, stream=True, timeout=180)
    r.raise_for_status()

    buf = ""
    seen_think_end = False
    for raw in r.iter_lines(decode_unicode=True):
        if not raw or not raw.startswith("data:"):
            continue
        data_str = raw[len("data:"):].strip()
        if data_str == "[DONE]":
            break
        try:
            chunk = json.loads(data_str)
        except json.JSONDecodeError:
            continue
        try:
            delta = chunk["choices"][0]["delta"].get("content", "")
        except (KeyError, IndexError):
            continue
        if not delta:
            continue
        if not strip_reasoning:
            yield delta
            continue
        # Buffer until we cross </think>, then yield everything after it
        if seen_think_end:
            yield delta
        else:
            buf += delta
            if "</think>" in buf:
                _, after = buf.split("</think>", 1)
                seen_think_end = True
                if after:
                    yield after
                buf = ""


# ─── self-test ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("config:")
    print(f"  base  = {API_BASE}")
    print(f"  model = {MODEL}")
    print(f"  key   = {API_KEY[:6]}…{API_KEY[-4:]}")
    print(f"  cache = {CACHE_DIR}")
    print()

    print("[1] ask() — plain")
    out = ask("Reply with the single word PONG.", use_cache=False)
    print(f"    → {out!r}")
    print()

    print("[2] ask_json() — structured")
    out = ask_json(
        "Return a JSON object with two keys: 'segment' (string=\"new_users\") "
        "and 'count' (int=2155).",
        use_cache=False,
    )
    print(f"    → {out}")
    print()

    print("[3] stream() — first 5 chunks")
    for i, chunk in enumerate(
        stream("Count from 1 to 5, one number per line.", strip_reasoning=True)
    ):
        print(f"    chunk[{i}]={chunk!r}")
        if i >= 5:
            break
    print("\nOK")
