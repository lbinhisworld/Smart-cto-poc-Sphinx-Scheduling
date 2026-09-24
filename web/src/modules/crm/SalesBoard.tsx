import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../../shell/auth";

type Person = {
  visit_id?: number;
  customer_code: string | null;
  customer_name: string;
  owner_sales: string;
  outcome?: string;
  stage?: string;
  visit_count?: number;
  completeness_percent?: number;
  missing?: string[];
};
type FunnelStep = {
  stage: string;
  count: number;
  to_next_pct: number | null;
  stuck: { kind: string; name: string; customer_code: string | null; owner_sales: string }[];
};
type Band = {
  percent: number;
  count: number;
  people: {
    customer_code: string;
    customer_name: string;
    owner_sales: string;
    percent: number;
    missing: string[];
    visit_count: number;
  }[];
};
type MatrixCell = { stage: string; count: number; people: Person[] };
type MatrixRow = { outcome: string; cells: MatrixCell[] };
type FollowAction = {
  customer_code: string | null;
  customer_name: string;
  next_step: string;
  next_date: string;
  overdue: boolean;
  owner_sales: string;
};
type Board = {
  note: string;
  include_all?: boolean;
  outcomes?: string[];
  stages?: string[];
  matrix?: MatrixRow[];
  funnel: { steps: FunnelStep[]; overall_pct: number | null; lost: number; note: string };
  completeness: Band[];
  totals: {
    valid_visits: number;
    lost: number;
    shown_customers?: number;
    conversion_pct?: number | null;
  };
  alerts: { kind: string; text: string; owner_sales?: string }[];
  alerts_total?: number;
  follow_actions?: FollowAction[];
};
type Opp = { id: number; name: string; customer_code: string; owner_sales: string };
type MoneyRow = {
  id: number;
  name: string;
  owner_sales: string;
  urgent_order_no?: string | null;
  column_status?: Record<string, string>;
  visit_text?: { narrative: string; next_step: string; next_date: string | null; overdue: boolean } | null;
  sample_process?: { code: string; stage: string; item: string; round_no: number } | null;
  sample_cost?: { qty: number; material: string; labor_overhead: string } | null;
  bom?: { status: string };
  internal_quote?: { planned_labor: string; gap: string | null } | null;
  customer_quote?: { amount: string } | null;
  sign?: { status: string; project_code?: string | null };
};
type Plan = {
  title?: string;
  original_due?: string;
  eligible?: boolean;
  reason?: string;
  suggested_due?: string;
  sales_sentences?: string[];
};

const ALERT_LABEL: Record<string, string> = {
  拜访低于目标: "目标",
  打样停滞: "打样",
  报价停滞: "报价",
  未打样: "转化",
  多次建联: "建联",
  拜访未齐: "完整度",
  信息齐了还没打样: "打样",
};

async function api<T>(path: string, role: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", "X-Demo-Role": role, ...init?.headers },
  });
  const body = await res.json();
  if (!res.ok || body.code !== 0) throw new Error(body.detail || body.message || "请求失败");
  return body.data as T;
}

function cellHeat(count: number, max: number): string {
  if (count <= 0) return "transparent";
  const t = max <= 0 ? 0 : count / max;
  if (t >= 0.7) return "rgba(245, 158, 11, 0.35)";
  if (t >= 0.35) return "rgba(245, 158, 11, 0.2)";
  return "rgba(245, 158, 11, 0.12)";
}

