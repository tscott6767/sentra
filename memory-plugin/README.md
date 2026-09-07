# Memory & Knowledge Plugin (v5.2)

This directory is the **vendored** source of the standalone
[persistent-memory-knowledge-Openwebui](https://github.com/tscott6767/persistent-memory-knowledge-Openwebui)
repo. `build.sh` clones it here if missing.

## What lives here

| File | Role |
|------|------|
| `memory_core.py` | Shared core — SQLite schema, bge-m3 embeddings, search, storage, Obsidian sync |
| `memory_filter.py` | Filter: inlet auto-recall + outlet auto-store (with pattern tagging) |
| `memory_tool.py` | Tool: model-callable memory/knowledge/source operations |
| `migrate_v5.py` | Schema check + function cleanup + core installation |
| `install.sh` | Standalone installer (for bare-metal / non-compose installs) |

## How it's wired in this repo

1. `openwebui/Dockerfile` installs `numpy`, `sentence-transformers`, `tiktoken`
   (the memory plugin's runtime deps) into the Open WebUI image.
2. `docker-compose.yml` bind-mounts `memory_core.py` into the OWUI data dir.
3. `init.sh` injects the Filter + Tool functions and the system prompt.

## Important note

The Filter + Tool are **Open WebUI "functions"** — they're pasted/injected into the
OWUI admin panel, not standalone services. `init.sh` automates this via the OWUI API;
if that fails (version drift), the manual steps are printed by `init.sh`.

See the standalone repo's README for the full architecture and tool reference.
