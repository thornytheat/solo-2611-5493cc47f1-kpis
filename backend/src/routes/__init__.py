"""路由聚合：所有业务路由统一 /api 前缀（Nginx 反代时剥掉 /api）。"""
from fastapi import APIRouter

from src.routes import audit as audit_routes
from src.routes import auth as auth_routes
from src.routes import channel as channel_routes
from src.routes import cohort as cohort_routes
from src.routes import export as export_routes
from src.routes import health as health_routes
from src.routes import ltv as ltv_routes
from src.routes import orders as orders_routes

api_router = APIRouter()
api_router.include_router(health_routes.router)
api_router.include_router(auth_routes.router)
api_router.include_router(orders_routes.router)
api_router.include_router(cohort_routes.router)
api_router.include_router(ltv_routes.router)
api_router.include_router(channel_routes.router)
api_router.include_router(export_routes.router)
api_router.include_router(audit_routes.router)

__all__ = ["api_router"]
