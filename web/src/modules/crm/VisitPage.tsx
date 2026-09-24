import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useAuth } from "../../shell/auth";

type GoalLine = {
  metric: string;
  target: number;
  done: number;
  gap: number;
  is_amount?: boolean;
  display_target?: string;
  display_done?: string;
};
type GoalBlock = { period_key: string; label: string; lines: GoalLine[] };
type VisitHome = {
  goals: { owner_sales: string; lines: GoalLine[] }[];
  goal_blocks?: { year: GoalBlock; month: GoalBlock; week: GoalBlock };
  actions: Action[];
};
type Action = {
  customer_code: string | null;
  customer_name: string;
  next_step: string;
  next_date: string;
  overdue: boolean;
};
type Match = { code: string; name: string };
type Draft = {
  source: string;
  note?: string;
  customer_name: string;
  matches: Match[];
  ask_create: boolean;
  visit_kind: string;
  narrative: string;
  outcome: string;
  next_step: string;
  next_date: string;
  opportunity_name: string;
  check_in_at: string;
  check_out_at: string;
  location_note: string;
  photo_note: string;
};

const OUTCOMES = ["关系建联", "触达决策人", "挖到商机"] as const;
const COMPLETE_SLOTS = ["客户是谁", "见了谁", "要什么", "这次说清了", "下一步约好了"] as const;
const FUNNEL_NEXT: Record<string, string> = {
  全部拜访: "有效拜访",
  有效拜访: "已建客户",
  已建客户: "商机",
  商机: "打样",
  打样: "报价",
  报价: "签单",
};

const CARD = "w-full rounded-2xl border px-3 py-3 text-left";
const LINE = { borderColor: "var(--line)", background: "var(--bg-card)" } as const;

async function api<T>(path: string, role: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", "X-Demo-Role": role, ...init?.headers },
  });
  const body = await res.json();
  if (!res.ok || body.code !== 0) {
    throw new Error(body.detail || body.message || "请求失败");
  }
  return body.data as T;
}

function goalRatio(line: GoalLine) {
  return { done: line.done, target: line.target, text: `${line.display_done ?? line.done}/${line.display_target ?? line.target}` };
}

