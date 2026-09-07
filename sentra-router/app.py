# Sentra — a self-hosted household AI stack.
# Copyright (C) 2026 Tony Scott
# SPDX-License-Identifier: GPL-3.0-or-later

"""
Sentra Router v2 — thin FastAPI OpenAI-compatible reverse proxy.

Budget model router: routes each request to the cheapest capable tier via
heuristics (NO LLM classifier).

Endpoints:
    GET  /v1/models            — list the 5 router model ids (OWUI discovery)
    POST /v1/chat/completions  — classify -> route -> fallback -> spend log
    GET  /health               — liveness

Config: single edit point at config.json (CONFIG_PATH env). NEVER edit code
for a model/provider swap — edit config.json, re-deploy, probe.

Auth: Bearer ROUTER_API_KEY (env) on all /v1/* routes. If ROUTER_API_KEY is
unset the app runs in open dev mode (warns) until the .env is configured.
"""
import json
import os
import re
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Optional

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

CONFIG_PATH = os.environ.get("CONFIG_PATH", "/app/config.json")
ROUTER_API_KEY = os.environ.get("ROUTER_API_KEY", "")

_config: Optional[dict] = None


def cfg() -> dict:
    global _config
    if _config is None:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            _config = json.load(f)
    return _config


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def est_tokens(text: str) -> int:
    """Naive token estimate: ~4 chars/token (English). Tunable via config thresholds."""
    return max(1, len(text) // 4) if text else 0


def extract_message_text(messages: list) -> str:
    """Flatten all message content into one string for heuristic checks."""
    parts: list[str] = []
    for m in messages or []:
        c = m.get("content")
        if isinstance(c, str):
            parts.append(c)
        elif isinstance(c, list):
            for item in c:
                if isinstance(item, dict) and item.get("type") == "text":
                    parts.append(item.get("text", ""))
        elif c is None:
            for tc in m.get("tool_calls") or []:
                fn = tc.get("function") or {}
                parts.append(fn.get("name", ""))
                parts.append(str(fn.get("arguments", "")))
    return "\n".join(parts)


def prompt_tokens(body: dict) -> int:
    text = extract_message_text(body.get("messages", []))
    for m in body.get("messages", []):
        if m.get("role") == "system" and isinstance(m.get("content"), str):
            text += m["content"]
    return est_tokens(text)


def has_image(messages: list) -> bool:
    for m in messages or []:
        c = m.get("content")
        if isinstance(c, list):
            for item in c:
                if isinstance(item, dict):
                    if "image" in item.get("type", "") or "image_url" in item:
                        return True
        elif isinstance(c, str):
            if c.startswith("data:image/") or "![image]" in c:
                return True
    return False


def is_code(messages: list, clf: dict) -> bool:
    text = extract_message_text(messages).lower()
    for marker in clf.get("code_fence_markers", []):
        if marker in text:
            return True
    for kw in clf.get("code_keywords", []):
        if kw in text:
            return True
    return False


def is_internal_task(body: dict, clf: dict) -> bool:
    """OWUI internal tasks (title/tags/autocomplete): non-stream, small, JSON-ish."""
    if body.get("stream", False) is not False:
        return False
    tok = prompt_tokens(body)
    if tok > clf.get("short_chat_token_limit", 4000):
        return False
    text = extract_message_text(body.get("messages", [])).lower()
    return "json" in text


def detect_secrets(text: str, patterns: list) -> bool:
    for p in patterns:
        if re.search(p, text, re.IGNORECASE):
            return True
    return False


def has_tools(body: dict) -> bool:
    return bool(body.get("tools"))


def tier_label(tier_key: str, tier: dict) -> str:
    model = tier.get("model", "")
    if tier_key == "local":
        return "local"
    return model.split("/")[-1] if "/" in model else model


def compute_cost(usage: dict, tier: dict) -> float:
    pin = float(tier.get("price_in_usd_per_mtok", 0.0))
    pout = float(tier.get("price_out_usd_per_mtok", 0.0))
    pt = int(usage.get("prompt_tokens", 0) or 0)
    ct = int(usage.get("completion_tokens", 0) or 0)
    return round((pt / 1_000_000.0) * pin + (ct / 1_000_000.0) * pout, 8)


# ---------------------------------------------------------------------------
# Classifier
# ---------------------------------------------------------------------------

def classify(body: dict) -> tuple[str, str]:
    c = cfg()
    clf = c.get("classifier", {})
    msgs = body.get("messages", [])
    text = extract_message_text(msgs)
    tok = prompt_tokens(body)

    # 1. Privacy gate — security first, never leak secrets to cloud
    pg = c.get("privacy_gate", {})
    if pg.get("enabled", True) and detect_secrets(text, pg.get("patterns", [])):
        return "local", "privacy_gate: secrets detected → local only"

    # 2. Image → vision tier (cheap/kimi is the only multimodal tier)
    if has_image(msgs):
        return "cheap", "image content → vision tier"

    # 3. Code → coding tier
    if is_code(msgs, clf):
        return "code", "code detected → coding tier"

    # 4. Huge prompt → std (glm-5.3, 1M ctx)
    if tok > int(clf.get("large_prompt_token_limit", 150000)):
        return "std", "prompt >150K tokens → glm-5.3"

    # 5. OWUI internal task → local
    if is_internal_task(body, clf):
        return "local", "internal task (non-stream, small, JSON) → local"

    # 6. Short chat → local (tool-capable now, free)
    if tok <= int(clf.get("short_chat_token_limit", 4000)):
        return "local", "short chat → local"

    # 7. Default → cheap (kimi-k2.6)
    return "cheap", "default → cheap (kimi-k2.6)"


# ---------------------------------------------------------------------------
# Sanitizer (local tier only; dormant now that local handles tools natively)
# ---------------------------------------------------------------------------

def sanitize_messages(messages: list, scfg: dict) -> list:
    out = []
    for m in messages:
        role = m.get("role")
        if role == "tool":
            txt = scfg.get("tool_role_text", "[Tool result] {content}").replace(
                "{content}", str(m.get("content", "")))
            out.append({"role": "user", "content": txt})
        elif role == "assistant" and m.get("tool_calls"):
            content = m.get("content") or ""
            for tc in m["tool_calls"]:
                fn = tc.get("function") or {}
                content += " " + scfg.get("tool_call_text", "[Tool call: {name}({args})]").replace(
                    "{name}", fn.get("name", "")).replace("{args}", str(fn.get("arguments", "")))
            out.append({"role": "assistant",
                        "content": content or scfg.get("null_content_replacement", "")})
        elif m.get("content") is None and not m.get("tool_calls"):
            out.append({"role": role, "content": scfg.get("null_content_replacement", "")})
        else:
            out.append(m)
    return out


# ---------------------------------------------------------------------------
# SSE synthesis (local tier + fallback path)
# ---------------------------------------------------------------------------

def message_chunks(message: dict, model: str, finish_reason: str) -> list:
    """Build OpenAI-style SSE chunks from a full (non-stream) assistant message."""
    created = int(time.time())
    content = message.get("content") or ""
    tool_calls = message.get("tool_calls") or []

    first_delta: dict[str, Any] = {"role": "assistant"}
    if content:
        first_delta["content"] = content
    chunks = [{
        "id": "chatcmpl-router", "object": "chat.completion.chunk", "created": created,
        "model": model, "choices": [{"index": 0, "delta": first_delta, "finish_reason": None}],
    }]

    for i, tc in enumerate(tool_calls):
        fn = tc.get("function") or {}
        args = fn.get("arguments", "")
        if isinstance(args, dict):
            args = json.dumps(args)
        chunks.append({
            "id": "chatcmpl-router", "object": "chat.completion.chunk", "created": created,
            "model": model,
            "choices": [{"index": 0, "delta": {"tool_calls": [{
                "index": i, "id": tc.get("id", f"call_{i}"), "type": "function",
                "function": {"name": fn.get("name", ""), "arguments": args},
            }]}, "finish_reason": None}],
        })

    chunks.append({
        "id": "chatcmpl-router", "object": "chat.completion.chunk", "created": created,
        "model": model, "choices": [{"index": 0, "delta": {}, "finish_reason": finish_reason}],
    })
    return chunks


def sse_stream(chunks: list) -> AsyncIterator[bytes]:
    for ch in chunks:
        yield f"data: {json.dumps(ch)}\n\n".encode()
    yield b"data: [DONE]\n\n"


def extract_usage_from_sse_tail(tail: bytes) -> Optional[dict]:
    """Pull the last top-level 'usage' object from an SSE stream tail (OpenRouter include_usage)."""
    text = tail.decode("utf-8", "replace")
    best = None
    for line in text.split("\n"):
        line = line.strip()
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if not payload or payload == "[DONE]":
            continue
        try:
            obj = json.loads(payload)
        except Exception:
            continue
        if obj.get("usage"):
            best = obj["usage"]
    return best


# ---------------------------------------------------------------------------
# Spend log
# ---------------------------------------------------------------------------

def write_spend(log_dir: str, entry: dict) -> None:
    try:
        os.makedirs(log_dir, exist_ok=True)
        with open(os.path.join(log_dir, "spend.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass  # logging must never break the response


# ---------------------------------------------------------------------------
# App + auth
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.client = httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0))
    if not ROUTER_API_KEY:
        print("WARNING: ROUTER_API_KEY unset — running in open dev mode.")
    yield
    await app.state.client.aclose()


app = FastAPI(lifespan=lifespan, title="Sentra Router v2")


def check_auth(request: Request) -> bool:
    if not ROUTER_API_KEY:
        return True
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:].strip() == ROUTER_API_KEY
    return False


