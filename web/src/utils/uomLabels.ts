/** 计量单位与产能口径 — 界面展示用中文（API 仍用英文枚举） */

const UOM_ZH: Record<string, string> = {
  PCS: "枚",
  BOARD: "版",
  BOX: "盒",
  PACK: "包",
  BAG: "袋",
  CARTON: "箱",
};

const CONFIDENCE_ZH: Record<string, string> = {
  HIGH: "高",
  MID: "中",
  LOW: "低",
};

export function uomLabel(code: string | undefined | null): string {
  if (!code) return "";
  return UOM_ZH[code] ?? code;
}

export function confidenceLabel(code: string | undefined | null): string {
  if (!code) return "";
  return CONFIDENCE_ZH[code] ?? code;
}

/** 格式化后端 uom_chain 行（兼容旧英文行） */
export function formatUomChainLine(line: string): string {
  let out = line;
  for (const [en, zh] of Object.entries(UOM_ZH)) {
    out = out.replaceAll(en, zh);
  }
  return out;
}

/** 标准产能一行（替代 SPH + 英文单位） */
export function formatSphLine(sph: {
  sph_value: number;
  sph_uom: string;
  sph_basis: string;
  sph_crew?: number | null;
  crew_std: number;
  confidence: string;
  label?: string;
}): string {
  if (sph.label && !/[A-Z]{2,}/.test(sph.label)) {
    return sph.label;
  }
  const u = uomLabel(sph.sph_uom);
  let basis =
    sph.sph_basis === "CREW"
      ? `班组产能（${sph.sph_crew ?? "—"} 人协作，不再乘人数）`
      : `按单人产能 × 标准 ${sph.crew_std} 人`;
  return `标准产能 ${sph.sph_value} ${u}/小时 · ${basis} · 置信度${confidenceLabel(sph.confidence)}`;
}
