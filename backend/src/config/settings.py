"""集中配置：全部来自环境变量，默认值与 .env.example 保持一致。

算法口径参数（衰减模型、毛利率、低样本阈值）也都放在这里，
后端是唯一计算方，前端不允许硬编码任何结果。
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    # 品牌与业务
    brand: str = "cohortltv"
    org_name: str = "沐野咖啡连锁 · 会员增长组"
    org_meta: str = "120 万会员 · 380 家门店 · 8 人增长组"

    # 数据库
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "cohortltv"
    db_user: str = "cohortltv"
    db_password: str = "cohortltv_pw_2026"
    db_schema: str = "cohortltv"

    # 安全
    jwt_secret: str = "cohortltv-jwt-secret-change-me-2026"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 120
    refresh_token_days: int = 7

    # 运行时
    redis_url: str = "redis://localhost:6379/0"
    seed_demo: bool = True
    rate_limit_default_per_minute: int = 240
    rate_limit_ltv_per_minute: int = 20
    rate_limit_rebuild_per_minute: int = 6
    rate_limit_import_per_minute: int = 10

    # 观察口径：快照月（含）为止，M0 = 首单月
    snapshot_month: str = "2026-11"
    matrix_months: int = 13
    forecast_months: int = 12

    # 衰减拟合
    fit_lambda_min: float = 0.02
    fit_lambda_max: float = 0.60
    fit_lambda_step: float = 0.001

    # 单位经济
    gross_margin_rate: float = 0.50
    low_sample_threshold: int = 30

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
