"""OpenAI, for the one call that plans a video's story (story.py).

Why OpenAI here and Claude elsewhere: sarah's course (COMS E6998, Fall 2026)
gave her team an OpenAI key with a $25 budget for the whole term, and she
asked for the editing to run on it (2026-10-18). So the call is small: one
request per video, index frames at OpenAI's "low" detail, a cheap model, and
the price of every call is worked out from its usage and kept with the
project.

The key lives only in web/.env on the creator's Mac (OPENAI_API_KEY; the
course forbids committing it or putting it in frontend code). Having a key
is not the same as agreeing to spend it: the AI switch in the app (sarah,
2026-10-18: "an ai button that turns on and off ... calculates how much is
spent for that edit before i proceed") is off until she turns it on, kept
in $VIBECUT_CACHE/ai.json, and even then each edit shows its estimate first
and only the Make that carries that estimate calls the model.

Plain urllib, no SDK: pip installs are blocked on her Mac.
"""

from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

from . import indexer

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
URL = "https://api.openai.com/v1/chat/completions"
MODEL = "gpt-6.1-sol"
# USD per 1M tokens (input, cached input, output), from OpenAI's price list
# as of 2026-10-15 [check before trusting a bill]. Unknown models are priced
# at the dearest row, so an estimate never comes out low.
PRICES = {"gpt-6.1-sol": (2.00, 0.10, 10.00), "gpt-6-luna": (0.10, 0.01, 0.50)}
DEAREST = (2.00, 0.10, 10.00)
TIMEOUT_S = 180


class OAIError(Exception):
    pass


def _env(name: str) -> str | None:
    if os.environ.get(name):
        return os.environ[name]
    try:
        lines = ENV_FILE.read_text().splitlines()
    except OSError:
        return None
    for line in lines:
        k, _, v = line.strip().partition("=")
        if k.strip() == name and v:
            return v.strip().strip("'\"")
    return None


def has_key() -> bool:
    return bool(_env("OPENAI_API_KEY"))


def _switch() -> Path:
    return indexer.CACHE / "ai.json"


def switched_on() -> bool:
    try:
        return bool(json.loads(_switch().read_text()).get("on"))
    except (OSError, ValueError, AttributeError):
        return False


def switch(on: bool) -> None:
    _switch().parent.mkdir(parents=True, exist_ok=True)
    _switch().write_text(json.dumps({"on": bool(on)}))


def enabled() -> bool:
    """A key, and the AI switch on. Each edit still shows its cost first."""
    return has_key() and switched_on()


def model() -> str:
    return _env("OPENAI_MODEL") or MODEL


def cost(usage: dict, name: str | None = None) -> float:
    """Dollars for one call's `usage` (chat completions shape)."""
    p_in, p_cached, p_out = PRICES.get(name or model(), DEAREST)
    prompt = int(usage.get("prompt_tokens") or 0)
    cached = int((usage.get("prompt_tokens_details") or {}).get("cached_tokens") or 0)
    out = int(usage.get("completion_tokens") or 0)
    return ((prompt - cached) * p_in + cached * p_cached + out * p_out) / 1e6


def image(jpeg: bytes) -> dict:
    return {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(jpeg).decode(),
                                               "detail": "low"}}


def ask_json(system: str, content: list[dict], schema: dict, name: str, max_tokens: int = 12000,
             post=None) -> tuple[dict, dict]:
    """One request whose answer must match `schema`. -> (answer, usage with
    `cost` and `model` added). `post(url, body, headers) -> dict` stands in
    for the network in tests."""
    key = _env("OPENAI_API_KEY")
    if not key:
        raise OAIError("no OpenAI key in web/.env")
    body = {"model": model(), "max_completion_tokens": max_tokens,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": content}],
            "response_format": {"type": "json_schema", "json_schema": {"name": name, "strict": True, "schema": schema}}}
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    resp = (post or _post)(URL, body, headers)
    usage = dict(resp.get("usage") or {})
    usage["model"] = resp.get("model") or body["model"]
    usage["cost"] = round(cost(usage, body["model"]), 4)
    choice = (resp.get("choices") or [{}])[0]
    msg = choice.get("message") or {}
    if msg.get("refusal"):
        raise OAIError("the model declined: " + str(msg["refusal"])[:120])
    if choice.get("finish_reason") == "length":
        raise OAIError("the model's answer was cut off")
    try:
        return json.loads(msg.get("content") or ""), usage
    except json.JSONDecodeError as e:
        raise OAIError("the model's answer wasn't valid JSON") from e


def _post(url: str, body: dict, headers: dict) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            why = json.loads(e.read()).get("error", {}).get("message", "")
        except Exception:  # noqa: BLE001
            why = ""
        if e.code == 401:
            raise OAIError("OpenAI rejected the key in web/.env") from e
        if e.code == 429:
            raise OAIError("OpenAI says the key is out of budget or rate-limited" + (f": {why[:120]}" if why else "")) from e
        raise OAIError(f"OpenAI error {e.code}" + (f": {why[:160]}" if why else "")) from e
    except (urllib.error.URLError, TimeoutError) as e:
        raise OAIError("couldn't reach OpenAI") from e
