# Local LLM Tier (opt-in)

The Sentra router has four model tiers. Three are cloud (OpenRouter) and work
with just an `OPENROUTER_API_KEY`. The fourth — **local** — is optional and
runs on your own hardware via [llama.cpp](https://github.com/ggml-org/llama.cpp).

> **You don't need this.** Cloud-only is the default and works everywhere.
> Add the local tier only if you want free, private inference on a machine
> with an NVIDIA GPU.

---

## How the local tier works

The router classifies each request and can send it to the local tier for:
- **Short chat** (≤ ~4000 tokens) — free, private
- **Privacy-gated content** — anything matching the secret-detection patterns
  is *forced* local and never sent to cloud
- **OWUI internal tasks** (titles, tags, autocomplete) — free

If the local tier is unreachable, the router falls back to `cheap` → `std`
automatically. So a broken/missing local tier degrades gracefully.

## Requirements

- NVIDIA GPU
- [`nvidia-container-toolkit`](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html) on the host
- A GGUF model file (e.g. Qwen3, Llama, Mistral) in `./models/`

Verify the toolkit before you start:

```bash
docker run --rm --gpus all nvidia/cuda:12.0.0-base-ubuntu22.04 nvidia-smi
```

## Option A — llama.cpp as a Docker service (recommended)

Uses the prebuilt override file `docker-compose.llama.yml`.

```bash
# 1. Download a GGUF model into ./models/
mkdir -p models
#    e.g. huggingface-cli download Qwen/Qwen3-8B Qwen3-8B-Q4_K_M.gguf --local-dir models/

# 2. Point the router's local tier at the llama-server container.
#    Edit sentra-router/config.json → tiers.local:
#      "base_url": "http://llama-server:8080/v1",
#      "model": "/models/<your-model>.gguf",

# 3. Bring up both compose files:
docker compose -f docker-compose.yml -f docker-compose.llama.yml up -d --build
```

The `-ngl 99` flag offloads all layers to GPU. Lower it if you hit VRAM limits.

## Option B — llama.cpp on the host (no container)

If you already run `llama-server` directly on the host machine:

```bash
# On the host:
llama-server -m /path/to/model.gguf --host 0.0.0.0 --port 8080 -ngl 99
```

Then point the router's local tier at the host from inside the container.
Because the router runs in Docker, `localhost` won't reach the host — use
`host.docker.internal` (macOS/Windows) or the host's LAN IP (Linux):

```json
"base_url": "http://host.docker.internal:8080/v1"
```

> **Linux note:** `host.docker.internal` needs `extra_hosts: ["host.docker.internal:host-gateway"]`
> on the router service, or just use the host's LAN IP directly.

## Editing the router config

`config.json` is bind-mounted read-only into the router container. After editing:

```bash
docker compose restart sentra-router
```

The router reads the file on first request, so no rebuild is needed — a restart
picks up the change.

## Verifying the local tier

```bash
# Router health
curl http://localhost:9100/health

# Local tier reachable?
curl http://localhost:8080/v1/models
```

Then in Open WebUI, select the `sentra-local` model (forced local tier) or
`sentra-auto` (classifier decides) and confirm short chats route local.
