# 斯芬克斯一体化前端

React 18 + TypeScript + Vite + Tailwind + React Router。

- **/login** 角色登录 · **/portal** 首页 · **/demo** 九幕剧本 · **/todos** 待办 · **/orders** · **/schedule** · **/stock** · **/bom** · **/cockpit**

## 开发

**必须同时开两个进程**，否则浏览器会 `ERR_CONNECTION_REFUSED`（没起前端）或页面空白/报错（没起后端）。

终端 1 — 后端（项目根目录，默认 `data/scheduling.db`，空库自动导种子）：

```bash
cd ..
.venv/bin/pip install -r requirements.txt   # 首次，需含 uvicorn
./scripts/start.sh
# 或: .venv/bin/python -m uvicorn api.app_factory:app --host 127.0.0.1 --port 8000 --reload
```

终端 2 — 前端（`/api` 代理到 8000，固定端口 **5180**）：

```bash
cd web
npm install   # 首次
npm run dev
```

浏览器打开 **http://127.0.0.1:5180**（与 `localhost:5180` 等价）

自检：`curl http://127.0.0.1:8000/api/health` 应返回 JSON；终端里 Vite 应显示 `ready` 且 Local 为 5180。

### 页面报 `500 Internal Server Error`

1. 确认 **8000 后端已启动**（只开前端、没开 uvicorn 时，Vite 代理也会表现为 500）。
2. **重启后端**（启动时会自动补 `conflicts_json` 等库表字段）。
3. 仍失败时在项目根执行：`./scripts/reset_db.sh`（删除并重建 `data/scheduling.db`），再重启后端并刷新页面。

## 九幕演示路径（Phase 8 · 详见 `/demo`）

1. **驾驶舱** `/cockpit` — 现状与 M1–M7  
2. **BOM** `/bom` — P2 工艺  
3. **金蝶** `/kingdee` — Mock 进单  
4. **订单/库存** — 入排产池  
5. **CTP** `/crm/ctp` — SO-002 试算  
6. **排程** `/schedule` — 一键倒排、试排、导出派工  
7. **变更** `/changes` — 影响清单 + 企微铃铛  
8. **插单** — 排程页 **插单试排** 四策略  
9. **验收** — `/demo` 范围说明 + BR-27 交期锚  

快捷入口：**/portal** · **/todos** · 文档 `docs/POC范围说明.md`、`docs/售前答复-实施与培训.md`

> 拖拽/改人力为 UI 预览 + 产能条重算；与后端 interactive apply 已部分联动。
