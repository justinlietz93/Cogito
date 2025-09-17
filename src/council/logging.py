"""Logging helpers for council agents."""
from __future__ import annotations

import logging
import os
from typing import Iterable

LOG_DIR = "logs"
PHILOSOPHY_LOG_DIR = os.path.join(LOG_DIR, "philosophy")
SCIENCE_LOG_DIR = os.path.join(LOG_DIR, "science")


def ensure_log_directories(paths: Iterable[str] = (LOG_DIR, PHILOSOPHY_LOG_DIR, SCIENCE_LOG_DIR)) -> None:
    """Ensure the agent log directories exist."""
    for path in paths:
        os.makedirs(path, exist_ok=True)


def setup_agent_logger(agent_name: str, scientific_mode: bool = False) -> logging.Logger:
    """Return a dedicated logger for an agent run."""
    ensure_log_directories()
    agent_log_dir = SCIENCE_LOG_DIR if scientific_mode else PHILOSOPHY_LOG_DIR
    log_file = os.path.join(agent_log_dir, f"agent_{agent_name}.log")

    logger = logging.getLogger(f"agent.{agent_name}")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        handler.close()

    file_handler = logging.FileHandler(log_file, mode="w", encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    return logger
