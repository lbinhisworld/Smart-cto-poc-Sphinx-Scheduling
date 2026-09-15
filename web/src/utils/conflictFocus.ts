import { WORK_CENTERS, type DeptCode, type GroupCode } from "../constants/groups";
import type { Conflict, ScheduleResult } from "../types/schedule";

export type ConflictCellTarget = {
  dept: string;
  group: string;
  date: string;
  focusTaskId: number | null;
};

function parseDeptGroupFromMessage(message: string): { dept: string; group: string } | null {
  const m = message.match(/(FINISHED_DEPT|SEMI_DEPT):(\w+)/);
  if (m) return { dept: m[1], group: m[2] };
  for (const wc of WORK_CENTERS) {
    if (message.includes(wc.name)) {
      return { dept: wc.dept, group: wc.code };
    }
  }
  for (const wc of WORK_CENTERS) {
    if (message.includes(wc.code)) {
      return { dept: wc.dept, group: wc.code };
    }
  }
  return null;
}

/** 从冲突记录解析工作中心×日 */
export function resolveConflictCell(
  c: Conflict,
  result: ScheduleResult | null,
): ConflictCellTarget | null {
  let dept = c.dept ?? null;
  let group = c.group_code ?? null;
  let date = c.cell_date ?? null;
  let focusTaskId = c.task_id ?? null;

  if (c.task_id && result) {
    const byId = result.tasks.find((x) => x.task_id === c.task_id);
    if (byId) {
      dept = dept ?? byId.dept ?? "FINISHED_DEPT";
      group = group ?? byId.group_code;
      date = date ?? byId.task_date;
      focusTaskId = byId.task_id;
    }
  }

  if ((!dept || !group || !date) && c.wo_no && result) {
    const byWo = result.tasks.find((x) => x.wo_no === c.wo_no);
    if (byWo) {
      dept = dept ?? byWo.dept ?? "FINISHED_DEPT";
      group = group ?? byWo.group_code;
      date = date ?? byWo.task_date;
      focusTaskId = focusTaskId ?? byWo.task_id;
    }
  }

  if (!date) {
    const dateMatch = c.message.match(/\d{4}-\d{2}-\d{2}/);
    if (dateMatch) date = dateMatch[0];
  }

  if (!dept || !group) {
    const parsed = parseDeptGroupFromMessage(c.message);
    if (parsed) {
      dept = dept ?? parsed.dept;
      group = group ?? parsed.group;
    }
  }

  if (dept && group && date) {
    return { dept, group, date, focusTaskId };
  }
  return null;
}

/** 看板列日期：默认窗口 + 任务与冲突涉及日期 */
export function boardDateColumns(
  today: string,
  tasks: { task_date: string }[],
  conflicts: Conflict[],
  baseRange: (t: string) => string[],
): string[] {
  const set = new Set(baseRange(today));
  for (const t of tasks) set.add(t.task_date);
  for (const c of conflicts) {
    if (c.cell_date) set.add(c.cell_date);
    const m = c.message.match(/\d{4}-\d{2}-\d{2}/);
    if (m) set.add(m[0]);
  }
  return [...set].sort();
}

export function deptGroupFromTask(t: {
  dept?: string;
  group_code: string;
}): { dept: DeptCode; group: GroupCode } {
  return {
    dept: (t.dept ?? "FINISHED_DEPT") as DeptCode,
    group: t.group_code as GroupCode,
  };
}
