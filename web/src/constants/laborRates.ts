/** POC 标准人时单价（与 seed/demo_data.json labor_rates 一致） */
export const LABOR_RATE_BY_WC: Record<string, number> = {
  "FINISHED_DEPT|MANUAL": 48,
  "FINISHED_DEPT|MOLD": 62,
  "FINISHED_DEPT|POURING": 55,
  "SEMI_DEPT|MANUAL": 46,
  "SEMI_DEPT|MOLD": 58,
  "SEMI_DEPT|POURING": 52,
};

export function laborRateFor(dept: string, groupCode: string): number {
  return LABOR_RATE_BY_WC[`${dept}|${groupCode}`] ?? 0;
}
