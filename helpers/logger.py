"""
helpers/logger.py — Structured logging setup
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler


def LOGGER(name: str) -> logging.Logger:
    """Return a configured logger for the given module name."""
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger  # Already configured

    logger.setLevel(logging.DEBUG)

    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler — INFO and above
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(fmt)
    logger.addHandler(console)

    # Rotating file handler — DEBUG and above
    os.makedirs("logs", exist_ok=True)
    file_handler = RotatingFileHandler(
        "logs/tunebot.log",
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    return logger
