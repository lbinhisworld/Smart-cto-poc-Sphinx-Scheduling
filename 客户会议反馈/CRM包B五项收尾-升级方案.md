# CRM 包 B 五项收尾 · 升级方案

> 2026-09-24。在 [第二次演示后-完整升级方案.md](第二次演示后-完整升级方案.md) 包 B 与 [CRM电脑端-低代码菜单对照.md](CRM电脑端-低代码菜单对照.md) 已交付大部分能力的基础上，收口五项演示与客户验收缺口。  
> 禁止写回 `so_order.due_date`（BR-27）。拜访草稿、不满 15 分钟的无效拜访不计目标与分布。

---

## 0. 与《CRM销售移动端-优化方案》的关系

移动端方案曾写「电脑商机大盘主图是漏斗 + 完整度」。**本批以 §5.2 为准**：销管/总经理第一眼是 **拜访成果 × 商机阶段 3×4 矩阵**；漏斗收成一行总数；拜访完整度可折叠为辅图。手机侧仍按移动端方案改产品名与分步确认，不重复做字段权限。

---

## 1. 五项清单

| # | 内容 | 验收一句 |
|---|------|----------|
| 1 | 商机大盘矩阵 + 下钻 + 预警 | 销管打开大盘见 3×4，切换全部拜访见陌拜，点格出名单 |
| 2 | 手机拜访确认链 | 说话→草稿→确认才写入；无效仍可保存；首页三条深链拜访 |
| 3 | Demo 种子 | 同一签约单两行 SKU；线索回收剧本；目标与有效拜访可复算 |
| 4 | 低代码列对齐 | 线索列、打样发起、报价头、目标月筛/编辑 |
| 5 | §5.4 权限回归 | 六角色调商机详情 API，无权字段不出现 |

---

## 2. 项 1 · 商机大盘

### 目标行为

- 行：`关系建联` / `触达决策人` / `挖到商机`；列：`还没成商机` / `打样` / `报价` / `签单`。
- 默认只计 **已确认且有效** 拜访；切换「全部拜访」时陌拜未建客户落在「还没成商机」。
- 点格：客户名单 → **再去拜访** / **补成商机** / 现有商机宽表。
- 销管预警：有效拜访低于目标；多次建联仍无成商机；已触达决策人无打样；打样/报价进行中 ≥7 天。

### 现状

- 后端 `board()` 已返回 `matrix`（`place_visits` + `_document_stage`）。
- 前端 `SalesBoard.tsx` 未消费 `matrix`，未传 `include_all`。

### 改动文件

- `db/crm_sales.py`：`_stall_alerts`、扩展 `_completeness_alerts` / `_matrix_alerts`
- `web/src/modules/crm/SalesBoard.tsx`：3×4 主图、toggle、漏斗副区
- `tests/test_crm_sales_board.py`：stall 与 matrix API

### 演示脚本

李业务手机确认「见到了决策人」→ 销管刷新大盘，该客户从建联格移到「触达决策人」行。

---

## 3. 项 2 · 手机拜访确认链

### 目标行为

- `POST /api/crm/visits/draft` 只出草稿不写库；`confirm` 才落拜访。
- 签退 − 签到 &lt; 15 分钟：`is_valid=false`，仍可确认，不计目标。
- 首页 `home.actions` 最多三条，点进 compose 带客户 query。
- 确认时按公司/电话匹配负责人线索，写跟进子表（与 PC 外勤一致）。
- 语音：浏览器语音识别，失败走手打/关键词/LLM；模型配置仅在系统配置（GM）。

### 改动文件

- `db/crm_sales.py`：`confirm_visit` 挂线索
- `db/crm_leads.py`：`link_visit_to_lead`（或复用 field visit 逻辑）
- `web/src/modules/crm/VisitPage.tsx`：分步 UI、语音、action 深链
- `tests/test_crm_visit_lead_link.py`

---

