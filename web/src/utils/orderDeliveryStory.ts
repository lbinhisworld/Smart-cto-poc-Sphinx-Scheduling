import type { DeptCode, GroupCode } from "../constants/groups";
import { laborRateFor } from "../constants/laborRates";
import { workCenterLabel } from "../constants/groups";
import type {
  Conflict,
  ConflictLevel,
  OrderRow,
  ScheduleResult,
  UnplacedEntry,
  Wo,
  WoTask,
} from "../types/schedule";
import { colinePointSet, headerOrderNo } from "./coline";

export type FeasibilityBucket = "feasible" | "late" | "unscheduled";

export type WoNodeStory = {
  woNo: string;
  woType: string;
  itemCode: string;
  workCenterLabel: string;
  dept: DeptCode;
  groupCode: GroupCode;
  dateFrom: string | null;
  dateTo: string | null;
  qtyScheduled: number;
  qtyBoardPlan: number;
  qtyBoardDone: number;
  unplacedRemaining: number;
  hoursWall: number;
  hoursMan: number;
  costPlanned: number;
  conflictLevel: ConflictLevel | null;
  coline: boolean;
  primaryTaskId: number | null;
  openCellDate: string | null;
};

export type OrderDeliveryStory = {
  headerOrderNo: string;
  order: OrderRow;
  feasibility: FeasibilityBucket;
  planDeliveryDate: string | null;
  earliestFinish: string | null;
  nodes: WoNodeStory[];
  lineSummary: string;
};

const LEVEL_RANK: Record<ConflictLevel, number> = {
  RED: 4,
  YELLOW: 3,
  GREY: 2,
  BLUE: 1,
};

function numHours(v: number | string): number {
  if (typeof v === "number") return v;
  const n = parseFloat(String(v));
  return Number.isFinite(n) ? n : 0;
}

function parseSuggestDate(suggest: string | null | undefined): string | null {
  if (!suggest) return null;
  if (suggest.startsWith("EARLIEST:")) return suggest.slice("EARLIEST:".length);
  if (suggest.startsWith("FEASIBLE:")) return suggest.slice("FEASIBLE:".length);
  return null;
}

function wosForHeader(result: ScheduleResult | null, header: string): Wo[] {
  if (!result) return [];
  return result.wos.filter((w) => headerOrderNo(w.source_order_no) === header);
}

function tasksForWo(tasks: WoTask[], woNo: string): WoTask[] {
  return tasks.filter((t) => t.wo_no === woNo);
}

function deptForWo(wo: Wo, tasks: WoTask[]): DeptCode {
  const t = tasks.find((x) => x.wo_no === wo.wo_no);
  const d = (wo.dept ?? t?.dept ?? "FINISHED_DEPT") as DeptCode;
  return d;
}

function sortWos(wos: Wo[], deps: ScheduleResult["dependencies"]): Wo[] {
  if (wos.length <= 1) return [...wos];
  const ids = new Set(wos.map((w) => w.wo_no));
  const edges = deps.filter(
    (d) => ids.has(d.pred_wo_no) && ids.has(d.succ_wo_no),
  );
  if (edges.length === 0) {
    return [...wos].sort((a, b) => {
      const ta = a.wo_type === "SEMI" ? 0 : 1;
      const tb = b.wo_type === "SEMI" ? 0 : 1;
      if (ta !== tb) return ta - tb;
      const ps = (a.plan_start ?? "").localeCompare(b.plan_start ?? "");
      if (ps !== 0) return ps;
      return a.wo_no.localeCompare(b.wo_no);
    });
  }
  const inDeg = new Map<string, number>();
  const adj = new Map<string, string[]>();
  for (const w of wos) {
    inDeg.set(w.wo_no, 0);
    adj.set(w.wo_no, []);
  }
  for (const e of edges) {
    adj.get(e.pred_wo_no)!.push(e.succ_wo_no);
    inDeg.set(e.succ_wo_no, (inDeg.get(e.succ_wo_no) ?? 0) + 1);
  }
  const q = wos.filter((w) => (inDeg.get(w.wo_no) ?? 0) === 0).map((w) => w.wo_no);
  q.sort();
  const out: Wo[] = [];
  while (q.length) {
    const id = q.shift()!;
    const wo = wos.find((w) => w.wo_no === id);
    if (wo) out.push(wo);
    for (const succ of adj.get(id) ?? []) {
      const nd = (inDeg.get(succ) ?? 0) - 1;
      inDeg.set(succ, nd);
      if (nd === 0) {
        q.push(succ);
        q.sort();
      }
    }
  }
  for (const w of wos) {
    if (!out.some((x) => x.wo_no === w.wo_no)) out.push(w);
  }
  return out;
}

