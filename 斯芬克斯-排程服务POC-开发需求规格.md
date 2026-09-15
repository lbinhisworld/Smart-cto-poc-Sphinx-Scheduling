# 斯芬克斯 · 排程服务 POC — 开发需求规格（Cursor 交付版）

> **版本**：v1.0 ｜ 2026-09-14
> **用途**：本文件是 **POC 阶段的唯一开发输入**。请把它整体放进项目根目录，Cursor 可直接依据本文件生成代码。
> **上游文档**（有疑问时回查，但**不要**把它们当开发输入）：
> - `04-排程专题/斯芬克斯-L2交互式倒排排程-实现方案.md`（v1.3，方案全文，本文件是它的 §3/§11/§13 的工程化落地）
> - `04-排程专题/斯芬克斯-从订单到工单的拆解过程（含SPH算例）.md`（v1.1，算例来源）
> - `04-排程专题/斯芬克斯-当前排程方式解析.md`（v1.2，现状事实）
> - `03-客户需求文档/斯芬克斯-客户现有Excel表头清单（字段梳理）.md`（派工单导出的列依据）
>
> **约定标记**
> - `MUST` 必须实现，不做则 POC 不成立；`SHOULD` 建议实现；`MAY` 有余力再做
> - `A1…A10` = 待客户确认项，**POC 采用本文档给定的默认值**（见 §13），不要卡住等确认
> - `BR-xx` = 业务规则编号，测试用例与代码注释一律引用该编号
>
> **一句话目标**：用 2 周做出一个能当着客户面演示的排程服务 —— 录入订单 → 一键倒排 → 自动生成二部半成品工单 → 改交期立刻报警。

---

## 1. 业务背景（写给 AI 的领域说明，务必先理解再写代码）

### 1.1 客户是谁、做什么

苏州斯芬克斯食品有限公司：巧克力 / 糖艺装饰件生产，多品种小批量，**按单生产（MTO）、无备货**。三地工厂，本次排程范围主要是苏州（研发打样 + 生产）与泗洪主产能基地。品项特征：SKU 多、订量少、颜色/包规多。

### 1.2 生产组织（排程的两个层级）

| 部门 | 职责 | 关键性 |
|---|---|---|
| **生产一部** | 成品组装（客户要的盒/枚） | 所有订单的主链路 |
| **生产二部** | 半成品生产（**仅部分品项需要**） | 两层排产的核心 |

一组执行单元：**手工组 / 模具组 / 浇注组 / 二部半成品组**。排程颗粒度 = **组 × 天**（不做机台、不做工序、不做到小时）。

### 1.3 现状：Excel「一表三用」

客户现在没有 MES，三张《组排程》Excel 同时充当：**排产计划 + 派工单 + 报工单**。生管每天早上手工算、手工填、手工核。

直接后果 —— 客户口述的三个痛点：
1. **漏排单**（尤其半成品：成品排好了，二部忘了排）
2. **改一次要重算半天**（改交期、加量、插单 → 全部人工核对）
3. **不知道会不会来不及**（没有提前预警，等发现时已经赶不出来）

### 1.4 计量体系（**整个系统最容易出错的地方**）

同一件货在不同环节用不同单位：

| 环节 | 单位 |
|---|---|
| 作业（生产/排程） | **版**（系统内部唯一计量口径） |
| 销售/报价 | 枚、盒 |
| 仓储物流 | 包、袋、箱 |

换算链：`枚 → 版 → 盒 → 包 → 袋 → 箱`

> ⚠️ 客户现有 Excel **只有 枚/版、版/盒**，`盒→包→袋→箱` 缺失（阻塞项 S1）。
> **POC 对策：只支持 枚/版/盒 三种单位参与计算**，其余单位字段保留但置空；遇到需要包/袋/箱计量的品项，标记为「不可自动排产」。

### 1.5 为什么排程必须单独做（不是 CRUD）

低代码/表单类 MIS 擅长"记录业务"，排程是"计算业务"：循环迭代、what-if 副本、毫秒级重算、规则频繁变且需要回归测试。**POC 采用独立服务实现，MIS 部分（CRM/订单/主数据）后续通过接口对接，本期不做。**

---

## 2. POC 的业务目标与范围

### 2.1 要达成的业务目标（验收口径）

| # | 目标 | 可验证方式 |
|---|---|---|
| G1 | **半成品不再漏排**：成品工单一落位，半成品工单自动生成并倒排 | 演示：录一张走半成品的订单 → 看板自动出现二部任务 |
| G2 | **交期风险提前预警 ≥ 4 天** | 演示：把交期改早 → 半成品工单变红 + 给出最快可交期 |
| G3 | **排产从"半天"到"几秒"** | 演示：一键倒排，10 张单 1 秒内出结果 |
| G4 | **生管敢用**：结果能看、能改、能撤销 | 演示：拖拽改期、改人力实时重算、what-if 试排后丢弃 |
| G5 | **插单有据可依**：确认前看到代价 | 演示：插一张单 → 方案对比 + 影响 diff → 选一个应用 |

### 2.2 演示脚本（POC 交付时按这 7 步走一遍，客户评审用）

```
1. 参数中心：展示 3 个真实品项的 SPH 四元组（值/口径/人数/单位）+ 单位换算链
2. 订单池：录入 SO-001（P1 100盒，交期 9/23）→ 一键倒排
   → 看板：手工组 9/22 120版 + 9/23 300版，工时 3.2h / 8h
3. 录入 SO-002（P2 200盒，交期 10/7，走半成品）
   → 看板：模具组 7 天任务；**二部半成品组 9/25 自动出现 282 版**（毛需求 412 − 库存 130）
4. 拖拽改期 / 改人力 → 工时与产能占用实时重算
5. ★ 把 SO-002 交期改到 9/30
   → 半成品 due 从 9/25 变 9/18 → **黄色提示：落在冻结区，需人工确认**
6. ★ 再改到 9/23
   → **红色 E2：半成品来不及。最快可交期 = 9/29**  ← 全场最高潮
7. 插单演示：新增紧急单 → 四策略代价对比 + diff 视图 → 应用 → 计划变更单
```

### 2.3 In Scope（POC 必须做）

- 参数中心（品项 / 单位换算 / SPH 四元组 / 工艺路线 / 组日历）+ Excel 导入
- 订单池（手工录入 + CSV 导入，模拟金蝶 Push）
- **倒排引擎**（纯函数，五步）
- 半成品两层排产（净需求 + 提前期倒排 + 依赖链）
- 冲突检测 E1–E10（只提示不阻断）
- 组×天交互看板（拖拽、改人力、锁定、拆合、what-if、撤销）
- 插单流程（时间栅栏 + 四策略 + diff 视图 + 留痕）
- 派工单导出（客户现有《组排程》Excel 格式）
- 全套单元测试（见 §11）

### 2.4 Out of Scope（POC **明确不做**，写了等于给自己挖坑）

| 不做 | 原因 |
|---|---|
| 对接金蝶 K/3 Push 接口 | POC 用 CSV/JSON 模拟，接口契约先定好即可 |
| SSO / 权限 / 组织架构 / 移动端 | 复用后续 MIS，POC 单用户 |
| 报工录入与 SPH 自校准闭环 | 二期（但数据模型要预留字段） |
| 有限产能求解、换线优化、APS（OR-Tools 等） | 一期明确不做，**禁止引入优化库** |
| 机台 / 工序 / 人员级排程 | 颗粒度固定为 组×天 |
| 正排、双向排 | 一期只用 JIT 倒排 |
| 自动修改订单交期 | ❌ **红线**，见 §12 禁止事项 |
| 生产看板大屏 / 车间端 APP | 二期 |

---

## 3. 术语与概念表（代码中命名以此为准）

