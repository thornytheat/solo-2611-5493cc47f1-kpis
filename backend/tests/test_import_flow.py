"""导入 → 版本切换 → 报告过期 → 重算 → 发布接管 的内存集成测试。

不依赖 PostgreSQL / SQLAlchemy：用最小 FakeSession 与内存仓储替身，
驱动真实的 import_service / ltv_service 编排逻辑，验证需求主链路：
1. 整批校验失败时订单/矩阵/版本全部不动（继续展示上一版）；
2. 同订单号重复导入不新增，更正批次产生新版本且矩阵一起切换；
3. 晚到旧批次被拒绝；
4. 源数据更新后旧报告变 stale，重算生成同血缘新版本，发布后旧版本转 superseded。
"""
from __future__ import annotations

import sys
import types
import unittest
from unittest import mock

from src.constants import error_codes as codes
from src.constants.enums import ImportBatchStatus, ReportStatus
from src.models.cohort import Cohort
from src.models.data_version import DataVersion
from src.models.import_batch import ImportBatch
from src.models.ltv_report import LtvReport
from src.models.member_order import MemberOrder
from src.models.retention_cell import RetentionCell
from src.services import import_service, ltv_service
from src.utils.errors import AppError


class FakeQuery:
    def __init__(self, items):
        self._items = list(items)
        self._order_desc = False

    def where(self, *a, **k):
        return self

    def order_by(self, *a, **k):
        # 最新优先的语义：按 created_at/published_at 倒序，取末尾插入项
        self._order_desc = True
        self._items = sorted(
            self._items,
            key=lambda o: getattr(o, "published_at", None) or getattr(o, "created_at", None) or 0,
            reverse=True,
        )
        return self

    def group_by(self, *a, **k):
        return self

    def limit(self, n):
        self._items = self._items[:n]
        return self

    def with_for_update(self):
        return self

    def scalars(self):
        return self

    def first(self):
        return self._items[0] if self._items else None

    def scalar_one(self):
        return self._items[0]

    def scalar_one_or_none(self):
        return self._items[0] if self._items else None

    def all(self):
        return self._items


import sqlalchemy.orm as _sa_orm

# 复用 ORM stub 里的可求值条件类（真实环境下就是 SQLAlchemy 表达式）
_Condition = _sa_orm._Cond  # type: ignore[attr-defined]


class _TrackedColumn:
    def __init__(self, field):
        self.field = field

    def __eq__(self, other):
        return _Condition(self.field, "eq", other)

    def __ne__(self, other):
        return _Condition(self.field, "ne", other)

    def __lt__(self, other):
        return _Condition(self.field, "lt", other)

    def __gt__(self, other):
        return _Condition(self.field, "gt", other)

    def __le__(self, other):
        return _Condition(self.field, "le", other)

    def __ge__(self, other):
        return _Condition(self.field, "ge", other)

    def is_(self, other):
        return _Condition(self.field, "is", other)


class _Select:
    """select(Model) 的最小替身：记录目标模型，execute 时从内存仓储取数。"""

    def __init__(self, model):
        self.model = model
        self._filters: list[_Condition] = []
        self._agg = None
        self._grouped = False
        self._from_model = None

    def select_from(self, model):
        self._from_model = model
        if self.model is None or not isinstance(self.model, type):
            self.model = model
        self._agg = "count"
        return self

    def where(self, *conditions):
        for cond in conditions:
            if isinstance(cond, _Condition):
                self._filters.append(cond)
        return self

    def order_by(self, *a, **k):
        return self

    def group_by(self, *a, **k):
        self._grouped = True
        return self

    def limit(self, n):
        self._limit = n
        return self

    def with_for_update(self):
        self._for_update = True
        return self

    def options(self, *a, **k):
        return self

    def with_for_update(self):
        return self


def _select(model=None, *cols):
    return _Select(model)


class _Func:
    def count(self, *a, **k):
        return ("count",)

    def distinct(self, *a, **k):
        return ("distinct",)

    def sum(self, *a, **k):
        return ("sum",)


_FAKE_SA = types.ModuleType("sqlalchemy")

