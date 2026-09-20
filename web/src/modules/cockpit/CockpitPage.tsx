import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { requestWithRole } from "../../api/client";
import { useAuth } from "../../shell/auth";

type CockpitSnapshot = {
  today?: string;
  orders?: {
    total?: number;
    pending?: number;
    in_scheduling?: number;
    near_due_7d?: number;
  };
  crm?: { opportunities?: number; active_samples?: number };
  production?: { plan_version?: number; wo_count?: number };
  labor_cost?: {
    plan_version?: number;
    totals?: { hours_man?: number; cost_planned?: number };
    top_products?: { item_code: string; cost_planned: number; hours_man_planned: number }[];
    note?: string;
  };
  qc?: {
    receipts_mtd?: number;
    exceptions_open?: number;
    complaints_open?: number;
    swab_fail_mtd?: number;
    product_fail_mtd?: number;
  };
  legacy_excel_sheets?: number;
  note?: string;
};

const FALLBACK_SNAPSHOT: CockpitSnapshot = {
  today: "2026-09-15",
  orders: { total: 12, pending: 8, in_scheduling: 3, near_due_7d: 6 },
  crm: { opportunities: 24, active_samples: 7 },
  production: { plan_version: 0, wo_count: 0 },
  legacy_excel_sheets: 20,
  note: "离线兜底：请确认后端 http://127.0.0.1:8000 已启动并已登录角色",
};

function StatCard({
  label,
  value,
  hint,
  to,
}: {
  label: string;
  value: string | number;
  hint?: string;
  to?: string;
}) {
  const body = (
    <>
      <p className="text-xs text-[var(--text-muted)]">{label}</p>
      <p className="mt-1 text-2xl font-semibold tabular-nums">{value}</p>
      {hint && <p className="mt-1 text-[10px] text-[var(--text-muted)]">{hint}</p>}
      {to && (
        <p className="mt-2 text-[10px] text-[var(--accent)] opacity-80 group-hover:opacity-100">
          查看列表 →
        </p>
      )}
    </>
  );
  const className =
    "group rounded-lg border p-4 transition " +
    (to ? "cursor-pointer hover:border-[var(--accent)] hover:shadow-sm " : "");
  const style = { borderColor: "var(--line)", background: "var(--bg-card)" };
  if (to) {
    return (
      <Link to={to} className={className} style={style}>
        {body}
      </Link>
    );
  }
  return (
    <div className={className} style={style}>
      {body}
    </div>
  );
}

