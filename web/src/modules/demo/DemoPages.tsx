import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { DEMO_TODAY } from "../../constants/groups";
import { useAuth } from "../../shell/auth";

const WEEKDAYS = ["日", "一", "二", "三", "四", "五", "六"] as const;

function formatDemoDate(iso: string) {
  const [y, m, d] = iso.split("-").map(Number);
  const weekday = WEEKDAYS[new Date(Date.UTC(y, m - 1, d)).getUTCDay()];
  return {
    ymd: iso,
    cn: `${y}年${m}月${d}日`,
    weekday: `星期${weekday}`,
  };
}

type Act = {
  act: number;
  title: string;
  module: string;
  role: string;
  path: string;
  steps: string[];
  note?: string;
};

type LoopAct = {
  step: number;
  title: string;
  role: string;
  path: string;
  steps: string[];
};

type Scope = {
  offline_ok: boolean;
  disclaimer: string;
  not_delivered: string[];
};

type ScenarioStatus = {
  today: string;
  locked: boolean;
  order_count: number;
  item_count: number;
  stock_zero: boolean;
  groups: { dept: string; group_code: string; label: string; headcount: number }[];
};

type Preview = {
  order_count: number;
  due_mode: string;
  item_share: string;
  core_skus: string[];
  cluster_order_nos: string[];
  due_histogram: { fence: number; mid: number; far: number };
  warnings: string[];
  intersections: { a: string; b: string; intersection: string[] }[];
};

const DUE_OPTIONS = [
  { id: "FOCUS_FENCE", label: "集中 4 天内（冻结区）" },
  { id: "FOCUS_MID", label: "集中 5–15 天" },
  { id: "FOCUS_FAR", label: "集中 16–30 天" },
  { id: "UNIFORM", label: "30 天内均匀" },
] as const;

const SHARE_OPTIONS = [
  { id: "NONE", label: "无品项共享（集合不相交）" },
  { id: "SHARE_10_1", label: "10% 单相交 1 个 SKU" },
  { id: "SHARE_20_4", label: "20% 单相交 4 个 SKU" },
] as const;

function apiError(j: { detail?: unknown; message?: string }, fallback: string): string {
  if (typeof j.detail === "string") return j.detail;
  if (Array.isArray(j.detail)) return j.detail.map((x) => JSON.stringify(x)).join("; ");
  return j.message || fallback;
}

