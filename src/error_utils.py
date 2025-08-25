"""
Error handling utilities for consistent exception raising with context.
"""


def raise_with_context(message, exc):
    """Raise a ValueError with a message and original exception context."""
    raise ValueError(message) from exc