export function CockpitPage() {
  const auth = useAuth();
  const role = auth.role;
  const [snap, setSnap] = useState<CockpitSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [usingFallback, setUsingFallback] = useState(false);

  const load = useCallback(() => {
    if (!role) return;
    setError(null);
    setUsingFallback(false);
    requestWithRole<CockpitSnapshot>("/api/cockpit/snapshot", role)
      .then((data) => {
        setSnap(data);
      })
      .catch((e) => {
        setSnap(FALLBACK_SNAPSHOT);
        setUsingFallback(true);
        setError(String(e));
      });
  }, [role]);

  useEffect(() => {
    setSnap(null);
    load();
  }, [load]);

  const sheets = snap?.legacy_excel_sheets ?? 20;
  const orders = snap?.orders ?? {};
  const crm = snap?.crm ?? {};
  const prod = snap?.production ?? {};
  const labor = snap?.labor_cost ?? {};
  const qc = snap?.qc ?? {};

  return (
    <div className="px-6 py-4">
      <h2 className="text-lg font-semibold">管理驾驶舱</h2>
      <p className="text-xs text-[var(--text-muted)]">
        Excel 一表三用（{sheets} Sheet）→ 一体化对照 · 基准日 {snap?.today ?? "—"}
      </p>

      {snap === null && (
        <p className="mt-6 text-sm text-[var(--text-muted)]">加载驾驶舱指标…</p>
      )}

      {error && (
        <div className="mt-3 rounded border border-amber-800/60 bg-amber-950/40 px-3 py-2 text-xs text-amber-100">
          {usingFallback ? "接口未就绪，以下为演示兜底数据。" : "加载失败。"} {error}
          <button type="button" className="ml-2 underline" onClick={() => load()}>
            重试
          </button>
        </div>
      )}

      {snap && (
        <>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard
              label="销售订单总数"
              value={orders.total ?? "—"}
              hint="含待排产池"
              to="/orders?view=all"
            />
            <StatCard
              label="待排产"
              value={orders.pending ?? "—"}
              to="/orders?view=pending"
            />
            <StatCard
              label="排程池中"
              value={orders.in_scheduling ?? "—"}
              to="/orders?view=in_scheduling"
            />
            <StatCard
              label="7 日内交期"
              value={orders.near_due_7d ?? "—"}
              to="/orders?view=near_due"
            />
            <StatCard
              label="CRM 商机"
              value={crm.opportunities ?? "—"}
              to="/crm/opportunities"
            />
            <StatCard
              label="在途打样"
              value={crm.active_samples ?? "—"}
              to="/crm/samples?active=1"
            />
            <StatCard
              label="计划版本"
              value={prod.plan_version != null ? `v${prod.plan_version}` : "—"}
              hint={prod.plan_version === 0 ? "尚未发布倒排计划" : undefined}
            />
            <StatCard label="已发布工单" value={prod.wo_count ?? "—"} />
            <StatCard
              label="当月来料批次数"
              value={qc.receipts_mtd ?? "—"}
              to="/qc/receipts"
            />
            <StatCard
              label="开放来料异常"
              value={qc.exceptions_open ?? "—"}
              to="/qc/exceptions"
            />
            <StatCard
              label="开放客诉"
              value={qc.complaints_open ?? "—"}
              to="/qc/complaints"
            />
            <StatCard
              label="计划人工成本"
              value={
                labor.totals?.cost_planned != null
                  ? `¥${Math.round(labor.totals.cost_planned)}`
                  : "—"
              }
              hint={
                labor.totals?.hours_man
                  ? `${labor.totals.hours_man.toFixed(0)} 人·时`
                  : "需先发布倒排计划"
              }
              to="/modules/hr/labor-cost"
            />
          </div>
          {labor.top_products && labor.top_products.length > 0 && (
            <div className="mt-4 rounded-lg border p-4" style={{ borderColor: "var(--line)", background: "var(--bg-card)" }}>
              <p className="text-xs font-medium text-[var(--text-muted)]">量产品项计划人工成本 Top</p>
              <ul className="mt-2 space-y-1 text-sm">
                {labor.top_products.map((p) => (
                  <li key={p.item_code} className="flex justify-between gap-4 tabular-nums">
                    <span>{p.item_code}</span>
                    <span>
                      ¥{p.cost_planned.toFixed(0)} · {p.hours_man_planned.toFixed(1)} 人·时
                    </span>
                  </li>
                ))}
              </ul>
              {labor.note && (
                <p className="mt-2 text-[10px] text-[var(--text-muted)]">{labor.note}</p>
              )}
            </div>
          )}
          {snap.note && (
            <p className="mt-4 text-xs text-[var(--text-muted)]">{snap.note}</p>
          )}
        </>
      )}

      <div className="mt-6 flex flex-wrap gap-3 text-sm">
        <Link to="/modules/hr/roster" className="text-[var(--accent)] underline">
          人事 M1
        </Link>
        <Link to="/modules/production" className="text-[var(--accent)] underline">
          生产 M5
        </Link>
        <Link to="/modules/finance" className="text-[var(--accent)] underline">
          财务 M6
        </Link>
        <Link to="/modules/project" className="text-[var(--accent)] underline">
          项目 M7
        </Link>
        <Link to="/demo" className="text-[var(--accent)] underline">
          九幕演示控制台
        </Link>
      </div>
    </div>
  );
}

export function ModuleSummaryPage({
  module,
}: {
  module: "hr" | "production" | "finance" | "project";
}) {
  const auth = useAuth();
  const role = auth.role;
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!role) return;
    setData(null);
    setError(null);
    requestWithRole<Record<string, unknown>>(`/api/modules/${module}/summary`, role)
      .then(setData)
      .catch((e) => setError(String(e)));
  }, [role, module]);

  const titles = { hr: "人事", production: "生产运营", finance: "财务", project: "项目" };

  return (
    <div className="px-6 py-4">
      <h2 className="text-lg font-semibold">{titles[module]}</h2>
      {data === null && !error && (
        <p className="mt-3 text-sm text-[var(--text-muted)]">加载中…</p>
      )}
      {error && (
        <p className="mt-3 text-sm text-rose-400">
          加载失败：{error}（请确认后端已启动并已登录）
        </p>
      )}
      {data && (
        <dl className="mt-4 grid max-w-md gap-2 text-sm">
          {Object.entries(data)
            .filter(([k]) => k !== "note")
            .map(([k, v]) => (
              <div key={k} className="flex justify-between gap-4 border-b border-[var(--line)] py-1">
                <dt className="text-[var(--text-muted)]">{k}</dt>
                <dd className="font-medium tabular-nums">{String(v)}</dd>
              </div>
            ))}
        </dl>
      )}
      {data?.note != null && (
        <p className="mt-3 text-xs text-[var(--text-muted)]">{String(data.note)}</p>
      )}
    </div>
  );
}