function maxConflictLevel(
  conflicts: Conflict[],
  woNo: string,
): ConflictLevel | null {
  let best: ConflictLevel | null = null;
  let rank = 0;
  for (const c of conflicts) {
    if (c.wo_no !== woNo) continue;
    const r = LEVEL_RANK[c.level] ?? 0;
    if (r > rank) {
      rank = r;
      best = c.level;
    }
  }
  return best;
}

function unplacedForWo(
  unplaced: UnplacedEntry[] | undefined,
  woNo: string,
): UnplacedEntry | undefined {
  return unplaced?.find((u) => u.wo_no === woNo);
}

function finishedWos(wos: Wo[]): Wo[] {
  return wos.filter((w) => w.wo_type === "FINISHED");
}

export function planDeliveryDateForHeader(
  result: ScheduleResult | null,
  header: string,
): string | null {
  const fins = finishedWos(wosForHeader(result, header));
  let max: string | null = null;
  for (const w of fins) {
    if (w.plan_end && (!max || w.plan_end > max)) max = w.plan_end;
  }
  if (max) return max;
  for (const w of wosForHeader(result, header)) {
    if (w.plan_end && (!max || w.plan_end > max)) max = w.plan_end;
  }
  return max;
}

export function earliestFinishForHeader(
  result: ScheduleResult | null,
  conflicts: Conflict[],
  header: string,
): string | null {
  const wos = wosForHeader(result, header);
  const woSet = new Set(wos.map((w) => w.wo_no));
  const finWoNos = new Set(finishedWos(wos).map((w) => w.wo_no));
  let binding: string | null = null;
  for (const c of conflicts) {
    if (!c.wo_no || !finWoNos.has(c.wo_no)) continue;
    const d = parseSuggestDate(c.suggest);
    if (d && (!binding || d > binding)) binding = d;
  }
  for (const u of result?.unplaced ?? []) {
    if (!woSet.has(u.wo_no)) continue;
    const ef = u.earliest_finish;
    if (ef && (!binding || ef > binding)) binding = ef;
  }
  return binding;
}

export function classifyOrderFeasibility(
  order: OrderRow,
  result: ScheduleResult | null,
  conflicts: Conflict[],
): FeasibilityBucket {
  const header = headerOrderNo(order.order_no);
  const wos = wosForHeader(result, header);
  if (!result || wos.length === 0) return "unscheduled";

  const due = order.due_date;
  const fins = finishedWos(wos);
  const finWoNos = new Set(fins.map((w) => w.wo_no));

  for (const c of conflicts) {
    if (c.level !== "RED" || (c.code !== "E1" && c.code !== "E2")) continue;
    if (c.wo_no && finWoNos.has(c.wo_no)) return "late";
  }

  for (const u of result.unplaced ?? []) {
    if (wos.some((w) => w.wo_no === u.wo_no)) return "late";
  }

  const planEnd = planDeliveryDateForHeader(result, header);
  if (planEnd && planEnd > due) return "late";

  const earliest = earliestFinishForHeader(result, conflicts, header);
  if (earliest && earliest > due) return "late";

  return "feasible";
}

function buildNode(
  wo: Wo,
  tasks: WoTask[],
  conflicts: Conflict[],
  unplaced: UnplacedEntry[] | undefined,
  colineKeys: Set<string>,
): WoNodeStory {
  const woTasks = tasksForWo(tasks, wo.wo_no);
  const dates = woTasks.map((t) => t.task_date).sort();
  const dept = deptForWo(wo, woTasks);
  const group = wo.group_code as GroupCode;
  let coline = false;
  for (const t of woTasks) {
    const item = wo.item_code;
    const key = `${t.dept ?? dept}|${t.group_code}|${t.task_date}|${item}`;
    if (colineKeys.has(key)) coline = true;
  }
  const qtyScheduled = woTasks.reduce((s, t) => s + t.qty_board, 0);
  const hoursWall = woTasks.reduce((s, t) => s + numHours(t.hours_wall), 0);
  const hoursMan = woTasks.reduce((s, t) => s + numHours(t.hours_man), 0);
  const rate = laborRateFor(dept, group);
  const miss = unplacedForWo(unplaced, wo.wo_no);
  const primary = woTasks[0] ?? null;
  return {
    woNo: wo.wo_no,
    woType: wo.wo_type,
    itemCode: wo.item_code,
    workCenterLabel: workCenterLabel(dept, group),
    dept,
    groupCode: group,
    dateFrom: dates[0] ?? wo.plan_start ?? null,
    dateTo: dates[dates.length - 1] ?? wo.plan_end ?? null,
    qtyScheduled,
    qtyBoardPlan: wo.qty_board_plan,
    qtyBoardDone: wo.qty_board_done ?? 0,
    unplacedRemaining: miss?.remaining ?? 0,
    hoursWall,
    hoursMan,
    costPlanned: Math.round(hoursMan * rate * 100) / 100,
    conflictLevel: maxConflictLevel(conflicts, wo.wo_no),
    coline,
    primaryTaskId: primary?.task_id ?? null,
    openCellDate: primary?.task_date ?? wo.plan_start ?? null,
  };
}

