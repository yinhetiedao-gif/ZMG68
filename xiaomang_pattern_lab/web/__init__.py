"""HTTP adapter for the existing WM2 transport contract and headless service."""

from .app import create_app

__all__ = ["create_app"]
