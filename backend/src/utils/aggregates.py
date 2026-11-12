"""金额分布等纯聚合工具（无 ORM 依赖，可单测）。"""
from __future__ import annotations

from collections.abc import Iterable, Sequence

AMOUNT_BUCKETS: list[tuple[str, float, float]] = [
    ("<¥20", 0, 20),
    ("¥20-40", 20, 40),
    ("¥40-80", 40, 80),
    ("¥80-150", 80, 150),
    ("¥150-300", 150, 300),
    ("≥¥300", 300, 10**9),
]


def bucket_amounts(
    amounts: Iterable[float],
    buckets: Sequence[tuple[str, float, float]] = tuple(AMOUNT_BUCKETS),
) -> dict:
    """订单金额分桶：左闭右开；返回每桶计数、订单数、总额、客单价。

    空输入不抛错：buckets 计数全 0、orders=0、total=0.0、avg_ticket=0.0。
    """
    values = [float(amount) for amount in amounts]
    rows = [
        {"label": label, "count": sum(1 for value in values if low <= value < high)}
        for label, low, high in buckets
    ]
    total = float(sum(values))
    return {
        "buckets": rows,
        "orders": len(values),
        "total": round(total, 2),
        "avg_ticket": round(total / len(values), 2) if values else 0.0,
    }
