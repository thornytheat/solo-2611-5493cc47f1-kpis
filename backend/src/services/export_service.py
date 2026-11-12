"""导出：渠道对比 CSV（4 行）+ 测算说明 MD。"""
from __future__ import annotations

import csv
import io

CSV_HEADER = [
    "渠道",
    "渠道代码",
    "CAC(元)",
    "样本会员数",
    "观察月数",
    "人均累计营收(元)",
    "月均营收(元)",
    "月均毛利贡献(元)",
    "回本周期(月)",
    "历史LTV(元)",
    "预测12月LTV(元)",
]


def channels_csv(results: dict) -> tuple[str, int]:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(CSV_HEADER)
    for row in results["channels"]:
        writer.writerow(
            [
                row["label"],
                row["channel"],
                f"{row['cac']:.2f}",
                row["members"],
                f"{row['observed_months']:.2f}",
                f"{row['cum_per_member']:.2f}",
                f"{row['monthly_revenue']:.2f}",
                f"{row['monthly_margin']:.2f}",
                f"{row['payback_months']:.1f}",
                f"{row['ltv_hist']:.2f}",
                f"{row['ltv_pred12']:.2f}",
            ]
        )
    return buffer.getvalue(), len(results["channels"])


def report_md(results: dict, report_name: str, published_at: str | None = None,
              report_meta: dict | None = None) -> str:
    fit = results["fit"]
    params = results["params"]
    report_meta = report_meta or {}
    version_label = report_meta.get("version_label", "")
    source_seq = report_meta.get("source_data_seq")
    lines = [
        f"# {report_name}",
        "",
    ]
    if version_label:
        lines.append(f"- 报告版本：{version_label}（旧版本导出留痕，口径冻结在发布时刻）")
    if source_seq is not None:
        lines.append(f"- 源数据版本：v{source_seq}")
    lines += [
        f"- 快照月：{results['snapshot_month']}（M0..M12），预测窗 {params['forecast_months']} 个月",
        f"- 同期群：{results['totals']['cohorts']} 个，会员 {results['totals']['members']:,} 人，"
        f"有效格 {results['totals']['observed_cells']} / 右删失 {results['totals']['censored_cells']}",
        f"- 拟合：{fit['model']}，λ = {fit['lambda']:.3f}，a = {fit['a']:.4f}，R² = {fit['r2']:.2f}",
        f"- ARPU₀ = ¥{results['arpu0']:.2f}；历史 LTV = ¥{results['ltv_hist']:,}；"
        f"预测 12 月 LTV = ¥{results['ltv_pred12']:,}",
        f"- 毛利率 {params['margin_rate'] * 100:.0f}%（回本周期按毛利口径）",
        "",
        "| 排名 | 渠道 | CAC | 样本 | 月均毛利贡献 | 回本周期 | 历史 LTV | 预测 12 月 LTV |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in results["channels"]:
        lines.append(
            f"| {row['rank']} | {row['label']} | ¥{row['cac']:.0f} | {row['members']} | "
            f"¥{row['monthly_margin']:.2f} | {row['payback_months']:.1f} 月 | "
            f"¥{row['ltv_hist']:.0f} | ¥{row['ltv_pred12']:.0f} |"
        )
    low = results["low_sample"]
    if low["channel_cells"]:
        lines += ["", "低样本剔除（<30 人，不参与排行）："]
        for cell in low["channel_cells"]:
            lines.append(f"- {cell['month']} × {cell['channel']}：{cell['members']} 人")
    lines += [
        "",
        f"- 口径：{results['notes']['fit']}",
        f"- 口径：{results['notes']['payback']}",
        "",
        f"生成时间：{published_at or '—'}",
    ]
    return "\n".join(lines) + "\n"