| 术语 | 英文/字段名 | 含义 |
|---|---|---|
| 版 | `board` | **系统内部唯一作业计量单位**，所有计算归一到版 |
| 枚 | `pcs` | 最小单件 |
| SPH | `sph` | Standard Pieces per Hour，标准小时产能。**四元组**：值 + 口径 + 人数 + 单位 |
| SPH 口径 | `sph_basis` | `SINGLE`（一人一小时）/ `CREW`（多人配合一小时，人数已含） |
| 墙钟小时 | `hours_wall` | 占日历的时间，**排日程用** |
| 人·时 | `hours_man` | `hours_wall × 投入人数`，**算成本用**。两者 MUST 分开存储 |
| 组 | `group_code` | 手工组 / 模具组 / 浇注组 / 二部半成品组 |
| 工单 | `wo` | 成品工单 `FINISHED` / 半成品工单 `SEMI` |
| 生产任务 | `wo_task` | 工单落在「某组某天」的一条 = **现有一行《组排程》** |
| 倒排 | backward scheduling | 从交期往回填任务 |
| JIT 模式 | `jit` | 尽量贴近交期，不提前占用近期产能（POC 唯一模式） |
| 时间栅栏 | time fence | 冻结区 / 协议区 / 自由区（§7.1） |
| 冻结区 | frozen zone | `today → today + 4 天`，长度 = 半成品提前期 |
| 涟漪 | ripple | 一个单变化导致一串单开工日往前移 |
| 死区 | deadband | 位移 < 0.5 天或工时变化 < 10% 则不重排 |
| what-if | simulation | 在内存副本上试排，不满意丢弃 |
| 计划版本 | `plan_version` | 每次重排生成一个版本号，用于 diff 与追溯 |

---

## 4. 业务规则全集（BR-xx，测试与代码注释引用此编号）

### 4.1 主数据与换算

| 编号 | 规则 | MUST |
|---|---|---|
| **BR-01** | 所有数量计算**必须先归一到「版」**；禁止拿枚直接除 SPH、也禁止拿盒直接除 SPH | ✅ |
| **BR-02** | `qty_board_plan = ceil(qty_order × board_per_box × (1 + loss_rate))`，向上取整到整数版 | ✅ |
| **BR-03** | 单位换算必须走 `md_uom_convert` 换算链；**禁止硬编码换算率**；POC 仅参与 枚/版/盒 | ✅ |
| **BR-04** | SPH 换算到「版/小时」：`sph_board = sph_value × factor(sph_uom → 版)` | ✅ |
| **BR-05** | 6 种单位枚举：`PCS / BOARD / BOX / PACK / BAG / CARTON`；POC 仅 `PCS/BOARD/BOX` 参与计算 | ✅ |

### 4.2 组产能与工时

| 编号 | 规则 | MUST |
|---|---|---|
| **BR-10** | `SINGLE` 口径：`group_rate = sph_board × crew_plan` | ✅ |
| **BR-11** | `CREW` 口径：`group_rate = sph_board`（**人数已含在 SPH 内，绝不再乘**）；若 `crew_plan ≠ sph_crew` → 冲突 **E8** | ✅ |
| **BR-12** | `hours_wall = qty_board ÷ group_rate`；`hours_man = hours_wall × crew_plan`；两者**分字段存储** | ✅ |
| **BR-13** | 组日容量 `day_cap = floor(hours_per_day × group_rate)`（单位：版，向下取整，保守） | ✅ |
| **BR-14** | `crew_plan ≤ group.headcount`；超过则不允许（前端拦截） | ✅ |

### 4.3 倒排

| 编号 | 规则 | MUST |
|---|---|---|
| **BR-20** | 倒排起点 `cursor = due_date`（**交期当天可排产**，视为当天完成即可发货） | ✅ |
| **BR-21** | 最早可排日 `earliest = max(today, 齐套日 ready_date)`；`cursor < earliest` 仍有余量 → 未安置 → **E1** | ✅ |
| **BR-22** | 只在工作日落位（`md_capacity_calendar.is_workday = true`），非工作日跳过 | ✅ |
| **BR-23** | 当日剩余容量 `free = day_cap − 已占用(含已锁定任务)`；`free ≤ 0` → 前一天 | ✅ |
| **BR-24** | 当日落位量 `qty = min(remaining, free)`，余数继续往前一天 → 自然形成跨天切分 | ✅ |
| **BR-25** | 处理顺序（**决定涟漪方向，务必按此实现**）：默认 `sort_mode = DUE_DESC`，即 `due_date 降序 → priority_score 降序 → wo_no 升序`；插单/改单场景用 `PIN_FIRST`（被触发或人工置顶的工单 rank=0 先排，其余仍按 DUE_DESC）；可选 `DUE_ASC`（紧急单优先，代价是晚单会被拆到更远的空位）。**POC 必须实现 DUE_DESC + PIN_FIRST** | ✅ |
| **BR-26** | `is_locked = true` 的工单**不参与重排**，但其已有任务 MUST 先计入占用 | ✅ |
| **BR-27** | 计划结果**只写开工/完工日与任务行，绝不写回订单交期** | ✅ 红线 |

### 4.4 半成品两层排产

| 编号 | 规则 | MUST |
|---|---|---|
| **BR-30** | 仅 `needs_semi = true` 的品项触发生成半成品工单 | ✅ |
| **BR-31** | `gross_semi_board = ceil(qty_order × semi_board_per_box × (1 + loss_rate))` | ✅ |
| **BR-32** | `net_semi_board = max(0, gross_semi_board − semi_stock_available)`；`= 0` 则**不生成**半成品工单（库存已覆盖） | ✅ |
| **BR-33** | 半成品 `due_date = 成品工单 plan_start − lead_time_days`（**自然日**，默认 4） | ✅ |
| **BR-34** | **必须先排成品、再排半成品**；成品一动，半成品 MUST 全部重算（含删除后重建） | ✅ |
| **BR-35** | 半成品倒排同样受 BR-21/22/23 约束；无法在 `earliest` 前安置 → **E2 红色** | ✅ |
| **BR-36** | 依赖表 `wo_dependency` 记录 `SEMI → FINISHED`，`type = FS`，`offset_days = lead_time_days` | ✅ |
| **BR-32b** | 多订单共用同一库存快照时，按 **BR-25 处理顺序**逐成品 WO 从运行池扣减；每行 BOM `net` 决定 SEMI 工单量（与 BR-32 公式一致，但 `semi_stock_available` 为池内剩余） | ✅ |
| **BR-37** | 成品 BOM 可有多行子件（`md_bom_line`）：`SEMI` 生成/扣库半成品 WO；`PURCHASED` 仅参与齐套与占库，**不生成 WO** | ✅ |
| **BR-38** | 运行内 `KitSnapshot`：`consume(item, qty_board)` 记录占库流水；前序订单占用的库存对后序表现为可用量减少（冲突 **E10**） | ✅ |
| **BR-39** | `kit_ready_date = max(SEMI 计划完工 + offset, 外购件就绪日)`；外购有库存则就绪日 = `today`，缺料记 shortage（WARN 下仍排产） | ✅ |
| **BR-39b** | `kit_mode`: `WARN`（默认，仅 E9/E10 提示）\| `STRICT`（成品 `plan_start < kit_ready` 时推后或组合 E2/E9）；POC 默认 **WARN** | ✅ |

### 4.5 插单与重排

| 编号 | 规则 | MUST |
|---|---|---|
| **BR-40** | **禁止全量重排作为默认行为**；默认按时间栅栏分区处理（§7.1） | ✅ |
| **BR-41** | 冻结区内已下发/已锁定任务不可被涟漪移动 | ✅ |
| **BR-42** | 变动死区：位移 `< 0.5 天` 或工时变化 `< 10%` 的任务**保持原位不重排** | ✅ |
| **BR-43** | 单次重排受影响工单 `> ripple_limit(默认 10)` 时，**不自动应用**，转为列表分批确认 | ✅ |
| **BR-44** | 每次重排生成 `plan_version`；diff 基于两个版本计算（§6.7） | ✅ |
| **BR-45** | 插单必须填「原因 + 期望交期」，并写入 `wo_insert_log` | ✅ |
| **BR-46** | 优先级权重**可配置**，默认 `交期紧急度 0.5 / 客户等级 0.2 / 金额 0.1 / 已备料 0.2 / 战略客户 0` | ✅ |
| **BR-47** | 系统对「物理不可行」MUST 明确判定并给出最快可交期，**禁止硬排一个做不到的计划** | ✅ |

### 4.6 冲突

| 编号 | 规则 |
|---|---|
| **BR-50** | 全部冲突（E1–E8、**E9–E10**）均为**软约束**：只提示、不阻断；人工违反时 MUST 填 `override_reason` |

---

## 5. 数据模型（Pydantic + SQLite 均可，字段 MUST 完全一致）

