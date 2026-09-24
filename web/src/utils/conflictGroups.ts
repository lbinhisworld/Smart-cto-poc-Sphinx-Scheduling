import { headerOrderNo } from "./coline";
import type {
  Conflict,
  ConflictLevel,
  OrderRow,
  Wo,
  WoTask,
} from "../types/schedule";

const LEVEL_RANK: Record<ConflictLevel, number> = {
  RED: 0,
  YELLOW: 1,
  GREY: 2,
  BLUE: 3,
};

export type ConflictWithIndex = {
  conflict: Conflict;
  index: number;
  woType: string | null;
};

export type ConflictDisplayRow = {
  /** 代表条（合并时为 bucket 内第一条） */
  conflict: Conflict;
  index: number;
  woType: string | null;
  /** 同 code / 文案 / 建议 / 工单类型且多条工单时合并展示 */
  merged?: ConflictWithIndex[];
};

export type ConflictOrderGroup = {
  key: string;
  orderNo: string | null;
  salesName: string;
  customer: string;
  itemCode: string;
  dueDate: string | null;
  crossOrderLabels: string[];
  worstLevel: ConflictLevel;
  items: ConflictWithIndex[];
  /** 组内折叠后的清单行（与 items 顺序语义一致，条数 ≤ items） */
  rows: ConflictDisplayRow[];
};

function mergeSignature(item: ConflictWithIndex): string {
  const c = item.conflict;
  return [
    c.code,
    c.level,
    c.message,
    c.suggest ?? "",
    item.woType ?? "",
  ].join("\u0001");
}

function itemCodeForEntry(
  item: ConflictWithIndex,
  wmap: Map<string, Wo>,
): string | null {
  const woNo = item.conflict.wo_no;
  if (!woNo) return null;
  return wmap.get(woNo)?.item_code ?? null;
}

/** 同订单组内合并完全同质的工单级冲突（典型：多子件各一条 E1） */
export function collapseGroupConflictItems(
  items: ConflictWithIndex[],
): ConflictDisplayRow[] {
  if (items.length === 0) return [];

  const bySig = new Map<string, ConflictWithIndex[]>();
  for (const it of items) {
    const sig = mergeSignature(it);
    const list = bySig.get(sig) ?? [];
    list.push(it);
    bySig.set(sig, list);
  }

  const consumed = new Set<ConflictWithIndex>();
  const rows: ConflictDisplayRow[] = [];

  for (const it of items) {
    if (consumed.has(it)) continue;
    const bucket = bySig.get(mergeSignature(it)) ?? [it];
    if (bucket.length === 1 || bucket.some((b) => !b.conflict.wo_no)) {
      rows.push({
        conflict: it.conflict,
        index: it.index,
        woType: it.woType,
      });
      consumed.add(it);
      continue;
    }
    for (const b of bucket) consumed.add(b);
    const head = bucket[0];
    rows.push({
      conflict: head.conflict,
      index: head.index,
      woType: head.woType,
      merged: bucket,
    });
  }

  return rows;
}

export function conflictDisplayRowKey(row: ConflictDisplayRow): string {
  if (row.merged && row.merged.length > 1) {
    const woNos = row.merged
      .map((m) => m.conflict.wo_no ?? "")
      .filter(Boolean)
      .sort()
      .join(",");
    return ["merged", row.conflict.code, woNos, String(row.index)].join("|");
  }
  return [
    row.conflict.code,
    row.conflict.wo_no ?? "",
    row.conflict.task_id ?? "",
    row.conflict.group_code ?? "",
    row.conflict.cell_date ?? "",
    String(row.index),
  ].join("|");
}

export function mergedItemCodes(
  row: ConflictDisplayRow,
  wmap: Map<string, Wo>,
): string[] {
  const source = row.merged ?? [{ conflict: row.conflict, index: row.index, woType: row.woType }];
  return unique(
    source
      .map((m) => itemCodeForEntry(m, wmap))
      .filter((c): c is string => Boolean(c)),
  );
}

function orderByNo(orders: OrderRow[]): Map<string, OrderRow> {
  const m = new Map<string, OrderRow>();
  for (const o of orders) {
    m.set(o.order_no, o);
    m.set(headerOrderNo(o.order_no), o);
  }
  return m;
}

