# cohortltv · 会员同期群留存与 LTV 测算台

一杯咖啡的会员生意，12 个首单月同期群，M0 到 M12 的留存格子上色，右删失格子标灰不参与拟合；
ARPU 留存拿去做加权最小二乘拿到 λ 与 R²，再折成 12 个月预测 LTV 和渠道回本周期 —— 一句话：
**把「客单 32 × 假设 8 次」换成能解释给财务的衰减曲线。**

---

## 1. 真实场景

**模拟客户**：沐野咖啡连锁 · 会员增长组（8 人），120 万会员、380 家门店，会员消费含饮品、烘焙与礼盒/咖啡豆。

**现有工作流**：每月初把订单导出 Excel 做数据透视，按开卡月份手工拼留存表；LTV 用「客单 32 元 × 假设 8 次 = ¥256」拍脑袋；渠道投放靠感觉分配预算。

**三个痛点**

1. 留存矩阵手工拼容易错位，右删失月份根本没标，导致早期群被低估；
2. LTV 假设没有依据、无法解释给财务，换一个 λ 就换一套结论却说不清为什么；
3. 渠道 CAC 与回本周期算不清，私域和信息流到底谁该加预算，只能凭印象。

**上下游**：上游是会员开卡与订单事实（本地 fixture，自然分布 + 季节性）；本系统替代「Excel 透视 + 拍脑袋 LTV」这一段；
下游是月度增长复盘、渠道预算会与门店拉新考核。

**一天的工作剧本（2026-11-12）**

| 时间 | 谁 | 做什么 | 系统里留下什么 |
| --- | --- | --- | --- |
| 09:10 | 林知遥（分析师） | 把 11 月会员订单同步进库，跑一次矩阵重建 | Celery 任务 `cohortltv.rebuild_matrix`，780 个留存格 |
| 09:20 | 林知遥 | 看 12 群 × 13 月矩阵，发现 2026-10 群只有 2 格（右删失 11 格） | 矩阵页 `右删失 66 格` |
| 09:35 | 林知遥 | 点开 2025-11 群，确认 M1 43.6%、M6 21.4% 与「储值权益到期」台阶 | 群详情曲线 + 金额分布 |
| 10:05 | 林知遥 | 跑 LTV 测算（观察期 M0..M12、毛利率 50%） | 报告草稿：λ 0.213 / R² 0.94 / 历史 ¥412 / 预测 ¥536 |
| 10:30 | 陈可（负责人） | 复核敏感性表，确认 λ ±0.03 时预测 LTV 区间可接受 | 报告状态 `published` |
| 11:00 | 陈可 | 打开渠道对比：私域 CAC ¥38 回本 1.4 月、信息流 ¥126 回本 4.9 月 | 渠道排行冻结在已发布口径 |
| 11:15 | 陈可 | 导出渠道对比 CSV（4 行）+ MD 说明发给财务 | `audit_logs` 记两条 `export.download` |
| 14:00 | 周明（门店运营，只读） | 登录只看到「门店自然流」一列，确认门店回本 0.4 月 | 后端按 `channel_scope` 过滤 |

**角色权限**

| 角色 | 账号 | 主要页面 | 权限 | 典型动作 |
| --- | --- | --- | --- | --- |
| `admin` 增长负责人 | `admin@cohortltv.io` | 全部 | 全部 + `ltv:publish` + `audit:read` | 发布报告、看审计、定 CAC 口径 |
| `analyst` 增长分析师 | `analyst@cohortltv.io` | 矩阵 / 详情 / 测算 / 渠道 | 读 + `matrix:rebuild` + `ltv:run` + `channels:export` | 重建矩阵、跑测算、导出 CSV/MD |
| `viewer` 渠道与门店（只读） | `viewer@cohortltv.io` | 矩阵 / 详情 / 渠道（仅自己渠道） | 只读，`channel_scope=store` | 看门店回本、看留存矩阵 |

