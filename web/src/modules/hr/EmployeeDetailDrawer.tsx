import { useEffect, useState } from "react";
import { requestWithRole } from "../../api/client";
import { renderContractStatusTag, renderHrEmpStatusTag, renderPunchTypeTag, renderRenewalCountdown } from "../../ui/cellRenderers";
import { useAuth } from "../../shell/auth";

type EmployeeDetail = {
  emp_no: string;
  name: string;
  department: string;
  position: string;
  status: string;
  hired_date: string | null;
  contract_start: string | null;
  contract_end: string | null;
  contract_status: string;
  renewal_status_label?: string;
  days_until_renewal: number | null;
  recent_punches: {
    id: number;
    punch_at: string;
    punch_type: string;
    device_name: string;
    synced_at: string;
  }[];
};

type Props = {
  empNo: string | null;
  onClose: () => void;
};

export function EmployeeDetailDrawer({ empNo, onClose }: Props) {
  const auth = useAuth();
  const role = auth.role;
  const [data, setData] = useState<EmployeeDetail | null>(null);

  useEffect(() => {
    if (!empNo || !role) {
      setData(null);
      return;
    }
    requestWithRole<EmployeeDetail>(`/api/hr/employees/${encodeURIComponent(empNo)}`, role).then(setData);
  }, [empNo, role]);

  if (!empNo) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/45" role="dialog" onClick={onClose}>
      <div
        className="flex h-full w-full max-w-xl flex-col overflow-hidden shadow-xl"
        style={{ background: "var(--bg-card)" }}
        onClick={(e) => e.stopPropagation()}
      >
        <div
          className="flex items-center justify-between border-b px-4 py-3"
          style={{ borderColor: "var(--line)" }}
        >
          <p className="font-semibold">员工档案</p>
          <button type="button" className="text-sm text-[var(--text-muted)]" onClick={onClose}>
            关闭
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto p-4 text-sm">
          {!data ? (
            <p className="text-xs text-[var(--text-muted)]">加载中…</p>
          ) : (
            <div className="space-y-4">
              <dl className="grid gap-2">
                <div>
                  <dt className="text-xs text-[var(--text-muted)]">工号</dt>
                  <dd className="font-mono">{data.emp_no}</dd>
                </div>
                <div>
                  <dt className="text-xs text-[var(--text-muted)]">姓名</dt>
                  <dd className="text-lg font-semibold">{data.name}</dd>
                </div>
                <div>
                  <dt className="text-xs text-[var(--text-muted)]">部门</dt>
                  <dd>{data.department}</dd>
                </div>
                <div>
                  <dt className="text-xs text-[var(--text-muted)]">岗位</dt>
                  <dd>{data.position}</dd>
                </div>
                <div>
                  <dt className="text-xs text-[var(--text-muted)]">状态</dt>
                  <dd>{renderHrEmpStatusTag(data.status)}</dd>
                </div>
                <div>
                  <dt className="text-xs text-[var(--text-muted)]">入职日期</dt>
                  <dd>{data.hired_date ?? "—"}</dd>
                </div>
                <div>
                  <dt className="text-xs text-[var(--text-muted)]">劳动合同</dt>
                  <dd>
                    {data.contract_start ?? "—"} ~ {data.contract_end ?? "—"}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-[var(--text-muted)]">续签状态</dt>
                  <dd>{renderContractStatusTag(data.contract_status)}</dd>
                </div>
                <div>
                  <dt className="text-xs text-[var(--text-muted)]">下次续签倒计时</dt>
                  <dd className="text-base">{renderRenewalCountdown(data.days_until_renewal)}</dd>
                </div>
              </dl>
              <section className="border-t pt-3" style={{ borderColor: "var(--line)" }}>
                <h3 className="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">
                  近期考勤（考勤机同步）
                </h3>
                {data.recent_punches.length === 0 ? (
                  <p className="mt-2 text-xs text-[var(--text-muted)]">暂无打卡记录</p>
                ) : (
                  <table className="mt-2 w-full text-xs">
                    <thead className="bg-[var(--table-head)] text-[var(--text-muted)]">
                      <tr>
                        <th className="px-2 py-1 text-left">时间</th>
                        <th className="text-left">类型</th>
                        <th className="text-left">设备</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.recent_punches.map((p) => (
                        <tr key={p.id} className="border-t" style={{ borderColor: "var(--line)" }}>
                          <td className="px-2 py-1 tabular-nums">{p.punch_at}</td>
                          <td>{renderPunchTypeTag(p.punch_type)}</td>
                          <td>{p.device_name}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </section>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
