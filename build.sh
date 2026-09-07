#!/usr/bin/env bash
# Sentra — a self-hosted household AI stack.
# Copyright (C) 2026 Tony Scott
# SPDX-License-Identifier: GPL-3.0-or-later

# build.sh — one-command bring-up for Sentra (Docker)
# Usage: ./build.sh
set -euo pipefail

cd "$(dirname "$0")"

log() { echo -e "\n\033[1;32m==> $*\033[0m"; }
warn() { echo -e "\033[1;33m⚠️  $*\033[0m"; }
die() { echo -e "\033[1;31mERROR: $*\033[0m" >&2; exit 1; }

# ─── 1. Preflight ────────────────────────────────────────────
log "Preflight checks"
command -v docker >/dev/null 2>&1 || die "docker not found — install Docker first"
docker compose version >/dev/null 2>&1 || die "docker compose plugin not found"
docker info >/dev/null 2>&1 || die "docker daemon not running — start it and retry"

# ─── 2. .env ─────────────────────────────────────────────────
if [[ ! -f .env ]]; then
  cp .env.example .env
  log "Created .env from .env.example"
fi
if grep -q 'OPENROUTER_API_KEY=sk-or-v1-xxxxxxxx' .env 2>/dev/null; then
  warn "OPENROUTER_API_KEY is still the placeholder — cloud tiers won't work until you set a real key in .env"
fi
if grep -q 'ROUTER_API_KEY=change-me' .env 2>/dev/null; then
  warn "ROUTER_API_KEY is still 'change-me' — set it to a random string (openssl rand -hex 24)"
fi

# ─── 3. Memory plugin (clone if missing) ─────────────────────
if [[ ! -f memory-plugin/memory_core.py ]]; then
  log "Cloning memory plugin (persistent-memory-knowledge-Openwebui)"
  TMP="$(mktemp -d)"
  git clone --depth 1 https://github.com/tscott6767/persistent-memory-knowledge-Openwebui.git "$TMP" \
    || die "failed to clone memory plugin repo"
  cp "$TMP"/memory_core.py "$TMP"/memory_filter.py "$TMP"/memory_tool.py "$TMP"/migrate_v5.py memory-plugin/
  rm -rf "$TMP"
else
  log "Memory plugin already present (memory-plugin/memory_core.py)"
fi

# ─── 4. Shared data dirs ─────────────────────────────────────
mkdir -p data/sandbox
log "Ensured data/sandbox exists (shared project dir + exec sandbox)"

# ─── 5. Build + up ───────────────────────────────────────────
log "Building images and starting containers"
docker compose up -d --build

# ─── 6. Post-boot config ─────────────────────────────────────
log "Running post-boot config (init.sh)"
./init.sh
