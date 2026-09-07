# Sentra — a self-hosted household AI stack.
# Copyright (C) 2026 Tony Scott
# SPDX-License-Identifier: GPL-3.0-or-later

# Sentra Router v2 — thin FastAPI reverse proxy
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY config.json .

EXPOSE 9100

# CONFIG_PATH default /app/config.json; override with bind-mount for hot swaps.
# ROUTER_API_KEY + OPENROUTER_API_KEY come from the environment (.env).
ENV CONFIG_PATH=/app/config.json

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "9100"]