低权角色调用高权接口一律由后端返回 **403**（`src/middlewares/rbac.py`），前端按钮禁用只是提示，不是权限。

## 2. 主要功能

1. **留存矩阵**（算法 1）：12 个首单月同期群 × M0..M12 共 156 格，热力上色用烘豆色阶；右删失格斜纹标记、不参与拟合；列合计留存、低样本标记、Celery 异步重建。
2. **同期群详情**：人数留存曲线（SVG 自绘）、订单金额分布直方图、渠道构成与营收拆分、M6 台阶业务解释。
3. **LTV 测算**（算法 2）：观察期 / 毛利率 / 渠道 CAC 可配；后端网格搜索 λ∈[0.02,0.60]、闭式解 a、加权 R²；输出历史 LTV、预测 12 月 LTV、渠道回本表与敏感性表（λ ±0.03、CAC ×0.8/1.0/1.2）。
4. **复核与发布**：分析师出草稿，负责人发布；发布后渠道页与导出口径冻结。
5. **渠道对比与导出**：回本周期排行、低样本剔除说明、CSV（4 行）与 MD 说明下载。
6. **横切**：JWT + 三角色 RBAC、审计日志（登录/重建/测算/发布/导出/越权）、Redis 滑动窗口限流、全局错误处理。

## 3. 快速启动

```bash
cp .env.example .env          # 默认端口已按批次约定填好
docker compose up -d --build  # 5 个服务：frontend / backend / worker / db / redis
docker compose ps             # 等 5/5 healthy
```

打开 <http://localhost:18257> ，用下面任一账号登录。

**演示账号**（密码统一 `Demo@2026`，域名 `cohortltv.io`）

| 邮箱 | 角色 |
| --- | --- |
| `admin@cohortltv.io` | 增长负责人（发布 / 审计） |
| `analyst@cohortltv.io` | 增长分析师（重建 / 测算 / 导出） |
| `viewer@cohortltv.io` | 渠道与门店只读（`channel_scope=store`） |

seed 幂等（自然键：`users.email` / `cohorts.month` / `member_orders.order_no` / `ltv_reports.name`），
`SEED_DEMO=true` 时容器启动自动跑一次，也可以手动：

```bash
docker compose exec -T backend python -m scripts.seed_demo
# SEED_SUMMARY brand=cohortltv cohorts=12 members=6000 orders=24000 channels=4 users=3
```

访问地址：前端 <http://localhost:18257> ，后端直连 <http://localhost:19257/api/health> ，PostgreSQL `localhost:17757`。

## 4. 技术栈

| 层 | 选型 |
| --- | --- |
| 前端 | Vue 3.4 + TypeScript + Vite 5 + Pinia + Vue Router + axios；图表全部 SVG 自绘，无联网 CDN |
| 后端 | Python 3.11 + FastAPI + SQLAlchemy 2.0 + Pydantic v2 + PyJWT + passlib(bcrypt) |
| 异步 | Celery 5 + Redis（矩阵重建任务、心跳） |
| 数据库 | PostgreSQL 16（schema `cohortltv`） |
| 网关 | Nginx 1.27（`/api/` 反代 backend:8000，SPA 回落） |
| 容器 | Docker Compose，5 服务全部带 healthcheck |

## 5. 目录

