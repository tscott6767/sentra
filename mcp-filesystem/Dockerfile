# Sentra — a self-hosted household AI stack.
# Copyright (C) 2026 Tony Scott
# SPDX-License-Identifier: GPL-3.0-or-later

# MCP filesystem server — official, no custom code
# Bridges @modelcontextprotocol/server-filesystem (Node.js, stdio) to HTTP
# via mcpo (Python). Open WebUI connects over HTTP/SSE.

FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    nodejs npm ca-certificates && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir mcpo

EXPOSE 8001

# mcpo <mcpo-flags> -- <stdio-mcp-server command>
# The served directory (/data) is bind-mounted from the host.
ENTRYPOINT ["mcpo"]
