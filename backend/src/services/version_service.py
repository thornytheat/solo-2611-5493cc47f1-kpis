"""数据版本服务：当前版本指针、版本切换、报告过期判定。

版本边界是「整批校验通过后一起切换」的落点：
- 订单写入新版本 → 矩阵在同事务重建 → DataVersion 翻转 current，三步一个事务；
- 任何一步抛错都由 session_scope 回滚，外部查询继续命中上一版；
- LTV 报告只存结果快照，数据变了不回写旧报告，只把 source_data_seq 落后的报告标为过期。
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.constants import error_codes as codes
from src.models.data_version import DataVersion
from src.utils.errors import AppError


def current_version(db: Session) -> DataVersion | None:
    return db.execute(
        select(DataVersion).order_by(DataVersion.seq.desc()).limit(1)
    ).scalar_one_or_none()


def lock_current_version(db: Session) -> DataVersion:
    """锁住当前版本行（FOR UPDATE），把并发导入切换串行化。

    导入事务在持锁期间读取的 current_seq 是权威值：后到事务等前一个提交后
    才拿到锁并看到新版本序号，晚到护栏因此不会在并发下漏判。
    """
    version = current_version(db)
    if version is None:
        raise AppError(codes.DATA_VERSION_NOT_FOUND, "缺少基线数据版本，无法应用导入批次")
    return db.execute(
        select(DataVersion).where(DataVersion.id == version.id).with_for_update()
    ).scalar_one()


def current_seq(db: Session) -> int:
    version = current_version(db)
    return int(version.seq) if version is not None else 0


def get_version(db: Session, seq: int) -> DataVersion:
    version = db.execute(select(DataVersion).where(DataVersion.seq == seq)).scalar_one_or_none()
    if version is None:
        raise AppError(codes.DATA_VERSION_NOT_FOUND, f"数据版本 v{seq} 不存在")
    return version


def list_versions(db: Session, limit: int = 50) -> list[DataVersion]:
    return list(
        db.execute(
            select(DataVersion).order_by(DataVersion.seq.desc()).limit(limit)
        ).scalars().all()
    )


def create_version(
    db: Session,
    *,
    label: str,
    snapshot_month: str,
    orders_count: int,
    members_count: int,
    cohorts_count: int,
    cells_count: int,
    change_note: str = "",
    source_batch_id=None,
) -> DataVersion:
    """分配下一个单调递增序号并落版本行（调用方负责同事务提交）。"""
    next_seq = current_seq(db) + 1
    version = DataVersion(
        seq=next_seq,
        label=label,
        source_batch_id=source_batch_id,
        snapshot_month=snapshot_month,
        orders_count=orders_count,
        members_count=members_count,
        cohorts_count=cohorts_count,
        cells_count=cells_count,
        change_note=change_note,
    )
    db.add(version)
    db.flush()
    return version


def is_stale(report, db: Session | None = None, *, current_data_seq: int | None = None) -> bool:
    """报告依据的源数据序号落后于当前版本即过期（报告快照本身不动）。"""
    seq = current_data_seq if current_data_seq is not None else current_seq(db)
    return int(report.source_data_seq) < int(seq)


__all__ = [
    "create_version",
    "current_seq",
    "current_version",
    "get_version",
    "is_stale",
    "list_versions",
    "lock_current_version",
]