> POC 用 SQLite 即可（`data/scheduling.db`），但引擎层 MUST 只依赖 Pydantic 模型，不依赖 ORM（保证纯函数可测）。

### 5.1 枚举（全局统一，禁止用字符串字面量）

```
Dept        = FINISHED_DEPT(生产一部) | SEMI_DEPT(生产二部)
GroupCode   = MANUAL(手工组) | MOLD(模具组) | POURING(浇注组) | SEMI(二部半成品组)
WoType      = FINISHED | SEMI
WoStatus    = DRAFT | PLANNED | RELEASED | DONE
Uom         = PCS | BOARD | BOX | PACK | BAG | CARTON
SphBasis    = SINGLE | CREW
Confidence  = HIGH | MID | LOW
ConflictLv  = RED | YELLOW | GREY | BLUE
ChangeType  = ADD | MOVE | DELAY | LATE | REMOVE
```

### 5.2 主数据

**`md_item` 品项**

| 字段 | 类型 | 说明 |
|---|---|---|
| item_code | str PK | 型号 |
| item_name | str | 品名 |
| dept | Dept | 所属部门 |
| group_code | GroupCode | 默认执行组 |
| unit_sale | Uom | 销售单位 |
| pcs_per_board | int | 枚/版 |
| board_per_box | Decimal | 版/盒 |
| loss_rate | Decimal | 损耗率，如 0.05 |
| color | str | 巧克力颜色（换线判定） |
| is_semi | bool | 是否半成品品项 |
| computable | bool | **是否可自动排产**（缺包/袋/箱换算链时 = false） |

**`md_uom_convert` 单位换算链**

| 字段 | 类型 | 说明 |
|---|---|---|
| item_code | str | |
| from_uom / to_uom | Uom | 相邻两级，如 PCS→BOARD、BOARD→BOX |
| factor | Decimal | `1 from_uom = factor × to_uom` |

> 实现要求：换算 MUST 通过链上逐级相乘得到，禁止直接写 `box→board` 的魔法数字（BR-03）。

**`md_item_route` 工艺路线**

| 字段 | 类型 | 说明 |
|---|---|---|
| item_code | str | 成品品项 |
| needs_semi | bool | 是否走半成品 |
| semi_item_code | str \| None | 半成品品项 |
| semi_board_per_box | Decimal \| None | 1 盒成品需几版半成品 |
| lead_time_days | int | 默认 4 |
| changeover_min | int | 换线时长（分钟），默认 30 |

**`md_sph` SPH 四元组（★ 风险最高的表）**

| 字段 | 类型 | 说明 |
|---|---|---|
| item_code + group_code | PK | |
| sph_value | Decimal | |
| sph_basis | SphBasis | SINGLE / CREW |
| sph_crew | int \| None | **CREW 时必填** |
| sph_uom | Uom | 单位 |
| crew_std | int | 标准投入人力 |
| confidence | Confidence | 未校准 = LOW，看板虚线 + 问号 |
| effective_date | date | 生效日（时态主数据） |
| source | str | 财务下发 / 实测 / 暂估 |
| updated_by / updated_at | | 留痕 |

**`md_capacity_calendar` 组日历**

| 字段 | 类型 | 说明 |
|---|---|---|
| group_code | GroupCode | |
| work_date | date | |
| is_workday | bool | |
| hours_per_day | Decimal | 默认 8 |
| headcount | int | 组在编人数 |
| reserved_ratio | Decimal | **预留产能比例，默认 0.15** |

> 预留产能实现：参与排程的有效日工时 = `hours_per_day × (1 − reserved_ratio)`；看板上预留段显示为斜纹。

### 5.3 业务数据

**`so_order` 订单（模拟金蝶）**

| 字段 | 类型 | 说明 |
|---|---|---|
| order_no | str PK | 单据编号 |
| customer | str | 购货单位 |
| item_code | str | |
| qty_order | Decimal | 订单量 |
| unit | Uom | 销售单位 |
| due_date | date | **订单交期（锚点，系统绝不修改）** |
| ready_date | date \| None | 齐套日（包材到料日） |
| customer_level | int 1-5 | 客户等级 |
| amount | Decimal | 订单金额 |
| is_urgent | bool | 紧急插单标记 |

**`wo` 工单**

| 字段 | 类型 | 说明 |
|---|---|---|
| wo_no | str PK | 系统生成 `WO-{order}-{seq}` |
| wo_type | WoType | |
| source_order_no | str | |
| item_code / group_code / dept | | |
| qty_order / qty_board_plan | Decimal / int | 计划版数（**含损耗**） |
| due_date | date | 成品=订单交期；半成品=成品开工日−4 |
| plan_start / plan_end | date \| None | 倒排结果 |
| earliest_start | date | `max(today, ready_date)` |
| crew_plan | int | 投入人力 |
| status | WoStatus | |
| is_locked | bool | |
| override_reason | str \| None | |
| plan_version | int | |
| parent_wo_no | str \| None | 半成品的父成品工单 |

**`wo_task` 生产任务（=《组排程》一行）**

| 字段 | 类型 | 说明 |
|---|---|---|
| task_id | PK | |
| wo_no / group_code | | |
| task_date | date | 生产日期 |
| qty_board | int | 当日计划版数 |
| hours_wall | Decimal | 墙钟小时 |
| hours_man | Decimal | 人·时 |
| crew_plan | int | 人力 |
| seq | int | 当日顺序（**同日按 color 排序以减少换线**） |
| changeover_min | int | 与前一任务的换线时长 |
| qty_actual / hours_actual | | 报工回填（POC 预留字段，不实现录入） |
| plan_version | int | |

**`wo_dependency` 依赖**

| 字段 | 说明 |
|---|---|
| pred_wo_no | 半成品工单 |
| succ_wo_no | 成品工单 |
| dep_type | 固定 `FS` |
| offset_days | 提前期（自然日，默认 4） |

**`wo_insert_log` 插单留痕**

| 字段 | 说明 |
|---|---|
| wo_no / 提出人 / 提出时间 | |
| reason | 枚举：客户催单 / 质量返工 / 销售漏单 / 计划失误 / 其他 |
| strategy | A 加班加人 / B 挤占 / C 拆单塞缝 / D 协商延后 |
| cost_json | 影响单数、延后天数、超交期单数、加班成本 |
| approver | 审批人 |
| plan_version_before / after | |

**`plan_version` 计划版本**

| 字段 | 说明 |
|---|---|
| version_no / created_at / trigger（初始排产 / 改单 / 插单 / 定时重排）/ snapshot_hash | |

---

## 6. 核心排程算法

> 引擎 MUST 是**纯函数**：`schedule(snapshot) -> ScheduleResult`，不碰数据库、不发网络请求、不读时钟（`today` 由入参传入）。
> 这是 what-if、单测、可复现的前提。**违反此条一律重写。**

### 6.0 顶层签名

```python
@dataclass
class ScheduleInput:
    today: date
    orders: list[Order]           # 本次参与排产的订单
    items: dict[str, Item]
    uom: dict[str, list[UomConvert]]
    routes: dict[str, ItemRoute]
    sph: dict[tuple[str, str], Sph]
    calendar: list[CalendarDay]
    stock: dict[str, Decimal]     # 半成品可用库存（按半成品 item_code）
    locked_tasks: list[WoTask]    # 已锁定/已下发，先占位
    config: ScheduleConfig        # fence_days=4, ripple_limit=10,
                                  # deadband_days=0.5, deadband_hours_ratio=0.10,
                                  # reserved_ratio=0.15, jit=True, weights=...

@dataclass
class ScheduleResult:
    wos: list[Wo]
    tasks: list[WoTask]
    dependencies: list[WoDependency]
    conflicts: list[Conflict]
    unplaced: list[Unplaced]      # 装不下的工单 + 原因 + 最快可完成日
```

### 6.1 Step 0 · 需求展开（订单 → 成品工单）

```python
def expand_order(order, item, uom_chain) -> Wo:
    box_per_unit   = convert(order.unit, Uom.BOX, item)      # 销售单位 → 盒
    qty_box        = order.qty_order * box_per_unit
    qty_board_raw  = qty_box * item.board_per_box * (1 + item.loss_rate)
    qty_board_plan = ceil(qty_board_raw)                     # BR-02
    return Wo(wo_type=FINISHED, due_date=order.due_date,
              earliest_start=max(today, order.ready_date or today), ...)
```

