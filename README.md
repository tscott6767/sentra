# Sentra

A self-hosted household AI stack — memory, model routing, and tools, wired together by a protocol.

**Sentra** is one name for three things: the wake word, the conversational persona, and the stack brand. The thin custom layer we build and own is called the **Sentra core**.

---

## Read this first — what this repo actually is

Sentra is **not** a single turnkey product. It's three layers, and only the first two are shipped:

| Tier | What it is | Status |
|------|-----------|--------|
| **1 · Software** | Dockerized services: memory, model router, MCP filesystem, exec sandbox | ✅ Shipped — works out of the box |
| **2 · Protocol** | Ralph Loop job-card template + system prompt + this schema | ✅ Shipped — config files, no code |
| **3 · Roadmap** | Orchestrator sidecar (autonomous loop runner, safety gates, audit diary) | 🚧 Not built yet |

**The honest bottom line:** cloning this repo gives you **memory + routing + tools + a protocol**. It does *not* give you a fully autonomous agent — the loop runner that executes Ralph jobs end-to-end is the roadmap item (see `core/SPEC.md` §6).

---

## What's inside

```
sentra/
├── docker-compose.yml      # memory + router + MCP + exec (Tier 1)
├── build.sh                # one-command bring-up
├── init.sh                 # injects Filter + Tool + system prompt via OWUI API
├── .env.example            # OPENROUTER_API_KEY, admin password
├── core/                   # Tier 2 — the protocol layer
│   ├── SPEC.md             # this system schema (canonical reference)
│   ├── ralph-loop.md       # Ralph Loop v1.2 job-card template
│   └── system-prompt.md    # Sentra persona + memory protocol + guardrails
├── memory-plugin/          # memory + knowledge system v5.2
├── sentra-router/          # budget model router (FastAPI)
└── mcp-exec/               # server-side code-execution sandbox
```

---

## Quick start (cloud-only)

```bash
git clone https://github.com/tscott6767/sentra && cd sentra
cp .env.example .env
./build.sh
# → Sentra is up: http://localhost:3000
```

Cloud-only needs just an OpenRouter key. Local LLM (llama.cpp + NVIDIA GPU) is opt-in via `.env` + a compose override — see `docs/local-llm.md` (roadmap).

Then finish the **Post-install setup** below (set keys, create the admin account, add the memory plugin + tools).

---

## Post-install setup (first run, ~10 min)

`build.sh` brings up the stack, but a few steps are manual. Do them once, in your browser.

### 1. Open the web UI

```bash
hostname -I        # inside the container — get its IP
```

Browse to `http://<IP>:3000` from any device on your network.

### 2. Create the admin account

The first user you create becomes admin — there's no pre-set login. Just sign up.

### 3. Set your keys

```bash
openssl rand -hex 24          # → use as ROUTER_API_KEY
nano .env                     # set ROUTER_API_KEY + OPENROUTER_API_KEY
docker compose up -d          # restart to apply
```

### 4. Add the memory plugin (Filter + Tool)

The Filter and Tool live in **different places** in the Open WebUI UI:

| What | Paste this file | Into |
|------|-----------------|------|
| Memory Filter | `memory-plugin/memory_filter.py` | Admin → Functions → New Filter |
| Memory Tool | `memory-plugin/memory_tool.py` | Workspace → Tools → New Tool |

```bash
cat memory-plugin/memory_filter.py   # copy → paste into Admin → Functions
cat memory-plugin/memory_tool.py     # copy → paste into Workspace → Tools
```

Enable **Global** + activate on each.

### 5. System prompt

Paste `core/system-prompt.md` into **Admin → Settings → General** (fill in `{{USER_NAME}}` etc.).

### 6. Connect the model router

**Admin → Settings → Connections → OpenAI API**:
- URL: `http://sentra-router:9100/v1`
- Key: your `ROUTER_API_KEY` from `.env`

Then add models `sentra-auto`, `sentra-local`, `sentra-cheap`, `sentra-std`, `sentra-code`.

### 7. Add the MCP tool servers

**Admin → Settings → Tools → Tool Servers → Add**:
- MCP-Filesystem: `http://mcp-filesystem:8001`
- MCP-Exec: `http://mcp-exec:8004`

### 8. Attach the Memory Tool to your model

**Workspace → Models → edit your model → enable "Memory Tool v5"**.

> The hostnames `sentra-router`, `mcp-filesystem`, `mcp-exec` resolve only inside
> the Docker network (`sentra-net`) — that's why they work from Open WebUI without
> needing IPs.

---

## The three tiers, explained

### Tier 1 — Software (shipped)

The parts that run as containers today:

- **Memory + knowledge v5.2** — SQLite + `bge-m3` embeddings, semantic gated recall, auto-store/auto-recall, source policies, Obsidian sync. Runs as an Open WebUI Filter + Tool pair.
- **Sentra Router** — a thin FastAPI reverse proxy that routes each request to a model tier (local / cheap / standard / coding) by capability and budget.
- **MCP filesystem** — the official `@modelcontextprotocol/server-filesystem`, no custom code.
- **MCP-exec sandbox** — server-side code execution (Python/JS/shell) with allowlist, timeout, and rlimits.

### Tier 2 — Protocol (shipped)

Not code — the rules that make the stack behave:

- **Ralph Loop v1.2** — a job-card protocol for running projects safely: confirm → lock → loop → gates → VERIFIED exit. See `core/ralph-loop.md`.
- **System prompt** — the Sentra persona, the memory-storage protocol (when to persist facts), and the guardrails. See `core/system-prompt.md`.
- **SPEC.md** — this schema; the single reference for what Sentra is and isn't.

### Tier 3 — Roadmap (not built)

The part that makes Sentra *autonomous* rather than *assisted*:

- **Orchestrator sidecar** — runs Ralph loops end-to-end without a human in the loop.
- **Safety gates** — deterministic halt-before-irreversible-action checks.
- **Audit diary** — a tamper-evident log of what the system did and why.
- **Budget model-router (L6)** — hard spend-cap enforcement on top of the current routing.

These are deliberately deferred. Until they ship, Sentra is a **copilot with strong memory and tools**, not a fully autonomous agent.

---

## Design doctrine

**Adopt, don't build.** Agentic tooling moves too fast to hand-build. Sentra builds only the core and adopts standard projects (Home Assistant, Frigate, Wyoming voice, Immich, paperless-ngx, Vaultwarden, Jellyfin) as swappable parts over standard protocols (MCP, MQTT/webhooks, OpenAI-compatible APIs).

See `core/SPEC.md` for the full schema, layer model, and component status.

---

## License

GPL-3.0 — see `LICENSE`.