# 被测函数内 select(列, 聚合) 拿不到模型类时，按调用函数名兜底
_SELECT_CALLER_MODEL = {
    "_refresh_cohorts": MemberOrder,
}


def _fake_select(*entities):
    # select(Model) / select(Model.col, func.count(...)) 两种形态都解析出模型类
    model = None
    for entity in entities:
        if isinstance(entity, type):
            model = entity
            break
    if model is None:
        # shim 列对象拿不到所属表，按被测代码的固定调用顺序兜底解析
        caller = sys._getframe(1).f_code.co_name
        caller_model = _SELECT_CALLER_MODEL.get(caller)
        if caller_model:
            model = caller_model
    return _Select(model)


_FAKE_SA.select = _fake_select
_FAKE_SA.func = _Func()
_FAKE_SA.delete = lambda *a, **k: ("delete",)


class FakeSession:
    # 模型类 -> 仓储键；桩模型没有 __name__ 时按此表解析
    registry: dict = {}

    def __init__(self):
        self.store: dict[str, list] = {}
        self.committed = 0
        self.rolled_back = 0

    def _key(self, model) -> str:
        if isinstance(model, str):
            return model
        if not isinstance(model, type):
            return "_agg"
        return self.registry.get(model, getattr(model, "__name__", str(model)))

    def add(self, obj):
        self.store.setdefault(type(obj).__name__, []).append(obj)

    def flush(self):
        import datetime
        import uuid
        # 真实 SQLAlchemy 的 mapped_column 默认返回 None；stub 用类列占位，
        # 这里给未赋值的实例属性补 ORM 风格默认值，避免类描述符遮蔽实例值。
        defaults = {
            "id": lambda: uuid.uuid4(),
            "created_at": lambda: datetime.datetime(2026, 11, 12, tzinfo=datetime.timezone.utc),
            "applied_at": lambda: None,
            "published_at": lambda: None,
        }
        for objs in self.store.values():
            for obj in objs:
                for attr, factory in defaults.items():
                    value = getattr(obj, attr, None)
                    if value is None or type(value).__module__.startswith("sqlalchemy.orm"):
                        obj.__dict__[attr] = factory()

    def commit(self):
        self.committed += 1

    def refresh(self, obj):
        self.flush()

    def rollback(self):
        self.rolled_back += 1

    def bulk_save_objects(self, rows):
        for row in rows:
            self.add(row)
        self.flush()

    def get(self, model, key):
        for obj in self.store.get(self._key(model), []):
            if getattr(obj, "id", None) == key:
                return obj
        return None

    def execute(self, stmt):
        if isinstance(stmt, _Select):
            key = self._key(stmt.model)
            if key == "_agg":
                agg_model = getattr(stmt, "_from_model", None)
                items = list(self.store.get(self._key(agg_model), [])) if agg_model else []
                return FakeQuery([len(items)])
            items = list(self.store.get(key, []))
            for cond in getattr(stmt, "_filters", []):
                items = self._apply_filter(items, cond)
            if getattr(stmt, "_agg", None) == "count":
                return FakeQuery([len(items)])
            if getattr(stmt, "_grouped", False):
                # 群规模按 cohort_month 去重会员数（测试替身：按月聚合成 (month, n) 元组）
                grouped: dict[str, set] = {}
                for item in items:
                    grouped.setdefault(getattr(item, "cohort_month", "?"), set()).add(
                        getattr(item, "member_code", id(item))
                    )
                return FakeQuery([(month, len(members)) for month, members in grouped.items()])
            return FakeQuery(items)
        return FakeQuery([])

    @staticmethod
    def _apply_filter(items, cond):
        if not isinstance(cond, _Condition):
            return items
        kept = []
        for item in items:
            actual = getattr(item, cond.field, None)
            if cond.op == "eq" and actual == cond.value:
                kept.append(item)
            elif cond.op == "ne" and actual != cond.value:
                kept.append(item)
            elif cond.op == "lt" and actual is not None and actual < cond.value:
                kept.append(item)
            elif cond.op == "gt" and actual is not None and actual > cond.value:
                kept.append(item)
            elif cond.op == "le" and actual is not None and actual <= cond.value:
                kept.append(item)
            elif cond.op == "ge" and actual is not None and actual >= cond.value:
                kept.append(item)
            elif cond.op == "is" and actual is cond.value:
                kept.append(item)
        return kept


