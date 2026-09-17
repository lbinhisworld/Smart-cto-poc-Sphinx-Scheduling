export type ConflictLevel = "RED" | "YELLOW" | "GREY" | "BLUE";

export type BomRouteSummary = {
  item_code: string;
  item_name: string;
  finished_group: string;
  finished_group_label: string;
  needs_semi: boolean;
  semi_item_code: string | null;
  lead_time_days: number | null;
  summary_text: string;
};

export type SchedulePhase =
  | "PENDING"
  | "IN_SCHEDULING"
  | "IN_PRODUCTION"
  | "COMPLETED";

export type OrderRow = {
  order_no: string;
  customer: string;
  sales_name: string;
  item_code: string;
  qty_order: number;
  unit: string;
  due_date: string;
  ready_date: string | null;
  customer_level: number;
  amount: number;
  is_urgent: boolean;
  schedule_phase?: SchedulePhase;
  bom_route?: BomRouteSummary | null;
};

export type Wo = {
  wo_no: string;
  wo_type: string;
  source_order_no: string;
  item_code: string;
  group_code: string;
  qty_board_plan: number;
  due_date: string;
  plan_start?: string | null;
  plan_end?: string | null;
  crew_plan: number;
  is_locked: boolean;
  parent_wo_no: string | null;
};

export type WoTask = {
  task_id: number;
  wo_no: string;
  dept?: string;
  group_code: string;
  task_date: string;
  qty_board: number;
  hours_wall: number | string;
  hours_man: number | string;
  crew_plan: number;
};

export type Conflict = {
  code: string;
  level: ConflictLevel;
  wo_no: string | null;
  task_id: number | null;
  message: string;
  suggest: string | null;
  dept?: string | null;
  group_code?: string | null;
  cell_date?: string | null;
  hours_wall_total?: number | string | null;
  hours_wall_limit?: number | string | null;
};

export type TraceAct = "EXPAND" | "QUEUE" | "PLACE" | "SEMI" | "CHECK";

export type TraceEvent = {
  act: TraceAct;
  kind: string;
  message: string;
  order_no?: string | null;
  wo_no?: string | null;
  wo_type?: string | null;
  item_code?: string | null;
  dept?: string | null;
  group_code?: string | null;
  task_date?: string | null;
  task_id?: number | null;
  qty_board?: number | null;
  remaining_after?: number | null;
  cap_board?: number | null;
  occupied_before?: number | null;
  free_before?: number | null;
  rank?: number | null;
  due_date?: string | null;
  skip_reason?: string | null;
};

export type ScheduleTrace = {
  sort_mode: string;
  events: TraceEvent[];
};

export type ColineGroup = {
  dept: string;
  group_code: string;
  task_date: string;
  item_code: string;
  wo_type: string;
  order_nos: string[];
  qty_board: number;
  wo_nos: string[];
};

export type ColineSummary = {
  point_count: number;
  qty_board_total: number;
  order_count: number;
  sku_count: number;
};

export type LotSummary = {
  point_count: number;
  qty_board_total: number;
};

export type ScheduleResult = {
  wos: Wo[];
  tasks: WoTask[];
  dependencies: { pred_wo_no: string; succ_wo_no: string }[];
  conflicts: Conflict[];
  kit_checks?: import("./kit").KitCheck[];
  kit_allocations?: import("./kit").KitAllocation[];
  coline_groups?: ColineGroup[];
  coline_summary?: ColineSummary;
  lot_summary?: LotSummary;
  trace?: ScheduleTrace | null;
};

export type ApiResponse<T> = {
  code: number;
  data: T;
  message: string;
};
