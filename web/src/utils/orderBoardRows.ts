import type { OrderRow, ScheduleResult } from "../types/schedule";

export type OrderBoardRow = {
  order: OrderRow;
  /** 当前计划中已有工单 */
  scheduled: boolean;
  planStart: string | null;
  planEnd: string | null;
};

function planSpanForOrder(
  result: ScheduleResult | null,
  orderNo: string,
): { planStart: string | null; planEnd: string | null } {
  if (!result) return { planStart: null, planEnd: null };
  const wos = result.wos.filter((w) => w.source_order_no === orderNo);
  let planStart: string | null = null;
  let planEnd: string | null = null;
  for (const w of wos) {
    if (w.plan_start && (!planStart || w.plan_start < planStart)) {
      planStart = w.plan_start;
    }
    if (w.plan_end && (!planEnd || w.plan_end > planEnd)) {
      planEnd = w.plan_end;
    }
  }
  return { planStart, planEnd };
}

/** 订单看板行：已排产在前（交期升序），未排产空行在最后 */
export function buildOrderBoardRows(
  orders: OrderRow[],
  selected: Set<string>,
  result: ScheduleResult | null,
  filterOrderNo: string | null,
): OrderBoardRow[] {
  let scope = orders.filter((o) => selected.has(o.order_no));
  if (filterOrderNo) {
    scope = scope.filter((o) => o.order_no === filterOrderNo);
  }

  const rows: OrderBoardRow[] = scope.map((order) => {
    const scheduled =
      result?.wos.some((w) => w.source_order_no === order.order_no) ?? false;
    const span = planSpanForOrder(result, order.order_no);
    return { order, scheduled, ...span };
  });

  const byDue = (a: OrderBoardRow, b: OrderBoardRow) =>
    a.order.due_date.localeCompare(b.order.due_date) ||
    a.order.order_no.localeCompare(b.order.order_no);

  const scheduledRows = rows.filter((r) => r.scheduled).sort(byDue);
  const unscheduledRows = rows.filter((r) => !r.scheduled).sort(byDue);
  return [...scheduledRows, ...unscheduledRows];
}
