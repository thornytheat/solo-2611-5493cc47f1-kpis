"""订单导入的纯函数核心：行归一、整批校验、差异判定与晚到批次识别。

本模块不触碰数据库 / Session，只吃普通 dict：
- `validate_rows` 把原始行变成「归一订单 + 错误明细」，整批视角校验（空批、批内重复单号）；
- `plan_changes` 对照当前版本的同号订单，逐行判定 insert / update / unchanged；
- `guard_batch_seq` 判定晚到旧批次（batch_seq 不大于当前数据版本即拒绝）。

持久化与事务边界由 `import_service` 负责：任一环节失败都不写库，
保证「整批校验通过后才一起切换，失败继续展示上一版」。
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from src.constants import error_codes as codes
from src.constants.enums import CHANNEL_VALUES
from src.utils.errors import AppError
from src.utils.months import month_index, month_span

REQUIRED_FIELDS: tuple[str, ...] = (
    "order_no",
    "member_code",
    "cohort_month",
    "channel",
    "order_month",
    "amount",
)
MAX_ERROR_DETAIL_FALLBACK = 100


@dataclass(frozen=True)
class NormalizedOrder:
    order_no: str
    member_code: str
    cohort_month: str
    channel: str
    store_code: str
    order_month: str
    month_index: int
    amount: float
    is_first_order: bool
    ordered_at: str | None = None


@dataclass
class RowError:
    index: int
    order_no: str
    field: str
    message: str


@dataclass
class ValidationResult:
    orders: list[NormalizedOrder]
    errors: list[RowError]
    rejected_count: int

    @property
    def ok(self) -> bool:
        return not self.errors and bool(self.orders)


@dataclass
class ChangePlan:
    inserts: list[NormalizedOrder] = field(default_factory=list)
    updates: list[NormalizedOrder] = field(default_factory=list)
    unchanged: list[NormalizedOrder] = field(default_factory=list)

    @property
    def counts(self) -> dict[str, int]:
        return {
            "inserted": len(self.inserts),
            "updated": len(self.updates),
            "unchanged": len(self.unchanged),
        }


def _as_str(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _parse_month(value: object, field_name: str) -> tuple[str | None, str | None]:
    """返回 (月份, 错误信息)；复用 months.month_index 的严格校验，非法月份不静默归一。"""
    text = _as_str(value)
    if not text:
        return None, f"{field_name} 不能为空（YYYY-MM）"
    try:
        month_index(text)
    except ValueError:
        return None, f"{field_name} 月份非法：{text!r}（要求 YYYY-MM）"
    return text, None


def _parse_amount(value: object) -> tuple[float | None, str | None]:
    if value is None or _as_str(value) == "":
        return None, "amount 不能为空"
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return None, f"amount 不是数字：{value!r}"
    if amount <= 0:
        return None, f"amount 必须为正数，收到 {amount}"
    if amount >= 10_000_000:
        return None, f"amount 超出上限（1 千万元），收到 {amount}"
    return round(amount, 2), None


def _parse_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in ("1", "true", "yes", "y", "是")


def normalize_row(raw: Mapping[str, object], index: int) -> tuple[NormalizedOrder | None, list[RowError]]:
    """单行归一：字段级校验全部收集（不在第一个错误处中断），便于整批回显。"""
    errors: list[RowError] = []
    order_no = _as_str(raw.get("order_no"))
    if not order_no:
        errors.append(RowError(index, "", "order_no", "order_no 不能为空"))
    elif len(order_no) > 40:
        errors.append(RowError(index, order_no, "order_no", "order_no 超长（>40）"))

    member_code = _as_str(raw.get("member_code"))
    if not member_code:
        errors.append(RowError(index, order_no, "member_code", "member_code 不能为空"))
    elif len(member_code) > 24:
        errors.append(RowError(index, order_no, "member_code", "member_code 超长（>24）"))

    cohort_month, cohort_err = _parse_month(raw.get("cohort_month"), "cohort_month")
    if cohort_err:
        errors.append(RowError(index, order_no, "cohort_month", cohort_err))
    order_month, order_err = _parse_month(raw.get("order_month"), "order_month")
    if order_err:
        errors.append(RowError(index, order_no, "order_month", order_err))

    channel = _as_str(raw.get("channel"))
    if not channel:
        errors.append(RowError(index, order_no, "channel", "channel 不能为空"))
    elif channel not in CHANNEL_VALUES:
        errors.append(
            RowError(index, order_no, "channel", f"未知渠道 {channel!r}，允许值：{list(CHANNEL_VALUES)}")
        )

    amount, amount_err = _parse_amount(raw.get("amount"))
    if amount_err:
        errors.append(RowError(index, order_no, "amount", amount_err))

    store_code = _as_str(raw.get("store_code"))[:16]

    month_idx: int | None = None
    if cohort_month and order_month and not cohort_err and not order_err:
        month_idx = month_span(cohort_month, order_month)
        if month_idx < 0:
            errors.append(
                RowError(
                    index, order_no, "order_month",
                    f"order_month {order_month} 早于 cohort_month {cohort_month}，月序不能为负",
                )
            )
            month_idx = None
        elif month_idx > 24:
            errors.append(
                RowError(index, order_no, "order_month", f"月序 {month_idx} 超出上限 24")
            )
            month_idx = None

    if errors:
        return None, errors

    return NormalizedOrder(
        order_no=order_no,
        member_code=member_code,
        cohort_month=cohort_month,  # type: ignore[arg-type]
        channel=channel,
        store_code=store_code,
        order_month=order_month,  # type: ignore[arg-type]
        month_index=month_idx if month_idx is not None else 0,
        amount=amount,  # type: ignore[arg-type]
        is_first_order=_parse_bool(raw.get("is_first_order")),
        ordered_at=_as_str(raw.get("ordered_at")) or None,
    ), []


def validate_rows(
    raw_rows: Sequence[Mapping[str, object]],
    *,
    max_rows: int,
    max_error_detail: int = MAX_ERROR_DETAIL_FALLBACK,
) -> ValidationResult:
    """整批校验：字段级错误 + 批内重复单号 + 行数上限。任一错误即整批不可切换。"""
    orders: list[NormalizedOrder] = []
    errors: list[RowError] = []
    seen: dict[str, int] = {}

    if not raw_rows:
        raise AppError(codes.IMPORT_EMPTY)
    if len(raw_rows) > max_rows:
        raise AppError(
            codes.IMPORT_INVALID,
            f"单批最多 {max_rows} 行，收到 {len(raw_rows)} 行",
            f"rows={len(raw_rows)} max={max_rows}",
        )

    for index, raw in enumerate(raw_rows):
        order, row_errors = normalize_row(raw, index)
        errors.extend(row_errors)
        if order is None:
            continue
        first_index = seen.get(order.order_no)
        if first_index is not None:
            errors.append(
                RowError(
                    index, order.order_no, "order_no",
                    f"批内订单号重复（首次出现于第 {first_index} 行），同批不能新增重复记录",
                )
            )
            continue
        seen[order.order_no] = index
        orders.append(order)

    return ValidationResult(
        orders=orders,
        errors=errors[:max_error_detail],
        rejected_count=len(errors),
    )


def _same_fact(existing: Mapping[str, object], order: NormalizedOrder) -> bool:
    """同号订单的事实字段比对（金额/会员/月份/渠道等）；任一不同即视为更正。"""
    return (
        float(existing.get("amount", 0)) == order.amount
        and str(existing.get("member_code", "")) == order.member_code
        and str(existing.get("cohort_month", "")) == order.cohort_month
        and str(existing.get("order_month", "")) == order.order_month
        and int(existing.get("month_index", -1)) == order.month_index
        and str(existing.get("channel", "")) == order.channel
        and str(existing.get("store_code", "")) == order.store_code
        and bool(existing.get("is_first_order", False)) == order.is_first_order
    )


def plan_changes(
    orders: Sequence[NormalizedOrder],
    existing: Mapping[str, Mapping[str, object]],
) -> ChangePlan:
    """对照当前版本订单，逐行判定新增 / 更正 / 无变化（同号不新增）。"""
    plan = ChangePlan()
    for order in orders:
        current = existing.get(order.order_no)
        if current is None:
            plan.inserts.append(order)
        elif _same_fact(current, order):
            plan.unchanged.append(order)
        else:
            plan.updates.append(order)
    return plan


def guard_batch_seq(batch_seq: int | None, current_seq: int) -> None:
    """晚到旧批次护栏：声明序号不大于当前版本 → 拒绝，新校正不被覆盖。

    batch_seq 为 None 表示投递方未声明版本，只靠批次号幂等拦截，不做序号比较。
    """
    if batch_seq is not None and batch_seq <= current_seq:
        raise AppError(
            codes.IMPORT_STALE_BATCH,
            f"批次序号 {batch_seq} 不大于当前数据版本 v{current_seq}，晚到旧批次拒绝切换",
            f"batch_seq={batch_seq} current_seq={current_seq}",
        )


def error_payload(errors: Sequence[RowError]) -> list[dict[str, object]]:
    return [
        {"index": err.index, "order_no": err.order_no, "field": err.field, "message": err.message}
        for err in errors
    ]


__all__ = [
    "ChangePlan",
    "NormalizedOrder",
    "RowError",
    "ValidationResult",
    "error_payload",
    "guard_batch_seq",
    "normalize_row",
    "plan_changes",
    "validate_rows",
]
