import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../../shell/auth";

type Breakdown = {
  order: Record<string, unknown>;
  kitting: { kitting_rate_pct?: number | null; shortages?: { item_code?: string; shortage_board?: number }[] };
  mrp_explode?: { line_details?: unknown[]; steps?: string[] };
  work_orders: { wo_no: string; wo_type: string; qty_board_plan: number }[];
  tasks: { task_id: number; group_code: string; task_date: string; qty_board: number }[];
};

type Props = {
  orderNo: string | null;
  onClose: () => void;
};

export function OrderDetailDrawer({ orderNo, onClose }: Props) {
  const auth = useAuth();
  const [data, setData] = useState<Breakdown | null>(null);

  useEffect(() => {
    if (!orderNo) return;
    fetch(`/api/mis/orders/${encodeURIComponent(orderNo)}/breakdown`, {
      headers: auth.headers(),
    })
      .then((r) => r.json())
      .then((j) => setData(j.data))
      .catch(() => setData(null));
  }, [orderNo, auth]);

  if (!orderNo) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/40" role="dialog">
      <div
        className="flex h-full w-full max-w-xl flex-col overflow-y-auto shadow-xl"
        style={{ background: "var(--bg-card)" }}
      >
        <div
          className="flex items-center justify-between border-b px-4 py-3"
          style={{ borderColor: "var(--line)" }}
        >
          <div>
            <p className="font-mono font-semibold">{orderNo}</p>
            <p className="text-xs text-[var(--text-muted)]">订单拆解 · 算料 / 工单 / 任务</p>
          </div>
          <button type="button" className="text-sm" onClick={onClose}>
            关闭
          </button>
        </div>
        <div className="space-y-4 p-4 text-sm">
          {data?.kitting && (
            <section>
              <h3 className="font-medium">齐套</h3>
              <p className="mt-1">齐套率 {data.kitting.kitting_rate_pct ?? "—"}%</p>
              {(data.kitting.shortages ?? []).length > 0 && (
                <ul className="mt-1 list-disc pl-5 text-red-600">
                  {data.kitting.shortages!.map((s, i) => (
                    <li key={i}>
                      缺 {s.item_code} {s.shortage_board} 版
                    </li>
                  ))}
                </ul>
              )}
            </section>
          )}
          {data?.mrp_explode?.steps && (
            <section>
              <h3 className="font-medium">算料展开</h3>
              <ol className="mt-1 list-decimal pl-5 text-[var(--text-muted)]">
                {data.mrp_explode.steps.slice(0, 6).map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
              </ol>
            </section>
          )}
          <section>
            <h3 className="font-medium">工单 ({data?.work_orders.length ?? 0})</h3>
            <ul className="mt-1 space-y-1 text-xs">
              {(data?.work_orders ?? []).map((w) => (
                <li key={w.wo_no}>
                  {w.wo_no} · {w.wo_type} · {w.qty_board_plan} 版
                </li>
              ))}
            </ul>
          </section>
          <section>
            <h3 className="font-medium">生产任务 ({data?.tasks.length ?? 0})</h3>
            <ul className="mt-1 space-y-1 text-xs">
              {(data?.tasks ?? []).slice(0, 12).map((t) => (
                <li key={t.task_id}>
                  {t.group_code} {t.task_date} · {t.qty_board} 版
                </li>
              ))}
            </ul>
          </section>
          <Link to="/schedule" className="inline-block text-[var(--accent)] underline">
            打开生产排程
          </Link>
        </div>
      </div>
    </div>
  );
}
