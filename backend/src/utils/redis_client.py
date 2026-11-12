"""Redis 客户端（限流、任务状态、worker 心跳共用）。"""
from __future__ import annotations

from functools import lru_cache

import redis

from src.config.settings import settings


@lru_cache
def get_redis() -> redis.Redis:
    return redis.Redis.from_url(settings.redis_url, decode_responses=True)


def ping_redis() -> bool:
    try:
        return bool(get_redis().ping())
    except Exception:
        return False
