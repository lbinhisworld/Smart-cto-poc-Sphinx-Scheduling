import { useEffect, useMemo, useState } from "react";
import { requestWithRole } from "../../api/client";
import { useAuth } from "../../shell/auth";

type TaskRow = {
  task_id: number;
  wo_no: string;
  task_date: string;
  qty_board: number;
  qty_board_plan?: number;
  qty_board_done?: number;
  qty_board_remain?: number;
  wo_status?: string | null;
  hours_man: number;
  hours_wall: number;
  crew_plan: number;
};

type Props = {
  workDate: string;
  scheduleDept: string;
  groupCode: string;
  groupLabel: string;
  onClose: () => void;
  onQtyChanged?: () => void;
};

export function LaborTaskDrawer({
  workDate,
  scheduleDept,
  groupCode,
  groupLabel,
  onClose,
  onQtyChanged,
}: Props) {
  const auth = useAuth();
  const role = auth.role;
  const [rows, setRows] = useState<TaskRow[]>([]);
  const [draftDone, setDraftDone] = useState<Record<string, string>>({});
  const [err, setErr] = useState<string | null>(null);
  const canConfirm = role === "GM" || role === "PMC" || role === "TEAM_LEADER";

  const load = () => {
    if (!role) return;
    const q = new URLSearchParams({
      work_date: workDate,
      schedule_dept: scheduleDept,
      group_code: groupCode,
    });
    requestWithRole<TaskRow[]>(`/api/labor/cell-tasks?${q}`, role).then(setRows);
  };

  useEffect(() => {
    load();
  }, [role, workDate, scheduleDept, groupCode]);

  const byWo = useMemo(() => {
    const m = new Map<string, TaskRow>();
    for (const t of rows) {
      if (!m.has(t.wo_no)) m.set(t.wo_no, t);
    }
    return [...m.values()];
  }, [rows]);

  const confirmQty = async (woNo: string, plan: number) => {
    if (!role) return;
    const raw = draftDone[woNo];
    if (raw === undefined || raw === "") {
      setErr("请填写完工版数");
      return;
    }
    const done = Math.ceil(Number(raw));
    if (!Number.isFinite(done) || done < 0 || done > plan) {
      setErr(`完工版数须为 0–${plan} 的整数版`);
      return;
    }
    setErr(null);
    try {
      await requestWithRole(`/api/labor/wos/${woNo}/qty-confirm`, role, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ qty_board_done: done, work_date: workDate }),
      });
      load();
      onQtyChanged?.();
    } catch (e) {
      setErr(String(e));
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/45" role="dialog" onClick={onClose}>
      <div
        className="flex h-full w-full max-w-lg flex-col overflow-hidden shadow-xl"
        style={{ background: "var(--bg-card)" }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b px-4 py-3" style={{ borderColor: "var(--line)" }}>
          <div>
            <p className="font-semibold">计划任务 · 完工版数</p>
            <p className="text-xs text-[var(--text-muted)]">
              {workDate} · {groupLabel} · 数量归一到版
            </p>
          </div>
          <button type="button" className="text-sm text-[var(--text-muted)]" onClick={onClose}>
            关闭
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto p-4">
          {err && <p className="mb-2 text-xs text-rose-400">{err}</p>}
          {rows.length === 0 ? (
            <p className="text-xs text-[var(--text-muted)]">该日该组无计划任务或未发布排程</p>
          ) : (
            <>
              <table className="w-full text-xs">
                <thead className="bg-[var(--table-head)] text-[var(--text-muted)]">
                  <tr>
                    <th className="px-2 py-1 text-left">工单</th>
                    <th className="text-right">当日版</th>
                    <th className="text-right">人·时</th>
                    <th className="text-right">墙钟</th>
                    <th className="text-right">人数</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((t) => (
                    <tr key={t.task_id} className="border-t" style={{ borderColor: "var(--line)" }}>
                      <td className="px-2 py-1 font-mono">{t.wo_no}</td>
                      <td className="text-right tabular-nums">{t.qty_board}</td>
                      <td className="text-right tabular-nums">{t.hours_man}</td>
                      <td className="text-right tabular-nums">{t.hours_wall}</td>
                      <td className="text-right tabular-nums">{t.crew_plan}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="mt-4 text-xs font-medium">按工单确认完工版数</p>
              <p className="mb-2 text-[11px] text-[var(--text-muted)]">
                未完部分进待确认池，不会自动重排；PMC 选择并入同品项或插单。
              </p>
              <ul className="space-y-2">
                {byWo.map((t) => {
                  const plan = t.qty_board_plan ?? t.qty_board;
                  const done = t.qty_board_done ?? 0;
                  const remain = t.qty_board_remain ?? Math.max(0, plan - done);
                  const closed = t.wo_status === "DONE" || t.wo_status === "PARTIAL";
                  return (
                    <li
                      key={t.wo_no}
                      className="rounded border px-2 py-2"
                      style={{ borderColor: "var(--line)" }}
                    >
                      <p className="font-mono text-xs">{t.wo_no}</p>
                      <p className="text-[11px] text-[var(--text-muted)]">
                        计划 {plan} 版 · 已完 {done} · 剩余 {remain}
                        {t.wo_status ? ` · ${t.wo_status}` : ""}
                      </p>
                      {canConfirm && !closed && (
                        <div className="mt-1 flex items-center gap-2">
                          <input
                            type="number"
                            min={0}
                            max={plan}
                            step={1}
                            className="w-24 rounded border px-1 py-0.5 text-right text-xs"
                            style={{ borderColor: "var(--line)" }}
                            placeholder="完工版"
                            value={draftDone[t.wo_no] ?? ""}
                            onChange={(e) =>
                              setDraftDone((d) => ({ ...d, [t.wo_no]: e.target.value }))
                            }
                          />
                          <button
                            type="button"
                            className="text-xs text-[var(--accent)] hover:underline"
                            onClick={() => void confirmQty(t.wo_no, plan)}
                          >
                            确认完工
                          </button>
                        </div>
                      )}
                    </li>
                  );
                })}
              </ul>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
