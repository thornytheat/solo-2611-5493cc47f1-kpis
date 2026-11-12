"""pytest 环境：把 backend 根目录放进 sys.path（容器内 /app，本地 backend/）。

单测只依赖纯函数模块，不连数据库 / 网络；容器内运行：
    docker compose exec -T backend python -m pytest tests -q
"""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
