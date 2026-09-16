import { useEffect, useMemo, useState } from "react";
import { Link, NavLink, useParams } from "react-router-dom";
import { useAuth } from "../../shell/auth";
import { renderContractStatusTag, renderHrEmpStatusTag, renderPunchTypeTag } from "../../ui/cellRenderers";
import { EmployeeDetailDrawer } from "./EmployeeDetailDrawer";

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

function HrSubNav() {
  const linkClass = ({ isActive }: { isActive: boolean }) =>
    `rounded-md px-3 py-1.5 text-sm ${isActive ? "bg-[var(--accent)] text-white" : "text-[var(--text-muted)] hover:text-[var(--text)]"}`;
  return (
    <nav className="mt-3 flex flex-wrap gap-2">
      <NavLink to="/modules/hr/roster" className={linkClass}>
        花名册
      </NavLink>
      <NavLink to="/modules/hr/attendance" className={linkClass}>
        考勤管理
      </NavLink>
    </nav>
  );
}

type EmployeeRow = {
  emp_no: string;
  name: string;
  department: string;
  position: string;
  status: string;
  hired_date: string | null;
  contract_end: string | null;
  contract_status: string;
};

const DEPT_PALETTE = [
  "bg-sky-950 text-sky-200 ring-sky-700",
  "bg-violet-950 text-violet-200 ring-violet-700",
  "bg-amber-950 text-amber-200 ring-amber-700",
  "bg-orange-950 text-orange-200 ring-orange-700",
  "bg-emerald-950 text-emerald-200 ring-emerald-700",
  "bg-rose-950 text-rose-200 ring-rose-700",
  "bg-cyan-950 text-cyan-200 ring-cyan-700",
];

function deptTag(dept: string, index: number) {
  const cls = DEPT_PALETTE[index % DEPT_PALETTE.length];
  return (
    <span className={`inline-block rounded-md px-2 py-0.5 text-[11px] font-medium ring-1 ${cls}`}>{dept}</span>
  );
}