> `computable = false` 的品项在此处直接跳过，输出为「不可自动排产」清单（不进池）。

### 6.2 Step 1 · 工时与组产能

```python
def group_rate(item, sph, crew_plan) -> Decimal:             # 版/小时
    sph_board = convert_qty(sph.sph_value, sph.sph_uom, Uom.BOARD, item)
    if sph.sph_basis == SINGLE:
        return sph_board * crew_plan                          # BR-10
    else:                                                     # CREW
        return sph_board                                      # BR-11（不再乘）
        # crew_plan != sph.sph_crew → 追加冲突 E8

def day_capacity(group, date, item, sph, crew_plan) -> int:
    h = calendar_hours(group, date) * (1 - reserved_ratio)    # 预留产能
    return floor(h * group_rate(item, sph, crew_plan))        # BR-13
```

### 6.3 Step 2 · 倒排落位（核心循环）

```python
def backward_place(wo, ctx, occupied: dict[(group, date), int]) -> list[WoTask]:
    remaining = wo.qty_board_plan
    cursor    = wo.due_date                      # BR-20
    tasks, guard = [], 0
    while remaining > 0:
        guard += 1
        if guard > 365: raise SchedulingLoopError          # 防死循环
        if cursor < wo.earliest_start:                     # BR-21
            return tasks, Unplaced(wo, 'E1', remaining)
        if not is_workday(wo.group_code, cursor):          # BR-22
            cursor -= 1day; continue
        free = day_capacity(...) - occupied[(wo.group_code, cursor)]
        if free <= 0:                                      # BR-23
            cursor -= 1day; continue
        qty = min(remaining, free)                         # BR-24
        tasks.append(WoTask(task_date=cursor, qty_board=qty,
                            hours_wall=qty / group_rate,
                            hours_man =qty / group_rate * crew_plan,
                            crew_plan=crew_plan))
        occupied[(wo.group_code, cursor)] += qty
        remaining -= qty
        cursor -= 1day                                     # ⬅️ 倒排唯一特征
    tasks.sort(key=date)
    return tasks, None
```

**整体编排**：

```python
def schedule(inp: ScheduleInput) -> ScheduleResult:
    1. occupied = 累加 locked_tasks                                  # BR-26
    2. 展开订单 → 成品工单列表（跳过不可排产品项）
    3. 排序（BR-25）：
         DUE_DESC (默认) : sort_key = (-due_date, -priority_score, wo_no)
         PIN_FIRST(插/改单): sort_key = (0 if wo_no in pinned else 1, -due_date, -priority_score, wo_no)
         DUE_ASC  (可选) : sort_key = ( due_date, -priority_score, wo_no)
    4. for wo in 成品工单（is_locked 的跳过）: backward_place()
    5. 生成/重建半成品工单（§6.4），再按同样规则倒排半成品
    6. 检测冲突（§6.5）
    7. return
```

> **为什么默认是 DUE_DESC 而不是"紧急单优先"（已验算，勿改）**
> 倒排下"晚交期先占位"，涟漪才表现为**其他单往前挤（提前）**，与 §13 的算例一致；
> 若用 DUE_ASC，早交期单先占满近期，晚交期的加量单会被拆散到很远的零散空位（例：A 会被拆成 9/23 + 9/18，中间 9/21、9/22 空着被别人占），计划反而不可执行。
> 代价是：产能不足时，**最后排的早交期单会报警**——这正是我们要的真实预警（紧急单排不下必须让人看见）。
> 插单/改单时必须切 `PIN_FIRST`，让触发变更的单先占位，"挤占"才成立。

### 6.4 Step 3 · 半成品展开（BR-30 ~ BR-36）

```python
def expand_semi(finished_wo, route, item, stock) -> Wo | None:
    if not route.needs_semi: return None
    gross = ceil(finished_wo.qty_order * route.semi_board_per_box * (1 + item.loss_rate))
    net   = max(0, gross - stock.get(route.semi_item_code, 0))       # BR-32
    if net == 0: return None
    semi_due = finished_wo.plan_start - timedelta(days=route.lead_time_days)   # BR-33
    return Wo(wo_type=SEMI, qty_board_plan=net, due_date=semi_due,
              earliest_start=max(today, ...), parent_wo_no=finished_wo.wo_no)
```

> **必须先排成品再排半成品**（BR-34）。成品 `plan_start` 变了 → 半成品工单**删除重建**（保留原 wo_no 便于 diff 时提示"已重排"）。
> 若 `semi_due < today` 或半成品未安置完 → **E2 红色**，并计算 `最快可交期`（见 §6.6）。

### 6.5 Step 4 · 冲突检测（E1–E10，全部软约束）

| 编号 | 判定表达式 | 级别 | 系统动作 | MUST |
|---|---|---|---|---|
| **E1** | 存在 `Unplaced`，或 `plan_start < earliest_start` | 🔴 RED | 工单标红 + 弹出「最快可完成日 / 建议交期」 | ✅ |
| **E2** | 半成品 `plan_end > semi_due` 或 半成品未安置 | 🔴 RED | 半成品工单标红 + 联动重排 + 给出最快可交期（**核心演示点**） | ✅ |
| **E3** | `plan_start < ready_date`（包材未到） | 🟡 YELLOW | 提示"包材预计 X 日到，建议顺延" | ✅ |
| **E4** | 组当日 `Σhours_wall > hours_per_day` | 🟡 YELLOW | 产能条变红 | ✅ |
| **E5** | `sph.confidence == LOW` | ⚪ GREY | 任务块虚线 + ❓ | ✅ |
| **E6** | 同组同日存在 `changeover_min > 0` 的多任务 | ⚪ GREY | 显示换线时长，建议按颜色排序 | SHOULD |
| **E7** | 同品项多个未合并订单落在相邻日期 | 🔵 BLUE | 提示"可合并，预计省 X 小时换线" | SHOULD |
| **E8** | CREW 口径下 `crew_plan != sph_crew` | 🟡 YELLOW | "投入人数与 SPH 标定不符，结果不可信" | ✅ |
| **E9** | 未齐套或成品 `plan_start < kit_ready_date` | 🟡 YELLOW | 齐套详情 + 缺料子件摘要 | ✅ |
| **E10** | 库存被前序订单占用（`KitAllocation` 流水） | 🟡 YELLOW | 占库明细：订单 × 子件 × 版数 | ✅ |

数据结构：

```python
@dataclass
class Conflict:
    code: str          # E1..E10
    level: ConflictLv
    wo_no: str | None
    task_id: int | None
    message: str       # 中文，可直接展示
    suggest: str | None  # 一键修复动作标识：DELAY_1D / ADD_CREW / SPLIT
```

### 6.6 「排不下」时：算最快可完成日，但**绝不改交期**（BR-27 / BR-47）

```python
def earliest_finish(wo, ctx) -> date:
    start = max(ctx.today, wo.earliest_start)
    if wo.wo_type == FINISHED and route.needs_semi:
        semi_days = ceil(net_semi / semi_day_cap)                 # 半成品占用工作日
        start = add_workdays(start, semi_days) + lead_time_days   # 半成品完成 + 提前期
    return add_workdays_backward(start, ceil(wo.qty_board_plan / day_cap) - 1)
```

输出形态（**禁止自动写回 `so_order.due_date`**）：

```
⚠️ 交期风险提示
订单 SO-002 要求 9/23，系统最快可完成 9/29（差 6 天）
原因：二部半成品最早 9/15 开工，9/15 完成，成品最早 9/21 才能开工，需 7 个工作日
建议：① 销售与客户协商改期 ② 二部加班压缩提前期 ③ 挪用其他单的半成品库存 130 版
【通知销售】【申请加班】【仍按原交期排（需填原因）】
```

### 6.7 diff 算法（插单/改单确认前的变更对比）

```python
def diff(base: ScheduleResult, new: ScheduleResult, today) -> DiffResult:
    # 按 wo_no 聚合 plan_start / plan_end / qty_board
    ADD    : wo 仅存在于 new
    REMOVE : wo 仅存在于 base
    MOVE   : plan_start 变化 且 plan_end <= due_date
    DELAY  : plan_end 后移（本模型罕见，主要为兼容锁定与人工拖拽）
    LATE   : new.plan_end > wo.due_date        # 🔴 超交期
```

