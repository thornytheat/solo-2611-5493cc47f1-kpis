"""订单导入核心的单元测试（标准库 unittest，离线可跑）：

覆盖需求里的四条硬规则：
1. 同一订单号重复导入不能新增记录（批内重复拦截 + 同版本同号走 update/unchanged）；
2. 晚到旧批次不能盖掉新校正（batch_seq ≤ 当前版本即拒绝）；
3. 整批校验：任一错误即整批不可写入，错误明细逐行回显；
4. 差异判定：同号事实变化才算更正，完全一致记 unchanged。
"""
from __future__ import annotations

import unittest

from src.constants import error_codes as codes
from src.services.import_core import (
    NormalizedOrder,
    guard_batch_seq,
    normalize_row,
    plan_changes,
    validate_rows,
)
from src.utils.errors import AppError


def _row(**overrides) -> dict:
    base = {
        "order_no": "MO0001",
        "member_code": "M01-0001",
        "cohort_month": "2026-10",
        "channel": "private",
        "order_month": "2026-10",
        "amount": 32.5,
        "store_code": "MY001",
        "is_first_order": True,
    }
    base.update(overrides)
    return base


class NormalizeRowTests(unittest.TestCase):
    def test_valid_row_normalizes(self) -> None:
        order, errors = normalize_row(_row(), 0)
        self.assertEqual(errors, [])
        self.assertIsInstance(order, NormalizedOrder)
        self.assertEqual(order.month_index, 0)
        self.assertEqual(order.amount, 32.5)
        self.assertTrue(order.is_first_order)

    def test_month_index_derived(self) -> None:
        order, _ = normalize_row(
            _row(order_no="MO2", order_month="2026-12"), 0
        )
        self.assertEqual(order.month_index, 2)

    def test_invalid_month_rejected_not_silently_normalized(self) -> None:
        _order, errors = normalize_row(_row(cohort_month="2026-13"), 3)
        self.assertTrue(any(e.field == "cohort_month" for e in errors))

    def test_unknown_channel(self) -> None:
        _order, errors = normalize_row(_row(channel="flyers"), 1)
        self.assertTrue(any(e.field == "channel" for e in errors))

    def test_amount_must_be_positive(self) -> None:
        for bad in (0, -5, "abc", None):
            with self.subTest(bad=bad):
                _order, errors = normalize_row(_row(amount=bad), 2)
                self.assertTrue(any(e.field == "amount" for e in errors))

    def test_order_month_before_cohort_month_rejected(self) -> None:
        _order, errors = normalize_row(
            _row(cohort_month="2026-10", order_month="2026-09"), 0
        )
        self.assertTrue(any(e.field == "order_month" for e in errors))

    def test_missing_required_fields_collected(self) -> None:
        _order, errors = normalize_row({}, 5)
        fields = {e.field for e in errors}
        self.assertEqual(
            fields, {"order_no", "member_code", "cohort_month", "order_month", "channel", "amount"}
        )


class ValidateBatchTests(unittest.TestCase):
    def test_empty_batch_raises(self) -> None:
        with self.assertRaises(AppError) as ctx:
            validate_rows([], max_rows=10)
        self.assertEqual(ctx.exception.code, codes.IMPORT_EMPTY)

    def test_oversized_batch_raises(self) -> None:
        rows = [_row(order_no=f"MO{i}") for i in range(4)]
        with self.assertRaises(AppError) as ctx:
            validate_rows(rows, max_rows=3)
        self.assertEqual(ctx.exception.code, codes.IMPORT_INVALID)

    def test_duplicate_order_no_within_batch_rejected(self) -> None:
        """同一订单号在同批出现两次：整批校验失败，不会新增两条记录。"""
        rows = [
            _row(order_no="DUP", amount=10),
            _row(order_no="DUP", amount=20),
        ]
        result = validate_rows(rows, max_rows=100)
        self.assertFalse(result.ok)
        self.assertEqual(len(result.orders), 1)  # 重复行不进入待写入集合
        self.assertTrue(any("批内订单号重复" in e.message for e in result.errors))
        self.assertGreaterEqual(result.rejected_count, 1)

    def test_multiple_field_errors_fail_whole_batch(self) -> None:
        rows = [
            _row(order_no="OK1"),
            _row(order_no="BAD", amount=-1, channel="nope"),
        ]
        result = validate_rows(rows, max_rows=100)
        self.assertFalse(result.ok)
        self.assertEqual(len(result.orders), 1)
        # 单行多个错误全部收集
        bad_errors = [e for e in result.errors if e.order_no == "BAD"]
        self.assertGreaterEqual(len(bad_errors), 2)

    def test_clean_batch_passes(self) -> None:
        rows = [_row(order_no=f"MO{i}", amount=10 + i) for i in range(5)]
        result = validate_rows(rows, max_rows=100)
        self.assertTrue(result.ok)
        self.assertEqual(len(result.orders), 5)


