import type { BomCatalog, BomDesign, BomExplode } from "../types/bom";
import type { KitAllocation, KitCheck } from "../types/kit";
import type {
  ApiResponse,
  OrderRow,
  ScheduleResult,
} from "../types/schedule";

export type StockItem = {
  item_code: string;
  item_name: string;
  qty_available: number;
  uom_display: string;
  source: string;
  warehouse_code?: string | null;
  updated_at?: string | null;
};

async function request<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });
  const raw = await res.text();
  if (!res.ok) {
    let detail = raw.slice(0, 400);
    try {
      const j = JSON.parse(raw) as { message?: string; detail?: string | unknown };
      if (j.message) detail = j.message;
      else if (j.detail !== undefined) {
        detail =
          typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
      }
    } catch {
      /* not json */
    }
    const backendHint =
      ".venv/bin/python -m uvicorn api.app_factory:app --host 127.0.0.1 --port 8000";
    if (res.status === 404 && path.startsWith("/api/bom")) {
      throw new Error(
        `BOM 接口不可用（后端可能未重启）。请在本项目根目录执行：${backendHint}`,
      );
    }
    if (res.status === 404 && path.includes("/api/schedule/interactive-preview")) {
      throw new Error(
        `拖拽试算接口不可用（后端需重启以加载新路由）。请执行：${backendHint}`,
      );
    }
    if (res.status === 404 && path.includes("/api/plan/cell-detail")) {
      throw new Error(
        `格子/任务详情接口不可用（后端需重启以加载新路由）。请在本项目根目录执行：${backendHint}`,
      );
    }
    if (
      res.status === 405 &&
      (path.includes("/api/orders/scheduling-pool") ||
        path.includes("/api/orders/publish"))
    ) {
      throw new Error(
        `加入/移出排程接口未加载（后端进程过旧，POST 被当成改订单）。请重启后端：${backendHint}`,
      );
    }
    if ((res.status === 500 || res.status === 502 || res.status === 503) && !raw.trim()) {
      detail = `无法连接后端 API（请先启动：${backendHint} 或 ./scripts/start.sh）`;
    }
    throw new Error(detail || `${res.status} ${res.statusText}`);
  }
  if (!raw.trim()) {
    throw new Error(
      "无法连接后端 API（请先启动：./scripts/start.sh，端口 8000）",
    );
  }
  let body: ApiResponse<T>;
  try {
    body = JSON.parse(raw) as ApiResponse<T>;
  } catch {
    throw new Error(`接口返回非 JSON：${raw.slice(0, 120)}`);
  }
  if (body.code !== 0) {
    throw new Error(body.message || "API error");
  }
  return body.data;
}

export function requestWithRole<T>(
  path: string,
  role: string,
  init?: RequestInit,
): Promise<T> {
  return request<T>(path, {
    ...init,
    headers: { "X-Demo-Role": role, ...init?.headers },
  });
}

export async function checkApiHealth(): Promise<boolean> {
  try {
    const data = await request<{ status?: string }>("/api/health");
    return data.status === "ok";
  } catch {
    return false;
  }
}

export type OrdersPayload = {
  orders: OrderRow[];
  orders_in_db?: number;
  db_file?: string;
  seed_sync?: { order_count: number };
};

export async function fetchOrders(): Promise<OrderRow[]> {
  const data = await request<OrdersPayload>("/api/orders");
  return data.orders;
}

export async function fetchOrdersDetailed(): Promise<OrdersPayload> {
  return request<OrdersPayload>("/api/orders");
}

export async function fetchSeedStatus(): Promise<{
  order_count: number;
  orders_in_db: number;
  needs_reload: boolean;
  db_file: string;
}> {
  return request("/api/dev/seed-status");
}

export async function reloadDemoSeed(): Promise<{
  order_count: number;
  orders_in_db: number;
  db_file: string;
}> {
  return request("/api/dev/import-seed", { method: "POST", body: "{}" });
}

export async function patchOrderDue(
  orderNo: string,
  dueDate: string,
): Promise<void> {
  await request(`/api/orders/${encodeURIComponent(orderNo)}`, {
    method: "PATCH",
    body: JSON.stringify({ due_date: dueDate }),
  });
}

export async function updateSchedulingPool(
  action: "add" | "remove",
  orderNos: string[],
): Promise<{ pool: string[] }> {
  return request("/api/orders/scheduling-pool", {
    method: "POST",
    body: JSON.stringify({ action, order_nos: orderNos }),
  });
}

export type PublishPoolSuccess = {
  published: true;
  plan_version: number;
  commitments: import("../utils/orderCommitments").OrderCommitment[];
  result: ScheduleResult;
};

export type PublishPoolBlocked = {
  published: false;
  blocks: { order_no: string; code: string; message: string }[];
  commitments: import("../utils/orderCommitments").OrderCommitment[];
  result: ScheduleResult;
};

export async function publishSchedulingPool(body: {
  today: string;
  order_nos?: string[];
  force_red?: boolean;
}): Promise<PublishPoolSuccess | PublishPoolBlocked> {
  const res = await fetch("/api/orders/publish", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      today: body.today,
      order_nos: body.order_nos,
      force_red: body.force_red ?? false,
      reserved_ratio: 0,
    }),
  });
  const raw = await res.text();
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    throw new Error(raw.slice(0, 400) || `${res.status} ${res.statusText}`);
  }
  if (res.status === 409) {
    const detail = (parsed as { detail?: PublishPoolBlocked }).detail;
    if (detail && detail.published === false) return detail;
    throw new Error(
      typeof detail === "string" ? detail : "发布被 E1/E2 阻断",
    );
  }
  if (!res.ok) {
    throw new Error(
      typeof (parsed as { message?: string }).message === "string"
        ? (parsed as { message: string }).message
        : raw.slice(0, 400),
    );
  }
  const bodyWrap = parsed as ApiResponse<PublishPoolSuccess>;
  if (bodyWrap.code !== 0) {
    throw new Error(bodyWrap.message || "API error");
  }
  return bodyWrap.data;
}

