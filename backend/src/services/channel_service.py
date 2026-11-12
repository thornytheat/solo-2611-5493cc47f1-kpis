"""渠道对比：读最新已发布测算（没有就现场算一份，标记 live）。

viewer 带 channel_scope 时只返回自己渠道 + 全渠道汇总行，
这样「门店只读自己渠道」是真的后端过滤，不是前端隐藏。

版本口径：已发布报告是结果快照，源数据更新也不回写它 —— 渠道页继续展示冻结口径，
同时回传 stale 标记提示「依据数据已过期，等待新版本发布后一起切换」；
没有已发布报告时才现场按当前数据版本测算。
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.models.user import User
from src.services import ltv_service, version_service


def comparison(db: Session, user: User) -> dict:
    current_seq = version_service.current_seq(db)
    report = ltv_service.latest_published(db)
    if report is not None:
        results = report.results
        stale = int(report.source_data_seq) < current_seq
        meta = {
            "source": "published",
            "report_id": str(report.id),
            "report_name": report.name,
            "published_at": report.published_at.isoformat() if report.published_at else None,
            "report_version_no": report.version_no,
            "lineage_id": str(report.lineage_id),
            "source_data_seq": report.source_data_seq,
            "current_data_seq": current_seq,
            "stale": stale,
            "review_state": ltv_service.review_state(report, current_seq),
        }
    else:
        results = ltv_service.compute_results(db)
        meta = {
            "source": "live",
            "report_id": None,
            "report_name": "现场测算（尚未发布报告）",
            "published_at": None,
            "report_version_no": None,
            "lineage_id": None,
            "source_data_seq": current_seq,
            "current_data_seq": current_seq,
            "stale": False,
            "review_state": "live",
        }

    rows = list(results["channels"])
    scope = getattr(user, "channel_scope", None)
    scoped = False
    if scope:
        rows = [row for row in rows if row["channel"] == scope]
        scoped = True

    totals = {
        "channels": len(rows),
        "members": sum(int(r["members"]) for r in rows),
        "best_payback": rows[0]["payback_months"] if rows else None,
        "worst_payback": rows[-1]["payback_months"] if rows else None,
        "weighted_cac": round(
            sum(float(r["cac"]) * int(r["members"]) for r in rows)
            / max(1, sum(int(r["members"]) for r in rows)),
            2,
        ),
    }

    return {
        **meta,
        "snapshot_month": results["snapshot_month"],
        "fit": results["fit"],
        "ltv_hist": results["ltv_hist"],
        "ltv_pred12": results["ltv_pred12"],
        "arpu0": results["arpu0"],
        "margin_rate": results["params"]["margin_rate"],
        "rows": rows,
        "totals": totals,
        "scope": {"channel_scope": scope, "scoped": scoped},
        "low_sample": results["low_sample"],
        "notes": results["notes"],
    }
