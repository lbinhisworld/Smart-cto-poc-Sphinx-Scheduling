import type { Conflict, OrderRow, ScheduleTrace, TraceEvent } from "../types/schedule";
import { SORT_MODE_LABEL } from "./scheduleTrace";

export type ProcessBubble = {
  id: string;
  tone: "info" | "place" | "alert" | "coline";
  text: string;
  orderNo?: string;
};

export function headerOrderNo(orderNo: string): string {
  return orderNo.split("#L")[0];
}

function shortDue(iso: string | null | undefined, fallback: string): string {
  if (!iso) return fallback;
  const parts = iso.split("-");
  if (parts.length >= 3) return `${Number(parts[1])}/${Number(parts[2])}`;
  return iso;
}

export function dueGap(oldDue: string | null | undefined, suggestedDue: string | null | undefined): "LATE" | "FEASIBLE" | "UNKNOWN" {
  if (!oldDue || !suggestedDue) return "UNKNOWN";
  if (suggestedDue > oldDue) return "LATE";
  return "FEASIBLE";
}

export function localBriefText(a: {
  orderNo: string;
  suggestedDue: string | null;
  reason: string;
  customer?: string;
  salesName?: string;
  itemCode?: string;
  oldDue?: string | null;
}): string {
  const no = headerOrderNo(a.orderNo);
  const old = shortDue(a.oldDue, "原交期");
  const neu = shortDue(a.suggestedDue, "最快可完成日");
  const who = a.customer
    ? `${a.customer}${a.salesName ? `（${a.salesName}）` : ""}`
    : "";
  const item = a.itemCode ? ` ${a.itemCode}` : "";
  if (dueGap(a.oldDue, a.suggestedDue) !== "LATE") {
    return (
      `${no} ${who}${item}，客户要 ${old}。` +
      `系统物理最快 ${neu}，早于或不晚于客户交期，交期本身够，不必改客户交期。` +
      `红灯是倒排贴着 ${old} 往回填时${a.reason}，不是客户要得太早。` +
      `请在排程侧把开工往前提或加班/加人，不要找销售改交期。`
    );
  }
  return (
    `我按如下口径回复销售：\n` +
    `${no} ${who}${item}，客户要 ${old}。` +
    `半成品库存不够，必须开生产工单补齐缺口。` +
    `按倒排试排后仍无法满足 ${old} 交付，建议交付不早于 ${neu}。` +
    `未确认前计划仍按 ${old} 挂红，不改客户交期。`
  );
}

function monthDay(iso: string): string {
  const parts = iso.split("-");
  if (parts.length < 3) return iso;
  return `${Number(parts[1])}/${Number(parts[2])}`;
}

/** 从本轮 trace 还原 E1 逐日尝试；引擎新日志已含全文时直接用。 */
export function formatUnplacedAudit(events: TraceEvent[], unplaced: TraceEvent): string {
  if (unplaced.message.includes("安排尝试") && unplaced.message.includes("所以结论")) {
    return unplaced.message;
  }
  const related = events.filter((e) => {
    if (e.kind !== "place" && e.kind !== "skip_day") return false;
    if (unplaced.wo_no) return e.wo_no === unplaced.wo_no;
    return e.order_no === unplaced.order_no && e.item_code === unplaced.item_code;
  });
  const bits: string[] = [];
  for (const e of related) {
    const day = e.task_date ? monthDay(e.task_date) : "?";
    if (e.kind === "place") {
      const extra =
        e.cap_board != null ? `（日产能 ${e.cap_board} 版，已占 ${e.occupied_before ?? 0}）` : "";
      bits.push(`${day} 放下 ${e.qty_board ?? "?"} 版${extra}`);
    } else if (e.skip_reason === "REST") {
      bits.push(`${day} 非工作日跳过`);
    } else if (e.skip_reason === "FULL") {
      const extra = e.cap_board != null ? `（上限 ${e.cap_board} 版）` : "";
      bits.push(`${day} 产能已满跳过${extra}`);
    } else {
      bits.push(`${day} 跳过`);
    }
  }
  const trail = bits.length ? bits.join("；") : "交期到最早可排日之间没有放下任何版";
  const remain = unplaced.qty_board ?? "?";
  const due = unplaced.due_date ? `从交期 ${monthDay(unplaced.due_date)} 往回填。` : "从交期往回填。";
  const earliest = unplaced.task_date ? monthDay(unplaced.task_date) : "最早可排日";
  return (
    `${unplaced.order_no ?? ""} ${unplaced.item_code ?? ""} ${due}\n` +
    `安排尝试：${trail}。\n` +
    `碰到最早可排日 ${earliest}，还剩 ${remain} 版。\n` +
    `所以结论：未能在最早可排日前安置完（E1）。`
  );
}

