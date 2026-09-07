# Sentra — a self-hosted household AI stack.
# Copyright (C) 2026 Tony Scott
# SPDX-License-Identifier: GPL-3.0-or-later

# Open WebUI + Sentra memory plugin dependencies
# Extends the official image with the Python packages the memory plugin needs
# (numpy, sentence-transformers for bge-m3, tiktoken for token counting).
FROM ghcr.io/open-webui/open-webui:main

# Memory plugin deps (bge-m3 embedding model is ~2GB, pulled on first run)
RUN pip install --no-cache-dir numpy sentence-transformers tiktoken
