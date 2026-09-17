import { GROUPS, WORK_CENTERS } from "../constants/groups";

const GROUP_LABEL: Record<string, string> = Object.fromEntries(
  GROUPS.map((g) => [g.code, g.name]),
);

/** 冲突类型（E1–E10 / FROZEN）展示名 */
const CONFLICT_CODE_LABEL: Record<string, string> = {
  E1: "E1 · 未安置 / 最早可排",
  E2: "E2 · 半成品来不及",
  E3: "E3 · 包材未齐套",
  E4: "E4 · 组日产能超限",
  E5: "E5 · SPH 未校准",
  E6: "E6 · 换线过多",
  E7: "E7 · 预留产能",
  E8: "E8 · 人力与 SPH 不符",
  E9: "E9 · 齐套未就绪",
  E10: "E10 · 库存被前序占用",
  FROZEN: "冻结区预警",
  RIPPLE: "涟漪影响超限",
};

/** 一键修复建议 */
export function suggestLabel(suggest: string | null | undefined): string | null {
  if (!suggest) return null;
  if (suggest.startsWith("EARLIEST:")) {
    const d = suggest.slice("EARLIEST:".length);
    return `最快可完成日 ${d}，晚于客户交期，建议与销售协商`;
  }
  if (suggest.startsWith("FEASIBLE:")) {
    const d = suggest.slice("FEASIBLE:".length);
    return `物理最快 ${d}，不晚于客户交期，交期本身够，不要改交期`;
  }
  const map: Record<string, string> = {
    DELAY_1D: "顺延 1 个工作日",
    ADD_CREW: "加班或增加人手",
    SPLIT: "拆单塞入空档",
    NOTIFY_SALES: "联系销售与客户协商交期",
    REVIEW_WINDOW: "交期本身够，红灯是倒排窗口/半成品卡点，不要改交期",
  };
  return map[suggest] ?? suggest;
}

export function conflictCodeLabel(code: string): string {
  return CONFLICT_CODE_LABEL[code] ?? code;
}

/** 将 message 中的组代码、英文建议片段替换为中文 */
export function formatConflictMessage(message: string): string {
  let out = message;
  for (const wc of WORK_CENTERS) {
    out = out.replaceAll(`${wc.dept}:${wc.code}`, wc.name);
  }
  for (const g of GROUPS) {
    out = out.replaceAll(g.code, g.name);
  }
  out = out.replaceAll("FINISHED_DEPT", "一部");
  out = out.replaceAll("SEMI_DEPT", "二部");
  return out;
}

export function groupLabel(code: string): string {
  return GROUP_LABEL[code] ?? code;
}

/** 各级别含义（冲突面板说明） */
export const CONFLICT_LEVEL_GUIDE: Record<
  import("../types/schedule").ConflictLevel,
  { title: string; codes: string; meaning: string }
> = {
  RED: {
    title: "红色 · 必须处理",
    codes: "E1、E2",
    meaning: "倒排窗口放不下或半成品赶不上。仅当最快日晚于客户交期才找销售改交期。",
  },
  YELLOW: {
    title: "黄色 · 可排但有风险",
    codes: "E3、E4、E8、E9、E10、冻结区",
    meaning: "软约束预警：产能超限、齐套/包材、冻结区内半成品、人力与 SPH 不符等。",
  },
  GREY: {
    title: "灰色 · 数据/工艺提醒",
    codes: "E5、E6",
    meaning: "SPH 未校准或换线偏多，结果仅供参考或需优化排法。",
  },
  BLUE: {
    title: "蓝色 · 优化建议",
    codes: "E7",
    meaning: "可合并订单、利用预留产能等，非必须处理。",
  },
};

function num(v: number | string | null | undefined): number | null {
  if (v == null || v === "") return null;
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? n : null;
}

/** 墙钟超限等数值备注（E4 优先读结构化字段） */
export function conflictMetricNote(c: import("../types/schedule").Conflict): string | null {
  if (c.code === "E4") {
    if (c.message.includes("日上限")) {
      return null;
    }
    const total = num(c.hours_wall_total);
    const limit = num(c.hours_wall_limit);
    if (total != null && limit != null && limit > 0) {
      const over = total - limit;
      const pct = Math.round((total / limit) * 1000) / 10;
      return `墙钟合计 ${total.toFixed(2)}h · 日上限 ${limit.toFixed(2)}h · 超限 +${over.toFixed(2)}h（${pct}%）`;
    }
  }
  return null;
}

export function conflictRowKey(c: import("../types/schedule").Conflict, index: number): string {
  return [
    c.code,
    c.wo_no ?? "",
    c.task_id ?? "",
    c.group_code ?? "",
    c.cell_date ?? "",
    index,
  ].join("|");
}
