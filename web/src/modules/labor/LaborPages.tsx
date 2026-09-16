import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { requestWithRole } from "../../api/client";
import { renderMoney } from "../../ui/cellRenderers";
import { useAuth } from "../../shell/auth";
import { LaborTaskDrawer } from "./LaborTaskDrawer";

const ANCHOR_FROM = "2026-09-01";
const ANCHOR_TO = "2026-09-30";
const DEFAULT_DAY = "2026-09-15";

type GridRow = {
  id: number | null;
  work_date: string;
  schedule_dept: string;
  group_code: string;
  group_label: string;
  display_dept: string;
  plan_version: number;
  hours_man_planned: number;
  hours_man_actual: number | null;
  status: string;
  rate_per_man_hour: number;
  cost_planned: number;
  cost_actual: number | null;
  hours_cap: number | null;
};

type SummaryRow = {
  display_dept: string;
  group_label: string;
  schedule_dept: string;
  group_code: string;
  hours_planned: number;
  hours_actual: number;
  cost_planned: number;
  cost_actual: number;
  variance_pct: number | null;
};

/** 班组长 · 组×日报工 */
export function ProductionTimeReportPage() {
  const auth = useAuth();
  const role = auth.role;
  const [workDate, setWorkDate] = useState(DEFAULT_DAY);
  const [rows, setRows] = useState<GridRow[]>([]);
  const [draftActual, setDraftActual] = useState<Record<string, string>>({});
  const [err, setErr] = useState<string | null>(null);
  const [detail, setDetail] = useState<GridRow | null>(null);
  const leaderScope = role === "TEAM_LEADER" ? "FINISHED_DEPT|MANUAL" : null;

  const load = useCallback(() => {
    if (!role) return;
    setErr(null);
    requestWithRole<GridRow[]>(`/api/labor/time-reports/grid?work_date=${workDate}`, role)
      .then(setRows)
      .catch((e) => setErr(String(e)));
  }, [role, workDate]);

  useEffect(() => {
    load();
  }, [load]);

  const canEditRow = (r: GridRow) => {
    if (role === "GM" || role === "PMC") return true;
    if (role === "TEAM_LEADER" && leaderScope === `${r.schedule_dept}|${r.group_code}`) return true;
    return false;
  };

  const saveAndConfirm = async (r: GridRow) => {
    if (!role) return;
    const key = `${r.schedule_dept}|${r.group_code}`;
    const val = draftActual[key] ?? (r.hours_man_actual != null ? String(r.hours_man_actual) : "");
    if (!val) {
      setErr("请填写实际总人·时");
      return;
    }
    setErr(null);
    try {
      const saved = await requestWithRole<{ id: number }>(`/api/labor/time-reports`, role, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          work_date: workDate,
          schedule_dept: r.schedule_dept,
          group_code: r.group_code,
          hours_man_actual: Number(val),
        }),
      });
      await requestWithRole(`/api/labor/time-reports/${saved.id}/confirm`, role, { method: "POST" });
      load();
    } catch (e) {
      setErr(String(e));
    }
  };

  const pv = rows[0]?.plan_version ?? 0;

  return (
    <div className="px-6 py-4">
      <h2 className="text-lg font-semibold">组×日报工</h2>
      <p className="text-xs text-[var(--text-muted)]">
        班组长填写当日实际总人·时 · 不得超过考勤上限（实到 × 日工时） · plan v{pv || "—"}
      </p>
      <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
        <label className="text-[var(--text-muted)]">报工日</label>
        <input
          type="date"
          className="rounded border px-2 py-1"
          style={{ borderColor: "var(--line)", background: "var(--bg-card)" }}
          value={workDate}
          onChange={(e) => setWorkDate(e.target.value)}
        />
        <Link to="/schedule" className="text-[var(--accent)] underline">
          去排程发布
        </Link>
      </div>
      {err && <p className="mt-2 text-xs text-rose-400">{err}</p>}
      <div className="mt-4 overflow-x-auto rounded-lg border" style={{ borderColor: "var(--line)" }}>
        <table className="w-full min-w-[880px] border-collapse text-xs">
          <thead className="bg-[var(--table-head)] text-[var(--text-muted)]">
            <tr>
              <th className="px-3 py-2 text-left">部门</th>
              <th className="text-left">工作组</th>
              <th className="text-right">计划人·时</th>
              <th className="text-right">考勤上限</th>
              <th className="text-right">实际人·时</th>
              <th className="text-right">单价</th>
              <th className="text-left">状态</th>
              <th className="text-left">操作</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const key = `${r.schedule_dept}|${r.group_code}`;
              const editable = canEditRow(r);
              return (
                <tr
                  key={key}
                  className="cursor-pointer border-t hover:bg-[var(--table-row-hover)]"
                  style={{ borderColor: "var(--line)" }}
                  onClick={() => setDetail(r)}
                >
                  <td className="px-3 py-2">{r.display_dept}</td>
                  <td>{r.group_label}</td>
                  <td className="text-right tabular-nums">{r.hours_man_planned.toFixed(2)}</td>
                  <td className="text-right tabular-nums text-[var(--text-muted)]">
                    {r.hours_cap == null ? "无考勤" : r.hours_cap.toFixed(2)}
                  </td>
                  <td className="text-right" onClick={(e) => e.stopPropagation()}>
                    {editable ? (
                      <input
                        type="number"
                        step="0.1"
                        className="w-20 rounded border px-1 py-0.5 text-right"
                        style={{ borderColor: "var(--line)" }}
                        value={draftActual[key] ?? (r.hours_man_actual ?? "")}
                        onChange={(e) => setDraftActual((d) => ({ ...d, [key]: e.target.value }))}
                      />
                    ) : (
                      <span className="tabular-nums">{r.hours_man_actual ?? "—"}</span>
                    )}
                  </td>
                  <td className="text-right tabular-nums">¥{r.rate_per_man_hour}</td>
                  <td>{r.status === "CONFIRMED" ? "已确认" : r.status === "DRAFT" ? "草稿" : "未报"}</td>
                  <td onClick={(e) => e.stopPropagation()}>
                    {editable && (
                      <button
                        type="button"
                        className="text-[var(--accent)] hover:underline"
                        onClick={() => void saveAndConfirm(r)}
                      >
                        确认
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {detail && (
        <LaborTaskDrawer
          workDate={detail.work_date}
          scheduleDept={detail.schedule_dept}
          groupCode={detail.group_code}
          groupLabel={detail.group_label}
          onClose={() => setDetail(null)}
        />
      )}
    </div>
  );
}

function varianceTag(pct: number | null) {
  if (pct == null) return <span className="text-[var(--text-muted)]">—</span>;
  const cls =
    pct > 5 ? "bg-rose-950 text-rose-200 ring-rose-800" : pct < -5 ? "bg-emerald-950 text-emerald-200 ring-emerald-800" : "bg-slate-800 text-slate-300 ring-slate-600";
  return (
    <span className={`inline-block rounded-md px-2 py-0.5 text-[11px] ring-1 ${cls}`}>
      {pct > 0 ? "+" : ""}
      {pct}%
    </span>
  );
}

type ReportLine = {
  work_date: string;
  schedule_dept: string;
  group_code: string;
  hours_man_planned: number;
  hours_man_actual: number | null;
  status: string;
  reported_by: string | null;
  note: string;
};

/** 人事 · 生产成本（部门-组） */
export function HrLaborCostPage() {
  const auth = useAuth();
  const role = auth.role;
  const [data, setData] = useState<{
    plan_version: number;
    totals: { cost_planned: number; cost_actual: number; variance_pct: number | null };
    rows: SummaryRow[];
  } | null>(null);
  const [detailRow, setDetailRow] = useState<SummaryRow | null>(null);
  const [reportLines, setReportLines] = useState<ReportLine[]>([]);

  useEffect(() => {
    if (!role) return;
    requestWithRole<NonNullable<typeof data>>(
      `/api/hr/labor-cost/summary?date_from=${ANCHOR_FROM}&date_to=${ANCHOR_TO}`,
      role,
    ).then(setData);
  }, [role]);

  useEffect(() => {
    if (!role || !detailRow) {
      setReportLines([]);
      return;
    }
    const q = new URLSearchParams({ date_from: ANCHOR_FROM, date_to: ANCHOR_TO });
    requestWithRole<ReportLine[]>(`/api/labor/time-reports?${q}`, role).then((all) =>
      setReportLines(
        all.filter(
          (r) =>
            r.schedule_dept === detailRow.schedule_dept && r.group_code === detailRow.group_code,
        ),
      ),
    );
  }, [role, detailRow]);

  const rows = useMemo(() => data?.rows ?? [], [data]);

  return (
    <div className="px-6 py-4">
      <h2 className="text-lg font-semibold">生产成本</h2>
      <p className="text-xs text-[var(--text-muted)]">
        计划来自排程 wo_task 人·时 · 实际来自班组长组×日确认报工 · 非薪酬发薪
      </p>
      <nav className="mt-3 flex gap-2 text-sm">
        <Link to="/modules/hr/roster" className="text-[var(--text-muted)] hover:text-[var(--accent)]">
          花名册
        </Link>
        <Link to="/modules/production/time-report" className="text-[var(--accent)] underline">
          组×日报工
        </Link>
      </nav>
      {data && (
        <div className="mt-4 grid gap-3 lg:grid-cols-3">
          <div className="rounded-lg border p-4" style={{ borderColor: "var(--line)", background: "var(--bg-card)" }}>
            <p className="text-xs text-[var(--text-muted)]">计划人工成本</p>
            <p className="mt-1 text-2xl font-semibold">{renderMoney(data.totals.cost_planned)}</p>
          </div>
          <div className="rounded-lg border p-4" style={{ borderColor: "var(--line)", background: "var(--bg-card)" }}>
            <p className="text-xs text-[var(--text-muted)]">实际人工成本</p>
            <p className="mt-1 text-2xl font-semibold">{renderMoney(data.totals.cost_actual)}</p>
          </div>
          <div className="rounded-lg border p-4" style={{ borderColor: "var(--line)", background: "var(--bg-card)" }}>
            <p className="text-xs text-[var(--text-muted)]">差异率 · plan v{data.plan_version || "—"}</p>
            <p className="mt-2">{varianceTag(data.totals.variance_pct)}</p>
          </div>
        </div>
      )}
      <div className="mt-4 overflow-x-auto rounded-lg border" style={{ borderColor: "var(--line)" }}>
        <table className="w-full min-w-[720px] text-xs">
          <thead className="bg-[var(--table-head)] text-[var(--text-muted)]">
            <tr>
              <th className="px-3 py-2 text-left">部门</th>
              <th className="text-left">工作组</th>
              <th className="text-right">计划人·时</th>
              <th className="text-right">实际人·时</th>
              <th className="text-right">计划成本</th>
              <th className="text-right">实际成本</th>
              <th className="text-left">差异</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr
                key={`${r.schedule_dept}|${r.group_code}`}
                className="cursor-pointer border-t hover:bg-[var(--table-row-hover)]"
                style={{ borderColor: "var(--line)" }}
                onClick={() => setDetailRow(r)}
              >
                <td className="px-3 py-2">{r.display_dept}</td>
                <td>{r.group_label}</td>
                <td className="text-right tabular-nums">{r.hours_planned.toFixed(2)}</td>
                <td className="text-right tabular-nums">{r.hours_actual.toFixed(2)}</td>
                <td className="text-right">{renderMoney(r.cost_planned)}</td>
                <td className="text-right">{renderMoney(r.cost_actual)}</td>
                <td>{varianceTag(r.variance_pct)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {detailRow && (
        <div className="fixed inset-0 z-50 flex justify-end bg-black/45" role="dialog" onClick={() => setDetailRow(null)}>
          <div
            className="flex h-full w-full max-w-md flex-col overflow-hidden shadow-xl"
            style={{ background: "var(--bg-card)" }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b px-4 py-3" style={{ borderColor: "var(--line)" }}>
              <div>
                <p className="font-semibold">{detailRow.display_dept} · {detailRow.group_label}</p>
                <p className="text-xs text-[var(--text-muted)]">组×日报工明细 · {ANCHOR_FROM} ~ {ANCHOR_TO}</p>
              </div>
              <button type="button" className="text-sm text-[var(--text-muted)]" onClick={() => setDetailRow(null)}>
                关闭
              </button>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto p-4">
              {reportLines.length === 0 ? (
                <p className="text-xs text-[var(--text-muted)]">该周期内无报工记录</p>
              ) : (
                <table className="w-full text-xs">
                  <thead className="bg-[var(--table-head)] text-[var(--text-muted)]">
                    <tr>
                      <th className="px-2 py-1 text-left">日期</th>
                      <th className="text-right">计划人·时</th>
                      <th className="text-right">实际人·时</th>
                      <th className="text-left">状态</th>
                    </tr>
                  </thead>
                  <tbody>
                    {reportLines.map((line) => (
                      <tr key={line.work_date} className="border-t" style={{ borderColor: "var(--line)" }}>
                        <td className="px-2 py-1">{line.work_date}</td>
                        <td className="text-right tabular-nums">{line.hours_man_planned.toFixed(2)}</td>
                        <td className="text-right tabular-nums">
                          {line.hours_man_actual != null ? line.hours_man_actual.toFixed(2) : "—"}
                        </td>
                        <td>{line.status === "CONFIRMED" ? "已确认" : line.status}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
