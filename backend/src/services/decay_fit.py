"""衰减曲线拟合（纯函数，无 DB 依赖）。

模型：R_m = a · exp(-λ·m)
- λ 在 [lambda_min, lambda_max] 上以 step 网格搜索；
- 给定 λ 时 a 有闭式加权最小二乘解：a = Σ w·R_m·e^{-λm} / Σ w·e^{-2λm}
- 权重 w 默认取群规模（大群对曲线影响更大，与小群噪声解耦）
- R² 按加权残差 / 加权总平方和计算

不引入 scipy/sklearn：13 个月列 × ≤600 个候选 λ，直接算即可。
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class FitPoint:
    month_index: int
    observed: float
    fitted: float
    weight: float


@dataclass
class FitResult:
    lam: float
    a: float
    r2: float
    sse: float
    sst: float
    cells_used: int
    points: list[FitPoint] = field(default_factory=list)

    def predict(self, months: int) -> float:
        """Σ_{m<months} a·exp(-λm)"""
        return sum(self.a * math.exp(-self.lam * m) for m in range(months))

    def retention(self, m: int) -> float:
        return self.a * math.exp(-self.lam * m)


def fit_exponential(
    rows: list[tuple[int, float, float]],
    lambda_min: float = 0.02,
    lambda_max: float = 0.60,
    step: float = 0.001,
) -> FitResult:
    """rows: [(month_index, observed_rate, weight)] —— 只传有效（非右删失）格子。"""
    if not rows:
        raise ValueError("no observed cells")

    # 先按月聚合，避免对大矩阵重复扫描
    agg_sum = [0.0] * 64
    agg_w = [0.0] * 64
    agg_wy2 = 0.0
    max_m = 0
    for m, y, w in rows:
        agg_sum[m] += w * y
        agg_w[m] += w
        agg_wy2 += w * y * y
        max_m = max(max_m, m)

    candidate = lambda_min
    count = int(round((lambda_max - lambda_min) / step))
    best: tuple[float, float, float] | None = None
    for i in range(count + 1):
        lam = round(lambda_min + i * step, 6)
        expo = [math.exp(-lam * m) for m in range(max_m + 1)]
        num = sum(agg_sum[m] * expo[m] for m in range(max_m + 1))
        den = sum(agg_w[m] * expo[m] * expo[m] for m in range(max_m + 1))
        if den <= 0:
            continue
        a = num / den
        sse = agg_wy2 - num * num / den
        if best is None or sse < best[0]:
            best = (sse, lam, a)

    if best is None:
        raise ValueError("degenerate fit")
    sse, lam, a = best

    total_w = sum(agg_w)
    mean = sum(agg_sum) / total_w
    sst = sum(agg_w[m] * (mean - agg_sum[m] / agg_w[m]) ** 2 for m in range(max_m + 1) if agg_w[m])
    r2 = 0.0 if sst <= 0 else max(0.0, 1.0 - sse / sst)

    points = [
        FitPoint(month_index=m, observed=agg_sum[m] / agg_w[m], fitted=a * math.exp(-lam * m),
                 weight=agg_w[m])
        for m in range(max_m + 1)
        if agg_w[m] > 0
    ]
    return FitResult(lam=lam, a=a, r2=r2, sse=sse, sst=sst, cells_used=len(rows), points=points)