def _upstream_headers(tier: dict) -> dict:
    h = {"Content-Type": "application/json", "Accept": "application/json"}
    key_env = tier.get("api_key_env")
    if key_env:
        key = os.environ.get(key_env, "")
        auth_type = tier.get("auth_type", "bearer")
        if auth_type == "bearer":
            h["Authorization"] = f"Bearer {key}"
        elif auth_type == "x-api-key":
            h["x-api-key"] = key
    return h


def _upstream_body(body: dict, tier: dict, stream: bool) -> dict:
    b = dict(body)
    b["model"] = tier["model"]
    b["stream"] = stream
    if tier.get("stream_usage") and stream:
        b.setdefault("stream_options", {"include_usage": True})
    return b


# ---------------------------------------------------------------------------
# Routing / fallback core
# ---------------------------------------------------------------------------

def _notice(routed: str, served: str) -> str:
    return f"[router: {routed} down → served by {tier_label(served, cfg()['tiers'][served])}]"


def _inject_notice(resp_json: dict, notice: str) -> dict:
    choices = resp_json.get("choices", [{}])
    if choices:
        msg = choices[0].setdefault("message", {})
        existing = msg.get("content") or ""
        msg["content"] = (notice + "\n\n" + existing) if existing else notice
    return resp_json


@app.get("/health")
async def health():
    return {"status": "ok", "service": "sentra-router-v2"}