function RosterDeptMetrics({ rows }: { rows: EmployeeRow[] }) {
  const total = rows.length;
  const active = rows.filter((r) => r.status === "ACTIVE").length;
  const deptCounts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const r of rows) {
      c[r.department] = (c[r.department] ?? 0) + 1;
    }
    return Object.entries(c).sort((a, b) => b[1] - a[1]);
  }, [rows]);
  const max = Math.max(...deptCounts.map(([, n]) => n), 1);

  return (
    <div className="mt-4 grid gap-3 lg:grid-cols-[minmax(140px,200px)_1fr]">
      <div className="rounded-lg border p-4" style={{ borderColor: "var(--line)", background: "var(--bg-card)" }}>
        <p className="text-xs text-[var(--text-muted)]">员工总数</p>
        <p className="mt-1 text-3xl font-semibold tabular-nums">{total}</p>
        <p className="mt-1 text-[10px] text-[var(--text-muted)]">在职 {active} · 与列表一致</p>
      </div>
      <div className="rounded-lg border p-4" style={{ borderColor: "var(--line)", background: "var(--bg-card)" }}>
        <p className="text-xs font-medium text-[var(--text-muted)]">各部门人数</p>
        <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {deptCounts.map(([dept, n], i) => {
            const pct = Math.round((n / max) * 100);
            return (
              <div key={dept} className="flex flex-col gap-1.5">
                <div className="flex items-center justify-between gap-2">
                  {deptTag(dept, i)}
                  <span className="text-lg font-semibold tabular-nums">{n}</span>
                </div>
                <div className="h-2 overflow-hidden rounded-md bg-[var(--line)]">
                  <div className="h-full rounded-md bg-[var(--accent)]" style={{ width: `${pct}%`, minWidth: n ? 4 : 0 }} />
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export function HrRosterPage() {
  const params = useParams<{ empNo?: string }>();
  const { data, error } = useFetch<EmployeeRow[]>("/api/hr/employees");
  const rows = useMemo(() => data ?? [], [data]);
  const [detailEmp, setDetailEmp] = useState<string | null>(params.empNo ?? null);

  useEffect(() => {
    if (params.empNo) setDetailEmp(params.empNo);
  }, [params.empNo]);

  return (
    <div className="px-6 py-4">
      <h2 className="text-lg font-semibold">花名册</h2>
      <p className="text-xs text-[var(--text-muted)]">员工档案 · 点击行或「详情」查看侧滑</p>
      <HrSubNav />
      {error && <p className="mt-2 text-xs text-rose-400">{error}</p>}
      <RosterDeptMetrics rows={rows} />
      <div className="mt-4 overflow-x-auto rounded-lg border" style={{ borderColor: "var(--line)" }}>
        <table className="w-full min-w-[720px] border-collapse text-xs">
          <thead className="bg-[var(--table-head)] text-[var(--text-muted)]">
            <tr>
              <th className="px-3 py-2 text-left">工号</th>
              <th className="px-3 py-2 text-left">姓名</th>
              <th className="px-3 py-2 text-left">部门</th>
              <th className="px-3 py-2 text-left">岗位</th>
              <th className="px-3 py-2 text-left">状态</th>
              <th className="px-3 py-2 text-left">入职日期</th>
              <th className="px-3 py-2 text-left">合同到期</th>
              <th className="px-3 py-2 text-left">操作</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((e, i) => (
              <tr
                key={e.emp_no}
                className="cursor-pointer border-t hover:bg-[var(--table-row-hover)]"
                style={{ borderColor: "var(--line)" }}
                onClick={() => setDetailEmp(e.emp_no)}
              >
                <td className="whitespace-nowrap px-3 py-2 font-mono text-[var(--accent)]">{e.emp_no}</td>
                <td className="whitespace-nowrap px-3 py-2 font-medium">{e.name}</td>
                <td className="whitespace-nowrap px-3 py-2">{deptTag(e.department, i)}</td>
                <td className="px-3 py-2">{e.position}</td>
                <td className="whitespace-nowrap px-3 py-2">{renderHrEmpStatusTag(e.status)}</td>
                <td className="whitespace-nowrap px-3 py-2 tabular-nums">{e.hired_date ?? "—"}</td>
                <td className="whitespace-nowrap px-3 py-2">
                  <span className="mr-2 tabular-nums">{e.contract_end ?? "—"}</span>
                  {renderContractStatusTag(e.contract_status)}
                </td>
                <td className="px-3 py-2">
                  <button
                    type="button"
                    className="text-[var(--accent)] hover:underline"
                    onClick={(ev) => {
                      ev.stopPropagation();
                      setDetailEmp(e.emp_no);
                    }}
                  >
                    详情
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <EmployeeDetailDrawer empNo={detailEmp} onClose={() => setDetailEmp(null)} />
    </div>
  );
}

type PunchRow = {
  id: number;
  emp_no: string;
  emp_name: string;
  department: string;
  punch_at: string;
  punch_type: string;
  device_code: string;
  device_name: string;
  synced_at: string;
};

const ANCHOR_DATE = "2026-09-15";

function AttendanceMetrics({ rows }: { rows: PunchRow[] }) {
  const inCount = rows.filter((r) => r.punch_type === "上班").length;
  const outCount = rows.filter((r) => r.punch_type === "下班").length;
  const devices = new Set(rows.map((r) => r.device_code)).size;
  const maxType = Math.max(inCount, outCount, 1);

  return (
    <div className="mt-4 grid gap-3 lg:grid-cols-[minmax(140px,200px)_1fr]">
      <div className="rounded-lg border p-4" style={{ borderColor: "var(--line)", background: "var(--bg-card)" }}>
        <p className="text-xs text-[var(--text-muted)]">打卡明细条数</p>
        <p className="mt-1 text-3xl font-semibold tabular-nums">{rows.length}</p>
        <p className="mt-1 text-[10px] text-[var(--text-muted)]">考勤机同步 · 当前筛选日</p>
      </div>
      <div className="rounded-lg border p-4" style={{ borderColor: "var(--line)", background: "var(--bg-card)" }}>
        <p className="text-xs font-medium text-[var(--text-muted)]">打卡类型 / 设备</p>
        <div className="mt-3 grid gap-3 sm:grid-cols-3">
          {[
            { label: "上班", n: inCount, tag: renderPunchTypeTag("上班") },
            { label: "下班", n: outCount, tag: renderPunchTypeTag("下班") },
          ].map(({ label, n, tag }) => (
            <div key={label} className="flex flex-col gap-1.5">
              <div className="flex items-center justify-between gap-2">
                {tag}
                <span className="text-lg font-semibold tabular-nums">{n}</span>
              </div>
              <div className="h-2 overflow-hidden rounded-md bg-[var(--line)]">
                <div
                  className="h-full rounded-md bg-[var(--accent)]"
                  style={{ width: `${Math.round((n / maxType) * 100)}%`, minWidth: n ? 4 : 0 }}
                />
              </div>
            </div>
          ))}
          <div className="flex flex-col justify-center rounded-md border px-3 py-2" style={{ borderColor: "var(--line)" }}>
            <p className="text-[10px] text-[var(--text-muted)]">同步设备数</p>
            <p className="text-xl font-semibold tabular-nums">{devices}</p>
          </div>
        </div>
      </div>
    </div>
  );
}

type GroupAttendanceRow = {
  schedule_dept: string;
  group_code: string;
  group_label: string;
  work_date: string;
  headcount_roster: number;
  headcount_present: number | null;
  source: string | null;
  feeds_scheduling: boolean;
};

export function HrAttendancePage() {
  const auth = useAuth();
  const [workDate, setWorkDate] = useState(ANCHOR_DATE);
  const [syncMsg, setSyncMsg] = useState<string | null>(null);
  const [syncBusy, setSyncBusy] = useState(false);
  const url = `/api/hr/attendance/punches?work_date=${encodeURIComponent(workDate)}`;
  const summaryUrl = `/api/hr/attendance/group-summary?work_date=${encodeURIComponent(workDate)}`;
  const { data, error } = useFetch<PunchRow[]>(url);
  const { data: groupSummary } = useFetch<GroupAttendanceRow[]>(summaryUrl);
  const rows = useMemo(() => data ?? [], [data]);

  const syncToScheduling = async () => {
    setSyncBusy(true);
    setSyncMsg(null);
    try {
      const res = await fetch(
        `/api/hr/attendance/sync-to-scheduling?work_date=${encodeURIComponent(workDate)}`,
        { method: "POST", headers: auth.headers() },
      );
      const j = await res.json();
      if (j.code !== 0) throw new Error(j.message || "同步失败");
      setSyncMsg(j.message || "已同步");
    } catch (e) {
      setSyncMsg(String(e));
    } finally {
      setSyncBusy(false);
    }
  };

  return (
    <div className="px-6 py-4">
      <h2 className="text-lg font-semibold">考勤管理</h2>
      <p className="text-xs text-[var(--text-muted)]">
        打卡 → 组×日实到人数 → 排程产能（在编/实到/墙钟上限）· POC Mock
      </p>
      <HrSubNav />
      <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
        <label className="text-[var(--text-muted)]">考勤日</label>
        <input
          type="date"
          className="rounded border px-2 py-1"
          style={{ borderColor: "var(--line)", background: "var(--bg-card)" }}
          value={workDate}
          onChange={(e) => setWorkDate(e.target.value)}
        />
        <button
          type="button"
          disabled={syncBusy}
          onClick={() => void syncToScheduling()}
          className="rounded bg-[var(--accent)] px-3 py-1 text-white disabled:opacity-40"
        >
          同步到排程产能
        </button>
        <Link to="/schedule" className="text-[var(--accent)] underline">
          打开排产看板
        </Link>
        <Link to="/modules/hr/roster" className="text-[var(--accent)] underline">
          查员工档案
        </Link>
      </div>
      {syncMsg && (
        <p className="mt-2 text-xs text-emerald-600 dark:text-emerald-400">{syncMsg}</p>
      )}
      {groupSummary && groupSummary.length > 0 && (
        <div className="mt-4 overflow-x-auto rounded-lg border" style={{ borderColor: "var(--line)" }}>
          <table className="w-full min-w-[640px] border-collapse text-xs">
            <thead className="bg-[var(--table-head)] text-[var(--text-muted)]">
              <tr>
                <th className="px-3 py-2 text-left">工作中心</th>
                <th className="px-3 py-2 text-right">在编</th>
                <th className="px-3 py-2 text-right">实到</th>
                <th className="px-3 py-2 text-left">来源</th>
                <th className="px-3 py-2 text-left">喂排程</th>
              </tr>
            </thead>
            <tbody>
              {groupSummary.map((g) => (
                <tr key={`${g.schedule_dept}-${g.group_code}`} className="border-t" style={{ borderColor: "var(--line)" }}>
                  <td className="px-3 py-2">{g.group_label}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{g.headcount_roster}</td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {g.headcount_present ?? "—"}
                  </td>
                  <td className="px-3 py-2">{g.source ?? "—"}</td>
                  <td className="px-3 py-2">{g.feeds_scheduling ? "是" : "否"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {error && <p className="mt-2 text-xs text-rose-400">{error}</p>}
      <AttendanceMetrics rows={rows} />
      <div className="mt-4 overflow-x-auto rounded-lg border" style={{ borderColor: "var(--line)" }}>
        <table className="w-full min-w-[900px] border-collapse text-xs">
          <thead className="bg-[var(--table-head)] text-[var(--text-muted)]">
            <tr>
              <th className="px-3 py-2 text-left">打卡时间</th>
              <th className="px-3 py-2 text-left">工号</th>
              <th className="px-3 py-2 text-left">姓名</th>
              <th className="px-3 py-2 text-left">部门</th>
              <th className="px-3 py-2 text-left">类型</th>
              <th className="px-3 py-2 text-left">考勤机</th>
              <th className="px-3 py-2 text-left">同步时间</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-3 py-8 text-center text-[var(--text-muted)]">
                  该日暂无考勤机同步记录
                </td>
              </tr>
            ) : (
              rows.map((p) => (
                <tr key={p.id} className="border-t" style={{ borderColor: "var(--line)" }}>
                  <td className="whitespace-nowrap px-3 py-2 tabular-nums">{p.punch_at}</td>
                  <td className="whitespace-nowrap px-3 py-2 font-mono">{p.emp_no}</td>
                  <td className="whitespace-nowrap px-3 py-2">{p.emp_name}</td>
                  <td className="whitespace-nowrap px-3 py-2">{p.department}</td>
                  <td className="whitespace-nowrap px-3 py-2">{renderPunchTypeTag(p.punch_type)}</td>
                  <td className="px-3 py-2">
                    <span className="font-mono text-[var(--text-muted)]">{p.device_code}</span> {p.device_name}
                  </td>
                  <td className="whitespace-nowrap px-3 py-2 tabular-nums text-[var(--text-muted)]">
                    {p.synced_at}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function HrModuleRedirect() {
  return (
    <div className="px-6 py-4 text-sm">
      <p className="text-[var(--text-muted)]">正在进入花名册…</p>
      <Link to="/modules/hr/roster" className="text-[var(--accent)] underline">
        花名册
      </Link>
    </div>
  );
}
