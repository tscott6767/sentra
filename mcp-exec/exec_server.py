#!/usr/bin/env python3
# Sentra — a self-hosted household AI stack.
# Copyright (C) 2026 Tony Scott
# SPDX-License-Identifier: GPL-3.0-or-later

"""MCP-Exec sandbox server — runs allowlisted files from the sandbox directory.

Runs under mcpo (HTTP bridge). Replaces client-session-bound code execution
with durable, server-side execution inside the sandbox container.

One tool:

    run(path, args="") -> str
        path : relative to SANDBOX_DIR (realpath containment enforced)
        args : optional, shlex-split, appended to argv (no shell involved)
        .py -> python3 · .js -> node · .sh → bash (extension allowlist)

        60s wall timeout (process-group SIGKILL on expiry)
        rlimits: CPU 55s · AS 4GB · fsize 256MB · nofile 64
        cwd = SANDBOX_DIR, output truncated at 1MB

Returns raw machine output: "EXIT:n" / "--- STDOUT ---" / "--- STDERR ---".
Never "it worked" — the caller reads the evidence.
"""

import os
import shlex
import shutil
import signal
import subprocess

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:  # fallback if only the standalone fastmcp package is present
    from fastmcp import FastMCP

SANDBOX = os.environ.get("SANDBOX_DIR", "/sandbox")
TIMEOUT_S = 60
MAX_OUT_CHARS = 1_000_000

RUNTIMES = {
    ".py": "python3",
    ".js": "node",
    ".sh": "bash",
}

mcp = FastMCP("exec-sandbox")


def _clip(text: str) -> str:
    if len(text) > MAX_OUT_CHARS:
        return text[:MAX_OUT_CHARS] + "\n[... output truncated at 1MB ...]"
    return text


def _limits():
    """Guardrails for sandboxed children — applied in the child pre-exec."""
    import resource

    resource.setrlimit(resource.RLIMIT_CPU, (55, 55))                 # runaway loops
    resource.setrlimit(resource.RLIMIT_FSIZE, (256 << 20, 256 << 20))  # 256MB per file
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    resource.setrlimit(resource.RLIMIT_AS, (4 << 30, 4 << 30))         # node needs ~2GB VA


@mcp.tool()
def run(path: str, args: str = "") -> str:
    """Execute a file inside the sandbox (.py/.js/.sh only).
    Returns EXIT code, STDOUT and STDERR as raw text."""
    resolved = os.path.realpath(os.path.join(SANDBOX, path))
    try:
        if os.path.commonpath([resolved, SANDBOX]) != SANDBOX:
            return "ERROR: path escapes sandbox"
    except ValueError:
        return "ERROR: path escapes sandbox"
    if not os.path.isfile(resolved):
        return "ERROR: file not found: {}".format(path)
    ext = os.path.splitext(resolved)[1].lower()
    runtime = RUNTIMES.get(ext)
    if runtime is None:
        return "ERROR: extension '{}' not allowed (use .py/.js/.sh)".format(ext)
    exe = shutil.which(runtime)
    if exe is None:
        return "ERROR: runtime '{}' not found on PATH".format(runtime)

    argv = [exe, resolved] + (shlex.split(args) if args else [])
    try:
        p = subprocess.Popen(
            argv,
            cwd=SANDBOX,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            preexec_fn=_limits,
            start_new_session=True,
        )
    except Exception as e:
        return "ERROR: spawn failed: {!r}".format(e)
    try:
        out, err = p.communicate(timeout=TIMEOUT_S)
        return (
            "EXIT:{}\n--- STDOUT ---\n{}\n--- STDERR ---\n{}".format(
                p.returncode, _clip(out), _clip(err)
            )
        )
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(p.pid), signal.SIGKILL)
        except Exception:
            pass
        try:
            out, err = p.communicate(timeout=5)
        except Exception:
            out, err = "", ""
        return (
            "ERROR: timeout ({}s) — process group killed\n"
            "--- partial STDOUT ---\n{}\n--- partial STDERR ---\n{}".format(
                TIMEOUT_S, _clip(out), _clip(err)
            )
        )


if __name__ == "__main__":
    mcp.run()
