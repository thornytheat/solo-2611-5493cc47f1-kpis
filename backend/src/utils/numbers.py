"""数值工具：安全除法、四舍五入（银行家舍入显式避开）、分转元。"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal


def safe_div(numerator: float, denominator: float, default: float = 0.0) -> float:
    if not denominator:
        return default
    return numerator / denominator


def round_half_up(value: float, digits: int = 0) -> float:
    quant = Decimal(1).scaleb(-digits)
    return float(Decimal(str(value)).quantize(quant, rounding=ROUND_HALF_UP))


def as_int(value: float) -> int:
    return int(round_half_up(value, 0))