export async function scheduleRun(
  orderNos: string[],
  today: string,
): Promise<{ plan_version: number; result: ScheduleResult }> {
  return request("/api/schedule/run", {
    method: "POST",
    body: JSON.stringify({
      order_nos: orderNos,
      today,
      reserved_ratio: 0,
    }),
  });
}

export async function scheduleWhatIf(
  orderNos: string[],
  today: string,
): Promise<{ plan_version: number; result: ScheduleResult }> {
  return request("/api/schedule/what-if", {
    method: "POST",
    body: JSON.stringify({
      order_nos: orderNos,
      today,
      reserved_ratio: 0,
    }),
  });
}

export async function scheduleApply(
  orderNos: string[],
  today: string,
): Promise<{ plan_version: number; result: ScheduleResult }> {
  return request("/api/schedule/apply", {
    method: "POST",
    body: JSON.stringify({
      order_nos: orderNos,
      today,
      reserved_ratio: 0,
    }),
  });
}

export async function fetchStock(): Promise<{
  items: StockItem[];
  db_file?: string;
  provider_note?: string;
}> {
  return request("/api/stock");
}

export async function patchStockQty(
  itemCode: string,
  qty: number,
): Promise<StockItem> {
  return request(`/api/stock/${encodeURIComponent(itemCode)}`, {
    method: "PATCH",
    body: JSON.stringify({ qty_available: qty }),
  });
}

export async function syncStockErpMock(
  mode: "merge" | "replace" = "merge",
): Promise<{ synced: number; as_of: string }> {
  return request(`/api/stock/sync-erp-mock?mode=${mode}`, { method: "POST", body: "{}" });
}

export async function fetchPlanKitStatus(version?: number): Promise<{
  plan_version: number;
  kit_checks: KitCheck[];
  kit_allocations: KitAllocation[];
}> {
  const q = version ? `?version=${version}` : "";
  return request(`/api/plan/kit-status${q}`);
}

export async function fetchCellDetail(body: {
  today: string;
  dept?: string;
  group_code: string;
  task_date: string;
  focus_task_id?: number;
  plan_version?: number;
  tasks?: ScheduleResult["tasks"];
}): Promise<{
  group_code: string;
  task_date: string;
  focus_task_id: number | null;
  is_workday: boolean;
  headcount: number;
  orders: {
    order_no: string;
    customer: string;
    sales_name?: string;
    item_code: string;
    wo_nos: string[];
    qty_board_in_cell: number;
  }[];
  tasks: {
    task_id: number;
    wo_no: string;
    source_order_no: string;
    item_code: string;
    qty_board: number;
    hours_wall: string;
    hours_man: string;
    crew_plan: number;
  }[];
  cell_metrics: Record<string, string>;
  task_metrics: Record<string, string> | null;
}> {
  return request("/api/plan/cell-detail", {
    method: "POST",
    body: JSON.stringify({ ...body, reserved_ratio: 0 }),
  });
}

export async function fetchPlan(
  version?: number,
): Promise<{ plan_version: number; result: ScheduleResult }> {
  const q = version ? `?version=${version}` : "";
  return request(`/api/plan${q}`);
}

export async function fetchConflicts(version?: number): Promise<{
  plan_version: number;
  conflicts: ScheduleResult["conflicts"];
}> {
  const q = version ? `?version=${version}` : "";
  return request(`/api/conflicts${q}`);
}

export async function interactivePreview(body: {
  today: string;
  order_nos: string[];
  baseline_wos: ScheduleResult["wos"];
  baseline_tasks: ScheduleResult["tasks"];
  proposed_wos: ScheduleResult["wos"];
  proposed_tasks: ScheduleResult["tasks"];
  trigger_task_id?: number;
}): Promise<{
  baseline: ScheduleResult;
  result: ScheduleResult;
  diff: { summary_text: string; entries: { change_type: string; wo_no: string; message: string }[] };
  conflicts: ScheduleResult["conflicts"];
  headcount_warnings: { code: string; level: string; message: string }[];
  order_impacts: import("../components/AdjustImpactModal").OrderImpact[];
  trigger_order_no: string | null;
}> {
  return request("/api/schedule/interactive-preview", {
    method: "POST",
    body: JSON.stringify({ ...body, reserved_ratio: 0 }),
  });
}

export async function fetchBomCatalog(): Promise<BomCatalog> {
  return request("/api/bom");
}

export async function fetchBomDesign(itemCode: string): Promise<BomDesign> {
  return request(`/api/bom/${encodeURIComponent(itemCode)}`);
}

export async function fetchBomExplode(
  itemCode: string,
  qty: number,
  unit: string,
  today?: string,
): Promise<BomExplode> {
  const params = new URLSearchParams({
    item_code: itemCode,
    qty: String(qty),
    unit,
  });
  if (today) params.set("today", today);
  return request(`/api/bom/explode?${params}`);
}