class PlanChangesTests(unittest.TestCase):
    def _orders(self) -> list[NormalizedOrder]:
        result = validate_rows(
            [
                _row(order_no="NEW", amount=40),
                _row(order_no="SAME", amount=32.5),
                _row(order_no="FIX", amount=99),
            ],
            max_rows=10,
        )
        self.assertTrue(result.ok)
        return result.orders

    def test_insert_update_unchanged_classification(self) -> None:
        existing = {
            "SAME": {
                "amount": 32.5,
                "member_code": "M01-0001",
                "cohort_month": "2026-10",
                "order_month": "2026-10",
                "month_index": 0,
                "channel": "private",
                "store_code": "MY001",
                "is_first_order": True,
            },
            "FIX": {
                "amount": 50.0,  # 旧金额 50，新批次更正为 99
                "member_code": "M01-0002",
                "cohort_month": "2026-10",
                "order_month": "2026-10",
                "month_index": 0,
                "channel": "private",
                "store_code": "MY002",
                "is_first_order": False,
            },
        }
        plan = plan_changes(self._orders(), existing)
        self.assertEqual([o.order_no for o in plan.inserts], ["NEW"])
        self.assertEqual([o.order_no for o in plan.updates], ["FIX"])
        self.assertEqual([o.order_no for o in plan.unchanged], ["SAME"])
        self.assertEqual(
            plan.counts, {"inserted": 1, "updated": 1, "unchanged": 1}
        )

    def test_reimport_same_batch_creates_nothing(self) -> None:
        """全部同号且无变化 → 零新增、零更正（重复导入幂等）。"""
        orders = validate_rows([_row(order_no="SAME")], max_rows=10).orders
        existing = {
            "SAME": {
                "amount": 32.5,
                "member_code": "M01-0001",
                "cohort_month": "2026-10",
                "order_month": "2026-10",
                "month_index": 0,
                "channel": "private",
                "store_code": "MY001",
                "is_first_order": True,
            }
        }
        plan = plan_changes(orders, existing)
        self.assertEqual(plan.counts, {"inserted": 0, "updated": 0, "unchanged": 1})


class StaleBatchGuardTests(unittest.TestCase):
    def test_older_batch_rejected(self) -> None:
        """晚到旧批次：声明序号 2，当前已到 v3 → 拒绝，新校正不被覆盖。"""
        with self.assertRaises(AppError) as ctx:
            guard_batch_seq(2, current_seq=3)
        self.assertEqual(ctx.exception.code, codes.IMPORT_STALE_BATCH)

    def test_equal_seq_rejected(self) -> None:
        with self.assertRaises(AppError) as ctx:
            guard_batch_seq(3, current_seq=3)
        self.assertEqual(ctx.exception.code, codes.IMPORT_STALE_BATCH)

    def test_newer_batch_allowed(self) -> None:
        guard_batch_seq(4, current_seq=3)  # 不抛错即通过

    def test_missing_seq_skips_guard(self) -> None:
        guard_batch_seq(None, current_seq=3)  # 未声明版本时只靠批次号幂等


if __name__ == "__main__":
    unittest.main()
