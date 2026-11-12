"""Demo seed：幂等，跑两次 SEED_SUMMARY 逐字一致。

链路：用户 → 同期群 → 数据版本 v1 → 订单事实（24,000，挂 v1）
      → 重建留存矩阵（算法 1，同事务切换）
      → 算一份基线 LTV 报告并发布（算法 2，记录 source_data_seq=1）。

自然键：
- users.email
- cohorts.month
- data_versions.seq / import_batches.batch_no
- (member_orders.version_id, member_orders.order_no) —— 同版本同单号不新增
- ltv_reports(lineage_id, version_no)；name 不再全局唯一，重算走同血缘新版本
- retention_cells(cohort_id, month_index, channel, version_id) —— 派生数据，按版本重建
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone

from sqlalchemy import func, insert, select

from src.config.database import session_scope
from src.config.settings import settings
from src.constants.enums import Channel, ReportStatus
from src.models.cohort import Cohort
from src.models.data_version import DataVersion
from src.models.ltv_report import LtvReport
from src.models.member_order import MemberOrder
from src.models.retention_cell import RetentionCell
from src.models.user import User
from src.services import ltv_service, retention_service, version_service
from src.services.auth_service import hash_password
from scripts import fixtures

BASELINE_REPORT = "2026-11 增长复盘基线"
CHUNK = 2000


def _seed_users(db) -> tuple[int, int]:
    created = skipped = 0
    for spec in fixtures.USERS:
        exists = db.execute(
            select(User).where(User.email == spec["email"])
        ).scalar_one_or_none()
        if exists is not None:
            skipped += 1
            continue
        db.add(
            User(
                email=spec["email"],
                password_hash=hash_password(fixtures.DEMO_PASSWORD),
                display_name=spec["display_name"],
                role=spec["role"],
                channel_scope=spec.get("channel_scope"),
                is_active=True,
            )
        )
        created += 1
    db.flush()
    return created, skipped


def _seed_cohorts(db) -> tuple[int, int]:
    created = skipped = 0
    for row in fixtures.cohort_seed_rows():
        exists = db.execute(
            select(Cohort).where(Cohort.month == row["month"])
        ).scalar_one_or_none()
        if exists is not None:
            skipped += 1
            continue
        db.add(
            Cohort(
                month=row["month"],
                size=row["size"],
                channel_mix=row["channel_mix"],
                note=row["note"],
            )
        )
        created += 1
    db.flush()
    return created, skipped


def _ensure_baseline_version(db) -> DataVersion:
    """幂等确保基线数据版本 v1 存在（seed 的所有订单与矩阵都挂它）。"""
    version = version_service.current_version(db)
    if version is not None:
        return version
    version = DataVersion(
        seq=1,
        label="seed 基线数据版本",
        source_batch_id=None,
        snapshot_month=fixtures.SNAPSHOT_MONTH,
        orders_count=0,
        members_count=0,
        cohorts_count=0,
        cells_count=0,
        change_note="确定性 fixture：12 群 / 24,000 单的初始数据版本",
    )
    db.add(version)
    db.flush()
    return version


def _seed_orders(db) -> tuple[int, int]:
    version = _ensure_baseline_version(db)
    existing = db.execute(
        select(func.count())
        .select_from(MemberOrder)
        .where(MemberOrder.version_id == version.id)
    ).scalar_one()
    if existing >= fixtures.TOTAL_ORDERS:
        return 0, int(existing)
    _, counts, rows = fixtures.demo_plan()
    for row in rows:
        row["version_id"] = version.id
    for start in range(0, len(rows), CHUNK):
        db.execute(insert(MemberOrder), rows[start:start + CHUNK])
    db.flush()
    print(
        f"[seed] orders generated rows={len(rows)} cells={len(counts)} version=v{version.seq}",
        flush=True,
    )
    return len(rows), 0


def _seed_matrix(db) -> dict | None:
    version = version_service.current_version(db)
    cell_count = db.execute(
        select(func.count())
        .select_from(RetentionCell)
        .where(RetentionCell.version_id == version.id)
    ).scalar_one()
    if cell_count:
        return None
    summary = retention_service.rebuild_matrix(
        db,
        snapshot_month=fixtures.SNAPSHOT_MONTH,
        months=len(fixtures.BASE_RETENTION),
        version_id=version.id,
    )
    version.orders_count = db.execute(
        select(func.count())
        .select_from(MemberOrder)
        .where(MemberOrder.version_id == version.id)
    ).scalar_one()
    version.members_count = db.execute(
        select(func.count(func.distinct(MemberOrder.member_code)))
        .where(MemberOrder.version_id == version.id)
    ).scalar_one()
    version.cohorts_count = db.execute(select(func.count()).select_from(Cohort)).scalar_one()
    db.commit()
    print(f"[seed] matrix rebuilt {summary}", flush=True)
    return summary


def _seed_report(db) -> bool:
    import uuid

    exists = db.execute(
        select(LtvReport).where(
            LtvReport.name == BASELINE_REPORT, LtvReport.version_no == 1
        )
    ).scalar_one_or_none()
    if exists is not None:
        return False
    admin = db.execute(
        select(User).where(User.email == fixtures.USERS[0]["email"])
    ).scalar_one_or_none()
    results = ltv_service.compute_results(
        db, snapshot_month=fixtures.SNAPSHOT_MONTH
    )
    current_seq = version_service.current_seq(db)
    report = LtvReport(
        name=BASELINE_REPORT,
        status=ReportStatus.PUBLISHED.value,
        params=results["params"],
        results=results,
        note="seed 基线：12 群 × 13 月，λ 网格搜索，渠道 CAC 取默认值。",
        created_by=admin.id if admin else None,
        lineage_id=uuid.uuid4(),
        version_no=1,
        source_data_seq=current_seq,
        supersedes_id=None,
        published_at=datetime.now(timezone.utc),
    )
    db.add(report)
    db.flush()
    print(
        "[seed] baseline report v{} data=v{} lambda={} r2={} ltv12={}".format(
            report.version_no,
            report.source_data_seq,
            (results.get("fit") or {}).get("lambda"),
            (results.get("fit") or {}).get("r2"),
            results.get("ltv_pred12"),
        ),
        flush=True,
    )
    return True


def seed_all() -> dict:
    created = skipped = 0
    with session_scope() as db:
        u_created, u_skipped = _seed_users(db)
        c_created, c_skipped = _seed_cohorts(db)
        created += u_created + c_created
        skipped += u_skipped + c_skipped
        if u_skipped or c_skipped:
            print(
                f"[seed] SEED_SKIPPED users={u_skipped} cohorts={c_skipped}",
                flush=True,
            )
        o_created, o_skipped = _seed_orders(db)
        created += o_created
        skipped += o_skipped
        _seed_matrix(db)
        if _seed_report(db):
            created += 1
        else:
            skipped += 1

        version = version_service.current_version(db)
        cohorts = db.execute(select(func.count()).select_from(Cohort)).scalar_one()
        members = db.execute(select(func.sum(Cohort.size))).scalar_one() or 0
        orders = db.execute(
            select(func.count())
            .select_from(MemberOrder)
            .where(MemberOrder.version_id == version.id)
        ).scalar_one()
        users = db.execute(select(func.count()).select_from(User)).scalar_one()
        cells = db.execute(
            select(func.count())
            .select_from(RetentionCell)
            .where(RetentionCell.version_id == version.id)
        ).scalar_one()

    summary = (
        f"SEED_SUMMARY brand={settings.brand} cohorts={int(cohorts)} "
        f"members={int(members)} orders={int(orders)} "
        f"channels={len(fixtures.COHORT_CHANNELS)} users={int(users)}"
    )
    print(summary, flush=True)
    print(
        f"SEED_DETAIL cells={int(cells)} snapshot={fixtures.SNAPSHOT_MONTH} "
        f"created={created} skipped={skipped}",
        flush=True,
    )
    return {
        "created": created,
        "skipped": skipped,
        "cohorts": int(cohorts),
        "members": int(members),
        "orders": int(orders),
        "users": int(users),
        "cells": int(cells),
    }


def main() -> int:
    settings.seed_demo = True
    try:
        seed_all()
    except Exception as exc:  # noqa: BLE001
        print(f"[seed] FAILED {exc}", file=sys.stderr, flush=True)
        raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
