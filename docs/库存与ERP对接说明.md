# 库存与 ERP 对接说明（POC）

## 本地演示

- 页面 **库存中心**：可改 `stock` 表数量（来源标记 `LOCAL`）。
- **模拟 ERP 同步**：`POST /api/stock/sync-erp-mock`，读取 [`seed/erp_stock_mock.json`](../seed/erp_stock_mock.json)，`merge` 写入库（来源 `ERP_MOCK`）。

## Mock JSON 格式

```json
{
  "as_of": "2026-09-15T08:00:00+00:00",
  "items": [
    { "item_code": "S2", "qty": 130, "uom": "BOARD", "warehouse_code": "SEMI_WH" }
  ]
}
```

## 排产使用

- `load_schedule_input` 读取 `stock` 快照 → `ScheduleInput.stock`。
- 引擎 `KitSnapshot` 按排产顺序扣减（BR-38）；结果写入 `plan_version.kit_json`（齐套检查与占库流水）。

## 未来 ERP（未实现）

- 只读拉取：`item_code`, `qty`, `uom`, `as_of`, `warehouse_id`。
- 映射到内部「版」走 `md_uom_convert`；**禁止**排程回写 ERP。
- 配置占位：`config/integrations.yaml` → `stock_provider: local | erp_mock | erp_http`。
