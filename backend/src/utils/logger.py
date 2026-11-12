"""统一日志格式（容器 stdout）。"""
from __future__ import annotations

import logging
import os

_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
_CONFIGURED = False


def _configure() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    logging.basicConfig(
        level=_LEVEL,
        format="%(asctime)s %(levelname)-5s [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    _configure()
    return logging.getLogger(name)