export function DemoConsolePage() {
  const auth = useAuth();
  const isGm = auth.role === "GM";
  const [acts, setActs] = useState<Act[]>([]);
  const [loopActs, setLoopActs] = useState<LoopAct[]>([]);
  const [scope, setScope] = useState<Scope | null>(null);
  const [status, setStatus] = useState<ScenarioStatus | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [headcount, setHeadcount] = useState(5);
  const [orderCount, setOrderCount] = useState<5 | 10 | 20 | 50 | 100>(5);
  const [dueMode, setDueMode] = useState<string>("UNIFORM");
  const [itemShare, setItemShare] = useState<string>("SHARE_10_1");
  const [preview, setPreview] = useState<Preview | null>(null);

  const loadStatus = useCallback(() => {
    fetch("/api/demo/scenario/status", { headers: auth.headers() })
      .then((r) => r.json())
      .then((j) => setStatus(j.data ?? null))
      .catch(() => undefined);
  }, [auth]);

  useEffect(() => {
    fetch("/api/demo/rehearsal", { headers: auth.headers() })
      .then((r) => r.json())
      .then((j) => {
        setActs(j.data?.acts ?? []);
        setLoopActs(j.data?.loop_acts ?? []);
        setScope(j.data?.scope ?? null);
      });
    loadStatus();
  }, [auth, loadStatus]);

  const postJson = async (url: string, body?: unknown) => {
    setBusy(true);
    setMsg(null);
    setErr(null);
    try {
      const r = await fetch(url, {
        method: "POST",
        headers: { ...auth.headers(), "Content-Type": "application/json" },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
      const j = await r.json();
      if (!r.ok) {
        setErr(apiError(j, `请求失败 ${r.status}`));
        return null;
      }
      setMsg(j.message || "完成");
      loadStatus();
      return j.data;
    } catch (e) {
      setErr(String(e));
      return null;
    } finally {
      setBusy(false);
    }
  };

  const triggerS5 = () => {
    postJson("/api/demo/trigger-sample-overdue?sample_code=SP-001");
  };

  const genBody = () => ({
    order_count: orderCount,
    due_mode: dueMode,
    item_share: itemShare,
    rng_seed: 20260915,
    auto_add_to_pool: false,
  });

  const applyPreset = (count: 5 | 10 | 20 | 50 | 100, due: string, share: string) => {
    setOrderCount(count);
    setDueMode(due);
    setItemShare(share);
    setPreview(null);
  };

  const demoDate = formatDemoDate(status?.today || DEMO_TODAY);

  return (
    <div className="px-6 py-4">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold">演示控制台 · 场景台</h2>
          <p className="mt-1 text-xs text-slate-400">
            生成后订单只进待排程，由生管全选加入排程。交期与下单日都按右侧基准日计算。
          </p>
        </div>
        <div
          className="min-w-[240px] rounded-lg border-2 border-sky-500/70 bg-sky-950/50 px-4 py-3 shadow-[0_0_24px_rgba(14,165,233,0.18)]"
          title="排程、齐套、造数全部锚定此日，不是电脑系统日期"
        >
          <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-sky-300">
            DEMO-TODAY · 演示基准日
          </p>
          <p className="mt-1 font-mono text-3xl font-bold tabular-nums leading-none tracking-tight text-sky-50">
            {demoDate.ymd}
          </p>
          <p className="mt-1.5 text-sm text-sky-100">
            {demoDate.cn} · {demoDate.weekday}
          </p>
          <p className="mt-1 text-[10px] text-sky-300/80">不是电脑今天 · 造数 / 排程 / 齐套都用这一天</p>
        </div>
      </div>
      {scope && (
        <div className="mt-2 rounded border border-amber-800/60 bg-amber-950/30 px-3 py-2 text-xs text-amber-100">
          <p>{scope.disclaimer}</p>
          <p className="mt-1 text-amber-200/80">明确不交付：{scope.not_delivered.join(" · ")}</p>
        </div>
      )}

      <section className="mt-4 rounded-lg border border-slate-800 bg-slate-900 p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-sm font-semibold text-slate-100">场景台</h3>
          {status && (
            <p className="text-[10px] text-slate-500">
              {status.locked ? "场景已锁（不会自动重导 12 单）" : "未锁 · 订单数变化可能触发种子重导"}
              {" · "}订单 {status.order_count} · 品项 {status.item_count}
              {status.stock_zero ? " · 库存已清零" : " · 库存非空"}
            </p>
          )}
        </div>
        {status && (
          <p className="mt-1 text-[10px] text-slate-500">
            编制：
            {status.groups.map((g) => `${g.label} ${g.headcount}人`).join(" · ")}
          </p>
        )}
        {!isGm && (
          <p className="mt-2 text-[10px] text-amber-400">清场 / 造数仅总经理可执行，请切换角色后操作。</p>
        )}
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <button
            type="button"
            disabled={busy || !isGm}
            className="rounded border border-rose-800 px-3 py-1 text-xs text-rose-200 disabled:opacity-40"
            onClick={() => {
              if (window.confirm("清空全部订单、排产/派工、报工，并把库存数量清零？产品维表保留。")) {
                postJson("/api/demo/scenario/reset-orders");
              }
            }}
          >
            初始化订单
          </button>
          <label className="flex items-center gap-1 text-[10px] text-slate-400">
            每组
            <input
              type="number"
              min={1}
              max={20}
              value={headcount}
              disabled={busy || !isGm}
              onChange={(e) => setHeadcount(Number(e.target.value) || 5)}
              className="w-12 rounded border border-slate-700 bg-slate-950 px-1 py-0.5 text-xs text-slate-100"
            />
            人
          </label>
          <button
            type="button"
            disabled={busy || !isGm}
            className="rounded border border-slate-600 px-3 py-1 text-xs disabled:opacity-40"
            onClick={() => {
              if (window.confirm(`按每组 ${headcount} 人重建生产花名册，并同步日历编制与出勤？`)) {
                postJson("/api/demo/scenario/reset-roster", { headcount });
              }
            }}
          >
            初始产线人员
          </button>
          <button
            type="button"
            disabled={busy || !isGm}
            className="rounded border border-slate-600 px-3 py-1 text-xs disabled:opacity-40"
            onClick={() => {
              if (window.confirm("恢复官方 12 单种子并解锁场景？本轮造数将丢失。")) {
                postJson("/api/demo/scenario/restore-seed");
              }
            }}
          >
            恢复官方种子
          </button>
        </div>

        <div className="mt-4 grid gap-3 md:grid-cols-3">
          <label className="text-[10px] text-slate-400">
            订单数量
            <select
              value={orderCount}
              onChange={(e) => setOrderCount(Number(e.target.value) as 5 | 10 | 20 | 50 | 100)}
              className="mt-1 block w-full rounded border border-slate-700 bg-slate-950 px-2 py-1 text-xs text-slate-100"
            >
              {[5, 10, 20, 50, 100].map((n) => (
                <option key={n} value={n}>
                  {n} 单
                </option>
              ))}
            </select>
          </label>
          <label className="text-[10px] text-slate-400">
            交期集中度
            <select
              value={dueMode}
              onChange={(e) => setDueMode(e.target.value)}
              className="mt-1 block w-full rounded border border-slate-700 bg-slate-950 px-2 py-1 text-xs text-slate-100"
            >
              {DUE_OPTIONS.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.label}
                </option>
              ))}
            </select>
          </label>
          <label className="text-[10px] text-slate-400">
            品项共享
            <select
              value={itemShare}
              onChange={(e) => setItemShare(e.target.value)}
              className="mt-1 block w-full rounded border border-slate-700 bg-slate-950 px-2 py-1 text-xs text-slate-100"
            >
              {SHARE_OPTIONS.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.label}
                </option>
              ))}
            </select>
          </label>
        </div>
        <p className="mt-2 text-[10px] text-slate-500">
          无共享且每单 2 行时最多 5 单。共享 = 两单各有 SKU 集合且相交，不是一单一行。
        </p>
        <div className="mt-2 flex flex-wrap gap-2">
          <button
            type="button"
            className="rounded border border-slate-700 px-2 py-1 text-[10px] text-slate-300"
            onClick={() => applyPreset(5, "UNIFORM", "NONE")}
          >
            预设：闭环畅通 · 5 单均匀无共享
          </button>
          <button
            type="button"
            className="rounded border border-slate-700 px-2 py-1 text-[10px] text-slate-300"
            onClick={() => applyPreset(20, "FOCUS_FENCE", "SHARE_10_1")}
          >
            预设：协同压力 · 20 单冻结区相交 1 SKU
          </button>
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            disabled={busy}
            className="rounded border border-sky-700 px-3 py-1 text-xs text-sky-300 disabled:opacity-40"
            onClick={async () => {
              const data = await postJson("/api/demo/scenario/preview-orders", genBody());
              if (data) setPreview(data);
            }}
          >
            预览订单集
          </button>
          <button
            type="button"
            disabled={busy || !isGm}
            className="rounded border border-emerald-700 px-3 py-1 text-xs text-emerald-300 disabled:opacity-40"
            onClick={async () => {
              if (!window.confirm("将先清场再写入本轮订单，全部进入待排程。继续？")) return;
              const data = await postJson("/api/demo/scenario/generate-orders", genBody());
              if (data) setPreview(data);
            }}
          >
            生成并填充
          </button>
          <Link to="/orders" className="rounded border border-slate-600 px-3 py-1 text-xs text-slate-300">
            去订单中心 →
          </Link>
          <Link to="/schedule" className="rounded border border-slate-600 px-3 py-1 text-xs text-slate-300">
            去排程 →
          </Link>
        </div>
        {preview && (
          <div className="mt-3 rounded border border-slate-800 bg-slate-950/60 px-3 py-2 text-[11px] text-slate-300">
            <p>
              {preview.order_count} 单 · 交期 冻结{preview.due_histogram.fence} / 中期
              {preview.due_histogram.mid} / 远期{preview.due_histogram.far}
              {preview.core_skus.length > 0 && ` · 核心相交 {${preview.core_skus.join(", ")}}`}
            </p>
            {preview.warnings.length > 0 && (
              <p className="mt-1 text-amber-300">{preview.warnings.join("；")}</p>
            )}
            {preview.intersections.length > 0 && (
              <ul className="mt-1 space-y-0.5 text-slate-400">
                {preview.intersections.slice(0, 8).map((x) => (
                  <li key={`${x.a}-${x.b}`}>
                    {`${x.a} ∩ ${x.b} = {${x.intersection.join(", ") || "∅"}}`}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </section>

      <div className="mt-3 flex flex-wrap gap-2">
        <button
          type="button"
          className="rounded border border-slate-600 px-3 py-1 text-xs"
          onClick={triggerS5}
        >
          联调：触发 S5 打样超期消息
        </button>
        <Link to="/todos" className="rounded border border-sky-700 px-3 py-1 text-xs text-sky-300">
          待办中心 →
        </Link>
      </div>
      {msg && <p className="mt-2 text-xs text-emerald-400">{msg}</p>}
      {err && <p className="mt-2 text-xs text-rose-400">{err}</p>}

      {loopActs.length > 0 && (
        <>
          <h3 className="mt-8 text-sm font-semibold text-slate-200">产销财务闭环</h3>
          <ol className="mt-3 space-y-3">
            {loopActs.map((a) => (
              <li key={a.step} className="rounded-lg border border-slate-800 bg-slate-900 p-4 text-sm">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="font-semibold text-slate-100">
                    第 {a.step} 步 · {a.title}
                  </p>
                  <Link to={a.path} className="text-xs text-sky-400 underline">
                    {a.path} · {a.role}
                  </Link>
                </div>
                <ul className="mt-2 list-decimal pl-5 text-xs text-slate-300">
                  {a.steps.map((s) => (
                    <li key={s}>{s}</li>
                  ))}
                </ul>
              </li>
            ))}
          </ol>
        </>
      )}

      <h3 className="mt-8 text-sm font-semibold text-slate-200">十幕剧本</h3>
      <ol className="mt-3 space-y-4">
        {acts.map((a) => (
          <li key={a.act} className="rounded-lg border border-slate-800 bg-slate-900 p-4 text-sm">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="font-semibold text-slate-100">
                第 {a.act} 幕 · {a.title}
              </p>
              <Link to={a.path} className="text-xs text-sky-400 underline">
                {a.path} · 建议 {a.role}
              </Link>
            </div>
            <p className="mt-1 text-[10px] text-slate-500">{a.module}</p>
            <ul className="mt-2 list-decimal pl-5 text-xs text-slate-300">
              {a.steps.map((s) => (
                <li key={s}>{s}</li>
              ))}
            </ul>
            {a.note && <p className="mt-2 text-[10px] text-slate-500">{a.note}</p>}
          </li>
        ))}
      </ol>
    </div>
  );
}

type TodoItem = {
  id: string;
  kind: string;
  title: string;
  detail: string;
  path: string;
  priority: string;
  pulse?: boolean;
};

export function TodoCenterPage() {
  const auth = useAuth();
  const [items, setItems] = useState<TodoItem[]>([]);

  useEffect(() => {
    fetch("/api/demo/todos", { headers: auth.headers() })
      .then((r) => r.json())
      .then((j) => setItems(j.data?.items ?? []));
  }, [auth.role, auth.headers]);

  return (
    <div className="px-6 py-4">
      <h2 className="text-lg font-semibold">待办中心</h2>
      <p className="text-xs text-slate-400">按当前角色聚合：变更审批、未完尾数、超期打样、企微模拟、齐套预警</p>
      <ul className="mt-4 space-y-2">
        {items.length === 0 && (
          <li className="text-sm text-slate-500">暂无待办（可去演示控制台触发 S5）</li>
        )}
        {items.map((t) => (
          <li key={t.id}>
            <Link
              to={t.path}
              className={`block rounded-lg border px-3 py-2 text-sm hover:border-sky-700 ${
                t.pulse
                  ? "animate-pulse border-amber-500 bg-amber-950/40"
                  : "border-slate-800 bg-slate-900"
              }`}
            >
              <span className="text-[10px] uppercase text-slate-500">{t.kind}</span>
              <p className="font-medium text-slate-100">{t.title}</p>
              <p className="text-xs text-slate-400">{t.detail}</p>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
