import { headcountOf, HOURS_PER_DAY, workCenterLabel } from "../constants/groups";
import type { DeptCode, GroupCode } from "../constants/groups";
import type { WoTask } from "../types/schedule";
import { hoursOf } from "./capacity";

export type LocalCellWarning = {
  code: string;
  message: string;
  cellKey: string;
  taskId?: number;
};

function cellKey(t: WoTask): string {
  return `${t.dept ?? "FINISHED_DEPT"}|${t.group_code}|${t.task_date}`;
}

export function localHeadcountWarnings(tasks: WoTask[]): LocalCellWarning[] {
  const warnings: LocalCellWarning[] = [];
  const byCell = new Map<string, WoTask[]>();
  for (const t of tasks) {
    const key = cellKey(t);
    if (!byCell.has(key)) byCell.set(key, []);
    byCell.get(key)!.push(t);
  }

  for (const [key, cellTasks] of byCell) {
    const [dept, group] = key.split("|") as [DeptCode, GroupCode];
    const hc = headcountOf(dept, group);
    const label = workCenterLabel(dept, group);
    const wall = cellTasks.reduce((s, t) => s + hoursOf(t), 0);
    const crewSum = cellTasks.reduce((s, t) => s + t.crew_plan, 0);

    for (const t of cellTasks) {
      if (hc && t.crew_plan > hc) {
        warnings.push({
          code: "CREW_OVER_HEAD",
          cellKey: key,
          taskId: t.task_id,
          message: `人力 ${t.crew_plan} 超过${label}在编 ${hc} 人`,
        });
      }
    }
    if (hc && crewSum > hc) {
      warnings.push({
        code: "CREW_SUM_OVER",
        cellKey: key,
        message: `当日人力合计 ${crewSum} 超过在编 ${hc} 人`,
      });
    }
    if (wall > HOURS_PER_DAY) {
      warnings.push({
        code: "WALL_OVER_DAY",
        cellKey: key,
        message: `墙钟合计 ${wall.toFixed(1)} 小时超过 ${HOURS_PER_DAY} 小时/日`,
      });
    }
  }
  return warnings;
}

export function taskOverHeadcount(task: WoTask): boolean {
  const dept = (task.dept ?? "FINISHED_DEPT") as DeptCode;
  const group = task.group_code as GroupCode;
  const hc = headcountOf(dept, group);
  return hc > 0 && task.crew_plan > hc;
}

export function warningsByCell(tasks: WoTask[]): Map<string, string[]> {
  const map = new Map<string, string[]>();
  for (const w of localHeadcountWarnings(tasks)) {
    const arr = map.get(w.cellKey) ?? [];
    if (!arr.includes(w.message)) arr.push(w.message);
    map.set(w.cellKey, arr);
  }
  return map;
}