@app.get("/v1/models")
async def list_models(request: Request):
    if not check_auth(request):
        return JSONResponse(status_code=401, content={"error": {"message": "invalid or missing API key"}})
    data = [{
        "id": alias, "object": "model", "created": int(time.time()), "owned_by": "sentra-router",
    } for alias in cfg()["model_aliases"].keys()]
    return {"object": "list", "data": data}


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    if not check_auth(request):
        return JSONResponse(status_code=401, content={"error": {"message": "invalid or missing API key"}})

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": {"message": "invalid JSON body"}})

    c = cfg()
    client: httpx.AsyncClient = request.app.state.client
    start = time.time()

    # 1. Privacy gate — always first, overrides forced tier + classifier (never leak to cloud)
    pg = c.get("privacy_gate", {})
    privacy = pg.get("enabled", True) and detect_secrets(
        extract_message_text(body.get("messages", [])), pg.get("patterns", []))

    # 2. Forced-tier passthrough (sentra-local/cheap/std/code) OR classifier (sentra-auto)
    if privacy:
        routed_tier, reason = "local", "privacy_gate: secrets detected → local only"
    else:
        alias = c.get("model_aliases", {}).get(body.get("model", "sentra-auto"), {})
        route = alias.get("route", "auto")
        if route == "auto":
            routed_tier, reason = classify(body)
        else:
            routed_tier, reason = route, f"forced tier ({body.get('model')})"

    chain = [routed_tier] + list(c.get("fallback_chains", {}).get(routed_tier, []))
    if privacy:
        chain = ["local"]  # secrets detected: local only, NEVER cloud fallback

    want_stream = bool(body.get("stream", False))
    request_has_tools = has_tools(body)
    errors: list[str] = []
    served_tier: Optional[str] = None
    upstream_usage: Optional[dict] = None
    last_resp_json: Optional[dict] = None

    for i, tier_key in enumerate(chain):
        tier = c["tiers"][tier_key]
        is_fallback = i > 0

        # tools-attached guard: never serve a tool request from a non-tool tier
        if request_has_tools and not tier.get("capabilities", {}).get("tools", False):
            errors.append(f"{tier_key}: not tool-capable (skipped)")
            continue

        # sanitizer: only for tiers explicitly listed (dormant by default)
        up_msgs = body.get("messages", [])
        if tier_key in c.get("sanitizer", {}).get("tiers", []):
            up_msgs = sanitize_messages(up_msgs, c["sanitizer"])
        up_body = dict(body)
        up_body["messages"] = up_msgs

        # local tier + fallback paths: non-stream upstream -> synthesize SSE later
        non_stream_upstream = (tier_key == "local") or is_fallback
        headers = _upstream_headers(tier)

        try:
            if not non_stream_upstream and want_stream:
                # cloud first-attempt streaming: byte-passthrough
                req = client.build_request(
                    "POST", tier["base_url"] + "/chat/completions",
                    json=_upstream_body(up_body, tier, True), headers=headers)
                resp = await client.send(req, stream=True)
                if resp.status_code != 200:
                    err = (await resp.aread()).decode("utf-8", "replace")
                    errors.append(f"{tier_key}: HTTP {resp.status_code} {err[:200]}")
                    await resp.aclose()
                    continue
                served_tier = tier_key
                notice = _notice(routed_tier, tier_key) if is_fallback else None

                stream_ctx: dict = {"usage": None}

                async def passthrough():
                    tail = b""
                    async for chunk in resp.aiter_bytes():
                        yield chunk
                        tail = (tail + chunk)[-16384:]
                    stream_ctx["usage"] = extract_usage_from_sse_tail(tail)
                    write_spend(c["router"]["spend_log_dir"], _spend_entry(
                        body, routed_tier, tier_key, stream_ctx["usage"], start, reason, is_fallback))

                return StreamingResponse(passthrough(), status_code=200, media_type="text/event-stream")

            else:
                # non-stream upstream (local, or fallback, or client didn't want stream)
                resp = await client.post(
                    tier["base_url"] + "/chat/completions",
                    json=_upstream_body(up_body, tier, False), headers=headers)
                if resp.status_code != 200:
                    errors.append(f"{tier_key}: HTTP {resp.status_code} {resp.text[:200]}")
                    continue
                resp_json = resp.json()
                served_tier = tier_key
                upstream_usage = resp_json.get("usage") or {}
                last_resp_json = resp_json
                break
        except httpx.TimeoutException:
            errors.append(f"{tier_key}: timeout")
        except httpx.ConnectError as e:
            errors.append(f"{tier_key}: connect failed ({e})")
        except Exception as e:
            errors.append(f"{tier_key}: {type(e).__name__}: {e}")

    # All tiers failed
    if served_tier is None:
        write_spend(c["router"]["spend_log_dir"], _spend_entry(
            body, routed_tier, None, None, start, reason, False, errors=errors))
        if privacy:
            return JSONResponse(status_code=403, content={"error": {
                "message": "router: secrets detected in prompt and local tier unavailable — "
                           "request denied to protect credentials (never sent to cloud).",
                "type": "privacy_deny", "errors": errors}})
        return JSONResponse(status_code=502, content={"error": {
            "message": f"router: all tiers failed (tried {chain}). Reasons: {errors}. "
                       "Check backend status / API keys.",
            "type": "router_total_failure", "chain_tried": chain,
            "errors": errors, "routing_reason": reason}})

    # Success path (non-stream upstream, or fallback notice injection)
    notice = _notice(routed_tier, served_tier) if served_tier != routed_tier else None
    if notice and last_resp_json is not None:
        last_resp_json = _inject_notice(last_resp_json, notice)

    write_spend(c["router"]["spend_log_dir"], _spend_entry(
        body, routed_tier, served_tier, upstream_usage, start, reason, served_tier != routed_tier))

    finish_reason = "stop"
    if last_resp_json is not None:
        choices = last_resp_json.get("choices", [{}])
        finish_reason = choices[0].get("finish_reason") or "stop"

    if want_stream:
        message = (last_resp_json or {}).get("choices", [{}])[0].get("message", {})
        model = c["tiers"][served_tier]["model"]
        return StreamingResponse(sse_stream(message_chunks(message, model, finish_reason)),
                                 status_code=200, media_type="text/event-stream")
    return JSONResponse(status_code=200, content=last_resp_json)


def _spend_entry(body, routed, served, usage, start, reason, fallback, errors=None) -> dict:
    c = cfg()
    tier = c["tiers"].get(served) if served else None
    entry = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "request_model": body.get("model"),
        "routed_tier": routed,
        "served_tier": served,
        "upstream_model": tier.get("model") if tier else None,
        "routing_reason": reason,
        "fallback": fallback,
        "latency_ms": int((time.time() - start) * 1000),
        "prompt_tokens": (usage or {}).get("prompt_tokens"),
        "completion_tokens": (usage or {}).get("completion_tokens"),
        "cost_usd": compute_cost(usage or {}, tier) if (tier and usage) else None,
        "status": "ok" if served else "failed",
        "errors": errors or [],
    }
    return entry
