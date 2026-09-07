# Sentra — a self-hosted household AI stack.
# Copyright (C) 2026 Tony Scott
# SPDX-License-Identifier: GPL-3.0-or-later

# MCP-Exec sandbox — server-side code execution
# Runs exec_server.py (FastMCP) under mcpo (HTTP bridge) on port 8004.
# Needs python3 + node + bash for the .py/.js/.sh runtimes.

FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    nodejs bash ca-certificates && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY exec_server.py .

RUN pip install --no-cache-dir mcpo fastmcp

# Sandbox dir (bind-mounted from the host in docker-compose)
RUN mkdir -p /sandbox
ENV SANDBOX_DIR=/sandbox

EXPOSE 8004

CMD ["mcpo", "--port", "8004", "--host", "0.0.0.0", "--", "python3", "exec_server.py"]
