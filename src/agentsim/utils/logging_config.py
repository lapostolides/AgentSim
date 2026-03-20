"""Structured logging configuration for AgentSim."""

from __future__ import annotations

import structlog


def configure_logging(verbose: bool = False) -> None:
    """Configure structlog for AgentSim.

    Args:
        verbose: If True, set log level to DEBUG. Otherwise INFO.
    """
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer() if verbose else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            10 if verbose else 20  # DEBUG=10, INFO=20
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
