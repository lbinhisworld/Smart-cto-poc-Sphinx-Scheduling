import { HOURS_PER_DAY } from "../constants/groups";
import type { WoTask } from "../types/schedule";

export function hoursOf(task: WoTask): number {
  const h = task.hours_wall;
  return typeof h === "number" ? h : parseFloat(h);
}

export function cellUtilization(tasks: WoTask[]): number {
  const sum = tasks.reduce((acc, t) => acc + hoursOf(t), 0);
  return sum / HOURS_PER_DAY;
}
