"""Graceful degradation wrapper for graph operations.

Provides a decorator that catches Neo4j connection errors and returns
a fallback value, plus a utility to check graph availability via socket.
"""

from __future__ import annotations

import functools
import socket
from typing import Any, Callable, TypeVar
from urllib.parse import urlparse

import structlog

logger = structlog.get_logger()

T = TypeVar("T")


def graceful_graph_op(fallback: Any) -> Callable:  # noqa: ANN401
    """Decorator factory: catch graph connection errors, return fallback.

    Catches ConnectionRefusedError, OSError, and (if neo4j is installed)
    neo4j.exceptions.ServiceUnavailable. All other exceptions propagate.

    Args:
        fallback: Value to return when the graph is unavailable.

    Returns:
        Decorator that wraps a function with connection-error handling.
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:  # noqa: ANN401
            # Build the exception tuple lazily to avoid import errors
            # when neo4j is not installed.
            caught_exceptions: tuple[type[Exception], ...] = (
                ConnectionRefusedError,
                OSError,
            )
            try:
                from neo4j.exceptions import ServiceUnavailable

                caught_exceptions = (*caught_exceptions, ServiceUnavailable)
            except ImportError:
                pass

            try:
                return func(*args, **kwargs)
            except caught_exceptions as exc:
                logger.warning(
                    "graph_unavailable",
                    operation=func.__name__,
                    error=str(exc),
                )
                return fallback  # type: ignore[return-value]

        return wrapper

    return decorator


def is_graph_available(bolt_uri: str = "bolt://localhost:7687") -> bool:
    """Check whether Neo4j is reachable via a socket connection test.

    Pure socket check -- does not import the neo4j driver.

    Args:
        bolt_uri: Bolt protocol URI to check.

    Returns:
        True if a TCP connection to the host:port succeeds.
    """
    parsed = urlparse(bolt_uri)
    host = parsed.hostname or "localhost"
    port = parsed.port or 7687

    try:
        with socket.create_connection((host, port), timeout=2.0):
            return True
    except (ConnectionRefusedError, OSError):
        return False
