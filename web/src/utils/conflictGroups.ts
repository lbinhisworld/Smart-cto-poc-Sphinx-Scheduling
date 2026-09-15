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
};

function orderByNo(orders: OrderRow[]): Map<string, OrderRow> {
  return new Map(orders.map((o) => [o.order_no, o]));
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
    seed: Omit<ConflictOrderGroup, "key" | "items" | "worstLevel">,
  ): ConflictOrderGroup => {
    const existing = groups.get(key);
    if (existing) return existing;
    const created: ConflictOrderGroup = {
      key,
      worstLevel: "BLUE",
      items: [],
      ...seed,
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
        const o = omap.get(no);
        return `${no} ${salesOf(o)}`;
      });
    } else {
      groupKey = "unlinked";
    }

    const order = orderNo ? omap.get(orderNo) : undefined;
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

  return [...groups.values()].sort((a, b) => {
    const lv = LEVEL_RANK[a.worstLevel] - LEVEL_RANK[b.worstLevel];
    if (lv !== 0) return lv;
    const da = a.dueDate ?? "";
    const db = b.dueDate ?? "";
    if (da !== db) return da.localeCompare(db);
    return (a.orderNo ?? a.key).localeCompare(b.orderNo ?? b.key);
  });
}
