"""复核状态与报告血缘的纯函数（无 ORM 依赖，可离线单测）。

状态语义：
- review_state 由「发布进度 status」×「数据新旧（source_data_seq vs 当前版本）」派生，
  报告的 status 本身不被数据更新改写，保证已发布快照的口径冻结语义；
- 发布门禁：过期（stale）或已被替代（superseded）的报告不允许发布，必须先重算；
- 同血缘发布互斥：一条血缘同一时刻只允许一份 published，新版本发布即接管。
"""
from __future__ import annotations

from src.constants import error_codes as codes
from src.constants.enums import ReportStatus, ReviewState
from src.utils.errors import AppError


def derive_review_state(status: str, source_data_seq: int, current_data_seq: int) -> str:
    stale = int(source_data_seq) < int(current_data_seq)
    if status == ReportStatus.PUBLISHED.value:
        return ReviewState.STALE_PUBLISHED.value if stale else ReviewState.PUBLISHED.value
    if status == ReportStatus.SUPERSEDED.value:
        return ReviewState.SUPERSEDED.value
    if status == ReportStatus.ARCHIVED.value:
        return ReportStatus.ARCHIVED.value
    return ReviewState.STALE_DRAFT.value if stale else ReviewState.DRAFT.value


def ensure_publishable(status: str, source_data_seq: int, current_data_seq: int) -> None:
    """发布门禁：不满足即抛 AppError，避免旧口径被冻结成新基线。"""
    if status == ReportStatus.PUBLISHED.value:
        raise AppError(codes.REPORT_ALREADY_PUBLISHED)
    if status == ReportStatus.SUPERSEDED.value:
        raise AppError(
            codes.REPORT_ALREADY_PUBLISHED, "该版本已被新版本替代，请发布血缘中的最新版本"
        )
    if int(source_data_seq) < int(current_data_seq):
        raise AppError(
            codes.REPORT_STALE,
            f"源数据已更新到 v{current_data_seq}（报告基于 v{source_data_seq}），请先重算",
            f"source={source_data_seq} current={current_data_seq}",
        )


def next_version_no(current_max_version_no: int | None) -> int:
    """同血缘新版本号：从 1 起单调递增。"""
    return 1 if not current_max_version_no else int(current_max_version_no) + 1


__all__ = ["derive_review_state", "ensure_publishable", "next_version_no"]