汇总行 MUST 显示：`本次调整：新增 1、移动 2、延后 1、超交期 1`
底部按钮：`[撤销]` `[仅应用无冲突部分]` `[全部应用]`

> **这一屏是整个 POC 最该打磨的界面**（§2.1 G5）。生管要的不是"系统帮我排好"，是"点确认前让我看见要付什么代价"。

---

## 7. 插单流程与算法（POC 的第二个核心）

### 7.0 口径修正（重要，与原方案 v1.1 表述不同，以此为准）

原方案 §11.4 写"策略 B 挤占 → 被挤的订单顺延"。**在纯倒排 + 无限产能模型下这不准确**：倒排只会把其他单**往前挤（提前）**，不会产生"延后"。只有当某单已到达其最早可开工日（齐套日/今天）无法再提前时，才表现为**装不下 → E1**。

因此 POC 中四种策略的**真实语义**是：

| 策略 | 实际计算方式 | 代价呈现 |
|---|---|---|
| **A 加班/加人** | 对指定组指定日期下发 `capacity_override`（`hours_per_day` 上调 / `reserved_ratio` 临时下调）后重排 | 加班工时 + 成本估算 |
| **B 挤占（默认）** | `sort_mode = PIN_FIRST` 让插单先占位，其余按 DUE_DESC 重排（BR-25） | **N 张单开工日提前 X 天**（不是延后！）+ 超交期单数 |
| **C 拆单塞缝** | 允许 `max_split_days` 更大、允许更小的任务粒度填缝（默认算法天然支持） | 换线次数 ↑、总换线时长 |
| **D 协商延后** | 当出现 E1/E2 时，输出受影响单的「最快可完成日」清单 | 需销售介入的订单列表 |

> 实现要求：**四个策略复用同一个 `schedule()` 纯函数，只是入参 config / capacity_override 不同**。这样测试成本极低，也保证结果一致。

### 7.1 时间栅栏（BR-40/41）

```
today ────────── +4d ────────── +10d ──────────▶
[ 🔒 冻结区 ]    [ 🟡 协议区 ]   [ 🟢 自由区 ]
 不可被涟漪移动   逐条确认+列影响   自动重排
```

- 冻结区长度 `fence_days = 4`，**= 半成品提前期**（不是拍脑袋，是从业务规则推出的，演示时要讲）
- 实现：`plan_start < today + fence_days` 且 `status in (RELEASED, DONE)` 的任务 → `is_locked = true`，先占位不参与重排
- 插单若交期落在冻结区内 → 允许排入，但 MUST 提示「落在冻结区，需人工确认」（演示第 5 步）

### 7.2 插单可行性判定（BR-47，先判定再排期）

```python
def check_insert_feasible(order, item, route, stock, today) -> Feasibility:
    avail_days = (order.due_date - today).days
    if not item.computable:
        return INFEASIBLE('缺少包/袋/箱换算率，不可自动排产')
    if route.needs_semi:
        gross = ceil(order.qty_order * route.semi_board_per_box * (1 + item.loss_rate))
        if stock.get(route.semi_item_code, 0) >= gross:
            return OK_WITH_WARN('占用半成品库存，可能影响其他单的预留')
        if avail_days < route.lead_time_days:
            return INFEASIBLE(f'半成品提前期需 {lead_time_days} 天，可用 {avail_days} 天，物理不可行')
        return OK
    if avail_days < 1:
        return INFEASIBLE('交期早于今天')
    return OK
```

不可行时 MUST 给出三条出路（§6.6 的输出形态），**禁止硬排**。

### 7.3 优先级评分（BR-46）

```python
score = (w1 * urgency + w2 * customer_level/5 + w3 * amount_ratio
         + w4 * is_ready + w5 * is_strategic)
# 默认 w1=0.5 w2=0.2 w3=0.1 w4=0.2 w5=0
# urgency = clamp(1 - (due_date - today).days / horizon_days, 0, 1)
```

权重 MUST 放在配置文件 `config/weights.yaml`，**禁止硬编码在代码里**（写死了每次插单都吵架）。

### 7.4 涟漪抑制（BR-42/43，五条手段，POC 实现 1/2/4/5）

| # | 手段 | POC | 实现要点 |
|---|---|---|---|
| 1 | 时间栅栏 | ✅ | §7.1 |
| 2 | **变动死区** | ✅ | 重排后对比：`abs(new_start - old_start) < 0.5 天` 或 `abs(hours变化率) < 10%` → **保持原任务不变** |
| 3 | 固定重排时点（每天 2 次） | ❌ | POC 不做（实时 + 确认前 diff 已足够）；数据模型预留 |
| 4 | 计划版本号 + 变更单 | ✅ | 每次应用生成 `plan_version` + 变更清单（哪些派工单新增/作废/改量） |
| 5 | 涟漪上限 | ✅ | 受影响工单 > `ripple_limit(10)` → 不自动应用，列表分批确认 |

> 死区是**投入产出比最高**的一条（半天工作量，消除绝大部分无谓抖动）。

### 7.5 插单交互流程（照此设计按钮与页面）

```
1. 订单池 → 勾选新单 → 【标记紧急插单】
2. 弹窗填：期望交期 + 插单原因（必填，枚举）+ 优先级理由
3. 【试排】(what-if) → 后台副本并行跑 A/B/C/D 四策略
4. 弹出【方案对比 + 影响 diff】：
   ┌ 方案 A 加班加人：成本 +¥1,200，影响 0 张单          ← 推荐
   ├ 方案 B 挤占    ：影响 3 张单，2 张开工日提前 1 天
   ├ 方案 C 拆单塞缝：增加 4 次换线，多耗 3.5h
   └ 方案 D 协商延后：需销售确认 SO-008、SO-011
   ── diff 明细（新增/移动/延后/超交期 四类 + 汇总行）
   ── [撤销] [仅应用无冲突部分] [全部应用]
5. 选定 → 【应用】→ 生成 plan_version + wo_insert_log
6. 自动生成【计划变更单】（新增/作废/改量的派工单清单，可打印）
7. 若影响已下发任务 → 强制填 override_reason
```

### 7.6 状态机

```
DRAFT ──倒排──▶ PLANNED ──下发──▶ RELEASED ──报工(二期)──▶ DONE
  ▲              │  │                 │
  └──解锁────────┘  └──改单/插单重算──┘
RELEASED 且 plan_start < today+fence → 自动 is_locked=true
```

---

## 8. 交互需求（前端）

### 8.1 页面清单

| # | 页面 | 内容 | 优先级 |
|---|---|---|---|
| P1 | **参数中心** | 品项 / 换算链 / SPH 四元组 / 工艺路线 / 组日历，5 张表 CRUD + Excel 批量导入 | MUST |
| P2 | **订单池** | 订单列表（金额/客户/品项/数量/交期/齐套/剩余天数红黄绿）+ 勾选 + 合并建议 + 【一键倒排】 | MUST |
| P3 | **排产看板** | 组×日期矩阵 + 拖拽 + 冲突面板 + 依赖连线 | MUST |
| P4 | **插单对话框** | 四策略对比 + diff 视图 + 应用 | MUST |
| P5 | **参数校准看板** | `confidence=LOW` 的品项数、覆盖率进度条 | SHOULD |
| P6 | 派工单导出 | 选组+日期 → 导出《组排程》Excel | MUST |
| P7 | **库存中心** | 品项可用量（版）、来源（LOCAL/ERP_MOCK/SEED）、本地改数、**模拟 ERP 同步**；排产后展示「计划占用」（来自最近一次齐套占库） | MUST |

### 8.2 看板 P3 详细规格（核心界面）

```
                09/22    09/23    09/24    09/25    09/26
手工组        [P1 120版][P1 300版]  ──      [P3 全部]  ──
              产能 40%   产能 100%          产能 85%
模具组           ──     [P2 200版][P2 200版][P2 200版] ──
浇注组        [P4 312版]  ──       ──        ──       ──
二部半成品       ──       ──       ──      [S2 282版]  ──
                                            ▲ 必须早于成品开工 4 天
```

- 行 = 组，列 = 日期（默认显示 `today-1 ~ today+21`，可滚动/翻页）
- 单元格 = 任务块：品项 + 版数 + 工时；底部条 = 当日产能占用率（>100% 红色）
- **虚线框 + ❓** = `confidence=LOW`（BR/E5）
- **红色波浪** = 冲突，hover 显示详情
- **斜纹区** = 预留产能段（15%）
- **箭头连线** = 半成品 → 成品依赖（BR-36 可视化）
- 非工作日列底色灰化，冻结区列加左侧竖线 + 锁图标

