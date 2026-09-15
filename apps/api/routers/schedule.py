"""M8 排程算核 HTTP 层（Phase 1：路由仍注册在 api.main，此处为 monorepo 挂载点）。"""

from __future__ import annotations

# 后续将 api/main.py 中 /api/schedule/*、/api/plan/* 等逐步迁入本模块的 register(app)。