function Bar({ done, target, warn }: { done: number; target: number; warn?: boolean }) {
  const pct = target <= 0 ? 0 : Math.min(100, Math.round((done / target) * 100));
  return (
    <div className="mt-1.5 h-1.5 overflow-hidden rounded-full" style={{ background: "var(--line)" }}>
      <div
        className={`h-full rounded-full ${warn ? "bg-amber-400" : "bg-[var(--accent)]"}`}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

function Dots({ percent, filled }: { percent: number; filled?: string[] }) {
  const have = new Set(filled ?? COMPLETE_SLOTS.slice(0, Math.round(percent / 20)));
  return (
    <div className="mt-2 flex gap-1">
      {COMPLETE_SLOTS.map((slot) => (
        <span
          key={slot}
          title={slot}
          className="h-1.5 flex-1 rounded-full"
          style={{ background: have.has(slot) ? "#059669" : "var(--line)" }}
        />
      ))}
    </div>
  );
}

function Tag({ text, tone = "muted" }: { text: string; tone?: "muted" | "amber" | "rose" | "ok" }) {
  const color =
    tone === "amber"
      ? "text-amber-300 border-amber-500/50"
      : tone === "rose"
        ? "text-rose-300 border-rose-500/50"
        : tone === "ok"
          ? "border-emerald-500 bg-emerald-600 text-white"
          : "text-[var(--text-muted)]";
  return (
    <span className={`inline-block rounded-full border px-2 py-0.5 text-[10px] ${color}`} style={tone === "muted" ? { borderColor: "var(--line)" } : undefined}>
      {text}
    </span>
  );
}

function SlotChips({ filled, missing }: { filled?: string[]; missing?: string[] }) {
  const have = new Set(filled ?? COMPLETE_SLOTS.filter((slot) => !(missing ?? []).includes(slot)));
  return (
    <div className="mt-2 flex flex-wrap gap-1">
      {COMPLETE_SLOTS.map((slot) => {
        const done = have.has(slot);
        return (
          <span
            key={slot}
            className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] ${
              done
                ? "border-emerald-500 bg-emerald-600 text-white"
                : "border-dashed text-[var(--text-muted)]"
            }`}
            style={done ? undefined : { borderColor: "var(--line)" }}
          >
            {done ? `✓ ${slot}` : slot}
          </span>
        );
      })}
    </div>
  );
}

function minutesBetween(start: string, end: string): number {
  const a = Date.parse(start);
  const b = Date.parse(end);
  if (!Number.isFinite(a) || !Number.isFinite(b) || b < a) return 0;
  return Math.round((b - a) / 60000);
}

function parseProgress(value: string | null): { done: number; plan: number } | null {
  if (!value) return null;
  const [done, plan] = value.split("/").map((n) => Number(n));
  if (!Number.isFinite(done) || !Number.isFinite(plan)) return null;
  return { done, plan };
}

export function VisitPage() {
  const auth = useAuth();
  const [params, setParams] = useSearchParams();
  const presetCode = params.get("customer_code") ?? "";
  const presetName = params.get("customer_name") ?? "";
  const rawTab = params.get("tab") || "today";
  const tab = rawTab === "visit" ? "today" : rawTab;
  const [home, setHome] = useState<VisitHome | null>(null);
  const [mode, setMode] = useState<"home" | "compose" | "draft">(presetName ? "compose" : "home");
  const [text, setText] = useState("");
  const [draft, setDraft] = useState<Draft | null>(null);
  const [picked, setPicked] = useState(presetCode);
  const [createCustomer, setCreateCustomer] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [listening, setListening] = useState(false);

  const loadHome = () => {
    if (!auth.role) return;
    api<VisitHome>("/api/crm/visits/home?today=2026-09-15", auth.role)
      .then(setHome)
      .catch((e) => setError(String(e)));
  };

  useEffect(() => {
    loadHome();
  }, [auth.role]);

  useEffect(() => {
    if (!presetName) return;
    setText("");
    setMode("compose");
    setDone(null);
    setPicked(presetCode);
  }, [presetName, presetCode]);

  const clearVisitParams = () => {
    const next = new URLSearchParams();
    if (tab !== "today") next.set("tab", tab);
    setParams(next, { replace: true });
  };

  const startVisit = (code: string, name: string) => {
    const next = new URLSearchParams();
    if (code) next.set("customer_code", code);
    if (name) next.set("customer_name", name);
    setParams(next);
    setText("");
    setMode("compose");
    setDone(null);
    setError(null);
  };

  const speak = () => {
    const w = window as unknown as {
      SpeechRecognition?: new () => SpeechRec;
      webkitSpeechRecognition?: new () => SpeechRec;
    };
    const Ctor = w.SpeechRecognition || w.webkitSpeechRecognition;
    if (!Ctor) {
      setError("这台浏览器没有语音识别，直接打字即可。");
      return;
    }
    const rec = new Ctor();
    rec.lang = "zh-CN";
    rec.onresult = (event) => {
      const said = event.results[0][0].transcript;
      setText((prev) => (prev ? `${prev}${said}` : said));
      setListening(false);
    };
    rec.onerror = () => setListening(false);
    rec.onend = () => setListening(false);
    setListening(true);
    setError(null);
    rec.start();
  };

  const organize = async () => {
    if (!auth.role || !text.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const next = await api<Draft>("/api/crm/visits/draft", auth.role, {
        method: "POST",
        body: JSON.stringify({ text, today: "2026-09-15" }),
      });
      if (presetCode) {
        next.matches = [{ code: presetCode, name: presetName || next.customer_name }];
        next.customer_name = presetName || next.customer_name;
        next.ask_create = false;
        next.visit_kind = "现有客户";
      }
      setDraft(next);
      setPicked(presetCode || (next.matches.length === 1 ? next.matches[0].code : ""));
      setCreateCustomer(next.ask_create);
      setMode("draft");
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const confirm = async () => {
    if (!auth.role || !draft) return;
    setBusy(true);
    setError(null);
    try {
      const data = await api<{
        is_valid: boolean;
        customer_name: string;
        completeness: { before_percent: number; after_percent: number; gained: string[]; missing: string[] };
      }>("/api/crm/visits/confirm", auth.role, {
        method: "POST",
        body: JSON.stringify({
          customer_name: draft.customer_name,
          customer_code: picked || null,
          create_customer: createCustomer && !picked,
          visit_kind: draft.visit_kind,
          narrative: draft.narrative,
          outcome: draft.outcome,
          next_step: draft.next_step,
          next_date: draft.next_date,
          opportunity_name: draft.outcome === "挖到商机" ? draft.opportunity_name : null,
          check_in_at: draft.check_in_at,
          check_out_at: draft.check_out_at,
          location_note: draft.location_note,
          photo_note: draft.photo_note,
        }),
      });
      const score = data.completeness;
      const gained = score.gained.length ? `补上了${score.gained.join("、")}。` : "这次没有新的信息。";
      const missing = score.missing.length ? `还缺${score.missing.join("、")}。` : "拜访信息已齐。";
      setDone(
        data.is_valid
          ? `已写入 ${data.customer_name || "这次拜访"}。完整度从 ${score.before_percent}% 到 ${score.after_percent}%。${gained}${missing}`
          : "已保存。不满 15 分钟，不计有效拜访，完整度和目标都不增加。",
      );
      setMode("home");
      setDraft(null);
      setText("");
      clearVisitParams();
      loadHome();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const mine = home?.goals[0];

  return (
    <div className="mx-auto flex min-h-full w-full max-w-md flex-col px-4 py-6 pb-24">
      <div className="mb-4 flex items-start justify-between gap-2">
        <div>
          <p className="text-sm font-semibold">销售移动端</p>
          <p className="mt-0.5 text-xs text-[var(--text-muted)]">{auth.userName || "李业务"}</p>
        </div>
        <Link
          to="/portal"
          className="shrink-0 rounded-full border px-3 py-1.5 text-[11px] text-[var(--text-muted)] hover:text-[var(--text-body)]"
          style={{ borderColor: "var(--line)", background: "var(--bg-card)" }}
        >
          返回电脑端
        </Link>
      </div>
      {error && <p className="mb-3 text-xs text-rose-400">{error}</p>}
      {done && <p className="mb-3 text-xs text-emerald-400">{done}</p>}

      {tab === "customers" && auth.role && <CustomerTab role={auth.role} />}
      {tab === "metrics" && auth.role && <MetricsTab role={auth.role} blocks={home?.goal_blocks} />}
      {tab === "orders" && auth.role && <OrdersTab role={auth.role} />}

      {tab === "today" && mode === "home" && (
        <div className="space-y-4">
          {mine && (
            <div className="grid grid-cols-2 gap-2">
              {mine.lines.map((line) => {
                const gap = Math.max(line.gap, 0);
                const doneGoal = gap === 0 && line.target > 0;
                const ratio = goalRatio(line);
                return (
                  <Link
                    key={line.metric}
                    to="/crm/visit?tab=metrics"
                    className={`${CARD} px-2 py-2`}
                    style={LINE}
                  >
                    <p className="text-[10px] leading-tight text-[var(--text-muted)]">{line.metric}</p>
                    <p className={`mt-1 text-xs font-semibold tabular-nums ${gap > 0 ? "text-amber-300" : ""}`}>
                      {ratio.text}
                      {doneGoal ? " ✓" : ""}
                    </p>
                    <Bar done={ratio.done} target={ratio.target} warn={gap > 0} />
                  </Link>
                );
              })}
            </div>
          )}
          <button
            type="button"
            className="w-full rounded-2xl bg-[var(--accent)] px-4 py-7 text-xl font-semibold text-white"
            onClick={() => {
              setDone(null);
              setText("");
              setMode("compose");
            }}
          >
            {presetName ? "记录这次拜访" : "记录拜访"}
          </button>
          <div className="space-y-2">
            <p className="text-xs font-medium text-[var(--text-muted)]">今天该做的</p>
            {(home?.actions ?? []).map((action) => (
              <button
                key={`${action.customer_name}-${action.next_date}`}
                type="button"
                className={CARD}
                style={{ ...LINE, borderColor: action.overdue ? "#f59e0b" : "var(--line)" }}
                onClick={() => startVisit(action.customer_code ?? "", action.customer_name)}
              >
                <span className="flex items-center justify-between gap-2">
                  <span className="font-medium">{action.customer_name}</span>
                  {action.overdue && <Tag text="过期" tone="amber" />}
                </span>
                <span className="mt-1 block text-xs text-[var(--text-muted)]">
                  {action.next_step} · {action.next_date}
                </span>
              </button>
            ))}
            {(home?.actions.length ?? 0) === 0 && (
              <p className="text-xs text-[var(--text-muted)]">今天没有到期的下一步。</p>
            )}
          </div>
        </div>
      )}

      {tab === "today" && mode === "compose" && (
        <div className="space-y-3">
          <p className="text-xs text-[var(--text-muted)]">{presetName ? `这次记在 ${presetName}` : "对着这家客户说话或打字"}</p>
          <textarea
            className="min-h-40 w-full rounded-2xl border p-3 text-sm"
            style={LINE}
            placeholder="说这次见了谁、谈了什么"
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
          <div className="flex gap-2">
            <button type="button" className="flex-1 rounded-2xl border px-3 py-3 text-sm" style={LINE} onClick={speak}>
              {listening ? "正在听…" : "说话"}
            </button>
            <button
              type="button"
              disabled={busy || !text.trim()}
              className="flex-1 rounded-2xl bg-[var(--accent)] px-3 py-3 text-sm text-white disabled:opacity-50"
              onClick={() => void organize()}
            >
              整理
            </button>
          </div>
          <button
            type="button"
            className="text-xs text-[var(--text-muted)]"
            onClick={() => {
              setMode("home");
              setText("");
              clearVisitParams();
            }}
          >
            返回今日
          </button>
        </div>
      )}

      {tab === "today" && mode === "draft" && draft && (
        <div className="space-y-3 text-sm">
          <p className="text-xs text-[var(--text-muted)]">
            {draft.source === "llm" ? "模型整理，确认后才写入" : "未接通模型，按关键词起草。确认后才写入"}
          </p>
          {draft.note && <p className="text-xs text-amber-300">{draft.note}</p>}
          {presetName ? (
            <p className="text-sm font-medium">{presetName}</p>
          ) : (
            <label className="block text-xs text-[var(--text-muted)]">
              客户
              <input
                className="mt-1 w-full rounded-2xl border px-3 py-2 text-sm"
                style={LINE}
                value={draft.customer_name}
                onChange={(e) => setDraft({ ...draft, customer_name: e.target.value })}
              />
            </label>
          )}
          {draft.matches.length > 1 && (
            <div className="space-y-1">
              <p className="text-xs text-[var(--text-muted)]">对上好几家，点一家</p>
              {draft.matches.map((m) => (
                <button
                  key={m.code}
                  type="button"
                  className={CARD}
                  style={{ ...LINE, borderColor: picked === m.code ? "var(--accent)" : "var(--line)" }}
                  onClick={() => {
                    setPicked(m.code);
                    setCreateCustomer(false);
                    setDraft({ ...draft, customer_name: m.name, visit_kind: "现有客户" });
                  }}
                >
                  {m.name}
                </button>
              ))}
            </div>
          )}
          {!presetName && draft.matches.length === 0 && (
            <label className="flex items-center gap-2 text-xs">
              <input type="checkbox" checked={createCustomer} onChange={(e) => setCreateCustomer(e.target.checked)} />
              没有这家客户，确认后新建
            </label>
          )}
          <label className="block text-xs text-[var(--text-muted)]">
            见了谁
            <select
              className="mt-1 w-full rounded-2xl border px-3 py-2 text-sm"
              style={LINE}
              value={draft.outcome}
              onChange={(e) => setDraft({ ...draft, outcome: e.target.value })}
            >
              {OUTCOMES.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>
          {draft.outcome === "挖到商机" && (
            <label className="block text-xs text-[var(--text-muted)]">
              要什么
              <input
                className="mt-1 w-full rounded-2xl border px-3 py-2 text-sm"
                style={LINE}
                value={draft.opportunity_name}
                onChange={(e) => setDraft({ ...draft, opportunity_name: e.target.value })}
              />
            </label>
          )}
          <label className="block text-xs text-[var(--text-muted)]">
            发生了什么
            <textarea
              className="mt-1 min-h-20 w-full rounded-2xl border p-3 text-sm"
              style={LINE}
              value={draft.narrative}
              onChange={(e) => setDraft({ ...draft, narrative: e.target.value })}
            />
          </label>
          <label className="block text-xs text-[var(--text-muted)]">
            下一步
            <p className="mt-1 text-sm text-[var(--text-body)]">{draft.next_step}</p>
            <input
              type="date"
              className="mt-1 w-full rounded-2xl border px-3 py-2 text-sm"
              style={LINE}
              value={draft.next_date}
              onChange={(e) => setDraft({ ...draft, next_date: e.target.value })}
            />
          </label>
          <p className="text-xs text-[var(--text-muted)]">
            已记 {minutesBetween(draft.check_in_at, draft.check_out_at)} 分钟
            {draft.location_note ? ` · ${draft.location_note}` : ""}
          </p>
          <button
            type="button"
            disabled={busy}
            className="w-full rounded-2xl bg-[var(--accent)] px-3 py-3 text-white disabled:opacity-50"
            onClick={() => void confirm()}
          >
            确认写入
          </button>
          <button type="button" className="text-xs text-[var(--text-muted)]" onClick={() => setMode("compose")}>
            返回修改原话
          </button>
        </div>
      )}

      <nav
        className="fixed bottom-0 left-0 right-0 mx-auto flex max-w-md border-t text-xs"
        style={{ borderColor: "var(--line)", background: "var(--bg-card)" }}
      >
        {(
          [
            ["today", "今日"],
            ["customers", "客户"],
            ["orders", "订单"],
            ["metrics", "指标"],
          ] as const
        ).map(([key, label]) => (
          <Link
            key={key}
            to={key === "today" ? "/crm/visit" : `/crm/visit?tab=${key}`}
            className="relative flex-1 py-3 text-center"
            style={{ color: tab === key ? "var(--accent)" : "var(--text-muted)" }}
          >
            {tab === key && <span className="absolute inset-x-6 top-0 h-0.5 rounded-full bg-[var(--accent)]" />}
            {label}
          </Link>
        ))}
      </nav>
    </div>
  );
}

function CustomerTab({ role }: { role: string }) {
  const [q, setQ] = useState("");
  const [data, setData] = useState<{
    customers: {
      customer_code: string;
      customer_name: string;
      percent: number;
      missing: string[];
      next_step: string;
      next_date: string | null;
      overdue: boolean;
    }[];
    unlinked: { visit_id: number; customer_name: string; is_valid: boolean; next_step: string; next_date: string | null }[];
  } | null>(null);
  const [open, setOpen] = useState<{
    customer_code: string;
    customer_name: string;
    percent: number;
    filled: string[];
    missing: string[];
    timeline: { id: number; narrative: string; outcome: string; is_valid: boolean; next_step: string; next_date: string | null }[];
    orders: { order_no: string; talk: string; due_date: string }[];
  } | null>(null);

  useEffect(() => {
    const handle = window.setTimeout(() => {
      api<NonNullable<typeof data>>(`/api/crm/mobile/customers?q=${encodeURIComponent(q)}`, role)
        .then(setData)
        .catch(() => setData(null));
    }, 200);
    return () => window.clearTimeout(handle);
  }, [q, role]);

  return (
    <div className="space-y-3">
      <input
        className="w-full rounded-2xl border px-3 py-2 text-sm"
        style={LINE}
        placeholder="搜客户"
        value={q}
        onChange={(e) => setQ(e.target.value)}
      />
      {data?.customers.map((row) => (
        <button
          key={row.customer_code}
          type="button"
          className={CARD}
          style={LINE}
          onClick={() => {
            api<NonNullable<typeof open>>(`/api/crm/mobile/customers/${row.customer_code}`, role).then(setOpen);
          }}
        >
          <span className="flex items-center justify-between gap-2">
            <span className="font-medium">{row.customer_name}</span>
            {row.overdue && <span className="h-2 w-2 rounded-full bg-amber-400" title="过期" />}
          </span>
          <Dots percent={row.percent} />
          <SlotChips missing={row.missing} />
        </button>
      ))}
      {(data?.unlinked.length ?? 0) > 0 && <p className="pt-2 text-xs font-medium text-[var(--text-muted)]">还没建客户</p>}
      {data?.unlinked.map((row) => (
        <Link
          key={row.visit_id}
          className={`${CARD} block text-sm`}
          style={LINE}
          to={`/crm/visit?customer_name=${encodeURIComponent(row.customer_name)}`}
        >
          {row.customer_name}
          <span className="mt-1 block text-xs text-[var(--text-muted)]">补上名称后才计入客户</span>
        </Link>
      ))}
      {open && (
        <div className="rounded-2xl border p-3 text-sm" style={LINE}>
          <div className="flex items-start justify-between">
            <p className="font-medium">{open.customer_name}</p>
            <button type="button" className="text-xs text-[var(--text-muted)]" onClick={() => setOpen(null)}>
              关闭
            </button>
          </div>
          <Dots percent={open.percent} filled={open.filled} />
          <SlotChips filled={open.filled} missing={open.missing} />
          <div className="mt-3 space-y-2">
            {open.timeline.map((row) => (
              <div key={row.id} className="rounded-xl border px-3 py-2 text-xs" style={LINE}>
                <Tag text={row.outcome} tone={row.is_valid ? "ok" : "amber"} />
                <p className="mt-1">{row.narrative}</p>
              </div>
            ))}
          </div>
          {open.orders.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-1">
              {open.orders.map((row) => (
                <Tag
                  key={row.order_no}
                  text={`${row.order_no} · ${row.talk}`}
                  tone={row.talk === "来不及" ? "rose" : row.talk === "交期内可做" ? "ok" : "muted"}
                />
              ))}
            </div>
          )}
          <Link
            className="mt-3 inline-block rounded-2xl bg-[var(--accent)] px-3 py-2 text-xs text-white"
            to={`/crm/visit?customer_code=${encodeURIComponent(open.customer_code)}&customer_name=${encodeURIComponent(open.customer_name)}`}
          >
            记录这次拜访
          </Link>
        </div>
      )}
    </div>
  );
}

function GoalSection({ title, block }: { title: string; block?: GoalBlock }) {
  if (!block) return null;
  return (
    <section>
      <p className="text-xs font-medium text-[var(--text-muted)]">
        {title} · {block.label}
      </p>
      <div className="mt-2 space-y-3">
        {block.lines.map((line) => {
          const gap = Math.max(line.gap, 0);
          const doneGoal = gap === 0 && line.target > 0;
          const ratio = goalRatio(line);
          return (
            <div key={line.metric}>
              <div className="flex items-baseline justify-between text-sm">
                <span>{line.metric}</span>
                <span className="tabular-nums">
                  {ratio.text}
                  {doneGoal ? " ✓" : ""}
                </span>
              </div>
              <Bar done={ratio.done} target={ratio.target} warn={gap > 0} />
              {gap > 0 && (
                <p className="mt-1 text-xs text-amber-300">
                  还差 {line.is_amount ? Number(gap).toFixed(2) : gap}
                </p>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}

function MetricsTab({
  role,
  blocks,
}: {
  role: string;
  blocks?: VisitHome["goal_blocks"];
}) {
  const [localBlocks, setLocalBlocks] = useState<VisitHome["goal_blocks"]>();
  const [funnel, setFunnel] = useState<{ stage: string; count: number; to_next_pct: number | null }[]>([]);
  useEffect(() => {
    if (!blocks) {
      api<VisitHome>("/api/crm/visits/home?today=2026-09-15", role).then((h) => setLocalBlocks(h.goal_blocks));
    }
    api<{ funnel: { steps: { stage: string; count: number; to_next_pct: number | null }[] } }>("/api/crm/board", role).then((data) =>
      setFunnel(data.funnel.steps),
    );
  }, [role, blocks]);
  const show = blocks ?? localBlocks;
  return (
    <div className="space-y-6">
      <GoalSection title="本年" block={show?.year} />
      <GoalSection title="本月" block={show?.month} />
      <GoalSection title="本周" block={show?.week} />
      <section>
        <p className="text-xs font-medium text-[var(--text-muted)]">转化到下一档</p>
        <div className="mt-2 space-y-3">
          {funnel.map((step) => {
            const nextName = FUNNEL_NEXT[step.stage];
            return (
              <div key={step.stage}>
                <div className="flex items-baseline justify-between text-sm">
                  <span>{step.stage}</span>
                  <span className="text-xs tabular-nums text-[var(--text-muted)]">
                    {nextName && step.to_next_pct != null
                      ? `${step.count} 次 · ${step.to_next_pct}% 到${nextName}`
                      : `${step.count} 次`}
                  </span>
                </div>
                <Bar done={step.to_next_pct ?? 100} target={100} />
              </div>
            );
          })}
        </div>
      </section>
    </div>
  );
}

type SalesOrder = {
  order_no: string;
  customer: string;
  item_name: string;
  due_date: string;
  talk: string;
  earliest: string | null;
  groups: string[];
  semi: string | null;
  finished: string | null;
};

function OrdersTab({ role }: { role: string }) {
  const [rows, setRows] = useState<SalesOrder[]>([]);
  const [open, setOpen] = useState<string | null>(null);
  const [plan, setPlan] = useState<{ title?: string; original_due?: string; eligible?: boolean; reason?: string; suggested_due?: string } | null>(null);
  useEffect(() => {
    api<SalesOrder[]>("/api/crm/mobile/orders", role).then(setRows).catch(() => setRows([]));
  }, [role]);
  return (
    <div className="space-y-3">
      <p className="text-xs text-[var(--text-muted)]">只看订单走到哪。改交期在电脑排程。</p>
      {rows.map((row) => (
        <button
          key={row.order_no}
          type="button"
          className={CARD}
          style={LINE}
          onClick={() => {
            setOpen(row.order_no);
            setPlan(null);
          }}
        >
          <span className="font-medium">
            {row.customer} · {row.item_name}
          </span>
          <span className="mt-1 block text-xs text-[var(--text-muted)]">约定交期 {row.due_date}</span>
          <span className="mt-2 flex flex-wrap items-center gap-1">
            <Tag
              text={row.talk}
              tone={row.talk === "来不及" ? "rose" : row.talk === "交期内可做" ? "ok" : "muted"}
            />
            {row.talk === "来不及" && row.earliest && <span className="text-xs text-rose-300">最快可交 {row.earliest}</span>}
          </span>
        </button>
      ))}
      {rows.length === 0 && <p className="text-xs text-[var(--text-muted)]">还没有挂到你名下或你拜访过的客户的订单。</p>}
      {open &&
        rows
          .filter((row) => row.order_no === open)
          .map((row) => {
            const semi = parseProgress(row.semi);
            const finished = parseProgress(row.finished);
            return (
              <div key={row.order_no} className="rounded-2xl border p-3 text-xs" style={LINE}>
                <p className="font-medium">{row.order_no}</p>
                <p className="mt-1 text-[var(--text-muted)]">组 {row.groups.join("、") || "还没排到组"}</p>
                <div className="mt-3 space-y-2">
                  <div>
                    <p>半成品 {semi ? `${semi.done}/${semi.plan}` : "无"}</p>
                    {semi && <Bar done={semi.done} target={semi.plan || 1} />}
                  </div>
                  <div>
                    <p>成品 {finished ? `${finished.done}/${finished.plan}` : "无"}</p>
                    {finished && <Bar done={finished.done} target={finished.plan || 1} />}
                  </div>
                </div>
                <button
                  type="button"
                  className="mt-3 rounded-2xl border px-3 py-2"
                  style={LINE}
                  onClick={() => {
                    api<NonNullable<typeof plan>>("/api/schedule/earliest-plan", role, {
                      method: "POST",
                      body: JSON.stringify({ order_no: row.order_no, today: "2026-09-15" }),
                    }).then(setPlan);
                  }}
                >
                  给销管的协商口径
                </button>
                {plan && (
                  <div className="mt-2 space-y-1">
                    <p>{plan.title || "提案 · 未改交期 · 未下发"}</p>
                    <p>原交期 {plan.original_due} 仍在。</p>
                    {plan.eligible ? <p>建议不早于 {plan.suggested_due}</p> : <p>{plan.reason}</p>}
                  </div>
                )}
              </div>
            );
          })}
    </div>
  );
}

type SpeechRec = {
  lang: string;
  start: () => void;
  onresult: (event: { results: { 0: { 0: { transcript: string } } } }) => void;
  onerror: () => void;
  onend: () => void;
};
