"""订单导入服务：补录 / 更正批次的校验、幂等、晚到护栏与原子切换。

一条导入请求的完整路径（全部在单个数据库事务内，失败整体回滚）：

1. 批次号幂等：同 batch_no 只允许成功应用一次，重复导入直接拒绝（不新增记录）；
2. 晚到护栏：batch_seq ≤ 当前数据版本序号 → 拒绝，旧批次不能盖掉新校正；
3. 整批校验：字段级错误 / 批内重复单号 / 行数上限，任一不过即返回错误明细，
   订单、矩阵、版本指针一律不动，页面继续展示上一版；
4. 差异判定：同 order_no 不新增，事实字段变化才算更正，完全一致记 unchanged；
5. 写入新版本：当前版本全量订单复制到新版本，叠加 insert/update；
6. 同事务重建矩阵（commit=False）→ 翻转 DataVersion → 旧 LTV 报告置为过期；
7. 留存 ImportBatch 留痕（applied/failed/rejected/validated 全状态可追溯）。
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.constants import error_codes as codes
from src.constants.enums import ImportBatchStatus
from src.constants.limits import IMPORT_MAX_ERROR_DETAIL, IMPORT_MAX_ROWS
from src.models.cohort import Cohort
from src.models.data_version import DataVersion
from src.models.import_batch import ImportBatch
from src.models.ltv_report import LtvReport
from src.models.member_order import MemberOrder
from src.services import import_core, retention_service, version_service
from src.services.import_core import NormalizedOrder
from src.utils.errors import AppError
from src.utils.logger import get_logger

logger = get_logger("cohortltv.import")


# --------------------------------------------------------------- 批次读取


def get_batch(db: Session, batch_id: str) -> ImportBatch:
    try:
        key = uuid.UUID(batch_id)
    except ValueError as exc:
        raise AppError(codes.IMPORT_BATCH_NOT_FOUND) from exc
    batch = db.get(ImportBatch, key)
    if batch is None:
        raise AppError(codes.IMPORT_BATCH_NOT_FOUND)
    return batch


def list_batches(db: Session, limit: int = 50) -> list[ImportBatch]:
    return list(
        db.execute(
            select(ImportBatch).order_by(ImportBatch.created_at.desc()).limit(limit)
        ).scalars().all()
    )


def serialize_batch(batch: ImportBatch) -> dict:
    return {
        "id": str(batch.id),
        "batch_no": batch.batch_no,
        "status": batch.status,
        "batch_seq": batch.batch_seq,
        "source_seq": batch.source_seq,
        "dry_run": batch.dry_run,
        "row_count": batch.row_count,
        "inserted_count": batch.inserted_count,
        "updated_count": batch.updated_count,
        "unchanged_count": batch.unchanged_count,
        "rejected_count": batch.rejected_count,
        "errors": batch.errors or [],
        "data_version_id": str(batch.data_version_id) if batch.data_version_id else None,
        "applied_at": batch.applied_at.isoformat() if batch.applied_at else None,
        "created_at": batch.created_at.isoformat() if batch.created_at else None,
    }


# --------------------------------------------------------------- 校验


def validate(db: Session, raw_rows: list[dict], *, batch_no: str, source_seq: int | None,
             max_rows: int = IMPORT_MAX_ROWS) -> tuple[object, dict]:
    """前置护栏 + 整批校验；返回 (ValidationResult, guard_meta)。

    护栏失败（重复批次 / 晚到旧批）直接抛 AppError，由调用方决定是否留 rejected 痕迹。
    """
    existing_batch = db.execute(
        select(ImportBatch).where(ImportBatch.batch_no == batch_no)
    ).scalar_one_or_none()
    if existing_batch is not None and existing_batch.status == ImportBatchStatus.APPLIED.value:
        raise AppError(
            codes.IMPORT_DUPLICATE_BATCH,
            f"批次号 {batch_no} 已应用（v{existing_batch.batch_seq}），重复导入不会新增记录",
            f"batch_no={batch_no} applied_seq={existing_batch.batch_seq}",
        )

    current_seq = version_service.current_seq(db)
    import_core.guard_batch_seq(source_seq, current_seq)

    result = import_core.validate_rows(raw_rows, max_rows=max_rows)
    return result, {"current_seq": current_seq}


def _load_current_orders(db: Session, version: DataVersion) -> dict[str, MemberOrder]:
    rows = db.execute(
        select(MemberOrder).where(MemberOrder.version_id == version.id)
    ).scalars().all()
    return {row.order_no: row for row in rows}


def _existing_view(orders: dict[str, MemberOrder]) -> dict[str, dict]:
    return {
        order_no: {
            "amount": float(row.amount),
            "member_code": row.member_code,
            "cohort_month": row.cohort_month,
            "order_month": row.order_month,
            "month_index": row.month_index,
            "channel": row.channel,
            "store_code": row.store_code,
            "is_first_order": row.is_first_order,
        }
        for order_no, row in orders.items()
    }


# --------------------------------------------------------------- 主流程


def import_orders(
    db: Session,
    *,
    batch_no: str,
    rows: list[dict],
    source_seq: int | None = None,
    dry_run: bool = False,
    note: str = "",
    user=None,
) -> dict:
    """导入入口：dry_run 只校验不落库；正式导入走完整原子切换。"""
    try:
        validation, meta = validate(
            db, rows, batch_no=batch_no, source_seq=source_seq
        )
    except AppError as exc:
        if exc.code in (codes.IMPORT_DUPLICATE_BATCH, codes.IMPORT_STALE_BATCH):
            _record_rejected(db, batch_no, source_seq, len(rows), exc, user)
            db.commit()
        raise

    if not validation.ok:
        batch = _record_failed(db, batch_no, source_seq, dry_run, rows, validation, user)
        db.commit()
        raise AppError(
            codes.IMPORT_INVALID,
            f"整批校验未通过：{validation.rejected_count} 处错误，订单与矩阵未改动",
            extra={"batch_id": str(batch.id), "errors": import_core.error_payload(validation.errors)},
        )

    if dry_run:
        return _dry_run_summary(db, batch_no, source_seq, rows, validation, user)

    return _apply(db, batch_no, source_seq, note, rows, validation, meta["current_seq"], user)


def _dry_run_summary(db, batch_no, source_seq, rows, validation, user) -> dict:
    current = version_service.current_version(db)
    existing = _existing_view(_load_current_orders(db, current)) if current else {}
    plan = import_core.plan_changes(validation.orders, existing)
    # dry-run 不占用正式批次号命名空间（加后缀），否则同批次号将无法再正式提交
    batch = ImportBatch(
        batch_no=f"{batch_no}#dryrun-{uuid.uuid4().hex[:8]}",
        status=ImportBatchStatus.VALIDATED.value,
        source_seq=source_seq,
        dry_run=True,
        row_count=len(rows),
        rejected_count=0,
        errors=[],
        created_by=user.id if user else None,
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return {
        "batch_id": str(batch.id),
        "batch_no": batch_no,
        "status": ImportBatchStatus.VALIDATED.value,
        "dry_run": True,
        "row_count": len(rows),
        **plan.counts,
        "rejected_count": 0,
        "errors": [],
        "would_activate_seq": version_service.current_seq(db) + 1,
    }


def _apply(db, batch_no, source_seq, note, rows, validation, current_seq, user) -> dict:
    snapshot = settings.snapshot_month
    # 持锁切换：锁住当前版本行后再做晚到护栏与序号分配，并发导入在此排队
    previous = version_service.lock_current_version(db)
    locked_seq = version_service.current_seq(db)
    import_core.guard_batch_seq(source_seq, locked_seq)

    current_orders = _load_current_orders(db, previous)
    plan = import_core.plan_changes(validation.orders, _existing_view(current_orders))

    # 1) 先建批次记录（applied 在版本翻转同事务内落库，失败一起回滚）
    batch = ImportBatch(
        batch_no=batch_no,
        status=ImportBatchStatus.APPLIED.value,
        batch_seq=locked_seq + 1,
        source_seq=source_seq,
        dry_run=False,
        row_count=len(rows),
        inserted_count=len(plan.inserts),
        updated_count=len(plan.updates),
        unchanged_count=len(plan.unchanged),
        rejected_count=0,
        errors=[],
        created_by=user.id if user else None,
        applied_at=datetime.now(timezone.utc),
    )
    db.add(batch)
    db.flush()

    # 2) 新版本行（序号由 version_service 保证单调递增）
    new_version = version_service.create_version(
        db,
        label=f"导入批次 {batch_no}",
        snapshot_month=snapshot,
        orders_count=0,
        members_count=0,
        cohorts_count=0,
        cells_count=0,
        change_note=note or (
            f"新增 {len(plan.inserts)} 单 / 更正 {len(plan.updates)} 单 / "
            f"无变化 {len(plan.unchanged)} 单"
        ),
        source_batch_id=batch.id,
    )

    # 3) 复制当前版本全量订单到新版本（保留历史行可追溯），叠加本批变更
    incoming = {order.order_no: order for order in validation.orders}
    new_rows: list[MemberOrder] = []
    for order_no, old in current_orders.items():
        replacement = incoming.get(order_no)
        if replacement is None:
            new_rows.append(_clone_order(old, new_version.id, batch.id))
        else:
            new_rows.append(
                _merge_order(replacement, new_version.id, batch.id, old, new_version.seq)
            )
    for order in plan.inserts:
        new_rows.append(_merge_order(order, new_version.id, batch.id, None, new_version.seq))

    db.bulk_save_objects(new_rows)
    db.flush()

    # 4) 同期群规模与首单月按新版本订单事实重算（补录可能带来新会员/新群）
    _refresh_cohorts(db, new_version)

    # 5) 同事务重建矩阵：失败抛错 → 整个导入回滚，外部继续读到上一版
    summary = retention_service.rebuild_matrix(
        db, snapshot_month=snapshot, version_id=new_version.id, commit=False
    )

    # 6) 版本统计回填
    orders_count = db.execute(
        select(func.count()).select_from(MemberOrder).where(MemberOrder.version_id == new_version.id)
    ).scalar_one()
    members_count = db.execute(
        select(func.count(func.distinct(MemberOrder.member_code)))
        .where(MemberOrder.version_id == new_version.id)
    ).scalar_one()
    new_version.orders_count = int(orders_count)
    new_version.members_count = int(members_count)
    new_version.cohorts_count = db.execute(
        select(func.count()).select_from(Cohort)
    ).scalar_one()
    new_version.cells_count = int(summary["cells"])
    batch.data_version_id = new_version.id

    # 7) 旧 LTV 报告过期标记（结果快照不动，只改复核状态字段；草稿/发布分别标注）
    _mark_reports_stale(db, new_version.seq)

    db.commit()
    logger.info(
        "import applied batch=%s seq=v%s inserts=%s updates=%s unchanged=%s cells=%s",
        batch_no, new_version.seq, len(plan.inserts), len(plan.updates),
        len(plan.unchanged), summary["cells"],
    )
    return {
        "batch_id": str(batch.id),
        "batch_no": batch_no,
        "status": ImportBatchStatus.APPLIED.value,
        "dry_run": False,
        "batch_seq": new_version.seq,
        "data_version_id": str(new_version.id),
        "row_count": len(rows),
        **plan.counts,
        "rejected_count": 0,
        "errors": [],
        "matrix": summary,
    }


def _clone_order(old: MemberOrder, version_id, batch_id) -> MemberOrder:
    return MemberOrder(
        version_id=version_id,
        order_no=old.order_no,
        member_code=old.member_code,
        cohort_month=old.cohort_month,
        channel=old.channel,
        store_code=old.store_code,
        order_month=old.order_month,
        month_index=old.month_index,
        amount=old.amount,
        is_first_order=old.is_first_order,
        ordered_at=old.ordered_at,
        source_batch_id=batch_id,
        updated_by_seq=old.updated_by_seq,
    )


def _merge_order(
    order: NormalizedOrder,
    version_id,
    batch_id,
    old: MemberOrder | None,
    new_seq: int,
) -> MemberOrder:
    ordered_at = old.ordered_at if old is not None else datetime.now(timezone.utc)
    return MemberOrder(
        version_id=version_id,
        order_no=order.order_no,
        member_code=order.member_code,
        cohort_month=order.cohort_month,
        channel=order.channel,
        store_code=order.store_code,
        order_month=order.order_month,
        month_index=order.month_index,
        amount=order.amount,
        is_first_order=order.is_first_order,
        ordered_at=ordered_at,
        source_batch_id=batch_id,
        updated_by_seq=new_seq if old is not None else None,
    )


def _refresh_cohorts(db: Session, version: DataVersion) -> None:
    """按新版本订单重算每个首单月群的规模（去重会员数），缺失的群补建。"""
    rows = db.execute(
        select(
            MemberOrder.cohort_month,
            func.count(func.distinct(MemberOrder.member_code)),
        )
        .where(MemberOrder.version_id == version.id)
        .group_by(MemberOrder.cohort_month)
    ).all()
    sizes = {month: int(size) for month, size in rows}
    existing = {c.month: c for c in db.execute(select(Cohort)).scalars().all()}
    for month, size in sorted(sizes.items()):
        cohort = existing.get(month)
        if cohort is None:
            db.add(Cohort(month=month, size=size, channel_mix={}, note="导入补录生成的同期群"))
        elif int(cohort.size) != size:
            cohort.size = size


def _mark_reports_stale(db: Session, current_seq: int) -> None:
    """旧报告过期：不回写结果快照、不改 status，过期由 source_data_seq 落后派生。

    渠道页与导出仍读最后一份 published（其快照本身没变，保证「失败继续展示上一版」）；
    测算页通过 review_state 显示「已过期 · 待重算」，重算并发布新版本后才切换口径。
    """
    stale_count = db.execute(
        select(func.count())
        .select_from(LtvReport)
        .where(LtvReport.source_data_seq < current_seq)
    ).scalar_one()
    logger.info("reports marked stale by data v%s count=%s", current_seq, stale_count)


def _record_failed(db, batch_no, source_seq, dry_run, rows, validation, user) -> ImportBatch:
    batch = ImportBatch(
        batch_no=f"{batch_no}#failed-{uuid.uuid4().hex[:8]}",
        status=ImportBatchStatus.FAILED.value,
        source_seq=source_seq,
        dry_run=dry_run,
        row_count=len(rows),
        rejected_count=validation.rejected_count,
        errors=import_core.error_payload(validation.errors)[:IMPORT_MAX_ERROR_DETAIL],
        created_by=user.id if user else None,
    )
    db.add(batch)
    db.flush()
    return batch


def _record_rejected(db, batch_no, source_seq, row_count, exc: AppError, user) -> None:
    # 重复批次号本身有唯一索引，留痕记录追加短随机后缀，避免与原批次冲突
    batch = ImportBatch(
        batch_no=f"{batch_no}#rejected-{uuid.uuid4().hex[:8]}",
        status=ImportBatchStatus.REJECTED.value,
        source_seq=source_seq,
        dry_run=False,
        row_count=row_count,
        errors=[{"code": exc.code, "message": exc.message, "detail": exc.detail}],
        created_by=user.id if user else None,
    )
    db.add(batch)
    db.flush()


__all__ = [
    "get_batch",
    "import_orders",
    "list_batches",
    "serialize_batch",
    "validate",
]
