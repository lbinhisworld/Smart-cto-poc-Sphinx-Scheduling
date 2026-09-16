import { useEffect, useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { useAuth } from "../../shell/auth";
import { renderMoney, renderOppStageTag, renderSampleStageTag } from "../../ui/cellRenderers";
import { Customer360Drawer } from "./Customer360Drawer";
import { OpportunityDetailDrawer } from "./OpportunityDetailDrawer";
import { SampleDetailDrawer } from "./SampleDetailDrawer";

function useFetch<T>(url: string): { data: T | null; error: string | null } {
  const auth = useAuth();
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    fetch(url, { headers: auth.headers() })
      .then((r) => r.json())
      .then((j) => setData(j.data))
      .catch((e) => setError(String(e)));
  }, [url, auth]);
  return { data, error };
}

type CustomerMetrics = {
  customer_count: number;
  channel_distribution: { label: string; count: number }[];
  level_distribution: { label: string; count: number }[];
  received_total: number;
  pending_total: number;
};

function CustomerListMetrics({ metrics }: { metrics: CustomerMetrics }) {
  const chMax = Math.max(...metrics.channel_distribution.map((x) => x.count), 1);
  const lvMax = Math.max(...metrics.level_distribution.map((x) => x.count), 1);
  return (
    <div className="mt-4 space-y-3">
      <div className="grid gap-3 lg:grid-cols-4">
        <div className="rounded-lg border p-4" style={{ borderColor: "var(--line)", background: "var(--bg-card)" }}>
          <p className="text-xs text-[var(--text-muted)]">客户数</p>
          <p className="mt-1 text-2xl font-semibold tabular-nums">{metrics.customer_count}</p>
        </div>
        <div className="rounded-lg border p-4" style={{ borderColor: "var(--line)", background: "var(--bg-card)" }}>
          <p className="text-xs text-[var(--text-muted)]">已收款（合同口径）</p>
          <p className="mt-1 text-2xl font-semibold">{renderMoney(metrics.received_total)}</p>
        </div>
        <div className="rounded-lg border p-4 lg:col-span-2" style={{ borderColor: "var(--line)", background: "var(--bg-card)" }}>
          <p className="text-xs text-[var(--text-muted)]">待收款</p>
          <p className="mt-1 text-2xl font-semibold">{renderMoney(metrics.pending_total)}</p>
        </div>
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        <div className="rounded-lg border p-4" style={{ borderColor: "var(--line)", background: "var(--bg-card)" }}>
          <p className="text-xs font-medium text-[var(--text-muted)]">渠道分布</p>
          <div className="mt-3 space-y-2">
            {metrics.channel_distribution.map((x) => (
              <div key={x.label} className="flex items-center gap-2 text-xs">
                <span className="w-16 shrink-0">{x.label}</span>
                <div className="h-2 flex-1 rounded bg-slate-800">
                  <div className="h-2 rounded bg-[var(--accent)]" style={{ width: `${(x.count / chMax) * 100}%` }} />
                </div>
                <span className="tabular-nums">{x.count}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="rounded-lg border p-4" style={{ borderColor: "var(--line)", background: "var(--bg-card)" }}>
          <p className="text-xs font-medium text-[var(--text-muted)]">级别分布</p>
          <div className="mt-3 space-y-2">
            {metrics.level_distribution.map((x) => (
              <div key={x.label} className="flex items-center gap-2 text-xs">
                <span className="w-10 shrink-0">{x.label}</span>
                <div className="h-2 flex-1 rounded bg-slate-800">
                  <div className="h-2 rounded bg-emerald-500/80" style={{ width: `${(x.count / lvMax) * 100}%` }} />
                </div>
                <span className="tabular-nums">{x.count}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

export function CrmCustomersPage() {
  const params = useParams<{ code?: string }>();
  const { data, error } = useFetch<{ code: string; name: string; owner_sales: string; duplicate_flag: boolean }[]>(
    "/api/crm/customers",
  );
  const { data: metrics } = useFetch<CustomerMetrics>("/api/crm/customers/metrics");
  const [detail, setDetail] = useState<string | null>(params.code ?? null);

  useEffect(() => {
    if (params.code) setDetail(params.code);
  }, [params.code]);

  return (
    <div className="px-6 py-4">
      <h2 className="text-lg font-semibold">客户档案</h2>
      <p className="text-xs text-[var(--text-muted)]">点击客户打开 360 侧滑 · 合同/订单/回款可穿透详情并返回</p>
      {error && <p className="mt-2 text-xs text-rose-400">{error}</p>}
      {metrics && <CustomerListMetrics metrics={metrics} />}
      <div className="mt-4 overflow-x-auto rounded-lg border" style={{ borderColor: "var(--line)" }}>
        <table className="w-full text-xs">
          <thead className="bg-[var(--table-head)] text-[var(--text-muted)]">
            <tr>
              <th className="px-3 py-2 text-left">编码</th>
              <th className="text-left">名称</th>
              <th className="text-left">销售</th>
              <th className="text-left">操作</th>
            </tr>
          </thead>
          <tbody>
            {(data ?? []).map((c) => (
              <tr key={c.code} className="border-t" style={{ borderColor: "var(--line)" }}>
                <td className="px-3 py-2 font-mono">{c.code}</td>
                <td>
                  {c.name}
                  {c.duplicate_flag && <span className="ml-1 text-amber-400">疑似重复</span>}
                </td>
                <td>{c.owner_sales}</td>
                <td>
                  <button
                    type="button"
                    className="text-[var(--accent)] hover:underline"
                    onClick={() => setDetail(c.code)}
                  >
                    360 详情
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Customer360Drawer customerCode={detail} onClose={() => setDetail(null)} />
    </div>
  );
}

type OpportunityListRow = {
  id: number;
  name: string;
  customer_code: string;
  customer_name: string;
  stage: string;
  amount: number;
  sales_name: string;
  owner_sales: string;
  expect_close_date: string | null;
  sample_code: string | null;
};

const OPP_PIPELINE = ["线索", "商机", "方案", "报价", "谈判", "成交"] as const;

function OpportunityStageMetrics({ rows }: { rows: OpportunityListRow[] }) {
  const total = rows.length;
  const counts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const st of OPP_PIPELINE) c[st] = 0;
    for (const r of rows) {
      c[r.stage] = (c[r.stage] ?? 0) + 1;
    }
    return c;
  }, [rows]);
  const max = useMemo(() => Math.max(...OPP_PIPELINE.map((st) => counts[st] ?? 0), 1), [counts]);

  return (
    <div className="mt-4 grid gap-3 lg:grid-cols-[minmax(140px,180px)_1fr]" aria-label="商机漏斗阶段指标">
      <div className="rounded-lg border p-4" style={{ borderColor: "var(--line)", background: "var(--bg-card)" }}>
        <p className="text-xs text-[var(--text-muted)]">商机总数</p>
        <p className="mt-1 text-3xl font-semibold tabular-nums">{total}</p>
        <p className="mt-1 text-[10px] text-[var(--text-muted)]">与下方列表口径一致</p>
      </div>
      <div className="rounded-lg border p-4" style={{ borderColor: "var(--line)", background: "var(--bg-card)" }}>
        <p className="text-xs font-medium text-[var(--text-muted)]">各阶段商机数</p>
        <div className="mt-3 grid gap-3 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-6">
          {OPP_PIPELINE.map((st) => {
            const n = counts[st] ?? 0;
            const pct = max > 0 ? Math.round((n / max) * 100) : 0;
            return (
              <div key={st} className="flex flex-col gap-1.5">
                <div className="flex items-center justify-between gap-2">
                  {renderOppStageTag(st)}
                  <span className="text-lg font-semibold tabular-nums">{n}</span>
                </div>
                <div className="h-2 overflow-hidden rounded-md bg-[var(--line)]">
                  <div
                    className="h-full rounded-md bg-[var(--accent)] transition-all"
                    style={{ width: `${pct}%`, minWidth: n > 0 ? "4px" : 0 }}
                    title={`${st}：${n}`}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export function CrmOpportunitiesPage() {
  const params = useParams<{ id?: string }>();
  const { data, error } = useFetch<OpportunityListRow[]>("/api/crm/opportunities");
  const rows = useMemo(() => data ?? [], [data]);
  const [detailId, setDetailId] = useState<number | null>(() => {
    const n = params.id ? Number(params.id) : NaN;
    return Number.isFinite(n) ? n : null;
  });

  useEffect(() => {
    const n = params.id ? Number(params.id) : NaN;
    if (Number.isFinite(n)) setDetailId(n);
  }, [params.id]);

  return (
    <div className="px-6 py-4">
      <h2 className="text-lg font-semibold">商机列表</h2>
      <p className="text-xs text-[var(--text-muted)]">点击行打开侧滑详情 · 可查看关联打样过程</p>
      {error && <p className="mt-2 text-xs text-rose-400">{error}</p>}
      <OpportunityStageMetrics rows={rows} />
      <div className="mt-4 overflow-x-auto rounded-lg border" style={{ borderColor: "var(--line)" }}>
        <table className="w-full min-w-[980px] border-collapse text-xs">
          <thead className="bg-[var(--table-head)] text-[var(--text-muted)]">
            <tr>
              <th className="px-3 py-2 text-left">商机</th>
              <th className="whitespace-nowrap px-3 py-2 text-left">客户编号</th>
              <th className="min-w-[140px] px-3 py-2 text-left">客户名称</th>
              <th className="whitespace-nowrap px-3 py-2 text-left">阶段</th>
              <th className="whitespace-nowrap px-3 py-2 text-right">金额</th>
              <th className="whitespace-nowrap px-3 py-2 text-left">销售</th>
              <th className="whitespace-nowrap px-3 py-2 text-left">预计成交</th>
              <th className="whitespace-nowrap px-3 py-2 text-left">打样</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((o) => (
              <tr
                key={o.id}
                className="cursor-pointer border-t hover:bg-[var(--table-row-hover)]"
                style={{ borderColor: "var(--line)" }}
                onClick={() => setDetailId(o.id)}
              >
                <td className="max-w-[200px] px-3 py-2 font-medium text-[var(--accent)]">{o.name}</td>
                <td className="whitespace-nowrap px-3 py-2 font-mono text-[var(--text-muted)]">
                  {o.customer_code}
                </td>
                <td className="px-3 py-2">{o.customer_name}</td>
                <td className="whitespace-nowrap px-3 py-2">{renderOppStageTag(o.stage)}</td>
                <td className="whitespace-nowrap px-3 py-2 text-right">{renderMoney(o.amount)}</td>
                <td className="whitespace-nowrap px-3 py-2">{o.sales_name || o.owner_sales}</td>
                <td className="whitespace-nowrap px-3 py-2 tabular-nums">{o.expect_close_date ?? "—"}</td>
                <td className="whitespace-nowrap px-3 py-2 font-mono text-[var(--text-muted)]">
                  {o.sample_code ?? "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <OpportunityDetailDrawer oppId={detailId} onClose={() => setDetailId(null)} />
    </div>
  );
}

type SampleListRow = {
  code: string;
  customer_code: string;
  customer_name: string;
  item_draft_name: string;
  current_stage: string;
  owner_sales: string;
  due_date: string | null;
};

const SAMPLE_PIPELINE = ["申请", "打样", "寄样", "客户反馈", "结案"] as const;

function SampleStageMetrics({ rows, activeOnly }: { rows: SampleListRow[]; activeOnly: boolean }) {
  const total = rows.length;
  const counts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const st of SAMPLE_PIPELINE) c[st] = 0;
    for (const r of rows) {
      const key = r.current_stage;
      c[key] = (c[key] ?? 0) + 1;
    }
    return c;
  }, [rows]);
  const max = useMemo(() => Math.max(...SAMPLE_PIPELINE.map((st) => counts[st] ?? 0), 1), [counts]);

  return (
    <div
      className="mt-4 grid gap-3 lg:grid-cols-[minmax(140px,180px)_1fr]"
      aria-label="打样流程阶段指标"
    >
      <div className="rounded-lg border p-4" style={{ borderColor: "var(--line)", background: "var(--bg-card)" }}>
        <p className="text-xs text-[var(--text-muted)]">{activeOnly ? "在途打样总数" : "打样流程总数"}</p>
        <p className="mt-1 text-3xl font-semibold tabular-nums">{total}</p>
        <p className="mt-1 text-[10px] text-[var(--text-muted)]">与下方列表口径一致</p>
      </div>
      <div className="rounded-lg border p-4" style={{ borderColor: "var(--line)", background: "var(--bg-card)" }}>
        <p className="text-xs font-medium text-[var(--text-muted)]">各阶段样品数</p>
        <div className="mt-3 grid gap-3 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-5">
          {SAMPLE_PIPELINE.map((st) => {
            const n = counts[st] ?? 0;
            const pct = max > 0 ? Math.round((n / max) * 100) : 0;
            return (
              <div key={st} className="flex flex-col gap-1.5">
                <div className="flex items-center justify-between gap-2">
                  {renderSampleStageTag(st)}
                  <span className="text-lg font-semibold tabular-nums">{n}</span>
                </div>
                <div className="h-2 overflow-hidden rounded-md bg-[var(--line)]">
                  <div
                    className="h-full rounded-md bg-[var(--accent)] transition-all"
                    style={{ width: `${pct}%`, minWidth: n > 0 ? "4px" : 0 }}
                    title={`${st}：${n}`}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export function CrmSamplesPage() {
  const [searchParams] = useSearchParams();
  const params = useParams<{ code?: string }>();
  const activeOnly = searchParams.get("active") === "1";
  const url = activeOnly ? "/api/crm/samples?active_only=true" : "/api/crm/samples";
  const { data } = useFetch<SampleListRow[]>(url);
  const rows = useMemo(() => data ?? [], [data]);
  const [detailCode, setDetailCode] = useState<string | null>(params.code ?? null);

  useEffect(() => {
    if (params.code) setDetailCode(params.code);
  }, [params.code]);

  return (
    <div className="px-6 py-4">
      <h2 className="text-lg font-semibold">样品流程</h2>
      <p className="text-xs text-[var(--text-muted)]">
        每条样品独立表单 · 点击「详情」查看打样过程子表
      </p>
      {activeOnly && (
        <p className="text-xs text-amber-200/80">筛选：在途打样（未结案）</p>
      )}
      <SampleStageMetrics rows={rows} activeOnly={activeOnly} />
      <div className="mt-4 overflow-x-auto rounded-lg border" style={{ borderColor: "var(--line)" }}>
        <table className="w-full text-xs">
          <thead className="bg-[var(--table-head)] text-[var(--text-muted)]">
            <tr>
              <th className="px-3 py-2 text-left">样品号</th>
              <th className="text-left">产品</th>
              <th className="text-left">客户</th>
              <th className="text-left">阶段</th>
              <th className="text-left">销售</th>
              <th className="text-left">节点</th>
              <th className="text-left">操作</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((s) => (
              <tr key={s.code} className="border-t" style={{ borderColor: "var(--line)" }}>
                <td className="px-3 py-2 font-mono text-[var(--accent)]">{s.code}</td>
                <td>{s.item_draft_name}</td>
                <td>
                  <span className="font-mono text-[var(--text-muted)]">{s.customer_code}</span> {s.customer_name}
                </td>
                <td>{renderSampleStageTag(s.current_stage)}</td>
                <td>{s.owner_sales}</td>
                <td className="tabular-nums">{s.due_date ?? "—"}</td>
                <td>
                  <button
                    type="button"
                    className="text-[var(--accent)] hover:underline"
                    onClick={() => setDetailCode(s.code)}
                  >
                    详情
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <SampleDetailDrawer sampleCode={detailCode} onClose={() => setDetailCode(null)} />
    </div>
  );
}

export function CrmReportsPage() {
  const { data: funnel } = useFetch<{ stages: string[]; counts: Record<string, number>; note: string }>(
    "/api/crm/reports/funnel",
  );
  const { data: weekly } = useFetch<{ active_count: number; overdue_count: number; note: string }>(
    "/api/crm/reports/sample-weekly",
  );
  return (
    <div className="px-6 py-4">
      <h2 className="text-lg font-semibold">销售固定报表</h2>
      <div className="mt-4 grid gap-4 md:grid-cols-2">
        <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
          <h3 className="text-sm font-medium">漏斗</h3>
          <p className="text-[10px] text-slate-500">{funnel?.note}</p>
          <ul className="mt-2 text-xs">
            {funnel?.stages.map((st) => (
              <li key={st} className="flex justify-between border-b border-slate-800 py-1">
                <span>{st}</span>
                <span>{funnel.counts[st] ?? 0}</span>
              </li>
            ))}
          </ul>
        </div>
        <div className="rounded-lg border border-slate-800 bg-slate-900 p-4 text-xs">
          <h3 className="text-sm font-medium">样品周报</h3>
          <p className="mt-2">在途 {weekly?.active_count ?? "—"} · 超期 {weekly?.overdue_count ?? "—"}</p>
          <p className="mt-1 text-slate-500">{weekly?.note}</p>
        </div>
      </div>
    </div>
  );
}

const CTP_ITEMS = [
  { code: "P1", label: "P1 巧克力装饰片" },
  { code: "P2", label: "P2 模具插件" },
  { code: "P4", label: "P4 浇注件" },
  { code: "P5", label: "P5" },
  { code: "P9", label: "P9 多半成品组合" },
];

export function CtpPage() {
  const auth = useAuth();
  const [itemCode, setItemCode] = useState("P2");
  const [qty, setQty] = useState("200");
  const [unit, setUnit] = useState("BOX");
  const [due, setDue] = useState("2026-09-28");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const run = () => {
    setBusy(true);
    setErr(null);
    fetch("/api/crm/ctp", {
      method: "POST",
      headers: { ...auth.headers(), "Content-Type": "application/json" },
      body: JSON.stringify({
        item_code: itemCode,
        qty_order: Number(qty),
        unit,
        due_date: due,
      }),
    })
      .then(async (r) => {
        const j = await r.json();
        if (!r.ok || j.code !== 0) throw new Error(j.detail || j.message || "试算失败");
        setResult(j.data);
      })
      .catch((e) => setErr(String(e)))
      .finally(() => setBusy(false));
  };
  const sales = result?.sales as
    | {
        headline?: string;
        status?: string;
        can_meet_due_date?: boolean;
        target_due?: string;
        plan_finish?: string | null;
        earliest_delivery?: string | null;
        finished_stock?: { summary?: string };
        materials?: { name: string; kind: string; status: string; summary: string }[];
        needs_production?: boolean;
        reasons?: string[];
        context?: string;
        order_qty_label?: string | null;
        product_label?: string;
      }
    | undefined;
  const feasible = sales?.can_meet_due_date ?? result?.feasible === true;
  const statusOk = sales?.status === "ok" || feasible;
  return (
    <div className="px-6 py-4">
      <h2 className="text-lg font-semibold">交期试算（CTP）</h2>
      <p className="text-xs text-slate-400">按品项 / 数量 / 当前产能池 what-if 试算，不落库</p>
      <div className="mt-3 flex flex-wrap items-end gap-2 text-sm">
        <label className="grid gap-1 text-xs text-[var(--text-muted)]">
          品项
          <select
            className="rounded border border-slate-700 bg-slate-950 px-2 py-1 text-sm text-[var(--text)]"
            value={itemCode}
            onChange={(e) => setItemCode(e.target.value)}
          >
            {CTP_ITEMS.map((it) => (
              <option key={it.code} value={it.code}>
                {it.label}
              </option>
            ))}
          </select>
        </label>
        <label className="grid gap-1 text-xs text-[var(--text-muted)]">
          数量
          <input
            className="w-24 rounded border border-slate-700 bg-slate-950 px-2 py-1 text-sm"
            value={qty}
            onChange={(e) => setQty(e.target.value)}
          />
        </label>
        <label className="grid gap-1 text-xs text-[var(--text-muted)]">
          单位
          <select
            className="rounded border border-slate-700 bg-slate-950 px-2 py-1 text-sm"
            value={unit}
            onChange={(e) => setUnit(e.target.value)}
          >
            <option value="BOX">盒</option>
            <option value="BOARD">版</option>
            <option value="PCS">枚</option>
          </select>
        </label>
        <label className="grid gap-1 text-xs text-[var(--text-muted)]">
          目标交期
          <input
            type="date"
            className="rounded border border-slate-700 bg-slate-950 px-2 py-1 text-sm"
            value={due}
            onChange={(e) => setDue(e.target.value)}
          />
        </label>
        <button
          type="button"
          className="rounded bg-sky-700 px-3 py-1 disabled:opacity-50"
          disabled={busy}
          onClick={run}
        >
          {busy ? "试算中…" : "试算"}
        </button>
        <Link to="/orders" className="text-sky-400 underline">
          转订单
        </Link>
      </div>
      {err && <p className="mt-2 text-xs text-rose-400">{err}</p>}
      {result && sales && (
        <div
          className={`mt-4 rounded-lg border p-4 text-sm ${
            statusOk ? "border-emerald-800/60 bg-emerald-950/30" : "border-rose-800/60 bg-rose-950/25"
          }`}
        >
          <p className={`text-base font-semibold ${statusOk ? "text-emerald-200" : "text-rose-200"}`}>
            {sales.headline ?? (feasible ? "可以满足目标交期" : "目标交期可能无法满足")}
          </p>
          <dl className="mt-3 grid gap-2 text-xs sm:grid-cols-2">
            <div>
              <dt className="text-[var(--text-muted)]">试算品项</dt>
              <dd className="text-[var(--text)]">
                {sales.product_label ?? itemCode}
                {sales.order_qty_label ? ` · ${sales.order_qty_label}` : ""}
              </dd>
            </div>
            <div>
              <dt className="text-[var(--text-muted)]">客户目标交期</dt>
              <dd className="text-[var(--text)]">{sales.target_due ?? String(result.requested_due ?? "—")}</dd>
            </div>
            <div>
              <dt className="text-[var(--text-muted)]">排产预计完工</dt>
              <dd className="text-[var(--text)]">{sales.plan_finish ?? String(result.plan_end ?? "—")}</dd>
            </div>
            <div>
              <dt className="text-[var(--text-muted)]">销售可承诺交期（参考）</dt>
              <dd className={`font-medium ${statusOk ? "text-emerald-300" : "text-amber-300"}`}>
                {sales.earliest_delivery ?? "—"}
              </dd>
            </div>
          </dl>

          <div className="mt-4 border-t border-slate-800/80 pt-3">
            <h3 className="text-xs font-medium uppercase tracking-wide text-[var(--text-muted)]">现货与物料</h3>
            <p className="mt-1 text-[var(--text)]">{sales.finished_stock?.summary ?? "—"}</p>
            {sales.materials && sales.materials.length > 0 && (
              <ul className="mt-2 space-y-1.5">
                {sales.materials.map((m) => (
                  <li key={m.name} className="flex flex-wrap items-baseline gap-x-2 text-xs">
                    <span className="rounded bg-slate-800/80 px-1.5 py-0.5 text-[10px] text-slate-300">{m.kind}</span>
                    <span className="text-slate-200">{m.name}</span>
                    <span
                      className={
                        m.status === "ok"
                          ? "text-emerald-400/90"
                          : m.status === "shortage"
                            ? "text-rose-400"
                            : "text-amber-300"
                      }
                    >
                      {m.summary}
                    </span>
                  </li>
                ))}
              </ul>
            )}
            {sales.needs_production && (
              <p className="mt-2 text-xs text-amber-200/90">
                本单不能单靠现货出齐，需纳入生产排程；上表「还需排产」部分决定最早可交日期。
              </p>
            )}
          </div>

          {sales.reasons && sales.reasons.length > 0 && (
            <div className="mt-4 border-t border-slate-800/80 pt-3">
              <h3 className="text-xs font-medium uppercase tracking-wide text-[var(--text-muted)]">说明</h3>
              <ul className="mt-1 list-inside list-disc space-y-0.5 text-xs text-slate-300">
                {sales.reasons.map((r) => (
                  <li key={r}>{r}</li>
                ))}
              </ul>
            </div>
          )}

          <p className="mt-3 text-[10px] leading-relaxed text-[var(--text-muted)]">{sales.context}</p>
        </div>
      )}
    </div>
  );
}
