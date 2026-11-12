"""initial schema (cohortltv)

建表口径以 SQLAlchemy 模型为唯一事实来源：迁移直接调用 Base.metadata.create_all，
避免 demo 阶段手写 DDL 与模型漂移；容器默认由 scripts/bootstrap_db.py 建表，
本迁移用于正式环境 `alembic upgrade head`。

Revision ID: 0001
Revises:
Create Date: 2026-11-12
"""
from __future__ import annotations

from alembic import op

from src.config.settings import settings
from src.models import Base

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    bind.exec_driver_sql(f'CREATE SCHEMA IF NOT EXISTS "{settings.db_schema}"')
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
