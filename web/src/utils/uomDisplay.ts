const UNIT_ZH: Record<string, string> = {
  BOX: "盒",
  PCS: "枚",
  BOARD: "版",
  KG: "千克",
  CARTON: "箱",
};

export function formatUnit(code: string): string {
  return UNIT_ZH[code] ?? code;
}

export function formatQtyUnit(qty: number, unit: string): string {
  const u = formatUnit(unit);
  const n = Number.isInteger(qty) ? String(qty) : qty.toFixed(2).replace(/\.?0+$/, "");
  return `${n} ${u}`;
}
