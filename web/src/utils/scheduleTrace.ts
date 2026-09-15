import type { TraceAct, TraceEvent } from "../types/schedule";

export const TRACE_ACTS: { id: TraceAct; label: string; hint: string }[] = [
  { id: "EXPAND", label: "1 展开", hint: "订货换算到版，生成成品工单" },
  { id: "QUEUE", label: "2 排队", hint: "晚交期先占格（DUE_DESC）" },
  { id: "PLACE", label: "3 落位", hint: "从交期往回填组×天" },
  { id: "SEMI", label: "4 半成品", hint: "扣库存后倒排二部" },
  { id: "CHECK", label: "5 体检", hint: "冲突只提示，不改交期" },
];

export const SORT_MODE_LABEL: Record<string, string> = {
  DUE_DESC: "晚交期先占格",
  PIN_FIRST: "插单/改单先钉住",
  DUE_ASC: "早交期先占格",
};

export function revealedTaskIds(events: TraceEvent[], index: number): Set<number> {
  const ids = new Set<number>();
  const end = Math.min(index, events.length - 1);
  for (let i = 0; i <= end; i += 1) {
    const id = events[i]?.task_id;
    if (id != null && events[i].kind === "place") ids.add(id);
  }
  return ids;
}

export type OccupancyRow = {
  orderNo: string;
  itemCode: string;
  qty: number;
  occupiedAfter: number;
};

export function occupancyLedger(
  events: TraceEvent[],
  uptoIndex: number,
  dept: string | null | undefined,
  group: string | null | undefined,
  date: string | null | undefined,
): { cap: number | null; rows: OccupancyRow[]; leftover: number | null } {
  if (!group || !date) return { cap: null, rows: [], leftover: null };
  let cap: number | null = null;
  const rows: OccupancyRow[] = [];
  let occupied = 0;
  const end = Math.min(uptoIndex, events.length - 1);
  for (let i = 0; i <= end; i += 1) {
    const e = events[i];
    if (e.kind !== "place" || e.task_date !== date || e.group_code !== group) continue;
    if (dept && e.dept && e.dept !== dept) continue;
    if (e.cap_board != null) cap = e.cap_board;
    occupied += e.qty_board ?? 0;
    rows.push({
      orderNo: e.order_no ?? "—",
      itemCode: e.item_code ?? "",
      qty: e.qty_board ?? 0,
      occupiedAfter: occupied,
    });
  }
  const leftover = cap != null ? Math.max(cap - occupied, 0) : null;
  return { cap, rows, leftover };
}

export function firstIndexOfAct(events: TraceEvent[], act: TraceAct): number {
  const i = events.findIndex((e) => e.act === act);
  return i < 0 ? 0 : i;
}

export type QueueRow = {
  orderNo: string;
  itemCode: string;
  dueDate: string | null;
  rank: number;
  arrived: boolean;
  justArrived: boolean;
};

/** 成品排队：未播到的格子先空着，播到 queue_rank 再入列 */
export function queuedFinishedOrders(
  events: TraceEvent[],
  uptoIndex: number,
): QueueRow[] {
  const rows: QueueRow[] = [];
  const end = Math.min(uptoIndex, events.length - 1);
  for (let i = 0; i < events.length; i += 1) {
    const e = events[i];
    if (e.kind !== "queue_rank" || e.wo_type !== "FINISHED") continue;
    const arrived = i <= end;
    rows.push({
      orderNo: arrived ? (e.order_no ?? "—") : "",
      itemCode: arrived ? (e.item_code ?? "") : "",
      dueDate: arrived ? (e.due_date ?? null) : null,
      rank: e.rank ?? rows.length + 1,
      arrived,
      justArrived: arrived && i === end,
    });
  }
  return rows;
}
