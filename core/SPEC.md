# Sentra — System Schema

**Version:** 1.0 · September 6, 2026
**Status:** Doctrine and architecture LOCKED · software seats shipped · orchestrator sidecar on roadmap
**Scope:** Public, self-contained reference for the Sentra household AI stack. This is the canonical schema — every component, its type (software / protocol / roadmap), and its current state.

---

## 1. Identity & Goal

- **System name / wake word:** Sentra — one name for the wake word, the conversational persona, and the stack brand.
- **The Sentra core** = the thin custom orchestration layer we build and own: memory system, Ralph Loop protocol, MCP glue, and (on the roadmap) the orchestrator sidecar with safety gates, audit diary, and budget model-router.
- **Goal:** a long-term, open-source, self-hosted AI stack for family + SOHO use — controlled and grown by the maintainer, published as a public GitHub repo. In one phrase: **a domestic/SOHO Claude Code with broader options and usability.**
- **NOT the goal:** a globally top-ranked harness. Accepted honest ceiling: competitive with leading open-source harnesses on memory architecture, state-outside-chat, and local-first integration — not competing with frontier products on public benchmarks.
- **Dominant risk:** maintenance sustainability. Every decision must minimise long-term upkeep.

---

## 2. Doctrine — Adopt, Don't Build

Agentic tooling moves too fast to hand-build. We build only the **core** and adopt standard projects as **swappable parts** wired over standard protocols (MCP, MQTT/webhooks, OpenAI-compatible APIs). The core defines the contract; any project that speaks the protocol can fill a seat; a better project replaces a part without touching the core.

### We build & own — the Sentra core

| Component | Type | Status |
|---|---|---|
| Memory + knowledge system (v5.2: SQLite + bge-m3, semantic gated recall) | software | ✅ Shipped |
| Ralph Loop protocol v1.2 (job cards: confirm → lock → loop → gates → VERIFIED exit) | protocol | ✅ Shipped (`ralph-loop.md`) |
| MCP glue: mcpo filesystem server + MCP-exec sandbox | software | ✅ Shipped |
| System prompt (persona + memory protocol + guardrails) | protocol | ✅ Shipped (`system-prompt.md`) |
| Orchestrator sidecar: loop engine, safety gates, audit diary, model router | software | 🚧 Roadmap |
| Safety rules + cloud budget-cap enforcement (L1/L6) | logic | 🚧 Roadmap (with sidecar) |

### We adopt & may swap — the parts

| Seat | Leading candidate |
|---|---|
| Execution engine (Ralph worker) | Hermes Agent (pilot; OpenClaw on watch list) |
| Home automation hub | Home Assistant (chosen over Domoticz — ecosystem size: Wyoming voice, LLM integration, Frigate hooks, ESPHome) |
| CCTV + AI detection | Frigate |
| Voice satellites ("Sentra") | Wyoming protocol stack + HA; ESP32-S3 or Pi hardware; locally trained wake word |
| Photo library | Immich (or Nextcloud) |
| Paperwork OCR | paperless-ngx |
| Password vault | Vaultwarden |
| Media server | Jellyfin |
| Local compute | llama.cpp (multi-GPU) |
| Cloud fallback | OpenRouter, hard-capped monthly spend |

---

## 3. Layer Model

```
CHANNELS  Open WebUI web · Telegram (L5) · Sentra voice satellites · ntfy alerts
              \      |      /
       SENTRA CORE ORCHESTRATOR (sidecar)
       Ralph protocol · gates · audit diary · L6 budget router
          |           |            |            |
      Memory v5.2   MCP tools    Home Assistant  Frigate CCTV
      (core)        (sandbox)    (MQTT/webhooks) (events → HA)
          |
       ENGINES: local llama.cpp ⇄ OpenRouter (capped) ⇄ agentic engines (Hermes pilot)
```

---

## 4. Ralph vs engines — the critical design rule

Ralph is a **protocol** (a job card), not software. Engines are the **workers**. The engine works *under* Ralph, never instead of it:

1. The filled-in Ralph card becomes the standing instructions of the engine session.
2. Spec, progress notes, and code live on the shared filesystem.
3. Engine memory stays **disabled** — memory v5.2 is the single source of truth.
4. Gates force a halt + ask the maintainer at: delete/overwrite · irreversible actions · same step failing twice · spec deviation.
5. Exit criteria must be **verified, not claimed** — machine output is evidence; engine confidence is not.

**Pilot (post-roadmap):** (a) Hermes-under-Ralph vs (b) plain local model + MCP tools in our own sidecar loop. Judge on: least custom glue · crash-resume behaviour · gate compliance · cost.

---

## 5. Capability domains → owners

| Domain | Owner |
|---|---|
| Memory, knowledge, context | Core (ours) |
| Research reports (L4) | Core glue (templates) + engines |
| Coding (L3) | Ralph + engine + MCP-exec sandbox |
| Autonomous jobs (L2) | Ralph + sidecar loop engine |
| Self-maintenance | Fleet health → gated remediation via sidecar |
| Home automation | Home Assistant (part) |
| CCTV | Frigate (part) |
| Voice satellites | Wyoming/HA stack (part) |
| Business | Basix CRM (existing app) |

---

## 6. Component status — shipped vs roadmap

### Shipped today (works out of the box)

| Component | Where it lives in this repo |
|---|---|
| Memory + knowledge v5.2 | `memory-plugin/` (Filter + Tool + core + installer) |
| Sentra Router (budget model router) | `sentra-router/` (FastAPI, Dockerfile) |
| MCP filesystem server | official `@modelcontextprotocol/server-filesystem` (no custom code) |
| MCP-exec sandbox | `mcp-exec/` (FastMCP server + Dockerfile) |
| Ralph Loop protocol v1.2 | `core/ralph-loop.md` |
| System prompt (persona + protocol) | `core/system-prompt.md` |

### Roadmap (not built — do not expect these in a clone)

| Component | Why it's not here yet |
|---|---|
| Orchestrator sidecar (loop engine) | Post-roadmap build — runs Ralph loops autonomously |
| Safety gates (L1) | Enforced by the sidecar; today enforced by the system prompt + human |
| Audit diary | Minimal version in scope; full version with the sidecar |
| Budget model-router (L6) | Today: the router routes; hard spend-cap enforcement is with the sidecar |

> **Honest framing:** a clone of this repo gives you **memory + routing + tools + a protocol**, not a fully autonomous agent. The autonomous loop runner is the roadmap item.

---

## 7. Governance & maintenance

- **Swap rule:** a better project replaces the part; the core is untouched. Review seats ~quarterly.
- Thin glue only. Adopt Open WebUI upstream features instead of duplicating. Pin versions with a backup/rollback procedure.
- Document everything for hand-off — a non-original maintainer must be able to follow it.
- Update the roadmap on every decision or supersession.

---

## 8. References

- Ralph Loop template: `core/ralph-loop.md`
- System prompt: `core/system-prompt.md`
- Router spec: `sentra-router/SPEC.md`
- Memory plugin: `memory-plugin/README.md`
