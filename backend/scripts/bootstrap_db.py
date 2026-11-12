"""建表引导：幂等 create_all（容器 entrypoint 第一步）。

demo 场景用 SQLAlchemy metadata 建表，避免首次启动卡在迁移版本对齐；
正式环境可改用 `alembic upgrade head`（见 backend/migrations/）。
"""
from __future__ import annotations

from sqlalchemy import text

from src.config.database import engine
from src.config.settings import settings
from src.models import Base


def main() -> None:
    with engine.begin() as conn:
        conn.execute(text("SELECT 1"))
        conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{settings.db_schema}"'))
    Base.metadata.create_all(bind=engine)
    print(
        f"[bootstrap] schema={settings.db_schema} tables={len(Base.metadata.tables)}",
        flush=True,
    )


if __name__ == "__main__":
    main()
