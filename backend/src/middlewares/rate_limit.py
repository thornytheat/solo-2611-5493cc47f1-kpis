"""Redis 滑动窗口限流（横切关注点：配额）。

桶：rebuild（重建矩阵）/ ltv（测算）/ default。超限返回 429 RATE_LIMITED。
"""
from __future__ import annotations

import time

from fastapi import Depends, Request

from src.constants import error_codes as codes
from src.constants.limits import (
    RATE_LIMIT_DEFAULT_PER_MINUTE,
    RATE_LIMIT_LTV_PER_MINUTE,
    RATE_LIMIT_REBUILD_PER_MINUTE,
    WINDOW_SECONDS,
)
from src.middlewares.auth import get_current_user
from src.models.user import User
from src.utils.errors import AppError
from src.utils.redis_client import get_redis

_LIMITS = {
    "rebuild": RATE_LIMIT_REBUILD_PER_MINUTE,
    "ltv": RATE_LIMIT_LTV_PER_MINUTE,
    "default": RATE_LIMIT_DEFAULT_PER_MINUTE,
}


def _check(key: str, limit: int, window_seconds: int = WINDOW_SECONDS) -> None:
    now = time.time()
    try:
        client = get_redis()
        pipeline = client.pipeline()
        pipeline.zremrangebyscore(key, 0, now - window_seconds)
        pipeline.zadd(key, {f"{now}": now})
        pipeline.zcard(key)
        pipeline.expire(key, window_seconds)
        count = int(pipeline.execute()[2])
    except Exception:
        return  # Redis 抖动不拦业务
    if count > limit:
        raise AppError(
            codes.RATE_LIMITED,
            "请求过于频繁，请稍后重试",
            f"key={key} count={count} limit={limit}",
            extra={"retry_after": window_seconds},
        )


def rate_limit(bucket: str = "default") -> object:
    def dependency(request: Request, user: User = Depends(get_current_user)) -> None:
        limit = _LIMITS.get(bucket, RATE_LIMIT_DEFAULT_PER_MINUTE)
        _check(f"ratelimit:{bucket}:{user.id}:{request.url.path}", limit)

    return Depends(dependency)