## 4. 项 3 · Demo 种子

### 目标行为

- `demo_data.json` 的 `order_lines` 至少一张生效合同对应订单 **2 行品项**，bump `order_lines_version`。
- 签约产品生产进度页同单两行、完成量/状态可区分（行级字段；订单头 `schedule_phase` 仍为订单级）。
- 线索：池内未分配 1 条；李业务「仅手写、应回收」；李业务「有效拜访、不回收」。
- 演示锚 `2026-09-15`；李业务 2026 年目标已拆月/周，第 3 周可见差额。

### 版本键

| 键 | bump 时行为 |
|----|-------------|
| `order_lines_version` | `ensure_order_lines` 重建行表 |
| `demo_version` | `ensure_demo_crm` 重建 CRM 子表（若改 crm 块） |

### 改动文件

- `seed/demo_data.json`、`seed/演示数据说明.md`
- `tests/test_contracted_progress.py`

---

## 5. 项 4 · 低代码列对齐

不做：导入/导出、真 GPS、对账、金蝶实时。

| 模块 | 要点 | 文件 |
|------|------|------|
| 线索 | 列表列与 doc 一致；池分配；打开列表触发回收 | `LeadsPages.tsx`、`crm_leads.py` |
| 打样 | 列表列 + **发起流程**（选商机、预交时间、草稿/提交） | `crm_samples_ui.py`、`sample_workflow.py`、`CrmPages.tsx`、router |
| 报价 | 详情头：客户、商机、税、区域等 | `QuotesPage.tsx`、`crm_quotes_ui.py` |
| 目标 | 月起止筛、年→月→周、编辑四指标（签约/回款为金额） | `GoalsPage.tsx`、`crm_goal_period.py` |

附录 A（字段对照）见 [CRM电脑端-低代码菜单对照.md](CRM电脑端-低代码菜单对照.md) 各节，实现以 API 字段名为准。

---

## 6. 项 5 · §5.4 列级权限

对 `GET /api/crm/opportunities/{id}`（及列表若含金额）断言：

| 角色 | 拜访正文 | 打样成本 | 内部报价 | 对客报价 | 签单 received |
|------|----------|----------|----------|----------|---------------|
| SALES | 有 | 无 | 无 | 有 | 无 |
| SALES_ASSIST | 有 | 无 | 无 | 有 | 无 contract_amount 规则同 MGR 团队额 |
| SALES_MGR | 有 | 无 | 无 | 有 | 有 contract_amount |
| RD | 无 | 有 | 无 | 无 | 仅 status |
| FIN | 无 | 有 | 有 | 有 | 有 received |
| GM | 有 | 有 | 有 | 有 | 全量 |

实现：`db/crm_sales.redact`；测试 `tests/test_crm_opportunity_redact_matrix.py`；列表漏网补 `crm_opportunity_ui`；`kb/coverage.yaml` 挂卡。

---

## 7. 实施顺序

```
写本文 → 种子(3) → 矩阵 UI(1) → 手机链(2) → 低代码(4) → 权限测(5)
```

每步跑 `pytest -q` 相关文件后再进下一步。

---

## 8. 测试清单

| 文件 | 断言要点 |
|------|----------|
| `test_crm_sales_board.py` | matrix、include_all、confirm 迁移、stall alerts |
| `test_contracted_progress.py` | 同单 ≥2 行 |
| `test_crm_visit_lead_link.py` | confirm 后线索跟进 |
| `test_crm_opportunity_redact_matrix.py` | 六角色字段矩阵 |
| `test_crm_leads.py` | 回收剧本（已有则回归） |

---

## 9. 风险

- **打样发起流程**：若缺 create API，需补样品单创建与 opp 阶段「打样中」，为本批最大增量。
- **目标指标**：低代码为「签约金额/回款金额」；若种子仍为次数，需在 `crm_goal_period` 与移动端块对齐，避免两套口径。
