"""限流与分页常量。"""
from __future__ import annotations

from src.config.settings import settings

RATE_LIMIT_DEFAULT_PER_MINUTE = settings.rate_limit_default_per_minute
RATE_LIMIT_LTV_PER_MINUTE = settings.rate_limit_ltv_per_minute
RATE_LIMIT_REBUILD_PER_MINUTE = settings.rate_limit_rebuild_per_minute

WINDOW_SECONDS = 60
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200
