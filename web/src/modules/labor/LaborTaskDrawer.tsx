import { useEffect, useState } from "react";
import { requestWithRole } from "../../api/client";
import { useAuth } from "../../shell/auth";

type TaskRow = {
  task_id: number;
  wo_no: string;
  task_date: string;
  qty_board: number;
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
};

export function LaborTaskDrawer({ workDate, scheduleDept, groupCode, groupLabel, onClose }: Props) {
  const auth = useAuth();
  const role = auth.role;
  const [rows, setRows] = useState<TaskRow[]>([]);

  useEffect(() => {
    if (!role) return;
    const q = new URLSearchParams({
      work_date: workDate,
      schedule_dept: scheduleDept,
      group_code: groupCode,
    });
    requestWithRole<TaskRow[]>(`/api/labor/cell-tasks?${q}`, role).then(setRows);
  }, [role, workDate, scheduleDept, groupCode]);

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/45" role="dialog" onClick={onClose}>
      <div
        className="flex h-full w-full max-w-lg flex-col overflow-hidden shadow-xl"
        style={{ background: "var(--bg-card)" }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b px-4 py-3" style={{ borderColor: "var(--line)" }}>
          <div>
            <p className="font-semibold">计划任务明细（只读）</p>
            <p className="text-xs text-[var(--text-muted)]">
              {workDate} · {groupLabel}
            </p>
          </div>
          <button type="button" className="text-sm text-[var(--text-muted)]" onClick={onClose}>
            关闭
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto p-4">
          {rows.length === 0 ? (
            <p className="text-xs text-[var(--text-muted)]">该日该组无计划任务或未发布排程</p>
          ) : (
            <table className="w-full text-xs">
              <thead className="bg-[var(--table-head)] text-[var(--text-muted)]">
                <tr>
                  <th className="px-2 py-1 text-left">工单</th>
                  <th className="text-right">版数</th>
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
          )}
        </div>
      </div>
    </div>
  );
}
