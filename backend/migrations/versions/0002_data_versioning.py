"""data versioning, order import batches and ltv report lineage

- data_versions：源数据版本指针（seq 单调递增）
- import_batches：导入批次全生命周期留痕（validated/applied/failed/rejected）
- member_orders：order_no 唯一约束改为 (version_id, order_no)，新增版本/批次/更正序号列
- retention_cells：新增 version_id（矩阵随版本一起切换，旧版本格子保留）
- ltv_reports：新增血缘 lineage_id / version_no / source_data_seq / supersedes_id，
  name 解除全局唯一（同血缘多版本），新增 (lineage_id, version_no) 唯一约束

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-12
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from src.config.settings import settings
from src.models import Base

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

SCHEMA = settings.db_schema


def upgrade() -> None:
    bind = op.get_bind()
    # 与 bootstrap_db 一致：模型 metadata 是唯一事实来源，新增表直接 create_all（幂等）；
    # 已存在的 member_orders / retention_cells / ltv_reports 走下面的显式 ALTER。
    Base.metadata.create_all(bind=bind)

    op.add_column(
        "member_orders",
        sa.Column("source_batch_id", UUID(as_uuid=True), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "member_orders",
        sa.Column("updated_by_seq", sa.Integer(), nullable=True),
        schema=SCHEMA,
    )
    # order_no 的单列唯一索引降级为普通索引，唯一性移到 (version_id, order_no)
    op.drop_index("ix_member_orders_order_no", table_name="member_orders", schema=SCHEMA)
    op.create_index(
        "ix_member_orders_order_no", "member_orders", ["order_no"], schema=SCHEMA
    )
    op.create_index(
        "ix_member_orders_version", "member_orders", ["version_id"], schema=SCHEMA
    )
    op.drop_constraint(
        "member_orders_order_no_key", "member_orders", schema=SCHEMA, type_="unique"
    )
    op.create_unique_constraint(
        "uq_member_orders_version_order_no",
        "member_orders",
        ["version_id", "order_no"],
        schema=SCHEMA,
    )

    op.add_column(
        "retention_cells",
        sa.Column("version_id", UUID(as_uuid=True), nullable=True),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_retention_cells_version_id",
        "retention_cells",
        ["version_id"],
        schema=SCHEMA,
    )

    op.drop_constraint("ltv_reports_name_key", "ltv_reports", schema=SCHEMA, type_="unique")
    op.add_column(
        "ltv_reports",
        sa.Column("lineage_id", UUID(as_uuid=True), nullable=False),
        schema=SCHEMA,
    )
    op.add_column(
        "ltv_reports",
        sa.Column("version_no", sa.Integer(), nullable=False, server_default="1"),
        schema=SCHEMA,
    )
    op.add_column(
        "ltv_reports",
        sa.Column("source_data_seq", sa.Integer(), nullable=False, server_default="1"),
        schema=SCHEMA,
    )
    op.add_column(
        "ltv_reports",
        sa.Column("supersedes_id", UUID(as_uuid=True), nullable=True),
        schema=SCHEMA,
    )
    op.create_unique_constraint(
        "uq_ltv_lineage_version",
        "ltv_reports",
        ["lineage_id", "version_no"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_constraint("uq_ltv_lineage_version", "ltv_reports", schema=SCHEMA, type_="unique")
    op.drop_column("ltv_reports", "supersedes_id", schema=SCHEMA)
    op.drop_column("ltv_reports", "source_data_seq", schema=SCHEMA)
    op.drop_column("ltv_reports", "version_no", schema=SCHEMA)
    op.drop_column("ltv_reports", "lineage_id", schema=SCHEMA)
    op.create_unique_constraint("ltv_reports_name_key", "ltv_reports", ["name"], schema=SCHEMA)

    op.drop_index("ix_retention_cells_version_id", table_name="retention_cells", schema=SCHEMA)
    op.drop_column("retention_cells", "version_id", schema=SCHEMA)

    op.drop_constraint(
        "uq_member_orders_version_order_no", "member_orders", schema=SCHEMA, type_="unique"
    )
    op.create_unique_constraint(
        "member_orders_order_no_key", "member_orders", ["order_no"], schema=SCHEMA
    )
    op.drop_index("ix_member_orders_version", table_name="member_orders", schema=SCHEMA)
    op.drop_column("member_orders", "updated_by_seq", schema=SCHEMA)
    op.drop_column("member_orders", "source_batch_id", schema=SCHEMA)

    bind = op.get_bind()
    bind.exec_driver_sql(f'DROP TABLE IF EXISTS "{SCHEMA}"."import_batches" CASCADE')
    bind.exec_driver_sql(f'DROP TABLE IF EXISTS "{SCHEMA}"."data_versions" CASCADE')