export function parseEarliest(suggest: string | null | undefined): string | null {
  if (!suggest) return null;
  const tagged = suggest.match(/(?:EARLIEST|FEASIBLE):(\d{4}-\d{2}-\d{2})/);
  if (tagged) return tagged[1];
  const iso = suggest.match(/(\d{4}-\d{2}-\d{2})/);
  return iso ? iso[1] : null;
}

export function isDueNegotiateSuggest(suggest: string | null | undefined): boolean {
  return Boolean(suggest?.startsWith("EARLIEST:"));
}

export function projectProcessBubbles(
  trace: ScheduleTrace | null | undefined,
  conflicts: Conflict[],
  orders: OrderRow[],
): ProcessBubble[] {
  const bubbles: ProcessBubble[] = [];
  if (!trace?.events.length) {
    bubbles.push({
      id: "empty",
      tone: "info",
      text: "尚无本轮倒排记录。点「一键倒排」或「试排」后，这里按记录回放，不会再算一遍。",
    });
    return bubbles;
  }
  const mode = SORT_MODE_LABEL[trace.sort_mode] ?? trace.sort_mode;
  bubbles.push({
    id: "start",
    tone: "info",
    text: `开始排产。策略：${mode}。以下是已算出的记录，正在按顺序说明。`,
  });

  const seenQueue = new Set<string>();
  const seenPlace = new Set<string>();
  for (const [i, e] of trace.events.entries()) {
    if (e.act === "QUEUE" && e.kind === "queue_rank" && e.order_no && !seenQueue.has(e.order_no)) {
      seenQueue.add(e.order_no);
      bubbles.push({
        id: `q-${i}`,
        tone: "info",
        orderNo: e.order_no,
        text: `排队 ${e.order_no}${e.item_code ? ` ${e.item_code}` : ""}${e.due_date ? ` · 交期 ${e.due_date}` : ""}（晚交期先占格）`,
      });
    }
    if (e.kind === "place" && e.order_no && !seenPlace.has(e.order_no)) {
      seenPlace.add(e.order_no);
      bubbles.push({
        id: `p-${i}`,
        tone: "place",
        orderNo: e.order_no,
        text: `正在倒排 ${e.order_no}${e.item_code ? `（${e.item_code}）` : ""}……从交期往回填。`,
      });
    }
    if (e.kind === "expand_lines" || e.kind === "sku_intersect") {
      bubbles.push({
        id: `x-${i}`,
        tone: "info",
        orderNo: e.order_no,
        text: e.message,
      });
    }
    if ((e.kind === "expand_semi" || e.kind === "semi_from_stock") && e.order_no) {
      bubbles.push({
        id: `s-${i}`,
        tone: "info",
        orderNo: e.order_no,
        text: e.message,
      });
    }
    if (e.kind === "unplaced" && e.order_no) {
      bubbles.push({
        id: `u-${i}`,
        tone: "alert",
        orderNo: e.order_no,
        text: formatUnplacedAudit(trace.events, e),
      });
    }
    if (e.kind === "coline_decision") {
      bubbles.push({
        id: `cl-${i}`,
        tone: "coline",
        text: e.message,
      });
    }
    if (e.kind === "coline_summary") {
      bubbles.push({
        id: `cs-${i}`,
        tone: "coline",
        text: e.message,
      });
    }
  }

  const reds = conflicts.filter((c) => c.level === "RED" && (c.code === "E1" || c.code === "E2"));
  const seenRed = new Set<string>();
  for (const c of reds) {
    const order = orderOfConflict(c, orders, trace.events);
    const key = `${order}-${c.code}`;
    if (seenRed.has(key)) continue;
    seenRed.add(key);
    const earliest = parseEarliest(c.suggest);
    const row = order ? orders.find((o) => headerOrderNo(o.order_no) === order) : undefined;
    const gap = dueGap(row?.due_date, earliest);
    const fastestNote = earliest
      ? gap === "LATE"
        ? `。系统最快 ${earliest}，晚于客户交期`
        : `。系统最快 ${earliest}，不晚于客户交期，交期本身够`
      : "";
    const unplaced = trace.events.find(
      (e) => e.kind === "unplaced" && order && e.order_no && headerOrderNo(e.order_no) === order,
    );
    if (c.code === "E1" && unplaced) {
      bubbles.push({
        id: `c-${key}`,
        tone: "alert",
        orderNo: order,
        text: `发现冲突 E1${order ? ` · ${order}` : ""}：见上方安置过程${fastestNote}`,
      });
      continue;
    }
    bubbles.push({
      id: `c-${key}`,
      tone: "alert",
      orderNo: order,
      text: `发现冲突 ${c.code}${order ? ` · ${order}` : ""}：${c.message} 排产过程见上方试排。${fastestNote}`,
    });
  }
  return bubbles;
}