FakeSession.registry = {
    DataVersion: "DataVersion",
    MemberOrder: "MemberOrder",
    Cohort: "Cohort",
    RetentionCell: "RetentionCell",
    LtvReport: "LtvReport",
    ImportBatch: "ImportBatch",
}


def _order_row(order_no: str, amount: float, **kw) -> dict:
    base = {
        "order_no": order_no,
        "member_code": f"M-{order_no}",
        "cohort_month": "2026-10",
        "order_month": "2026-10",
        "channel": "private",
        "amount": amount,
        "store_code": "MY1",
        "is_first_order": True,
    }
    base.update(kw)
    return base


class _Obj:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class ImportVersionFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = FakeSession()
        # 准备基线版本 v1 + 一条基线订单
        self.v1 = _Obj(
            id="v1-id", seq=1, label="base", snapshot_month="2026-11",
            orders_count=1, members_count=1, cohorts_count=1, cells_count=0,
        )
        self.db.store["DataVersion"] = [self.v1]
        base_order = _Obj(
            id="o1", version_id="v1-id", order_no="MO1", member_code="M-MO1",
            cohort_month="2026-10", channel="private", store_code="MY1",
            order_month="2026-10", month_index=0, amount=10.0,
            is_first_order=True, ordered_at=None, source_batch_id=None,
            updated_by_seq=None,
        )
        self.db.store["MemberOrder"] = [base_order]
        self.db.store["Cohort"] = [_Obj(id="c1", month="2026-10", size=1, channel_mix={})]
        self.db.store["RetentionCell"] = []
        self.db.store["LtvReport"] = []
        self.db.store["ImportBatch"] = []

        # 替身：版本服务的 current_version/current_seq
        self._patches = [
            mock.patch.object(import_service, "select", _FAKE_SA.select),
            mock.patch.object(import_service, "func", _FAKE_SA.func),
            mock.patch.object(
                import_service.version_service, "current_version",
                side_effect=lambda db: self.db.store["DataVersion"][-1],
            ),
            mock.patch.object(
                import_service.version_service, "lock_current_version",
                side_effect=lambda db: self.db.store["DataVersion"][-1],
            ),
            mock.patch.object(
                import_service.version_service, "current_seq",
                side_effect=lambda db: self.db.store["DataVersion"][-1].seq,
            ),
            mock.patch.object(
                import_service.version_service, "create_version",
                side_effect=self._fake_create_version,
            ),
            mock.patch.object(
                import_service.retention_service, "rebuild_matrix",
                side_effect=self._fake_rebuild,
            ),
        ]
        for p in self._patches:
            p.start()
            self.addCleanup(p.stop)

    def _fake_create_version(self, db, **kw):
        kw.pop("cells_count", None)
        seq = db.store["DataVersion"][-1].seq + 1
        version = _Obj(id=f"v{seq}-id", seq=seq, cells_count=0, **kw)
        db.store["DataVersion"].append(version)
        return version

    def _fake_rebuild(self, db, **kw):
        version = next(v for v in db.store["DataVersion"] if v.id == kw["version_id"])
        return {
            "cells": 5,
            "data_version_seq": version.seq,
            "data_version_id": version.id,
        }

    def test_invalid_batch_changes_nothing(self) -> None:
        before_orders = len(self.db.store["MemberOrder"])
        before_versions = len(self.db.store["DataVersion"])
        with self.assertRaises(AppError) as ctx:
            import_service.import_orders(
                self.db,
                batch_no="B-BAD",
                rows=[_order_row("MO2", amount=-3)],
                user=None,
            )
        self.assertEqual(ctx.exception.code, codes.IMPORT_INVALID)
        # 订单与版本指针均未动，失败批次只留痕
        self.assertEqual(len(self.db.store["MemberOrder"]), before_orders)
        self.assertEqual(len(self.db.store["DataVersion"]), before_versions)
        self.assertEqual(
            self.db.store["ImportBatch"][0].status, ImportBatchStatus.FAILED.value
        )

    def test_correction_creates_version_without_duplicate_order(self) -> None:
        result = import_service.import_orders(
            self.db,
            batch_no="B-OK-1",
            rows=[_order_row("MO1", amount=88.0), _order_row("MO2", amount=20.0)],
            user=None,
        )
        self.assertEqual(result["status"], ImportBatchStatus.APPLIED.value)
        self.assertEqual(result["batch_seq"], 2)
        self.assertEqual(result["updated"], 1)   # MO1 是更正
        self.assertEqual(result["inserted"], 1)  # MO2 是新增
        # 新版本只持有 2 条订单（同号不新增），旧版本 1 条原样保留
        v2 = self.db.store["DataVersion"][-1]
        v2_orders = [o for o in self.db.store["MemberOrder"] if o.version_id == v2.id]
        self.assertEqual(len(v2_orders), 2)
        v1_orders = [o for o in self.db.store["MemberOrder"] if o.version_id == "v1-id"]
        self.assertEqual(len(v1_orders), 1)
        corrected = next(o for o in v2_orders if o.order_no == "MO1")
        self.assertEqual(corrected.amount, 88.0)
        self.assertEqual(corrected.updated_by_seq, 2)

    def test_duplicate_batch_no_rejected(self) -> None:
        import_service.import_orders(
            self.db, batch_no="B-DUP", rows=[_order_row("MO9", 1.0)], user=None
        )
        with self.assertRaises(AppError) as ctx:
            import_service.import_orders(
                self.db, batch_no="B-DUP", rows=[_order_row("MO9", 1.0)], user=None
            )
        self.assertEqual(ctx.exception.code, codes.IMPORT_DUPLICATE_BATCH)

    def test_late_old_batch_rejected(self) -> None:
        # 当前已到 v2，投递方声明依据 v1 的晚到批次 → 拒绝
        import_service.import_orders(
            self.db, batch_no="B-V2", rows=[_order_row("MO7", 1.0)], user=None
        )
        with self.assertRaises(AppError) as ctx:
            import_service.import_orders(
                self.db, batch_no="B-LATE", source_seq=1,
                rows=[_order_row("MO8", 1.0)], user=None,
            )
        self.assertEqual(ctx.exception.code, codes.IMPORT_STALE_BATCH)
        statuses = [b.status for b in self.db.store["ImportBatch"]]
        self.assertIn(ImportBatchStatus.REJECTED.value, statuses)


class ReportLineageFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = FakeSession()
        self.v1 = _Obj(seq=1)
        self.db.store["DataVersion"] = [self.v1]
        self.db.store["LtvReport"] = []

        self._patches = [
            mock.patch.object(ltv_service, "select", _FAKE_SA.select),
            mock.patch.object(
                ltv_service.version_service, "current_seq",
                side_effect=lambda db: db.store["DataVersion"][-1].seq,
            ),
            mock.patch.object(
                ltv_service, "compute_results",
                side_effect=self._fake_results,
            ),
        ]
        for p in self._patches:
            p.start()
            self.addCleanup(p.stop)

    def _fake_results(self, db, **kw):
        seq = db.store["DataVersion"][-1].seq
        return {
            "snapshot_month": "2026-11",
            "params": {"margin_rate": 0.5, "forecast_months": 12},
            "fit": {"lambda": 0.2, "a": 1.0, "r2": 0.9},
            "channels": [],
            "totals": {"cohorts": 1, "members": 1, "observed_cells": 1,
                       "censored_cells": 0, "revenue": 10.0},
            "low_sample": {"cohorts": [], "channel_cells": []},
            "notes": {},
            "data_version_seq": seq,
        }

    def _make_report(self, seq: int, status: str = ReportStatus.DRAFT.value,
                     version_no: int = 1, lineage=None):
        import datetime
        import uuid
        lineage = lineage or uuid.uuid4()
        published_at = datetime.datetime(2026, 11, 1) if status == ReportStatus.PUBLISHED.value else None
        report = LtvReport(
            id=uuid.uuid4(), name="复盘口径", status=status,
            params={}, results={"fit": {}}, note="", created_by=None,
            lineage_id=lineage, version_no=version_no, source_data_seq=seq,
            supersedes_id=None, published_at=published_at,
            created_at=datetime.datetime(2026, 11, 1),
        )
        self.db.store["LtvReport"].append(report)
        return report

    def test_data_update_marks_report_stale_and_blocks_publish(self) -> None:
        report = self._make_report(seq=1)
        self.db.store["DataVersion"].append(_Obj(seq=2))  # 源数据更新

        from src.services.review_core import derive_review_state
        state = derive_review_state(report.status, report.source_data_seq, 2)
        self.assertEqual(state, "stale_draft")

        with self.assertRaises(AppError) as ctx:
            ltv_service.publish_report(self.db, report.id, None)
        self.assertEqual(ctx.exception.code, codes.REPORT_STALE)

    def test_recompute_makes_new_lineage_version_and_publish_takes_over(self) -> None:
        v1_report = self._make_report(seq=1, status=ReportStatus.PUBLISHED.value)
        self.db.store["DataVersion"].append(_Obj(seq=2))

        # 重算：同血缘 v2，基于新数据
        new_report = ltv_service.recompute_report(self.db, v1_report.id, None)
        self.assertEqual(new_report.lineage_id, v1_report.lineage_id)
        self.assertEqual(new_report.version_no, 2)
        self.assertEqual(new_report.source_data_seq, 2)
        self.assertEqual(new_report.supersedes_id, v1_report.id)
        self.assertEqual(new_report.status, ReportStatus.DRAFT.value)

        # 发布新版本：旧 published 转 superseded，口径切换到新版本
        published = ltv_service.publish_report(self.db, new_report.id, None)
        self.assertEqual(published.status, ReportStatus.PUBLISHED.value)
        self.assertEqual(v1_report.status, ReportStatus.SUPERSEDED.value)

        # 最新发布即新版本
        latest = ltv_service.latest_published(self.db)
        self.assertEqual(latest.id, new_report.id)