**必须支持的 7 个动作**（缺一不可，否则生管会退回 Excel）：

| 动作 | 说明 |
|---|---|
| 拖拽改期 | 拖到另一天/另一组，实时重算 |
| 拆单 / 合并 | 一个工单拆到多天；同品项多单合并（提示省多少换线） |
| 改人力 | 就地改 `crew_plan`，**实时重算工时**；CREW 口径不符 → E8 |
| 锁定 | `is_locked`，锁定后引擎不得移动 |
| 强制插单 | 拖入已满的一天 → 弹 `override_reason` 输入框 |
| **what-if 模拟** | 【试排】在副本上跑，不满意丢弃 |
| **撤销 / 重做** | 全操作栈（没有撤销没人敢用） |

### 8.3 冲突面板（右侧常驻）

- 按 红 / 黄 / 灰 / 蓝 分组，点击定位到对应任务块
- 每条给一键修复建议：`DELAY_1D` / `ADD_CREW` / `SPLIT` / `NOTIFY_SALES`
- 顶部显示统计：🔴 2 🟡 3 ⚪ 5

### 8.4 派工单导出（P6）

导出列 MUST 与客户现有《组排程》一致（依据 `03-客户需求文档/斯芬克斯-客户现有Excel表头清单（字段梳理）.md`），建议列序：

`生产日期 | 组 | 型号 | 品名 | 单位 | 计划生产数量(版) | 人力 | 生产人员 | 顺序 | 备注`

用 `openpyxl` + 模板，**列名与列序逐字一致**，生管零学习成本。

### 8.5 库存中心（P7）

- 表格：品项、名称、可用量（版）、来源、更新时间；标注「演示数据 · 非 ERP 真源」。
- 行内改数 → `PATCH /api/stock/{item_code}`；顶栏 **模拟 ERP 同步** → `POST /api/stock/sync-erp-mock`（详见 `docs/库存与ERP对接说明.md`）。
- 最近一次排产后展示 **计划占用**（齐套占库聚合）；BOM 页半成品卡片可跳转并带 `?item=` 过滤。

---

## 9. API 设计（REST，FastAPI）

| Method | Path | 说明 |
|---|---|---|
| GET/POST | `/api/items` | 品项 CRUD + 批量导入 |
| GET/POST | `/api/uom` | 换算链 |
| GET/POST | `/api/sph` | SPH 四元组（**变更必须留痕**） |
| GET/POST | `/api/routes` | 工艺路线 |
| GET/POST | `/api/calendar` | 组日历 |
| GET/POST | `/api/orders` | 订单（含 CSV 导入，模拟金蝶 Push） |
| POST | `/api/orders/import` | CSV 导入 |
| **POST** | **`/api/schedule/run`** | 正式排产。body: `{order_nos, today, config}` → 生成新 `plan_version` |
| **POST** | **`/api/schedule/what-if`** | 试排（不落库）。body 同上 + 可覆盖 config → 返回 `ScheduleResult` |
| **POST** | **`/api/schedule/insert`** | 插单试排：body `{order_no, due_date, reason}` → 返回四策略 + diff |
| POST | `/api/schedule/apply` | 应用某个方案（含 `override_reason`、`strategy`） |
| GET | `/api/plan?version=` | 查询计划（wos + tasks） |
| GET | `/api/plan/diff?from=&to=` | 两版本 diff |
| GET | `/api/conflicts?version=` | 冲突列表 |
| POST | `/api/wo/{wo_no}/lock` | 锁定/解锁 |
| PATCH | `/api/task/{id}` | 改日期/人力/数量（人工干预，触发局部重算） |
| POST | `/api/plan/{version}/release` | 下发（status → RELEASED） |
| GET | `/api/dispatch/export?group=&date_from=&date_to=` | 导出派工单 xlsx |
| GET | `/api/stock` | 库存列表 + meta（provider、last_sync） |
| PATCH | `/api/stock/{item_code}` | POC 本地改可用量 |
| POST | `/api/stock/sync-erp-mock` | 模拟 ERP 拉取并 upsert（`mode=merge\|replace`） |
| GET | `/api/plan/kit-status?version=` | 齐套检查 + 占库流水（或随 schedule `result.kit_checks`） |
| GET | `/api/health` | 健康检查 |

统一响应：`{code: 0, data: ..., message: ""}`，异常码见 §10.5。

---

## 10. 技术栈与工程约定

### 10.1 技术栈（推荐，可替换但需保持分层）

| 层 | 选型 | 理由 |
|---|---|---|
| 后端 | **Python 3.12 + FastAPI + SQLAlchemy 2.x + SQLite** | 引擎好写、好测；POC 无需 Postgres |
| 校验 | Pydantic v2 | 与引擎模型共用 |
| 测试 | **pytest**（覆盖率目标：引擎 ≥ 90%） | 见 §11 |
| 前端 | **React 18 + TypeScript + Vite + Tailwind** | 看板交互重，React 生态最省事 |
| 看板 | **自研 CSS Grid 组×天矩阵** + `@dnd-kit/core` 拖拽 | 客户要的是矩阵不是甘特；dhtmlx/vis 反而更重 |
| Excel | openpyxl（导入参数 / 导出派工单） | 与现有格式逐列一致 |
| 精度 | **数量用 `int`（版）/ Decimal（换算率、工时）**，禁止 float 参与比较 | 见 §12 禁止事项 |

> 降级方案（若前端人手紧张）：FastAPI + Jinja2 + HTMX + 少量原生 JS，看板用 `<table>` + HTML5 原生拖拽，交互降级但 POC 可演示。**不推荐 Streamlit**（diff/拖拽体验差）。

### 10.2 目录结构（必须遵守，引擎 MUST 独立）

```
scheduling-poc/
├── .cursorrules                  # 见本文件 §12，Cursor 红线
├── README.md
├── config/
│   ├── weights.yaml              # 优先级权重（BR-46）
│   └── schedule.yaml             # fence_days / ripple_limit / deadband / reserved_ratio
├── engine/                       # ★ 纯函数区：禁止 import db / http / datetime.now()
│   ├── models.py                 # Pydantic 模型（与 §5 字段一致）
│   ├── uom.py                    # 换算链（BR-03）
│   ├── capacity.py               # group_rate / day_capacity（BR-10~14）
│   ├── expand.py                 # 需求展开 / 半成品展开（BR-01~02,30~33）
│   ├── backward.py               # 倒排落位（BR-20~27）
│   ├── conflicts.py              # E1–E8（BR-50）
│   ├── insert.py                 # 插单可行性 + 四策略（BR-40~47）
│   ├── diff.py                   # 版本对比（§6.7）
│   └── schedule.py               # 顶层编排 schedule(ScheduleInput)
├── api/                          # FastAPI 路由
├── db/                           # SQLAlchemy models + repository
├── seed/seed_data.json           # §11.2 fixture，一键导入
├── tests/                        # pytest，与 §11 一一对应
└── web/                          # React 前端
```

### 10.3 精度与取整（统一，避免测试对不上）

| 项 | 规则 |
|---|---|
| 版数 | `int`，`ceil` 向上取整 |
| 换算率 / 损耗率 | `Decimal`，保留 6 位 |
| 工时 | `Decimal`，内部保留 4 位，**接口与 UI 展示 2 位** |
| 金额 | `Decimal`，2 位（POC 仅估算加班成本，可简化） |
| 日期 | `datetime.date`，**不带时区、不带时间**；`today` 一律由入参传入 |
| 浮点比较 | 测试中用 `pytest.approx(rel=1e-6)` 或先量化为 `Decimal` |

### 10.4 错误码

| code | 含义 |
|---|---|
| 1001 | 品项缺少换算链，不可自动排产（`computable=false`） |
| 1002 | SPH 缺失或 `CREW` 口径缺 `sph_crew` |
| 1003 | 倒排无解（装不下）→ 见 `unplaced` |
| 1004 | 插单物理不可行（提前期不足） |
| 1005 | 违反软约束但未填 `override_reason` |
| 1006 | 工单已锁定，不可修改 |
| 1007 | `crew_plan > headcount` |

### 10.5 性能

