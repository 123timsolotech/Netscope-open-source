"""Logging for the app and the CLI."""

import logging


def configure_logging(level: str) -> None:
    """Give the ``netscope`` loggers a handler, so messages show next to uvicorn's."""
    app_logger = logging.getLogger("netscope")
    app_logger.setLevel(level)
    if not app_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s:     [%(name)s] %(message)s"))
        app_logger.addHandler(handler)
        app_logger.propagate = False
