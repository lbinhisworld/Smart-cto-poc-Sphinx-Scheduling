# 斯芬克斯一体化前端

React 18 + TypeScript + Vite + Tailwind + React Router。

- **/login** 角色登录 · **/portal** 首页 · **/orders** 销售订单 · **/schedule** 排程 · **/stock** · **/bom**

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

## 演示路径（对齐 §2.2 第 2 / 4 步）

1. 订单池勾选三单 → **一键倒排** → 看板出现各组×天任务与产能条。
2. **拖拽**任务到其他日期/组 → 本地预览 + 产能条重算；**改人力**同理。
3. **试排** / **应用方案** / **丢弃预览** 与后端 what-if、apply 联动。
4. 修改 SO-002 交期后重新倒排 → 右侧冲突面板出现 E2 等待定位。

> 拖拽/改人力当前为 **UI 预览 + 产能条重算**；落库级任务 PATCH 与全栈撤销栈在后续阶段补齐。
