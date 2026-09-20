import type { RoleCode } from "./auth";

export type MenuItem = { key: string; label: string; path: string; module: string };

/** 首页 / 侧栏：待办、演示控制台为一级直达（不进五类） */
export const NAV_TOP_LEVEL_KEYS = ["todos", "demo"] as const;

/** 业务域 → 菜单 key（与 MENU 对齐） */
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
      "quotes",
      "kingdee",
    ],
  },
  { id: "hr", label: "人事", itemKeys: ["hr_roster", "hr_attendance", "hr_labor_cost"] },
  {
    id: "production",
    label: "生产",
    itemKeys: ["schedule", "stock", "bom", "production", "labor_time_report", "dept1_stats"],
  },
  { id: "finance", label: "财务", itemKeys: ["finance"] },
  {
    id: "qc",
    label: "品控",
    itemKeys: [
      "qc_receipts",
      "qc_exceptions",
      "qc_daily_defects",
      "qc_complaints",
      "qc_audits",
      "qc_lab_external",
      "qc_swab_tests",
      "qc_product_tests",
      "qc_master",
    ],
  },
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
  quotes: "产品报价表 · 转订单",
  kingdee: "Mock Push 进单 · 主数据同步",
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
  demo: "九幕剧本 · 排程/成本概念讲解",
  qc_receipts: "原辅料来料 · 编码主数据",
  qc_exceptions: "来料异常闭环",
  qc_daily_defects: "生产每日异常",
  qc_complaints: "客诉登记 · 整改跟踪",
  qc_audits: "二方/三方审核",
  qc_lab_external: "实验室外来测试",
  qc_swab_tests: "涂抹检测 · 合格线",
  qc_product_tests: "产品检测 · 合格线",
  qc_master: "供应商/原辅料 · 金蝶同步",
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
  { key: "quotes", label: "产品报价", path: "/orders/quotes", module: "M3" },
  { key: "kingdee", label: "金蝶同步", path: "/kingdee", module: "M3" },
  { key: "schedule", label: "生产排程", path: "/schedule", module: "M8" },
  { key: "stock", label: "库存中心", path: "/stock", module: "M4" },
  { key: "bom", label: "BOM 工艺", path: "/bom", module: "M4" },
  { key: "hr_roster", label: "花名册", path: "/modules/hr/roster", module: "M1" },
  { key: "hr_attendance", label: "考勤管理", path: "/modules/hr/attendance", module: "M1" },
  { key: "hr_labor_cost", label: "生产成本", path: "/modules/hr/labor-cost", module: "M1" },
  { key: "production", label: "生产运营", path: "/modules/production", module: "M5" },
  { key: "labor_time_report", label: "组×日报工", path: "/modules/production/time-report", module: "M5" },
  { key: "dept1_stats", label: "一部产能统计", path: "/modules/production/stats/dept1", module: "M5" },
  { key: "finance", label: "财务摘要", path: "/modules/finance", module: "M6" },
  { key: "project", label: "项目交付", path: "/modules/project", module: "M7" },
  { key: "qc_receipts", label: "原辅料来料", path: "/qc/receipts", module: "M9" },
  { key: "qc_exceptions", label: "原辅料异常", path: "/qc/exceptions", module: "M9" },
  { key: "qc_daily_defects", label: "每日异常", path: "/qc/daily-defects", module: "M9" },
  { key: "qc_complaints", label: "客诉登记", path: "/qc/complaints", module: "M9" },
  { key: "qc_audits", label: "二方三方审核", path: "/qc/audits", module: "M9" },
  { key: "qc_lab_external", label: "外来测试", path: "/qc/lab-external", module: "M9" },
  { key: "qc_swab_tests", label: "涂抹检测", path: "/qc/swab-tests", module: "M9" },
  { key: "qc_product_tests", label: "产品检测", path: "/qc/product-tests", module: "M9" },
  { key: "qc_master", label: "品控主数据", path: "/qc/master", module: "M9" },
];

const QC_KEYS = [
  "portal",
  "todos",
  "qc_receipts",
  "qc_exceptions",
  "qc_daily_defects",
  "qc_complaints",
  "qc_audits",
  "qc_lab_external",
  "qc_swab_tests",
  "qc_product_tests",
  "qc_master",
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
    "quotes",
    "qc_complaints",
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
    "quotes",
    "qc_complaints",
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
    "dept1_stats",
    "hr_labor_cost",
    "qc_daily_defects",
  ],
  WH: ["portal", "todos", "orders", "kingdee", "stock", "dept1_stats", "qc_receipts", "qc_exceptions", "qc_master"],
  FIN: ["portal", "todos", "cockpit", "orders", "quotes", "finance", "hr_labor_cost", "dept1_stats"],
  HR: ["portal", "todos", "hr_roster", "hr_attendance", "hr_labor_cost", "dept1_stats"],
  TEAM_LEADER: ["portal", "todos", "labor_time_report", "dept1_stats", "schedule"],
  QC: QC_KEYS,
};

export function fallbackMenuForRole(role: RoleCode): MenuItem[] {
  const keys = new Set(ROLE_MENU_KEYS[role] ?? ["portal"]);
  return MENU.filter((m) => keys.has(m.key));
}
