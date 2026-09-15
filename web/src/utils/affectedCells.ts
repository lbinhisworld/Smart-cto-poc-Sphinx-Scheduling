import type { WoTask } from "../types/schedule";
import type { HeadcountWarning } from "../components/AdjustImpactModal";

function cellKey(t: WoTask): string {
  return `${t.dept ?? "FINISHED_DEPT"}|${t.group_code}|${t.task_date}`;
}

/** 与后端 db/interactive_preview._affected_cells 一致 */
export function affectedCells(
  baseline: WoTask[],
  proposed: WoTask[],
  triggerTaskId?: number | null,
): Set<string> {
  const baseById = new Map(baseline.map((t) => [t.task_id, t]));
  const cells = new Set<string>();

  for (const p of proposed) {
    const b = baseById.get(p.task_id);
    if (!b) {
      cells.add(cellKey(p));
      continue;
    }
    if (
      (b.dept ?? "FINISHED_DEPT") !== (p.dept ?? "FINISHED_DEPT") ||
      b.group_code !== p.group_code ||
      b.task_date !== p.task_date ||
      b.crew_plan !== p.crew_plan ||
      b.qty_board !== p.qty_board
    ) {
      cells.add(cellKey(b));
      cells.add(cellKey(p));
    }
  }
  if (triggerTaskId != null) {
    const t = proposed.find((x) => x.task_id === triggerTaskId);
    if (t) cells.add(cellKey(t));
  }
  return cells;
}

export function filterHeadcountWarnings(
  warnings: HeadcountWarning[],
  cells: Set<string>,
  proposed: WoTask[],
): HeadcountWarning[] {
  const byId = new Map(proposed.map((t) => [t.task_id, t]));
  return warnings.filter((w) => {
    const d = (w as HeadcountWarning & { dept?: string }).dept;
    const g = (w as HeadcountWarning & { group_code?: string }).group_code;
    const wd = (w as HeadcountWarning & { work_date?: string }).work_date;
    if (d && g && wd && cells.has(`${d}|${g}|${wd}`)) return true;
    if (g && wd && !d && cells.has(`FINISHED_DEPT|${g}|${wd}`)) return true;
    if (w.task_id != null) {
      const t = byId.get(w.task_id);
      if (t && cells.has(cellKey(t))) return true;
    }
    return false;
  });
}