export function SalesBoard() {
  const auth = useAuth();
  const role = auth.role;
  const [board, setBoard] = useState<Board | null>(null);
  const [picked, setPicked] = useState<Person | null>(null);
  const [opps, setOpps] = useState<Opp[]>([]);
  const [detail, setDetail] = useState<MoneyRow | null>(null);
  const [plan, setPlan] = useState<Plan | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [includeAll, setIncludeAll] = useState(false);
  const [showMore, setShowMore] = useState(false);
  const [selectedCell, setSelectedCell] = useState<string | null>(null);
  const [matrixListed, setMatrixListed] = useState<{ label: string; people: Person[] } | null>(null);

  const load = () => {
    if (!role) return;
    const q = includeAll ? "?include_all=true" : "";
    api<Board>(`/api/crm/board${q}`, role)
      .then((data) => {
        setBoard(data);
        if (!selectedCell && data.matrix) {
          let best: { key: string; label: string; people: Person[]; count: number } | null = null;
          for (const row of data.matrix) {
            for (const cell of row.cells) {
              if (cell.count <= 0) continue;
              const key = `${row.outcome}|${cell.stage}`;
              if (!best || cell.count > best.count) {
                best = {
                  key,
                  label: `${row.outcome} · ${cell.stage}`,
                  people: cell.people.map((p) => ({ ...p, outcome: row.outcome, stage: cell.stage })),
                  count: cell.count,
                };
              }
            }
          }
          if (best) {
            setSelectedCell(best.key);
            setMatrixListed({ label: best.label, people: best.people });
          }
        }
      })
      .catch((e) => setError(String(e)));
  };

  useEffect(() => {
    setSelectedCell(null);
    setMatrixListed(null);
    load();
  }, [role, includeAll]);

  const matrixMax = useMemo(() => {
    if (!board?.matrix) return 1;
    return Math.max(...board.matrix.flatMap((r) => r.cells.map((c) => c.count)), 1);
  }, [board]);

  const openPerson = (person: Person) => {
    if (!role) return;
    setPicked(person);
    setDetail(null);
    setPlan(null);
    api<Opp[]>("/api/crm/opportunities", role)
      .then((rows) => {
        const mine = rows.filter((row) => person.customer_code && row.customer_code === person.customer_code);
        setOpps(mine);
        if (mine[0]) {
          return api<MoneyRow>(`/api/crm/opportunities/${mine[0].id}`, role).then(setDetail);
        }
        return undefined;
      })
      .catch((e) => setError(String(e)));
  };

  const pickCell = (outcome: string, stage: string, people: Person[]) => {
    const key = `${outcome}|${stage}`;
    setSelectedCell(key);
    setMatrixListed({
      label: `${outcome} · ${stage}`,
      people: people.map((p) => ({ ...p, outcome, stage })),
    });
    setPicked(null);
    setDetail(null);
  };

  const stageCols = board?.stages ?? ["还没成商机", "打样", "报价", "签单"];

  return (
    <div className="mt-4 space-y-4">
      {error && <p className="text-xs text-rose-400">{error}</p>}

      {board && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {[
            { label: "分布客户", value: board.totals.shown_customers ?? "—" },
            { label: "有效拜访", value: board.totals.valid_visits },
            { label: "签单转化", value: board.totals.conversion_pct != null ? `${board.totals.conversion_pct}%` : "—" },
            { label: "丢单停住", value: board.totals.lost },
          ].map((kpi) => (
            <div
              key={kpi.label}
              className="rounded-xl border px-4 py-3"
              style={{ borderColor: "var(--line)", background: "var(--bg-card)" }}
            >
              <p className="text-[11px] text-[var(--text-muted)]">{kpi.label}</p>
              <p className="mt-1 text-2xl font-semibold tabular-nums">{kpi.value}</p>
            </div>
          ))}
        </div>
      )}

      <div
        className="rounded-xl border p-4"
        style={{ borderColor: "var(--line)", background: "var(--bg-card)" }}
      >
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h3 className="text-sm font-semibold">拜访成果 × 商机阶段</h3>
            <p className="mt-0.5 text-[11px] text-[var(--text-muted)]">
              默认只计已确认且满 15 分钟的有效拜访。点格子看客户名单，再点客户看商机单据列。
            </p>
          </div>
          <label className="flex items-center gap-2 text-xs text-[var(--text-muted)]">
            <input
              type="checkbox"
              checked={includeAll}
              onChange={(e) => setIncludeAll(e.target.checked)}
            />
            全部拜访
          </label>
        </div>

        {board?.matrix && (
          <div className="mt-4 overflow-x-auto">
            <table className="w-full min-w-[560px] border-collapse text-sm">
              <thead>
                <tr className="text-xs text-[var(--text-muted)]">
                  <th className="px-2 py-2 text-left">成果 \ 阶段</th>
                  {stageCols.map((st) => (
                    <th key={st} className="px-2 py-2 text-center font-medium">
                      {st}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {board.matrix.map((row) => (
                  <tr key={row.outcome}>
                    <td className="px-2 py-3 text-xs font-medium">{row.outcome}</td>
                    {row.cells.map((cell) => {
                      const key = `${row.outcome}|${cell.stage}`;
                      const selected = selectedCell === key;
                      return (
                        <td key={cell.stage} className="p-1.5 text-center">
                          <button
                            type="button"
                            disabled={cell.count === 0}
                            className={`min-w-[3rem] rounded-lg px-3 py-2 text-base font-semibold tabular-nums transition ${
                              cell.count === 0 ? "text-[var(--text-muted)] opacity-40" : "hover:ring-1 hover:ring-amber-500/50"
                            } ${selected ? "ring-2 ring-amber-400" : ""}`}
                            style={{
                              background: cellHeat(cell.count, matrixMax),
                              borderColor: selected ? "#fbbf24" : "transparent",
                            }}
                            onClick={() => pickCell(row.outcome, cell.stage, cell.people)}
                          >
                            {cell.count}
                          </button>
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {matrixListed && (
          <div className="mt-4 border-t pt-4" style={{ borderColor: "var(--line)" }}>
            <p className="text-xs font-medium text-[var(--text-muted)]">{matrixListed.label} · {matrixListed.people.length} 家</p>
            <div className="mt-3 grid gap-2 md:grid-cols-2">
              {matrixListed.people.map((person) => (
                <button
                  key={`m-${person.customer_code}-${person.customer_name}`}
                  type="button"
                  className="rounded-lg border px-3 py-2.5 text-left transition hover:border-amber-500/40"
                  style={{ borderColor: "var(--line)", background: "var(--bg)" }}
                  onClick={() => openPerson(person)}
                >
                  <div className="flex items-start justify-between gap-2">
                    <span className="font-medium text-[var(--accent)]">{person.customer_name}</span>
                    <span className="text-[10px] text-[var(--text-muted)]">{person.owner_sales}</span>
                  </div>
                  <p className="mt-1 text-[11px] text-[var(--text-muted)]">
                    有效拜访 {person.visit_count ?? 0} 次 · 完整度 {person.completeness_percent ?? 0}%
                  </p>
                  {(person.missing?.length ?? 0) > 0 && (
                    <p className="mt-0.5 text-[10px] text-amber-200/90">还缺：{person.missing?.join("、")}</p>
                  )}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {(board?.alerts.length ?? 0) > 0 && (
        <div
          className="rounded-xl border p-4"
          style={{ borderColor: "rgba(245,158,11,0.35)", background: "rgba(120,53,15,0.15)" }}
        >
          <div className="flex items-center justify-between gap-2">
            <h3 className="text-sm font-semibold text-amber-100">销管关注</h3>
            {(board?.alerts_total ?? 0) > (board?.alerts.length ?? 0) && (
              <span className="text-[10px] text-amber-200/70">
                展示 {board?.alerts.length} / {board?.alerts_total} 条
              </span>
            )}
          </div>
          <ul className="mt-2 space-y-2">
            {board?.alerts.map((alert) => (
              <li key={alert.text} className="flex gap-2 text-xs text-amber-50/95">
                <span className="shrink-0 rounded bg-amber-900/60 px-1.5 py-0.5 text-[10px]">
                  {ALERT_LABEL[alert.kind] ?? alert.kind}
                </span>
                <span>{alert.text}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {(board?.follow_actions?.length ?? 0) > 0 && (
        <div className="rounded-xl border p-4" style={{ borderColor: "var(--line)", background: "var(--bg-card)" }}>
          <h3 className="text-sm font-semibold">下一步该跟进</h3>
          <p className="mt-0.5 text-[11px] text-[var(--text-muted)]">来自已确认拜访的 SOP，过期标黄</p>
          <div className="mt-3 grid gap-2 md:grid-cols-2 lg:grid-cols-3">
            {board?.follow_actions.map((action) => (
              <Link
                key={`${action.customer_name}-${action.next_date}`}
                to={`/crm/visit?customer_code=${encodeURIComponent(action.customer_code ?? "")}&customer_name=${encodeURIComponent(action.customer_name)}`}
                className="rounded-lg border px-3 py-2 text-xs"
                style={{
                  borderColor: action.overdue ? "#f59e0b" : "var(--line)",
                  background: "var(--bg)",
                }}
              >
                <span className="font-medium">{action.customer_name}</span>
                <span className="mt-1 block text-[var(--text-muted)]">
                  {action.next_step} · {action.next_date}
                  {action.overdue ? " · 已过期" : ""}
                </span>
                <span className="text-[10px] text-[var(--text-muted)]">{action.owner_sales}</span>
              </Link>
            ))}
          </div>
        </div>
      )}

      <button
        type="button"
        className="text-xs text-[var(--accent)]"
        onClick={() => setShowMore((v) => !v)}
      >
        {showMore ? "收起" : "展开"}漏斗与拜访完整度
      </button>
      {showMore && board && (
        <div className="rounded-xl border p-4 text-xs" style={{ borderColor: "var(--line)" }}>
          <p className="text-[var(--text-muted)]">{board.funnel.note}</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {board.funnel.steps.map((step) => (
              <span key={step.stage} className="rounded-full border px-2 py-1 tabular-nums" style={{ borderColor: "var(--line)" }}>
                {step.stage} {step.count}
              </span>
            ))}
          </div>
          <div className="mt-4 grid grid-cols-3 gap-2 md:grid-cols-6">
            {board.completeness.map((band) => (
              <div key={band.percent} className="rounded border px-2 py-2" style={{ borderColor: "var(--line)" }}>
                <p className="text-[var(--text-muted)]">{band.percent}%</p>
                <p className="text-lg font-semibold tabular-nums">{band.count}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {picked && picked.customer_name && (
        <div className="rounded-xl border p-4 text-sm shadow-lg" style={{ borderColor: "var(--line)", background: "var(--bg-card)" }}>
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-lg font-semibold">{picked.customer_name}</p>
              <p className="text-xs text-[var(--text-muted)]">
                {picked.outcome} · {picked.stage} · {picked.owner_sales}
              </p>
            </div>
            <button type="button" className="text-xs text-[var(--text-muted)]" onClick={() => setPicked(null)}>
              关闭
            </button>
          </div>
          <div className="mt-3 flex flex-wrap gap-2 text-xs">
            <Link
              className="rounded-lg border px-3 py-1.5 font-medium"
              style={{ borderColor: "var(--line)" }}
              to={`/crm/visit?customer_code=${encodeURIComponent(picked.customer_code ?? "")}&customer_name=${encodeURIComponent(picked.customer_name)}`}
            >
              再去拜访
            </Link>
            {!detail && (
              <Link
                className="rounded-lg border px-3 py-1.5"
                style={{ borderColor: "var(--line)" }}
                to={`/crm/visit?customer_name=${encodeURIComponent(picked.customer_name)}`}
              >
                补成商机
              </Link>
            )}
          </div>
          {detail && (
            <WideRow detail={detail} role={role ?? ""} onReload={() => openPerson(picked)} plan={plan} setPlan={setPlan} />
          )}
          {opps.length > 1 && (
            <div className="mt-3 flex flex-wrap gap-2 text-xs">
              {opps.map((opp) => (
                <button
                  key={opp.id}
                  type="button"
                  className="rounded border px-2 py-1"
                  style={{ borderColor: "var(--line)" }}
                  onClick={() => role && api<MoneyRow>(`/api/crm/opportunities/${opp.id}`, role).then(setDetail)}
                >
                  {opp.name}
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function WideRow({
  detail,
  role,
  onReload,
  plan,
  setPlan,
}: {
  detail: MoneyRow;
  role: string;
  onReload: () => void;
  plan: Plan | null;
  setPlan: (plan: Plan | null) => void;
}) {
  const status = detail.column_status ?? {};
  const [reason, setReason] = useState("价格");
  const [msg, setMsg] = useState("");

  return (
    <div className="mt-4 space-y-3 text-xs">
      <p className="text-[11px] font-medium text-[var(--text-muted)]">商机单据列（打样 / 报价 / 签单进度）</p>
      <div className="grid grid-cols-2 gap-2 md:grid-cols-3">
        {Object.entries(status).map(([key, value]) => (
          <div key={key} className="rounded-lg border px-2 py-2" style={{ borderColor: "var(--line)" }}>
            <p className="text-[var(--text-muted)]">{key}</p>
            <p className="mt-1 font-medium">{value}</p>
          </div>
        ))}
      </div>
      {detail.visit_text && (
        <p className={detail.visit_text.overdue ? "text-amber-300" : ""}>
          {detail.visit_text.narrative} · 下一步 {detail.visit_text.next_step} {detail.visit_text.next_date}
        </p>
      )}
      {detail.sample_process && (
        <p>
          打样 {detail.sample_process.code} {detail.sample_process.item} · 第 {detail.sample_process.round_no} 轮 ·{" "}
          {detail.sample_process.stage}
        </p>
      )}
      {detail.sample_cost && (
        <p>
          打样成本 数量 {detail.sample_cost.qty} · 物料 {detail.sample_cost.material} · 人工制费 {detail.sample_cost.labor_overhead}
        </p>
      )}
      {detail.bom && <p>工时 / BOM：{detail.bom.status}</p>}
      {detail.internal_quote && (
        <p>
          计划人工 {detail.internal_quote.planned_labor}
          {detail.internal_quote.gap != null ? ` · 与售价差额 ${detail.internal_quote.gap}` : ""}
        </p>
      )}
      {detail.customer_quote && <p>对客报价 {detail.customer_quote.amount}</p>}
      {detail.sign && (
        <p>
          签单 {detail.sign.status}
          {detail.sign.project_code ? ` · ${detail.sign.project_code}` : ""}
        </p>
      )}

      {detail.urgent_order_no && (role === "GM" || role === "SALES_MGR" || role === "SALES" || role === "SALES_ASSIST") && (
        <button
          type="button"
          className="rounded border px-2 py-1"
          style={{ borderColor: "var(--line)" }}
          onClick={() => {
            api<Plan>("/api/schedule/earliest-plan", role, {
              method: "POST",
              body: JSON.stringify({ order_no: detail.urgent_order_no, today: "2026-09-15" }),
            })
              .then(setPlan)
              .catch((e) => setMsg(String(e)));
          }}
        >
          打开最快方案
        </button>
      )}
      {plan && (
        <div className="rounded border border-amber-700/60 bg-amber-950/30 p-3">
          <p className="font-medium">{plan.title || "提案 · 未改交期 · 未下发"}</p>
          <p className="mt-1">原交期 {plan.original_due} 仍在。</p>
          {plan.eligible ? (
            <>
              <p>建议不早于 {plan.suggested_due}</p>
              {(plan.sales_sentences ?? []).map((line) => (
                <p key={line}>{line}</p>
              ))}
            </>
          ) : (
            <p>{plan.reason}</p>
          )}
        </div>
      )}

      {(role === "GM" || role === "SALES_MGR") && (
        <button
          type="button"
          className="rounded border px-2 py-1"
          style={{ borderColor: "var(--line)" }}
          onClick={() => {
            api(`/api/crm/opportunities/${detail.id}/grade`, role, {
              method: "POST",
              body: JSON.stringify({ grade: "A" }),
            })
              .then(() => {
                setMsg("已标 A 级，签单格为已转项目");
                onReload();
              })
              .catch((e) => setMsg(String(e)));
          }}
        >
          标成 A 级并转项目
        </button>
      )}
      {(role === "GM" || role === "SALES" || role === "SALES_MGR" || role === "SALES_ASSIST") && (
        <div className="flex items-center gap-2">
          <select
            className="rounded border px-2 py-1"
            style={{ borderColor: "var(--line)", background: "var(--bg-card)" }}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          >
            {["价格", "交期", "样品未过", "客户取消", "其他"].map((item) => (
              <option key={item}>{item}</option>
            ))}
          </select>
          <button
            type="button"
            className="rounded border px-2 py-1"
            style={{ borderColor: "var(--line)" }}
            onClick={() => {
              api(`/api/crm/opportunities/${detail.id}/lose`, role, {
                method: "POST",
                body: JSON.stringify({ reason }),
              })
                .then(() => setMsg("已标丢单"))
                .catch((e) => setMsg(String(e)));
            }}
          >
            丢单
          </button>
        </div>
      )}
      {msg && <p>{msg}</p>}
    </div>
  );
}
