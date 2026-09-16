import type { RoleCode } from "./auth";

export type MenuItem = { key: string; label: string; path: string; module: string };

/** 首页 / 侧栏：待办、演示控制台为一级直达（不进五类） */
export const NAV_TOP_LEVEL_KEYS = ["todos", "demo"] as const;

/** 五类业务域 → 菜单 key（与 MENU 对齐） */
export const NAV_CATEGORY_DEFS: { id: string; label: string; itemKeys: string[] }[] = [
  { id: "mgmt", label: "管理", itemKeys: ["cockpit", "project"] },
  {
    id: "sales",
    label: "销售",
    itemKeys: [
      "crm_customers",
      "crm_opportunities",
      "crm_samples",
      "crm_reports",
      "ctp",
      "changes",
      "orders",
      "kingdee",
    ],
  },
  { id: "hr", label: "人事", itemKeys: ["hr_roster", "hr_attendance", "hr_labor_cost"] },
  {
    id: "production",
    label: "生产",
    itemKeys: ["schedule", "stock", "bom", "production", "labor_time_report"],
  },
  { id: "finance", label: "财务", itemKeys: ["finance"] },
];

export type GroupedNav = {
  home: MenuItem | null;
  topLevel: MenuItem[];
  categories: { label: string; items: MenuItem[] }[];
};

const MENU_BY_KEY = (): Map<string, MenuItem> => new Map(MENU.map((m) => [m.key, m]));

export function groupedNavForRole(role: RoleCode, items?: MenuItem[]): GroupedNav {
  const allowed = new Set((items ?? fallbackMenuForRole(role)).map((m) => m.key));
  const byKey = MENU_BY_KEY();
  const pick = (key: string) => (allowed.has(key) ? byKey.get(key) : undefined);

  const home = pick("portal") ?? null;
  const topLevel = NAV_TOP_LEVEL_KEYS.map((k) => pick(k)).filter(Boolean) as MenuItem[];
  const categories = NAV_CATEGORY_DEFS.map((cat) => ({
    label: cat.label,
    items: cat.itemKeys.map((k) => pick(k)).filter(Boolean) as MenuItem[],
  })).filter((c) => c.items.length > 0);

  return { home, topLevel, categories };
}

/** 首页卡片副标题 */
export const MENU_SHORT_DESC: Record<string, string> = {
  cockpit: "M1–M7 摘要 · Excel 对照",
  project: "项目交付与风险摘要",
  crm_customers: "客户 360 · 子表穿透",
  crm_opportunities: "漏斗阶段 · 关联打样",
  crm_samples: "打样流程 · 环节子表",
  crm_reports: "漏斗 · 样品周报",
  ctp: "交期试算 · 品项数量产能池",
  changes: "影响清单 · PMC 审批",
  orders: "多视图 · 字段权限",
  kingdee: "Mock Push 进单",
  hr_roster: "员工档案 · 续签状态提醒",
  hr_attendance: "考勤机同步明细",
  hr_labor_cost: "计划 vs 实际 · 部门-组",
  schedule: "倒排看板 · 插单试排",
  labor_time_report: "班组长组×日 · 人·时",
  stock: "占库 · ERP Mock",
  bom: "工艺扇入 · 版盒换算",
  production: "计划版本 · 工单摘要",
  finance: "毛利预警 · 成本锁定",
  todos: "变更 · 排程池 · 打样/企微",
  demo: "九幕剧本 · 验收口径",
};

/** 与 packages/shared/auth.py MENU 对齐；API 失败时兜底 */
const MENU: MenuItem[] = [
  { key: "portal", label: "首页", path: "/portal", module: "M0" },
  { key: "todos", label: "待办中心", path: "/todos", module: "M0" },
  { key: "demo", label: "演示控制台", path: "/demo", module: "M0" },
  { key: "cockpit", label: "管理驾驶舱", path: "/cockpit", module: "M0" },
  { key: "crm_customers", label: "客户档案", path: "/crm/customers", module: "M2" },
  { key: "crm_opportunities", label: "商机列表", path: "/crm/opportunities", module: "M2" },
  { key: "crm_samples", label: "样品流程", path: "/crm/samples", module: "M2" },
  { key: "crm_reports", label: "销售报表", path: "/crm/reports", module: "M2" },
  { key: "ctp", label: "交期试算 CTP", path: "/crm/ctp", module: "M2" },
  { key: "changes", label: "订单变更", path: "/changes", module: "M3" },
  { key: "orders", label: "销售订单", path: "/orders", module: "M3" },
  { key: "kingdee", label: "金蝶同步", path: "/kingdee", module: "M3" },
  { key: "schedule", label: "生产排程", path: "/schedule", module: "M8" },
  { key: "stock", label: "库存中心", path: "/stock", module: "M4" },
  { key: "bom", label: "BOM 工艺", path: "/bom", module: "M4" },
  { key: "hr_roster", label: "花名册", path: "/modules/hr/roster", module: "M1" },
  { key: "hr_attendance", label: "考勤管理", path: "/modules/hr/attendance", module: "M1" },
  { key: "hr_labor_cost", label: "生产成本", path: "/modules/hr/labor-cost", module: "M1" },
  { key: "production", label: "生产运营", path: "/modules/production", module: "M5" },
  { key: "labor_time_report", label: "组×日报工", path: "/modules/production/time-report", module: "M5" },
  { key: "finance", label: "财务摘要", path: "/modules/finance", module: "M6" },
  { key: "project", label: "项目交付", path: "/modules/project", module: "M7" },
];

const ROLE_MENU_KEYS: Record<RoleCode, string[]> = {
  GM: MENU.map((m) => m.key),
  SALES_MGR: [
    "portal",
    "todos",
    "demo",
    "crm_customers",
    "crm_opportunities",
    "crm_samples",
    "crm_reports",
    "ctp",
    "changes",
    "orders",
  ],
  SALES: [
    "portal",
    "todos",
    "crm_customers",
    "crm_opportunities",
    "crm_samples",
    "ctp",
    "changes",
    "orders",
  ],
  PMC: [
    "portal",
    "todos",
    "demo",
    "changes",
    "orders",
    "kingdee",
    "schedule",
    "stock",
    "bom",
    "production",
    "labor_time_report",
    "hr_labor_cost",
  ],
  WH: ["portal", "todos", "orders", "kingdee", "stock"],
  FIN: ["portal", "todos", "cockpit", "orders", "finance", "hr_labor_cost"],
  HR: ["portal", "todos", "hr_roster", "hr_attendance", "hr_labor_cost"],
  TEAM_LEADER: ["portal", "todos", "labor_time_report", "schedule"],
};

export function fallbackMenuForRole(role: RoleCode): MenuItem[] {
  const keys = new Set(ROLE_MENU_KEYS[role] ?? ["portal"]);
  return MENU.filter((m) => keys.has(m.key));
}
