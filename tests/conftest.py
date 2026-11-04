"""Pytest fixtures."""

from __future__ import annotations

import os

# Offscreen Qt for CI/headless.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
