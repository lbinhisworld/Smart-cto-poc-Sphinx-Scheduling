export const DEMO_TODAY = "2026-09-15";
export const FENCE_DAYS = 4;
export const HOURS_PER_DAY = 8;
export const HORIZON_DAYS = 21;

export type DeptCode = "FINISHED_DEPT" | "SEMI_DEPT";
export type GroupCode = "MANUAL" | "MOLD" | "POURING";

export type WorkCenter = {
  dept: DeptCode;
  code: GroupCode;
  name: string;
  headcount: number;
};

/** 工作中心 = 部门 × 工艺组（6 行看板） */
export const WORK_CENTERS: WorkCenter[] = [
  { dept: "FINISHED_DEPT", code: "MANUAL", name: "一部·手工组", headcount: 3 },
  { dept: "FINISHED_DEPT", code: "MOLD", name: "一部·模具组", headcount: 2 },
  { dept: "FINISHED_DEPT", code: "POURING", name: "一部·浇注组", headcount: 2 },
  { dept: "SEMI_DEPT", code: "MANUAL", name: "二部·手工组", headcount: 4 },
  { dept: "SEMI_DEPT", code: "MOLD", name: "二部·模具组", headcount: 3 },
  { dept: "SEMI_DEPT", code: "POURING", name: "二部·浇注组", headcount: 2 },
];

/** @deprecated 使用 WORK_CENTERS */
export const GROUPS = WORK_CENTERS;

export function wcKey(dept: DeptCode, code: GroupCode): string {
  return `${dept}|${code}`;
}

export function headcountOf(dept: DeptCode, code: GroupCode): number {
  return WORK_CENTERS.find((g) => g.dept === dept && g.code === code)?.headcount ?? 0;
}

export function workCenterLabel(dept: DeptCode, code: GroupCode): string {
  return WORK_CENTERS.find((g) => g.dept === dept && g.code === code)?.name ?? code;
}
