"""限流与分页常量。"""
from __future__ import annotations

from src.config.settings import settings

RATE_LIMIT_DEFAULT_PER_MINUTE = settings.rate_limit_default_per_minute
RATE_LIMIT_LTV_PER_MINUTE = settings.rate_limit_ltv_per_minute
RATE_LIMIT_REBUILD_PER_MINUTE = settings.rate_limit_rebuild_per_minute
# 整批导入是重事务（校验 + 全量复制 + 矩阵重建），配额比普通接口更保守
RATE_LIMIT_IMPORT_PER_MINUTE = settings.rate_limit_import_per_minute

WINDOW_SECONDS = 60
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200

# 订单导入：单次批次最大行数（整批在一个事务内校验 + 切换）
IMPORT_MAX_ROWS = 5000
# 校验失败明细在响应/批次记录里最多保留的条数（全量计数不受影响）
IMPORT_MAX_ERROR_DETAIL = 100
