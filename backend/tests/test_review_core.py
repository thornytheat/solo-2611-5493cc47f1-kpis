"""复核状态机与发布门禁的单元测试（纯函数，离线可跑）。

覆盖：
- 复核状态由 status × 数据新旧派生，源数据更新只让报告「过期」，不改写发布状态；
- 过期报告禁止发布（必须先重算），已替代版本禁止发布，已发布不能重复发布；
- 同血缘版本号单调递增。
"""
from __future__ import annotations

import unittest

from src.constants import error_codes as codes
from src.constants.enums import ReportStatus, ReviewState
from src.services.review_core import (
    derive_review_state,
    ensure_publishable,
    next_version_no,
)
from src.utils.errors import AppError


class ReviewStateTests(unittest.TestCase):
    def test_fresh_draft(self) -> None:
        self.assertEqual(
            derive_review_state(ReportStatus.DRAFT.value, 3, 3), ReviewState.DRAFT.value
        )

    def test_stale_draft_after_data_update(self) -> None:
        self.assertEqual(
            derive_review_state(ReportStatus.DRAFT.value, 2, 3),
            ReviewState.STALE_DRAFT.value,
        )

    def test_published_fresh_and_stale(self) -> None:
        self.assertEqual(
            derive_review_state(ReportStatus.PUBLISHED.value, 3, 3),
            ReviewState.PUBLISHED.value,
        )
        self.assertEqual(
            derive_review_state(ReportStatus.PUBLISHED.value, 1, 3),
            ReviewState.STALE_PUBLISHED.value,
        )

    def test_superseded_is_terminal(self) -> None:
        # 已被新版本替代：即使数据也过期，终态仍是 superseded
        self.assertEqual(
            derive_review_state(ReportStatus.SUPERSEDED.value, 1, 3),
            ReviewState.SUPERSEDED.value,
        )


class PublishGateTests(unittest.TestCase):
    def test_fresh_draft_can_publish(self) -> None:
        ensure_publishable(ReportStatus.DRAFT.value, 3, 3)  # 不抛错即通过

    def test_stale_report_blocked(self) -> None:
        with self.assertRaises(AppError) as ctx:
            ensure_publishable(ReportStatus.DRAFT.value, 2, 3)
        self.assertEqual(ctx.exception.code, codes.REPORT_STALE)

    def test_already_published_blocked(self) -> None:
        with self.assertRaises(AppError) as ctx:
            ensure_publishable(ReportStatus.PUBLISHED.value, 3, 3)
        self.assertEqual(ctx.exception.code, codes.REPORT_ALREADY_PUBLISHED)

    def test_superseded_blocked(self) -> None:
        with self.assertRaises(AppError) as ctx:
            ensure_publishable(ReportStatus.SUPERSEDED.value, 3, 3)
        self.assertEqual(ctx.exception.code, codes.REPORT_ALREADY_PUBLISHED)


class LineageVersionTests(unittest.TestCase):
    def test_version_no_monotonic(self) -> None:
        self.assertEqual(next_version_no(None), 1)
        self.assertEqual(next_version_no(0), 1)
        self.assertEqual(next_version_no(1), 2)
        self.assertEqual(next_version_no(7), 8)


if __name__ == "__main__":
    unittest.main()