function pickRepresentativeOrder(
  orders: OrderRow[],
  header: string,
): OrderRow | null {
  const exact = orders.find((o) => o.order_no === header);
  if (exact) return exact;
  const related = orders.filter((o) => headerOrderNo(o.order_no) === header);
  return related[0] ?? null;
}

function lineSummaryFor(order: OrderRow, extraLines?: string[]): string {
  const base = `${order.item_code} × ${order.qty_order} ${order.unit}`;
  if (!extraLines?.length) return base;
  if (extraLines.length === 1) return extraLines[0];
  return `${extraLines.slice(0, 3).join("；")}${extraLines.length > 3 ? ` 等 ${extraLines.length} 行` : ""}`;
}

export function buildOrderDeliveryStory(
  header: string,
  orders: OrderRow[],
  result: ScheduleResult | null,
  tasks: WoTask[],
  conflicts: Conflict[],
  lineTexts?: string[],
): OrderDeliveryStory | null {
  const order = pickRepresentativeOrder(orders, header);
  if (!order) return null;

  const wos = wosForHeader(result, header);
  const feasibility =
    wos.length === 0
      ? "unscheduled"
      : classifyOrderFeasibility(order, result, conflicts);

  const sorted = sortWos(wos, result?.dependencies ?? []);
  const colineKeys = colinePointSet(result ?? null);
  const nodes = sorted.map((wo) =>
    buildNode(wo, tasks, conflicts, result?.unplaced, colineKeys),
  );

  return {
    headerOrderNo: header,
    order: { ...order, order_no: header },
    feasibility,
    planDeliveryDate: planDeliveryDateForHeader(result, header),
    earliestFinish: earliestFinishForHeader(result, conflicts, header),
    nodes,
    lineSummary: lineSummaryFor(order, lineTexts),
  };
}

export function buildOrderDeliveryStories(
  orders: OrderRow[],
  selectedOrderNos: Set<string>,
  result: ScheduleResult | null,
  tasks: WoTask[],
  conflicts: Conflict[],
  lineTextsByHeader?: Record<string, string[]>,
): {
  feasible: OrderDeliveryStory[];
  late: OrderDeliveryStory[];
  unscheduled: OrderDeliveryStory[];
} {
  const headers = new Set<string>();
  for (const o of orders) {
    if (!selectedOrderNos.has(o.order_no)) continue;
    headers.add(headerOrderNo(o.order_no));
  }

  const feasible: OrderDeliveryStory[] = [];
  const late: OrderDeliveryStory[] = [];
  const unscheduled: OrderDeliveryStory[] = [];

  for (const h of [...headers].sort()) {
    const story = buildOrderDeliveryStory(
      h,
      orders,
      result,
      tasks,
      conflicts,
      lineTextsByHeader?.[h],
    );
    if (!story) continue;
    if (story.feasibility === "unscheduled") unscheduled.push(story);
    else if (story.feasibility === "late") late.push(story);
    else feasible.push(story);
  }

  const byDue = (a: OrderDeliveryStory, b: OrderDeliveryStory) =>
    a.order.due_date.localeCompare(b.order.due_date) ||
    a.headerOrderNo.localeCompare(b.headerOrderNo);

  feasible.sort(byDue);
  late.sort(byDue);
  unscheduled.sort(byDue);

  return { feasible, late, unscheduled };
}

export function formatDateRange(from: string | null, to: string | null): string {
  if (!from && !to) return "—";
  if (!from || from === to) return from ?? to ?? "—";
  return `${from} ~ ${to}`;
}