```
gb-584/
├── docker-compose.yml          # 5 服务 + 命名卷 + healthcheck
├── .env / .env.example
├── backend/
│   ├── Dockerfile  entrypoint.sh  requirements.txt  alembic.ini
│   ├── migrations/             # alembic（容器默认走 bootstrap_db，迁移备用）
│   ├── scripts/
│   │   ├── bootstrap_db.py     # 建 schema + create_all
│   │   ├── fixtures.py         # 12 群 / 24,000 单的确定性生成器
│   │   └── seed_demo.py        # 幂等 seed + SEED_SUMMARY
│   └── src/
│       ├── config/             # settings / database / celery_app / app
│       ├── constants/          # enums / roles / channels / error_codes / limits / templates
│       ├── models/             # cohort / member_order / retention_cell / ltv_report / audit_log / user
│       ├── schemas/            # auth / cohort / ltv / channel / audit / common
│       ├── services/           # decay_fit / retention / cohort / ltv / channel / export / auth / audit
│       ├── controllers/        # 参数编排 + 审计
│       ├── routes/             # /api 路由（健康、认证、矩阵、测算、渠道、导出、审计）
│       ├── middlewares/        # auth / rbac / rate_limit / audit_logger / security_headers / error_handler
│       └── utils/              # jwt / errors / logger / redis_client / months / numbers
├── worker/
│   ├── Dockerfile  healthcheck.sh
│   └── src/{config,tasks}      # celery_app / matrix（重建）/ heartbeat
└── frontend/
    ├── Dockerfile  nginx.conf  index.html  vite.config.ts
    └── src/
        ├── api/                # http / auth / cohort / ltv / channel / audit
        ├── stores/             # auth / cohort / ltv
        ├── types/              # api / user / domain
        ├── constants/          # enums / roles / messages
        ├── components/common/  # AppShell / PageHeader / StampSeal / EmptyState / ErrorNotice / RoastLegend
        ├── components/business/# RetentionHeatTable / RetentionCurve / AmountHistogram / SensitivityTable / PaybackBars
        ├── hooks/              # useAsync / useLtvForm
        ├── utils/              # request / format / curve
        ├── router/             # index / guards
        ├── pages/              # Login / Matrix / CohortDetail / Ltv / Channels
        └── styles/             # tokens.css / base.css
```

## 6. 环境变量

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `COMPOSE_PROJECT_NAME` | `cohortltv` | 容器名前缀 |
| `FRONTEND_PORT` | `18257` | 前端宿主端口 → 容器 80 |
| `BACKEND_PORT` | `19257` | 后端宿主端口 → 容器 8000 |
| `DB_PORT` | `17757` | PostgreSQL 宿主端口 → 容器 5432 |
| `DB_NAME` / `DB_USER` / `DB_PASSWORD` | `cohortltv` / `cohortltv` / `cohortltv_pw_2026` | 库与账号 |
| `JWT_SECRET` | 演示值 | 生产必须替换 |
| `REDIS_URL` | `redis://redis:6379/0` | Celery broker + 限流 + 心跳 |
| `SEED_DEMO` | `true` | 启动时跑一次幂等 seed |

后端还有一组口径参数默认值（`src/config/settings.py`）：`SNAPSHOT_MONTH=2026-11`、`MATRIX_MONTHS=13`、
`FIT_LAMBDA_MIN/MAX=0.02/0.60`、`GROSS_MARGIN_RATE=0.50`、`LOW_SAMPLE_THRESHOLD=30`。

## 7. Docker 说明

- 恰好 5 个服务，全部带 healthcheck：`db`（pg_isready）、`redis`（redis-cli ping）、`backend`（`/api/health`）、
  `worker`（Redis 心跳键 `cohortltv:worker:heartbeat`，兜底 celery ping）、`frontend`（wget `/`）。
- `backend`/`worker` 依赖 `db`、`redis` 的 `service_healthy`；`frontend` 依赖 `backend` healthy。
- 命名卷：`db_data`（PG 数据）、`redis_data`（AOF）。
- 前端构建用 `ARG NPM_REGISTRY`（默认 npmmirror，可 `--build-arg` 覆盖）；pip 走清华源。
- 收尾：`docker compose down -v --remove-orphans`。

## 8. 算法口径（前后端同源，前端只展示）

**算法 1 · 同期群留存矩阵**（`backend/src/services/retention_service.py`）

- 分群：按首单月（`member_orders.cohort_month`），群规模 N = 该群去重会员数；
- M0 = 首单月（全员活跃）；Mn = 第 n 个月有 ≥1 单的去重会员数 / N；
- 快照月（2026-11）尚未走到的月序 → `right_censored=true`，`active=0`、`retention=null`，不参与拟合；
- 每个格子按渠道拆一份，`channel='all'` 是矩阵汇总格。

