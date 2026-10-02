"""Validate untrusted JSON tool calls against trusted, local schemas."""
from .core import validate_call

__all__ = ["validate_call"]