- 单组 30 天 × 4 组 × 50 工单：`schedule()` MUST < 500ms
- what-if 四策略并行：MUST < 2s
- 引擎 MUST 无 IO（禁止在循环里查库）

---

## 11. 测试用例（MUST 全部通过，这是给 Cursor 的第一批任务）

> **先写测试，再写实现**（TDD）。本节的数字已手工验算，可直接作为断言。
> 时钟统一：`today = 2026-09-15`（周二）。日历：周一至周五工作 8h，周末休息。
> 冻结区：`9/15 ~ 9/19`。预留产能 POC 测试时设为 **0**（§11.2 说明），默认值 0.15。

### 11.1 种子数据（写入 `seed/seed_data.json`）

**品项**

| item | 组 | 枚/版 | 版/盒 | 损耗 | 颜色 | 走半成品 |
|---|---|---|---|---|---|---|
| P1 巧克力装饰片A | MANUAL | 24 | 4 | 5% | 黑 | 否 |
| P2 卡通造型件B | MOLD | 20 | 6 | 3% | 白 | 是 → S2 |
| S2 造型件B胚(半成品) | SEMI | 20 | 1 | 3% | 白 | — |
| P4 浇注件C | POURING | 30 | 5 | 4% | 牛奶 | 否 |

**SPH**

| item | 组 | value | basis | sph_crew | uom | crew_std | confidence | 推导 group_rate | 日容量(8h) |
|---|---|---|---|---|---|---|---|---|---|
| P1 | MANUAL | 300 | SINGLE | — | PCS | 3 | MID | 300/24×3 = **37.5 版/h** | **300 版** |
| P2 | MOLD | 250 | SINGLE | — | PCS | 2 | MID | 250/20×2 = **25 版/h** | **200 版** |
| S2 | SEMI | 40 | CREW | 4 | BOARD | 4 | LOW | **40 版/h** | **320 版** |
| P4 | POURING | 600 | SINGLE | — | PCS | 2 | HIGH | 600/30×2 = **40 版/h** | **320 版** |

**工艺路线**：P2 → `needs_semi=true, semi_item_code=S2, semi_board_per_box=2, lead_time_days=4`

**库存**：`S2 可用 130 版`

**日历**：`2026-09-15 ~ 2026-10-15`，周一至周五 `is_workday=true, hours_per_day=8`；headcount：MANUAL 3 / MOLD 2 / POURING 2 / SEMI 4

**订单**

| order | item | 数量 | 单位 | 交期 | 客户 | 齐套日 |
|---|---|---|---|---|---|---|
| SO-001 | P1 | 100 | 盒 | 2026-09-23 | A | 2026-09-15 |
| SO-002 | P2 | 200 | 盒 | 2026-10-07 | B | 2026-09-15 |
| SO-003 | P4 | 60 | 盒 | 2026-09-24 | C | 2026-09-20 |

### 11.2 必过断言清单

```python
# ── T1 单位换算（BR-01/03/04）────────────────────────
def test_uom_chain():
    assert to_board(Decimal('1'), Uom.BOX, P1) == 4            # 1盒=4版
    assert to_board(Decimal('300'), Uom.PCS, P1) == Decimal('12.5')  # 300枚=12.5版
    assert P4.computable is True                                # 只用到枚/版/盒

# ── T2 需求展开（BR-02）──────────────────────────────
def test_expand():
    assert expand(P1, qty=100, unit=BOX).qty_board_plan == 420   # 100*4*1.05
    assert expand(P2, qty=200, unit=BOX).qty_board_plan == 1236  # 200*6*1.03=1236
    assert expand(P4, qty=60,  unit=BOX).qty_board_plan == 312   # 60*5*1.04=312

# ── T3 SPH 口径（BR-10/11，最容易写错的地方）──────────
def test_sph_single():
    assert group_rate(P1, crew=3) == Decimal('37.5')            # 300/24*3
def test_sph_crew_no_multiply():
    assert group_rate(S2, crew=4) == Decimal('40')              # ⚠️ 不得再乘 4
    assert conflicts_when(S2, crew=5).has('E8')                 # 人数不符 → E8
def test_sph_basis_error_magnitude():                            # 算例②：口径错差 3 倍
    assert abs(hours(P1, 420, crew=3, basis=SINGLE) - Decimal('11.2')) < EPS
    assert abs(hours(P1, 420, crew=3, basis=CREW)   - Decimal('33.6')) < EPS

# ── T4 倒排基础（BR-20~24）───────────────────────────
def test_backward_basic():
    r = schedule([SO_001], today=date(2026,9,15))
    assert r.tasks_of('P1') == [(date(2026,9,22), 120), (date(2026,9,23), 300)]
    assert r.wo.plan_start == date(2026,9,22) and r.wo.plan_end == date(2026,9,23)
    assert abs(r.tasks[0].hours_wall - Decimal('3.2')) < EPS    # 120/37.5
    assert abs(r.tasks[1].hours_wall - Decimal('8')) < EPS      # 300/37.5
    assert abs(r.tasks[1].hours_man  - Decimal('24')) < EPS     # 8*3 人·时

def test_backward_skip_weekend():
    # SO-003 交期 9/24(四)，齐套 9/20 → 312 版一天装下
    r = schedule([SO_003], today=date(2026,9,15))
    assert r.tasks_of('P4') == [(date(2026,9,24), 312)]

# ── T5 半成品两层（BR-30~36，POC 核心）───────────────
def test_semi_net_demand():
    r = schedule([SO_002], today=date(2026,9,15))
    semi = r.semi_wo_of('SO-002')
    assert semi.qty_board_plan == 282          # 毛需求 ceil(200*2*1.03)=412 − 库存 130
    assert semi.due_date == date(2026,9,25)    # 成品 plan_start 9/29 − 4 天
    assert r.tasks_of('P2')[0] == (date(2026,9,29), 36)   # 余量落在最早一天
    assert len(r.tasks_of('P2')) == 7                     # 200*6 + 36
    assert r.dependencies[0].offset_days == 4

def test_semi_skipped_when_stock_enough():
    set_stock('S2', 500)
    assert schedule([SO_002]).semi_wo_of('SO-002') is None      # BR-32

# ── T6 演示剧本：改交期（BR-33/35，★ 全场最高潮）──────
def test_semi_infeasible():
    r = schedule([SO_002(due=date(2026,9,23))], today=date(2026,9,15))
    assert r.conflicts.has('E2', level=RED)
    assert r.unplaced_or_late.earliest_finish == date(2026,9,29)
    # 断言：系统绝不能修改 so_order.due_date
    assert get_order('SO-002').due_date == date(2026,9,23)

def test_semi_into_frozen_zone():
    r = schedule([SO_002(due=date(2026,9,30))], today=date(2026,9,15))
    assert r.semi_wo.plan_start == date(2026,9,18)      # 落在冻结区 → 需人工确认提示
    assert r.conflicts.has('E2') is False               # 装得下，只是提示

# ── T7 涟漪（BR-25/26，§13 算例）─────────────────────
def test_ripple_forward_push():
    # 直接构造工单（跳过换算）：E=9/21、C=9/22、A=9/23，各 300 版，手工组日容量 300
    # sort_mode = PIN_FIRST(A)  ← A 是本次被改量的单，先占位（BR-25）
    base = schedule([E, C, A], sort_mode='PIN_FIRST', pinned=['A'])
    A.qty_board_plan = 600
    new = schedule([E, C, A], sort_mode='PIN_FIRST', pinned=['A'])
    assert new.tasks_of('A') == [(date(2026,9,22), 300), (date(2026,9,23), 300)]
    assert new.plan_start('C') == date(2026,9,21)   # 9/22 被 A 占 → 提前到 9/21
    assert new.plan_start('E') == date(2026,9,18)   # 9/21 被 C 占；9/20(日) 9/19(六) 非工作日
    assert new.due('C') == base.due('C')            # ★ 交期不变（BR-27）

def test_locked_not_moved():
    lock(C)
    assert schedule([E, C, A]).plan_start('C') == date(2026,9,22)

# ── T8 死区（BR-42）──────────────────────────────────
def test_deadband_suppresses_small_change():
    A.qty_board_plan = 301          # 工时变化 < 10%
    assert schedule([E,C,A]).plan_start('C') == date(2026,9,22)   # 不动

# ── T9 冲突软约束（BR-50）────────────────────────────
def test_conflicts_never_block():
    r = schedule([SO_002(due=date(2026,9,23))])
    assert r.wos[0].status == 'PLANNED'        # 有红色冲突也照样出计划
    assert r.conflicts[0].suggest is not None

# ── T10 插单（BR-40~47）──────────────────────────────
def test_insert_infeasible_by_leadtime():
    f = check_insert_feasible(order(P2, due=date(2026,9,17)))
    assert f.status == 'INFEASIBLE'            # 可用 2 天 < 提前期 4 天

def test_insert_four_strategies():
    res = schedule_insert(URGENT_ORDER)
    assert set(res.strategies) == {'A','B','C','D'}
    assert res.diff.summary_text == '本次调整：新增 1、移动 2、延后 0、超交期 0'
```