**算法 2 · LTV 与回本**（`backend/src/services/decay_fit.py` + `ltv_service.py`）

- ARPU₀ = 各群 M0 营收 / 各群规模（全渠道加权）；
- 拟合对象是 **ARPU 留存** `y = (格内营收 / 群规模) / ARPU₀`（人数留存矩阵单独展示，M6 台阶不影响拟合）；
- 模型 `R_m = a·exp(-λm)`：λ 在 `[0.02, 0.60]` 上 0.001 步长网格搜索，给定 λ 时
  `a = Σ w·y·e^{-λm} / Σ w·e^{-2λm}` 为加权最小二乘闭式解，权重 `w = 群规模`；
- 历史 LTV = 观察期内群累计营收 / 群规模，跨群按会员数加权；
- 预测 12 月 LTV = `ARPU₀ × Σ_{m=0..11} a·exp(-λm)`；
- 回本周期 = `CAC / 月均毛利贡献`，月均毛利贡献 = 观察期人均月营收 × 毛利率（默认 50%）；
- 群或「群×渠道」样本 < 30 → `low_sample`，不进入渠道排行；
- 无 scipy/sklearn 依赖：13 个月列 × 581 个候选 λ，纯 Python 手写。

## 9. 共享枚举出现位置

**枚举 A：渠道 `Channel`（private / paid_feed / store / partner / all）**

- 后端：`backend/src/constants/enums.py`、`backend/src/constants/channels.py`（标签/CAC/占比/营收系数）、
  `backend/src/models/retention_cell.py`、`backend/src/services/{retention,ltv,channel,cohort}_service.py`、
  `backend/src/services/export_service.py`、`backend/scripts/fixtures.py`
- 前端：`frontend/src/constants/enums.ts`、`frontend/src/utils/format.ts`、
  `frontend/src/components/business/{RetentionHeatTable,PaybackBars}.vue`、
  `frontend/src/pages/{CohortDetail,Channels}.vue`、`frontend/src/components/common/AppShell.vue`

**枚举 B：留存格状态 / 报告状态 / 任务状态 / 衰减模型
（`CellState`、`ReportStatus`、`JobStatus`、`DecayModel`）**

- 后端：`backend/src/constants/enums.py`、`backend/src/constants/error_codes.py`（状态相关的错误码）、
  `backend/src/constants/templates.py`（动作名与口径文案）、`backend/src/models/{retention_cell,ltv_report}.py`、
  `backend/src/services/{retention,ltv,cohort}_service.py`、`backend/src/controllers/cohort_controller.py`
- 前端：`frontend/src/constants/enums.ts`、`frontend/src/constants/messages.ts`、
  `frontend/src/stores/{cohortStore,ltvStore}.ts`、`frontend/src/pages/{MatrixPage,LtvPage}.vue`、
  `frontend/src/components/business/RetentionHeatTable.vue`

**枚举 C：角色 `admin / analyst / viewer`**

- 后端：`backend/src/constants/roles.py`、`backend/src/middlewares/rbac.py`、`backend/src/services/auth_service.py`
- 前端：`frontend/src/constants/roles.ts`、`frontend/src/stores/authStore.ts`、`frontend/src/components/common/AppShell.vue`

## 10. 本地开发（可选）

```bash
# 后端
cd backend && python3.11 -m venv .venv && source .venv/bin/activate
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
DB_HOST=localhost DB_PORT=17757 python -m scripts.bootstrap_db
DB_HOST=localhost DB_PORT=17757 uvicorn src.main:app --reload --port 19257
# 前端
cd frontend && npm install --registry=https://registry.npmmirror.com && npm run dev   # 18257
```

## 11. License

MIT（演示项目，数据为合成 fixture，不含真实用户信息）。