class ImportDryRunTests(ImportVersionFlowTests):
    def test_dry_run_does_not_write_and_keeps_batch_no_free(self) -> None:
        """dry-run 只校验不落库，且不占用正式批次号，同批次号随后可正式提交。"""
        versions_before = len(self.db.store["DataVersion"])
        orders_before = len(self.db.store["MemberOrder"])

        preview = import_service.import_orders(
            self.db,
            batch_no="B-PREVIEW",
            rows=[_order_row("MO1", 88.0), _order_row("MO3", 5.0)],
            dry_run=True,
            user=None,
        )
        self.assertEqual(preview["status"], ImportBatchStatus.VALIDATED.value)
        self.assertEqual(preview["updated"], 1)
        self.assertEqual(preview["inserted"], 1)
        self.assertEqual(preview["would_activate_seq"], 2)
        # 订单与版本指针零改动
        self.assertEqual(len(self.db.store["DataVersion"]), versions_before)
        self.assertEqual(len(self.db.store["MemberOrder"]), orders_before)

        validated = self.db.store["ImportBatch"][0]
        self.assertTrue(validated.batch_no.startswith("B-PREVIEW#dryrun-"))

        # 同批次号正式提交不应被唯一索引/重复批次拦截
        applied = import_service.import_orders(
            self.db,
            batch_no="B-PREVIEW",
            rows=[_order_row("MO1", 88.0), _order_row("MO3", 5.0)],
            dry_run=False,
            user=None,
        )
        self.assertEqual(applied["status"], ImportBatchStatus.APPLIED.value)
        self.assertEqual(applied["batch_seq"], 2)

    def test_serialize_batch_shape(self) -> None:
        import_service.import_orders(
            self.db, batch_no="B-SHAPE", rows=[_order_row("MO5", 9.0)], user=None
        )
        batch = self.db.store["ImportBatch"][0]
        payload = import_service.serialize_batch(batch)
        for key in (
            "id", "batch_no", "status", "batch_seq", "source_seq", "dry_run",
            "row_count", "inserted_count", "updated_count", "unchanged_count",
            "rejected_count", "errors", "data_version_id", "applied_at", "created_at",
        ):
            self.assertIn(key, payload)
        self.assertEqual(payload["batch_seq"], 2)
        self.assertEqual(payload["status"], ImportBatchStatus.APPLIED.value)


if __name__ == "__main__":
    unittest.main()
