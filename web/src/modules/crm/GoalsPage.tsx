import { Fragment, useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { requestWithRole } from "../../api/client";
import { useAuth } from "../../shell/auth";

const METRICS = ["新增客户数", "拜访量", "签约金额", "回款金额"] as const;
const QTY_METRICS = new Set<string>(["新增客户数", "拜访量"]);

type YearForm = {
  owner_sales: string;
  owner_dept: string;
  targets: Record<(typeof METRICS)[number], string>;
  auto_split: boolean;
};

const emptyForm = (): YearForm => ({
  owner_sales: "李业务",
  owner_dept: "销售部",
  targets: {
    新增客户数: "48",
    拜访量: "144",
    签约金额: "360000",
    回款金额: "240000",
  },
  auto_split: true,
});

type MetricCell = {
  target: number | string;
  done: number | string;
  gap: number | string;
  kind: "qty" | "amount";
};

type WeekNode = {
  period_key: string;
  period_label: string;
  metrics: Record<string, MetricCell>;
};

type MonthNode = {
  period_key: string;
  period_label: string;
  metrics: Record<string, MetricCell>;
  weeks: WeekNode[];
};

type YearNode = {
  owner_sales: string;
  owner_dept: string;
  period_key: string;
  period_label: string;
  metrics: Record<string, MetricCell>;
  months: MonthNode[];
};

function fmtCell(m: MetricCell | undefined) {
  if (!m) return "—";
  if (m.kind === "amount") return `${m.done} / ${m.target}`;
  return `${m.done} / ${m.target}`;
}

async function postCrm(path: string, headers: HeadersInit, body: unknown) {
  const res = await fetch(path, {
    method: "POST",
    headers: { ...headers, "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const raw = await res.text();
  let json: { code?: number; message?: string; detail?: string | unknown } = {};
  try {
    json = JSON.parse(raw) as typeof json;
  } catch {
    throw new Error(raw.slice(0, 200) || `${res.status} ${res.statusText}`);
  }
  if (!res.ok) {
    const detail =
      typeof json.detail === "string"
        ? json.detail
        : json.message || (raw.slice(0, 200) || `${res.status} 请求失败`);
    throw new Error(detail);
  }
  if (json.code !== undefined && json.code !== 0) {
    throw new Error(json.message || "请求失败");
  }
}

export function GoalsPage() {
  const auth = useAuth();
  const role = auth.role;
  const canEdit = role === "GM" || role === "SALES_MGR";
  const [year, setYear] = useState(2026);
  const [monthFrom, setMonthFrom] = useState(1);
  const [monthTo, setMonthTo] = useState(12);
  const [ownerFilter, setOwnerFilter] = useState("");
  const [trees, setTrees] = useState<YearNode[]>([]);
  const [openYears, setOpenYears] = useState<Set<string>>(new Set());
  const [openMonths, setOpenMonths] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [owners, setOwners] = useState<string[]>([]);
  const [formOpen, setFormOpen] = useState(true);
  const [form, setForm] = useState<YearForm>(() => emptyForm());

  useEffect(() => {
    if (!role || !canEdit) return;
    requestWithRole<string[]>("/api/crm/goals/owners", role)
      .then((rows) => setOwners(rows.length ? rows : ["李业务"]))
      .catch(() => setOwners(["李业务"]));
  }, [role, canEdit]);

  const load = useCallback(async () => {
    if (!role) return;
    const q = new URLSearchParams({
      year: String(year),
      month_from: String(monthFrom),
      month_to: String(monthTo),
    });
    if (ownerFilter.trim()) q.set("owner_sales", ownerFilter.trim());
    try {
      const rows = await requestWithRole<YearNode[]>(`/api/crm/goals/periods?${q}`, role);
      setTrees(rows);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [year, monthFrom, monthTo, ownerFilter, role]);

  useEffect(() => {
    load();
  }, [load]);

  const toggle = (set: Set<string>, key: string, setter: (s: Set<string>) => void) => {
    const next = new Set(set);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    setter(next);
  };

  const splitYear = async (owner: string) => {
    if (!role) return;
    if (
      !window.confirm(
        `将 ${owner} 的 ${year} 年目标均分到各月、各周？\n已手改过的月/周会被覆盖。`,
      )
    ) {
      return;
    }
    setBusy(true);
    setNotice(null);
    setError(null);
    try {
      await postCrm("/api/crm/goals/split", auth.headers(), { owner_sales: owner, year: Number(year) });
      const yKey = `${owner}-${year}`;
      setOpenYears((prev) => new Set(prev).add(yKey));
      setNotice(`已拆分：${owner} · ${year} 年（月、周已重算）`);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const splitMonth = async (owner: string, periodKey: string) => {
    if (!role) return;
    const month = Number(periodKey.split("-")[1]);
    if (!Number.isFinite(month)) return;
    if (!window.confirm(`将 ${owner} 的 ${periodKey} 目标均分到该月各周？`)) return;
    setBusy(true);
    setNotice(null);
    setError(null);
    try {
      await postCrm("/api/crm/goals/split", auth.headers(), {
        owner_sales: owner,
        year: Number(year),
        month,
      });
      const yKey = `${owner}-${year}`;
      setOpenYears((prev) => new Set(prev).add(yKey));
      setOpenMonths((prev) => new Set(prev).add(`${yKey}-${periodKey}`));
      setNotice(`已拆分：${owner} · ${periodKey} → 各周`);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const fillFormFromYear = (node: YearNode) => {
    const targets = { ...emptyForm().targets };
    for (const m of METRICS) {
      const cell = node.metrics[m];
      if (cell) targets[m] = String(cell.target);
    }
    setForm({
      owner_sales: node.owner_sales,
      owner_dept: node.owner_dept,
      targets,
      auto_split: true,
    });
    setYear(Number(node.period_key) || year);
    setFormOpen(true);
  };

  const saveYearGoal = async () => {
    if (!role) return;
    const owner = form.owner_sales.trim();
    if (!owner) {
      setError("请选择或填写目标人");
      return;
    }
    const targets: Record<string, number | string> = {};
    for (const m of METRICS) {
      const raw = form.targets[m].trim();
      if (!raw) {
        setError(`请填写${m}`);
        return;
      }
      if (QTY_METRICS.has(m)) {
        const n = Number.parseInt(raw, 10);
        if (!Number.isFinite(n) || n < 0) {
          setError(`${m} 须为非负整数`);
          return;
        }
        targets[m] = n;
      } else {
        const n = Number.parseFloat(raw);
        if (!Number.isFinite(n) || n < 0) {
          setError(`${m} 须为非负金额`);
          return;
        }
        targets[m] = n.toFixed(2);
      }
    }
    setBusy(true);
    setNotice(null);
    setError(null);
    try {
      await postCrm("/api/crm/goals/year", auth.headers(), {
        owner_sales: owner,
        owner_dept: form.owner_dept.trim() || "销售部",
        year: Number(year),
        targets,
        auto_split: form.auto_split,
      });
      const yKey = `${owner}-${year}`;
      setOpenYears((prev) => new Set(prev).add(yKey));
      setNotice(form.auto_split ? `已保存 ${owner} · ${year} 年目标，并已拆到月/周` : `已保存 ${owner} · ${year} 年目标`);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const deleteYear = async (owner: string) => {
    if (!role) return;
    if (!window.confirm(`删除 ${owner} ${year} 年目标及下属月、周？`)) return;
    setBusy(true);
    setNotice(null);
    try {
      await requestWithRole(
        `/api/crm/goals/periods?owner_sales=${encodeURIComponent(owner)}&year=${year}`,
        role,
        { method: "DELETE" },
      );
      setNotice(`已删除 ${owner} · ${year} 年目标`);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="px-6 py-4">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold">目标管理</h1>
          <p className="mt-1 text-xs text-[var(--text-muted)]">
            年 → 月 → 周展开；完成数按发生日归期。业务员在
            <Link to="/crm/visit?tab=metrics" className="mx-1 text-[var(--accent)] underline">
              销售移动端 · 指标
            </Link>
            查看本年 / 本月 / 本周。
          </p>
        </div>
        <Link
          to="/crm/visit"
          className="rounded border px-3 py-1.5 text-xs text-[var(--text-muted)] hover:text-[var(--text-body)]"
          style={{ borderColor: "var(--line)" }}
        >
          销售移动端
        </Link>
      </div>

      {!canEdit && (
        <p className="mb-3 rounded-lg border border-amber-500/40 bg-amber-950/30 px-3 py-2 text-xs text-amber-100">
          当前角色仅可查看完成数。目标拆分、删除请使用总经理或销管账号登录。
        </p>
      )}
      {notice && <p className="mb-3 text-sm text-emerald-400">{notice}</p>}
      {error && <p className="mb-3 text-sm text-rose-400">{error}</p>}
      {busy && <p className="mb-3 text-xs text-[var(--text-muted)]">处理中…</p>}

      {canEdit && (
        <div
          className="mb-4 rounded-lg border p-4 text-sm"
          style={{ borderColor: "var(--line)", background: "var(--bg-card)" }}
        >
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <p className="font-medium">设置全年目标</p>
            <button
              type="button"
              className="text-xs text-[var(--text-muted)] underline"
              onClick={() => setFormOpen((v) => !v)}
            >
              {formOpen ? "收起" : "展开"}
            </button>
          </div>
          {formOpen && (
            <>
              <p className="mb-3 text-xs text-[var(--text-muted)]">
                先选定目标人与目标年，填写四项全年指标。勾选「保存后自动拆分」会均分到 12 个月及各周（覆盖已有月/周目标）。
              </p>
              <div className="flex flex-wrap gap-3">
                <label className="flex flex-col gap-1 text-xs text-[var(--text-muted)]">
                  目标人
                  <input
                    list="goal-owner-options"
                    className="rounded border px-2 py-1 w-32"
                    style={{ borderColor: "var(--line)", background: "var(--bg-body)" }}
                    value={form.owner_sales}
                    onChange={(e) => setForm({ ...form, owner_sales: e.target.value })}
                  />
                  <datalist id="goal-owner-options">
                    {owners.map((o) => (
                      <option key={o} value={o} />
                    ))}
                  </datalist>
                </label>
                <label className="flex flex-col gap-1 text-xs text-[var(--text-muted)]">
                  目标部门
                  <input
                    className="rounded border px-2 py-1 w-28"
                    style={{ borderColor: "var(--line)", background: "var(--bg-body)" }}
                    value={form.owner_dept}
                    onChange={(e) => setForm({ ...form, owner_dept: e.target.value })}
                  />
                </label>
                <label className="flex flex-col gap-1 text-xs text-[var(--text-muted)]">
                  目标年
                  <input
                    type="number"
                    className="rounded border px-2 py-1 w-24"
                    style={{ borderColor: "var(--line)", background: "var(--bg-body)" }}
                    value={year}
                    onChange={(e) => setYear(Number(e.target.value))}
                  />
                </label>
              </div>
              <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {METRICS.map((m) => (
                  <label key={m} className="flex flex-col gap-1 text-xs text-[var(--text-muted)]">
                    {m}
                    <input
                      type="text"
                      inputMode={QTY_METRICS.has(m) ? "numeric" : "decimal"}
                      className="rounded border px-2 py-1 tabular-nums"
                      style={{ borderColor: "var(--line)", background: "var(--bg-body)" }}
                      value={form.targets[m]}
                      onChange={(e) =>
                        setForm({ ...form, targets: { ...form.targets, [m]: e.target.value } })
                      }
                    />
                  </label>
                ))}
              </div>
              <div className="mt-3 flex flex-wrap items-center gap-3">
                <label className="flex items-center gap-2 text-xs text-[var(--text-muted)]">
                  <input
                    type="checkbox"
                    checked={form.auto_split}
                    onChange={(e) => setForm({ ...form, auto_split: e.target.checked })}
                  />
                  保存后自动拆到月、周
                </label>
                <button
                  type="button"
                  disabled={busy}
                  className="rounded bg-[var(--accent)] px-4 py-1.5 text-xs text-white disabled:opacity-50"
                  onClick={() => void saveYearGoal()}
                >
                  保存全年目标
                </button>
              </div>
            </>
          )}
        </div>
      )}

      <div
        className="mb-4 flex flex-wrap gap-3 rounded-lg border p-3 text-sm"
        style={{ borderColor: "var(--line)", background: "var(--bg-card)" }}
      >
        <label className="flex flex-col gap-1 text-xs text-[var(--text-muted)]">
          目标年
          <input
            type="number"
            className="rounded border px-2 py-1 w-24"
            style={{ borderColor: "var(--line)", background: "var(--bg-body)" }}
            value={year}
            onChange={(e) => setYear(Number(e.target.value))}
          />
        </label>
        <label className="flex flex-col gap-1 text-xs text-[var(--text-muted)]">
          目标月起
          <input
            type="number"
            min={1}
            max={12}
            className="rounded border px-2 py-1 w-20"
            style={{ borderColor: "var(--line)", background: "var(--bg-body)" }}
            value={monthFrom}
            onChange={(e) => setMonthFrom(Number(e.target.value))}
          />
        </label>
        <label className="flex flex-col gap-1 text-xs text-[var(--text-muted)]">
          目标月止
          <input
            type="number"
            min={1}
            max={12}
            className="rounded border px-2 py-1 w-20"
            style={{ borderColor: "var(--line)", background: "var(--bg-body)" }}
            value={monthTo}
            onChange={(e) => setMonthTo(Number(e.target.value))}
          />
        </label>
        <label className="flex flex-col gap-1 text-xs text-[var(--text-muted)]">
          目标人
          <input
            className="rounded border px-2 py-1 w-28"
            style={{ borderColor: "var(--line)", background: "var(--bg-body)" }}
            placeholder="全部"
            value={ownerFilter}
            onChange={(e) => setOwnerFilter(e.target.value)}
          />
        </label>
        <button
          type="button"
          className="self-end rounded bg-[var(--accent)] px-3 py-1.5 text-xs text-white"
          onClick={() => load()}
        >
          筛选
        </button>
      </div>

      <div className="overflow-x-auto rounded-lg border" style={{ borderColor: "var(--line)" }}>
        <table className="w-full min-w-[960px] text-left text-xs">
          <thead style={{ background: "var(--bg-nav)" }}>
            <tr>
              <th className="px-3 py-2 font-medium">期间 / 目标人</th>
              <th className="px-3 py-2 font-medium">部门</th>
              {METRICS.map((m) => (
                <th key={m} className="px-3 py-2 font-medium">
                  {m}
                  <span className="block font-normal text-[10px] text-[var(--text-muted)]">完成/目标</span>
                </th>
              ))}
              {canEdit && (
                <th
                  className="sticky right-0 z-10 px-3 py-2 font-medium"
                  style={{ background: "var(--bg-nav)" }}
                >
                  操作
                </th>
              )}
            </tr>
          </thead>
          <tbody>
            {trees.map((y) => {
              const yKey = `${y.owner_sales}-${y.period_key}`;
              const yOpen = openYears.has(yKey);
              return (
                <Fragment key={yKey}>
                  <tr className="border-t" style={{ borderColor: "var(--line)" }}>
                    <td className="px-3 py-2">
                      <button
                        type="button"
                        className="mr-2 text-[var(--accent)]"
                        onClick={() => toggle(openYears, yKey, setOpenYears)}
                      >
                        {yOpen ? "▼" : "▶"}
                      </button>
                      {y.period_label} · {y.owner_sales}
                    </td>
                    <td className="px-3 py-2">{y.owner_dept}</td>
                    {METRICS.map((m) => (
                      <td key={m} className="px-3 py-2 tabular-nums">
                        {fmtCell(y.metrics[m])}
                      </td>
                    ))}
                    {canEdit && (
                      <td
                        className="sticky right-0 z-10 px-3 py-2"
                        style={{ background: "var(--bg-body)" }}
                      >
                        <div className="flex flex-wrap gap-1.5">
                          <button
                            type="button"
                            disabled={busy}
                            className="rounded border px-2 py-1 text-[11px] disabled:opacity-50"
                            style={{ borderColor: "var(--line)" }}
                            onClick={(e) => {
                              e.stopPropagation();
                              fillFormFromYear(y);
                            }}
                          >
                            编辑
                          </button>
                          <button
                            type="button"
                            disabled={busy}
                            className="rounded border px-2 py-1 text-[11px] text-[var(--accent)] disabled:opacity-50"
                            style={{ borderColor: "var(--line)" }}
                            onClick={(e) => {
                              e.stopPropagation();
                              void splitYear(y.owner_sales);
                            }}
                          >
                            重新拆分
                          </button>
                          <button
                            type="button"
                            disabled={busy}
                            className="rounded border px-2 py-1 text-[11px] text-rose-300 disabled:opacity-50"
                            style={{ borderColor: "var(--line)" }}
                            onClick={(e) => {
                              e.stopPropagation();
                              void deleteYear(y.owner_sales);
                            }}
                          >
                            删除
                          </button>
                        </div>
                      </td>
                    )}
                  </tr>
                  {yOpen &&
                    y.months.map((mo) => {
                      const mKey = `${yKey}-${mo.period_key}`;
                      const mOpen = openMonths.has(mKey);
                      return (
                        <Fragment key={mKey}>
                          <tr className="border-t bg-black/10" style={{ borderColor: "var(--line)" }}>
                            <td className="px-3 py-2 pl-8">
                              <button
                                type="button"
                                className="mr-2 text-[var(--accent)]"
                                onClick={() => toggle(openMonths, mKey, setOpenMonths)}
                              >
                                {mOpen ? "▼" : "▶"}
                              </button>
                              {mo.period_label}
                            </td>
                            <td />
                            {METRICS.map((m) => (
                              <td key={m} className="px-3 py-2 tabular-nums">
                                {fmtCell(mo.metrics[m])}
                              </td>
                            ))}
                            {canEdit && (
                              <td
                                className="sticky right-0 z-10 px-3 py-2"
                                style={{ background: "rgba(0,0,0,0.15)" }}
                              >
                                <button
                                  type="button"
                                  disabled={busy}
                                  className="rounded border px-2 py-1 text-[11px] text-[var(--accent)] disabled:opacity-50"
                                  style={{ borderColor: "var(--line)" }}
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    void splitMonth(y.owner_sales, mo.period_key);
                                  }}
                                >
                                  拆到周
                                </button>
                              </td>
                            )}
                          </tr>
                          {mOpen &&
                            mo.weeks.map((w) => (
                              <tr
                                key={`${mKey}-${w.period_key}`}
                                className="border-t bg-black/20"
                                style={{ borderColor: "var(--line)" }}
                              >
                                <td className="px-3 py-2 pl-14 text-[var(--text-muted)]">{w.period_label}</td>
                                <td />
                                {METRICS.map((m) => (
                                  <td key={m} className="px-3 py-2 tabular-nums">
                                    {fmtCell(w.metrics[m])}
                                  </td>
                                ))}
                                {canEdit && <td />}
                              </tr>
                            ))}
                        </Fragment>
                      );
                    })}
                </Fragment>
              );
            })}
            {trees.length === 0 && (
              <tr>
                <td colSpan={canEdit ? 7 : 6} className="px-3 py-6 text-center text-[var(--text-muted)]">
                  暂无目标数据。演示种子会在首次访问时写入「李业务 · 2026」。
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
