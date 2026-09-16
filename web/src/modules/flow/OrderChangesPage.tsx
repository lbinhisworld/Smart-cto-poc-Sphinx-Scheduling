import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useAuth } from "../../shell/auth";

type ChangeRow = {
  id: number;
  order_no: string;
  status: string;
  impact: { diff_summary?: string; ripple_count?: number };
};

export function OrderChangesPage() {
  const auth = useAuth();
  const [searchParams] = useSearchParams();
  const [rows, setRows] = useState<ChangeRow[]>([]);
  const [orderNo, setOrderNo] = useState(() => searchParams.get("order") ?? "SO-002");
  const [newDue, setNewDue] = useState(() => searchParams.get("due") ?? "2026-09-20");

  useEffect(() => {
    const o = searchParams.get("order");
    const d = searchParams.get("due");
    if (o) setOrderNo(o);
    if (d) setNewDue(d);
  }, [searchParams]);

  const load = useCallback(() => {
    fetch("/api/order-changes", { headers: auth.headers() })
      .then((r) => r.json())
      .then((j) => setRows(j.data ?? []));
  }, [auth]);

  useEffect(() => {
    load();
  }, [load]);

  const submit = () => {
    fetch("/api/order-changes", {
      method: "POST",
      headers: { ...auth.headers(), "Content-Type": "application/json" },
      body: JSON.stringify({ order_no: orderNo, new_due: newDue }),
    }).then(() => load());
  };

  const approve = (id: number) => {
    fetch(`/api/order-changes/${id}/approve`, {
      method: "POST",
      headers: auth.headers(),
    }).then(() => load());
  };

  const canSubmit = auth.role === "SALES" || auth.role === "SALES_MGR" || auth.role === "GM";
  const canApprove = auth.role === "PMC" || auth.role === "GM";

  return (
    <div className="px-6 py-4">
      <h2 className="text-lg font-semibold">订单变更 · 影响清单</h2>
      {canSubmit && (
        <div className="mt-3 flex flex-wrap gap-2 text-sm">
          <input
            className="rounded border border-slate-700 bg-slate-950 px-2 py-1"
            value={orderNo}
            onChange={(e) => setOrderNo(e.target.value)}
          />
          <input
            className="rounded border border-slate-700 bg-slate-950 px-2 py-1"
            value={newDue}
            onChange={(e) => setNewDue(e.target.value)}
          />
          <button type="button" className="rounded border border-slate-600 px-3 py-1" onClick={submit}>
            销售提交变更
          </button>
        </div>
      )}
      <ul className="mt-4 space-y-3">
        {rows.map((r) => (
          <li key={r.id} className="rounded-lg border border-slate-800 bg-slate-900 p-3 text-xs">
            <p className="font-mono text-slate-100">
              #{r.id} {r.order_no} · {r.status}
            </p>
            <p className="mt-1 text-slate-400">{r.impact?.diff_summary ?? "—"}</p>
            <p className="text-slate-500">涟漪订单数 {r.impact?.ripple_count ?? 0}</p>
            {canApprove && r.status === "PENDING" && (
              <button
                type="button"
                className="mt-2 rounded bg-emerald-800 px-2 py-1"
                onClick={() => approve(r.id)}
              >
                PMC 批准
              </button>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