function findOrder(omap: Map<string, OrderRow>, orderNo: string): OrderRow | undefined {
  return omap.get(orderNo) ?? omap.get(headerOrderNo(orderNo));
}

function woByNo(wos: Wo[]): Map<string, Wo> {
  return new Map(wos.map((w) => [w.wo_no, w]));
}

function unique(xs: string[]): string[] {
  return [...new Set(xs)];
}

/** 格子级冲突（如 E4）影响到的订单号 */
export function orderNosOnConflictCell(
  c: Conflict,
  wos: Wo[],
  tasks: WoTask[],
): string[] {
  if (!c.cell_date || !c.group_code) return [];
  const woNos = tasks
    .filter(
      (t) =>
        t.task_date === c.cell_date &&
        t.group_code === c.group_code &&
        (!c.dept || !t.dept || t.dept === c.dept),
    )
    .map((t) => t.wo_no);
  const wanted = new Set(woNos);
  return unique(
    wos.filter((w) => wanted.has(w.wo_no)).map((w) => w.source_order_no),
  );
}

function salesOf(order: OrderRow | undefined): string {
  const s = order?.sales_name?.trim();
  return s ? s : "销售未填";
}

export function groupConflictsByOrder(
  conflicts: Conflict[],
  orders: OrderRow[],
  wos: Wo[],
  tasks: WoTask[],
): ConflictOrderGroup[] {
  const omap = orderByNo(orders);
  const wmap = woByNo(wos);
  const groups = new Map<string, ConflictOrderGroup>();

  const ensure = (
    key: string,
    seed: Omit<ConflictOrderGroup, "key" | "items" | "worstLevel" | "rows">,
  ): ConflictOrderGroup => {
    const existing = groups.get(key);
    if (existing) return existing;
    const created: ConflictOrderGroup = {
      ...seed,
      key,
      worstLevel: "BLUE",
      items: [],
      rows: [],
    };
    groups.set(key, created);
    return created;
  };

  const push = (g: ConflictOrderGroup, item: ConflictWithIndex) => {
    g.items.push(item);
    if (LEVEL_RANK[item.conflict.level] < LEVEL_RANK[g.worstLevel]) {
      g.worstLevel = item.conflict.level;
    }
  };

  conflicts.forEach((c, index) => {
    const wo = c.wo_no ? wmap.get(c.wo_no) : undefined;
    const fromWo = wo?.source_order_no ?? null;
    const cellOrders = fromWo ? [] : orderNosOnConflictCell(c, wos, tasks);

    let orderNo: string | null = fromWo;
    let groupKey: string;
    let cross: string[] = [];

    if (orderNo) {
      groupKey = `order:${orderNo}`;
    } else if (cellOrders.length === 1) {
      orderNo = cellOrders[0];
      groupKey = `order:${orderNo}`;
    } else if (cellOrders.length > 1) {
      groupKey = `cell:${c.dept ?? ""}:${c.group_code ?? ""}:${c.cell_date ?? ""}`;
      cross = cellOrders.map((no) => {
        const o = findOrder(omap, no);
        return `${headerOrderNo(no)} ${salesOf(o)}`;
      });
    } else {
      groupKey = "unlinked";
    }

    const order = orderNo ? findOrder(omap, orderNo) : undefined;
    const g = ensure(groupKey, {
      orderNo,
      salesName: orderNo ? salesOf(order) : cross.length ? "多销售" : "销售未填",
      customer: order?.customer ?? "",
      itemCode: order?.item_code ?? wo?.item_code ?? "",
      dueDate: order?.due_date ?? wo?.due_date ?? null,
      crossOrderLabels: cross,
    });
    push(g, { conflict: c, index, woType: wo?.wo_type ?? null });
  });

  const sorted = [...groups.values()].sort((a, b) => {
    const lv = LEVEL_RANK[a.worstLevel] - LEVEL_RANK[b.worstLevel];
    if (lv !== 0) return lv;
    const da = a.dueDate ?? "";
    const db = b.dueDate ?? "";
    if (da !== db) return da.localeCompare(db);
    return (a.orderNo ?? a.key).localeCompare(b.orderNo ?? b.key);
  });
  for (const g of sorted) {
    g.rows = collapseGroupConflictItems(g.items);
  }
  return sorted;
}