function orderOfConflict(c: Conflict, orders: OrderRow[], events: TraceEvent[]): string | undefined {
  const byWo = events.find((e) => e.wo_no === c.wo_no && e.order_no);
  if (byWo?.order_no) return headerOrderNo(byWo.order_no);
  const hit = orders.find((o) => c.message.includes(o.order_no) || c.message.includes(headerOrderNo(o.order_no)));
  return hit ? headerOrderNo(hit.order_no) : undefined;
}

export type RedAssist = {
  orderNo: string;
  code: string;
  message: string;
  reason: string;
  suggestedDue: string | null;
  kind: "NEGOTIATE" | "WINDOW";
};

export function redAssists(
  conflicts: Conflict[],
  orders: OrderRow[],
  events: TraceEvent[],
): RedAssist[] {
  const byOrder = new Map<string, RedAssist>();
  for (const c of conflicts) {
    if (c.level !== "RED" || (c.code !== "E1" && c.code !== "E2")) continue;
    const orderNo = orderOfConflict(c, orders, events);
    if (!orderNo) continue;
    const fastest =
      parseEarliest(c.suggest) || parseEarliest(c.message);
    const row = orders.find((o) => headerOrderNo(o.order_no) === orderNo);
    const kind: RedAssist["kind"] =
      isDueNegotiateSuggest(c.suggest) || dueGap(row?.due_date, fastest) === "LATE"
        ? "NEGOTIATE"
        : "WINDOW";
    const unplaced = events.find(
      (e) => e.kind === "unplaced" && e.order_no && headerOrderNo(e.order_no) === orderNo,
    );
    const message =
      c.code === "E1" && unplaced ? formatUnplacedAudit(events, unplaced) : c.message;
    const next: RedAssist = {
      orderNo,
      code: c.code,
      message,
      reason: c.code === "E2" ? "半成品来不及成品倒排开工" : "未在最早可排日前安置完",
      suggestedDue: fastest,
      kind,
    };
    const prev = byOrder.get(orderNo);
    if (!prev) {
      byOrder.set(orderNo, next);
      continue;
    }
    const mergedKind: RedAssist["kind"] =
      prev.kind === "NEGOTIATE" || next.kind === "NEGOTIATE" ? "NEGOTIATE" : "WINDOW";
    if (!prev.suggestedDue && next.suggestedDue) {
      byOrder.set(orderNo, { ...prev, ...next, suggestedDue: next.suggestedDue, kind: mergedKind });
    } else if (next.code === "E2" && prev.code !== "E2") {
      byOrder.set(orderNo, {
        ...next,
        suggestedDue: next.suggestedDue ?? prev.suggestedDue,
        kind: mergedKind,
      });
    } else {
      prev.kind = mergedKind;
      if (!prev.suggestedDue && fastest) prev.suggestedDue = fastest;
    }
  }
  return [...byOrder.values()];
}