### 11.3 覆盖率要求

- `engine/` 目录 **≥ 90% 行覆盖**
- 每个 `BR-xx` 至少 1 条断言，测试名中标注编号，例：`test_br11_crew_no_multiply`

---

## 12. 给 Cursor 的红线（写入 `.cursorrules`，禁止违反）

```
1. 【纯函数】engine/ 下禁止 import db、requests、datetime.now()。today 只能由入参传入。
2. 【单位】禁止拿「枚」或「盒」直接除 SPH。所有计算前必须经 uom.py 归一到「版」。(BR-01)
3. 【SPH 口径】CREW 口径禁止再乘人数。(BR-11)
4. 【交期红线】禁止任何写回 so_order.due_date 的代码。交期只能人改。(BR-27)
5. 【软约束】冲突只提示，禁止 raise 阻断排产。(BR-50)
6. 【不硬编码】换算率、SPH、权重、fence_days、deadband 一律走配置/数据表。
7. 【无优化库】禁止引入 OR-Tools / 遗传算法 / 求解器。一期不需要。
8. 【取整】数量用 int(ceil)，工时用 Decimal(4位)，禁止 float 参与相等比较。
9. 【先测试】engine/ 下每个函数先写 pytest，再写实现。测试不通过视为未交付。
10. 【不造假】禁止用 mock 数据掩盖未实现逻辑；未实现的 MUST 显式 raise NotImplementedError 并登记。
11. 【半成品顺序】必须先排成品再排半成品；成品变动必须重建半成品工单。(BR-34)
12. 【禁止全量重排默认】插单/改单默认走时间栅栏 + 涟漪抑制。(BR-40)
```

**Cursor 使用建议**：
- 把本文件与 `.cursorrules` 一起放项目根目录，第一次提问用：`@斯芬克斯-排程服务POC-开发需求规格.md 按 §14 任务 T1 开始，先写 tests/test_uom.py`
- 每完成一个任务，跑 `pytest -q` 并让我看结果再进入下一个
- 引擎逻辑有疑问时，先回查本文 `BR-xx` 编号，仍不确定再问

---

## 13. POC 默认假设（待客户确认项 A1–A10，**不要等确认再开工**）

| # | 假设 | POC 默认值 | 真正值待确认 |
|---|---|---|---|
| A1 | 组日工时 | 8h | 客户确认 |
| A2 | 预留产能比例 | 0.15（测试时设 0） | 老板决策（§待确认#14） |
| A3 | 冻结区天数 | 4（= 半成品提前期） | 待确认 |
| A4 | 半成品提前期 | 4 自然日 | 可按品项覆盖 |
| A5 | 半成品净需求扣减仓库 | 半成品仓（单一仓） | 待确认#5 |
| A6 | 库存取数 | 快照（手动录入/导入） | 实时 or T+1 待确认 |
| A7 | 「生产工时」口径 | 墙钟小时 | 待确认#4（🔴 阻塞） |
| A8 | 生产二部与三个组的归属 | 二部 = 独立的「二部半成品组」 | 待确认#3 |
| A9 | 交期当天可排产 | 是 | 待确认 |
| A10 | 优先级权重 | 0.5/0.2/0.1/0.2/0 | 交客户配置 |

> 以上默认值 MUST 写进 `config/schedule.yaml`，**不要散落在代码里**。

---

## 14. 开发任务分解（按顺序执行，每步跑通再进下一步）

| # | 任务 | 产出 | 预估 |
|---|---|---|---|
| T1 | 项目骨架 + Pydantic 模型 + 配置 yaml | 可 import 的 `engine/` 空壳 | 0.5d |
| T2 | `uom.py` 换算链 + 测试 T1 | pytest 绿 | 0.5d |
| T3 | `capacity.py`（BR-10~14）+ 测试 T3 | pytest 绿 | 0.5d |
| T4 | `expand.py` 需求展开 + 测试 T2 | pytest 绿 | 0.5d |
| T5 | `backward.py` 倒排落位 + 测试 T4 | pytest 绿 | 1d |
| T6 | 半成品展开与依赖（BR-30~36）+ 测试 T5/T6 | **pytest 绿 = 核心已通** | 1d |
| T7 | `conflicts.py` E1–E8 + 测试 T9 | pytest 绿 | 0.5d |
| T8 | `diff.py` + 测试 | pytest 绿 | 0.5d |
| T9 | `insert.py` 四策略 + 可行性 + 死区 + 测试 T7/T8/T10 | pytest 绿 | 1d |
| T10 | FastAPI + SQLite + 种子数据导入脚本 | 接口可调用 | 1d |
| T11 | React 看板（组×天矩阵 + 拖拽 + 冲突面板） | 演示第 2/4 步可跑 | 2d |
| T12 | 参数中心 + 订单池 + 导入导出 | 演示第 1 步可跑 | 1d |
| T13 | 插单对话框（四策略 + diff） | 演示第 7 步可跑 | 1.5d |
| T14 | 派工单 Excel 导出 + 演示脚本联调 | **POC 可交付** | 1d |
| T15 | 库存表扩展 + StockProvider + `/api/stock` + `test_stock_api` | pytest 绿 | 0.5d |
| T16 | `md_bom_line` + `kit_pool` + 多子件展开 + 双单抢库单测 | pytest 绿 | 1d |
| T17 | `kitting` + E9/E10 + `kit_json` / kit-status API | pytest 绿 | 0.5d |
| T18 | P7 库存中心 + 订单池齐套列 + 齐套抽屉 + 演示说明更新 | 端到端可演示 | 1d |

> 合计约 **12–13 人日**（T1–T14），与"2 周 POC"一致；T15–T18 为库存/齐套升级增量。T1–T9（引擎 + 测试）约 6 天，是**不可压缩**的部分。

---

## 15. 验收标准（POC 交付时逐条打勾）

| # | 标准 | 判定 |
|---|---|---|
| 1 | §2.2 的 7 步演示脚本全部跑通，无手动改数据 | 现场演示 |
| 2 | `pytest -q` 全绿，`engine/` 覆盖率 ≥ 90% | CI 报告 |
| 3 | 引擎单次排产 < 500ms（50 工单 × 4 组 × 30 天） | 性能日志 |
| 4 | 半成品工单 100% 自动生成，无一漏排（BR-34） | 随机 10 单验证 |
| 5 | 交期字段在数据库中**零次**被系统写入 | 代码审计 + 日志 |
| 6 | 所有冲突可点击定位、可一键修复建议 | 走查 |
| 7 | 撤销功能覆盖全部 7 个交互动作 | 走查 |
| 8 | 导出的派工单 Excel 列名/列序与客户现有一致 | 与字段清单文档比对 |

---

## 附：本文件与方案文档的差异说明（供内部核对）

| 主题 | 方案文档（v1.3）表述 | 本文件（POC）处理 |
|---|---|---|
| 策略 B「挤占」 | "被挤订单顺延" | **修正**：倒排下表现为"其他单开工日提前"，不会延后；仅当到达 earliest 无法提前时才报 E1（§7.0） |
| 冻结区 | 冻结区内不可排 | 修正：冻结区保护的是**已锁定任务**；新单可排入但 MUST 人工确认提示 |
| 固定重排时点 | 五条抑制手段之一 | POC 不实现（实时 + 确认前 diff 已足够），数据模型预留 |
| 报工与 SPH 校准 | 第五条架构块 | POC 不做，字段预留 |
| 包/袋/箱 换算 | 阻塞项 S1 | POC 仅支持枚/版/盒；其余品项标 `computable=false` |
