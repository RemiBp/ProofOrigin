"""Expose FastAPI app for ASGI servers."""
from __future__ import annotations

from fastapi import FastAPI

from prooforigin.api.main import create_app

app: FastAPI = create_app()


__all__ = ["app", "create_app"]
