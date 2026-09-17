import type { ColineGroup, ScheduleResult } from "../types/schedule";

export function headerOrderNo(orderNo: string): string {
  return orderNo.split("#L")[0];
}

export function colinePointKey(
  dept: string,
  group: string,
  date: string,
  itemCode: string,
): string {
  return `${dept}|${group}|${date}|${itemCode}`;
}

export function colinePointSet(result: ScheduleResult | null | undefined): Set<string> {
  const out = new Set<string>();
  for (const g of result?.coline_groups ?? []) {
    out.add(colinePointKey(g.dept, g.group_code, g.task_date, g.item_code));
  }
  return out;
}

export function colineGroupAt(
  result: ScheduleResult | null | undefined,
  dept: string,
  group: string,
  date: string,
  itemCode: string,
): ColineGroup | undefined {
  return (result?.coline_groups ?? []).find(
    (g) =>
      g.dept === dept &&
      g.group_code === group &&
      g.task_date === date &&
      g.item_code === itemCode,
  );
}

export function formatColineSummary(result: ScheduleResult | null | undefined): string {
  const s = result?.coline_summary;
  if (!s || s.point_count <= 0) return "本轮没有同组同日同品项的并线点。";
  const lot = result?.lot_summary;
  const lotBit =
    lot && lot.point_count > 0
      ? ` 已确认合批 ${lot.point_count} 点 / ${lot.qty_board_total} 版。`
      : " 已确认合批 0 点。";
  return (
    `识别共线：${s.point_count} 个点 · 合计 ${s.qty_board_total} 版` +
    `（${s.order_count} 张订单、${s.sku_count} 个品项）。${lotBit}`
  );
}
