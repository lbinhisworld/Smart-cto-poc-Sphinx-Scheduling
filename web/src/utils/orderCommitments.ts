import type { Conflict, ScheduleResult } from "../types/schedule";

export type OrderCommitment = {
  order_no: string;
  plan_start: string | null;
  plan_end: string | null;
  promised_finish: string | null;
  has_red_conflict: boolean;
  has_yellow_conflict: boolean;
  semi_wo_count: number;
};

const BLOCKING = new Set(["E1", "E2"]);

export function commitmentsFromResult(
  result: ScheduleResult,
  orderNos: string[],
): OrderCommitment[] {
  const wanted = new Set(orderNos);
  const byOrder = new Map<string, typeof result.wos>();
  for (const w of result.wos) {
    if (!wanted.has(w.source_order_no)) continue;
    if (!byOrder.has(w.source_order_no)) byOrder.set(w.source_order_no, []);
    byOrder.get(w.source_order_no)!.push(w);
  }

  const blockingWo = new Set(
    result.conflicts
      .filter((c) => c.level === "RED" && c.code && BLOCKING.has(c.code) && c.wo_no)
      .map((c) => c.wo_no as string),
  );

  return [...wanted].sort().map((ono) => {
    const wos = byOrder.get(ono) ?? [];
    const finished = wos.filter((w) => w.wo_type === "FINISHED");
    const semi = wos.filter((w) => w.wo_type === "SEMI");
    let plan_end: string | null = null;
    let plan_start: string | null = null;
    if (finished.length) {
      const ends = finished.map((w) => w.plan_end).filter(Boolean) as string[];
      const starts = finished.map((w) => w.plan_start).filter(Boolean) as string[];
      if (ends.length) plan_end = ends.sort().at(-1)!;
      if (starts.length) plan_start = starts.sort()[0];
    }
    const woSet = new Set(wos.map((w) => w.wo_no));
    const has_red = wos.some((w) => blockingWo.has(w.wo_no));
    const has_yellow = result.conflicts.some(
      (c: Conflict) => c.level === "YELLOW" && c.wo_no && woSet.has(c.wo_no),
    );
    return {
      order_no: ono,
      plan_start,
      plan_end,
      promised_finish: plan_end,
      has_red_conflict: has_red,
      has_yellow_conflict: has_yellow,
      semi_wo_count: semi.length,
    };
  });
}

export function poolHasBlockingRed(
  result: ScheduleResult,
  orderNos: string[],
): boolean {
  return commitmentsFromResult(result, orderNos).some((c) => c.has_red_conflict);
}

export function sortByDueAsc<T extends { due_date: string; order_no: string }>(
  rows: T[],
): T[] {
  return [...rows].sort(
    (a, b) =>
      a.due_date.localeCompare(b.due_date) ||
      a.order_no.localeCompare(b.order_no),
  );
}
