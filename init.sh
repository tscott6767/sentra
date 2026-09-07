#!/usr/bin/env bash
# Sentra — a self-hosted household AI stack.
# Copyright (C) 2026 Tony Scott
# SPDX-License-Identifier: GPL-3.0-or-later

# init.sh — post-boot configuration for Sentra
# Injects the memory plugin (Filter + Tool) + system prompt into Open WebUI,
# and prints the remaining manual steps (router + MCP connections).
#
# The Filter/Tool injection uses the Open WebUI admin API. It is BEST-EFFORT:
# OWUI's API shifts between versions, so if a call fails the script falls back
# to printing exact manual steps. Either way you end up configured.
set -uo pipefail

OWUI_URL="${OWUI_URL:-http://localhost:3000}"
EMAIL="${OWUI_ADMIN_EMAIL:-admin@localhost.local}"
PASSWORD="${OWUI_ADMIN_PASSWORD:-change-me}"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
step() { echo -e "\n${GREEN}==> $*${NC}"; }
warn() { echo -e "${YELLOW}⚠️  $*${NC}"; }
info() { echo -e "${CYAN}   $*${NC}"; }

# ─── 1. Wait for Open WebUI ──────────────────────────────────
step "Waiting for Open WebUI at $OWUI_URL"
for i in $(seq 1 60); do
  if curl -sf -o /dev/null "$OWUI_URL/health"; then
    info "Open WebUI is up."
    break
  fi
  sleep 3
  [[ $i -eq 60 ]] && warn "Open WebUI not responding after 3 min — check 'docker compose ps'"
done

# ─── 2. Verify memory_core.py is in the data dir ─────────────
step "Verifying memory_core.py is mounted"
if docker exec sentra-openwebui test -f /app/backend/data/memory_core.py; then
  info "memory_core.py present in container."
else
  warn "memory_core.py NOT found in container — re-run build.sh (it clones the plugin)."
fi

# ─── 3. Login + inject Filter/Tool via API (best-effort) ─────
step "Attempting API injection of Filter + Tool"
TOKEN=""
LOGIN=$(curl -s -X POST "$OWUI_URL/api/v1/auths/signin" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}" 2>/dev/null || true)

if echo "$LOGIN" | grep -q '"token"'; then
  TOKEN=$(echo "$LOGIN" | grep -o '"token":"[^"]*"' | cut -d'"' -f4)
  info "Logged in as $EMAIL."
else
  warn "Could not log in automatically. If the admin account exists, run the manual steps below."
fi

create_function() {
  # $1 = name, $2 = type (filter|tool), $3 = file
  [[ -z "$TOKEN" ]] && return 1
  local name="$1" type="$2" file="$3"
  [[ -f "$file" ]] || { warn "missing $file"; return 1; }
  # Read the Python source as a JSON string (no jq dependency: python3)
  local code
  code=$(python3 -c "import json,sys; print(json.dumps(open(sys.argv[1]).read()))" "$file")
  curl -s -o /dev/null -w "%{http_code}" -X POST "$OWUI_URL/api/v1/functions/" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"$name\",\"type\":\"$type\",\"code\":$code,\"is_active\":true,\"is_global\":true}"
}

if [[ -n "$TOKEN" ]]; then
  RC1=$(create_function "Memory Filter v5.1" "filter" "memory-plugin/memory_filter.py")
  RC2=$(create_function "Memory Tool v5" "tool" "memory-plugin/memory_tool.py")
  info "Filter create HTTP $RC1 · Tool create HTTP $RC2"
  [[ "$RC1" == "200" && "$RC2" == "200" ]] \
    && info "Filter + Tool injected successfully." \
    || warn "API injection returned non-200 (Filter=$RC1 Tool=$RC2) — use the manual steps below."
else
  info "Skipped API injection (no token)."
fi

# ─── 4. Remaining manual steps (always printed) ──────────────
cat <<EOF

${CYAN}════════════════════════════════════════════════════════════${NC}
${GREEN}Sentra is up. Finish these steps in the Open WebUI admin UI:${NC}
${CYAN}════════════════════════════════════════════════════════════${NC}

${YELLOW}1 · Memory plugin (if API injection failed)${NC}
   Admin → Functions → New Filter  → name "Memory Filter v5.1"
     paste memory-plugin/memory_filter.py · Global ON · activate
   Admin → Functions → New Tool    → name "Memory Tool v5"
     paste memory-plugin/memory_tool.py · Global ON · activate

${YELLOW}2 · System prompt${NC}
   Admin → Settings → General (or per-model)
     paste core/system-prompt.md (fill in {{USER_NAME}} etc.)

${YELLOW}3 · Model router connection${NC}
   Admin → Settings → Connections → OpenAI API
     URL:  http://sentra-router:9100/v1
     Key:  <ROUTER_API_KEY from .env>
   Then add models: sentra-auto, sentra-local, sentra-cheap, sentra-std, sentra-code
     (discover via GET /v1/models on the router)

${YELLOW}4 · MCP tool servers${NC}
   Admin → Settings → Tools → Tool Servers → Add
     MCP-Filesystem:  http://mcp-filesystem:8001
     MCP-Exec:        http://mcp-exec:8004
   Attach Memory Tool v5 to your model in Workspace → Models.

${YELLOW}5 · Attach the memory Tool to your model${NC}
   Workspace → Models → edit model → enable "Memory Tool v5" in tools.

${CYAN}════════════════════════════════════════════════════════════${NC}
EOF
