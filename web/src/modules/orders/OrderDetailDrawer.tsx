import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { requestWithRole } from "../../api/client";
import { formatQtyUnit, formatUnit } from "../../utils/uomDisplay";
import { renderMoney, renderDate, renderProgress, renderStatusTag } from "../../ui/cellRenderers";
import { useAuth } from "../../shell/auth";

type OrderLine = {
  line_no: number;
  item_code: string;
  item_name: string;
  qty: number;
  unit: string;
  unit_price: number;
  line_amount: number;
};

type Breakdown = {
  order: {
    order_no: string;
    customer: string;
    sales_name?: string;
    due_date: string;
    amount?: number;
    order_status?: string;
    schedule_phase?: string;
    kitting_rate_pct?: number | null;
    item_code?: string;
  };
  lines: OrderLine[];
  kitting: { kitting_rate_pct?: number | null; shortages?: { item_code?: string; shortage_board?: number }[] };
  mrp_explode?: { steps?: string[] };
  work_orders: { wo_no: string; wo_type: string; qty_board_plan: number }[];
  tasks: { task_id: number; group_code: string; task_date: string; qty_board: number }[];
};

type Props = {
  orderNo: string | null;
  onClose: () => void;
  onChanged?: () => void;
};

export function OrderDetailDrawer({ orderNo, onClose, onChanged }: Props) {
  const auth = useAuth();
  const navigate = useNavigate();
  const role = auth.role;
  const [data, setData] = useState<Breakdown | null>(null);
  const [tab, setTab] = useState<"detail" | "breakdown">("detail");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!orderNo || !role) return;
    setData(null);
    setTab("detail");
    setErr(null);
    requestWithRole<Breakdown>(
      `/api/mis/orders/${encodeURIComponent(orderNo)}/breakdown`,
      role,
    )
      .then(setData)
      .catch((e) => setErr(String(e)));
  }, [orderNo, role]);

  if (!orderNo) return null;

  const canChange =
    role === "GM" || role === "SALES" || role === "SALES_MGR" || role === "PMC";
  const canDelete = role === "GM" || role === "PMC" || role === "SALES_MGR";

  const goChange = () => {
    navigate(`/changes?order=${encodeURIComponent(orderNo)}&due=${data?.order.due_date ?? ""}`);
    onClose();
  };

  const doDelete = async () => {
    if (!window.confirm(`确认作废订单 ${orderNo}？排程池中的单不可作废。`)) return;
    if (!role) return;
    setBusy(true);
    setErr(null);
    try {
      const r = await fetch(`/api/mis/orders/${encodeURIComponent(orderNo)}`, {
        method: "DELETE",
        headers: { "X-Demo-Role": role },
      });
      const text = await r.text();
      const j = text ? JSON.parse(text) : {};
      if (!r.ok) throw new Error(j.detail || j.message || text);
      onChanged?.();
      onClose();
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  };

  const o = data?.order;
  const lines = data?.lines ?? [];

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/50" role="dialog" onClick={onClose}>
      <div
        className="flex h-full w-full max-w-lg flex-col overflow-hidden shadow-2xl"
        style={{ background: "var(--bg-card)" }}
        onClick={(e) => e.stopPropagation()}
      >
        <div
          className="flex shrink-0 items-start justify-between border-b px-4 py-3"
          style={{ borderColor: "var(--line)" }}
        >
          <div>
            <p className="font-mono text-lg font-semibold">{orderNo}</p>
            <p className="text-xs text-[var(--text-muted)]">{o?.customer ?? "加载中…"}</p>
          </div>
          <button type="button" className="text-sm text-[var(--text-muted)] hover:text-[var(--text-body)]" onClick={onClose}>
            关闭
          </button>
        </div>

        <div className="flex shrink-0 gap-1 border-b px-3 py-2 text-xs" style={{ borderColor: "var(--line)" }}>
          <button
            type="button"
            className={`rounded px-2 py-1 ${tab === "detail" ? "bg-[var(--nav-active-bg)] text-[var(--accent)]" : ""}`}
            onClick={() => setTab("detail")}
          >
            订单详情
          </button>
          <button
            type="button"
            className={`rounded px-2 py-1 ${tab === "breakdown" ? "bg-[var(--nav-active-bg)] text-[var(--accent)]" : ""}`}
            onClick={() => setTab("breakdown")}
          >
            算料 / 工单
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto p-4 text-sm">
          {err && <p className="mb-3 text-xs text-rose-400">{err}</p>}

          {tab === "detail" && (
            <>
              {o && (
                <dl className="grid grid-cols-2 gap-x-3 gap-y-2 text-xs">
                  <dt className="text-[var(--text-muted)]">交期</dt>
                  <dd>{renderDate(o.due_date)}</dd>
                  <dt className="text-[var(--text-muted)]">金额</dt>
                  <dd>{renderMoney(o.amount ?? null)}</dd>
                  <dt className="text-[var(--text-muted)]">状态</dt>
                  <dd>{o.order_status ? renderStatusTag(o.order_status) : "—"}</dd>
                  <dt className="text-[var(--text-muted)]">销售</dt>
                  <dd>{o.sales_name ?? "—"}</dd>
                  <dt className="text-[var(--text-muted)]">齐套率</dt>
                  <dd>{renderProgress(o.kitting_rate_pct ?? null)}</dd>
                </dl>
              )}

              <h3 className="mt-4 text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">
                采购产品清单
              </h3>
              <div className="mt-2 overflow-x-auto rounded border" style={{ borderColor: "var(--line)" }}>
                <table className="w-full text-xs">
                  <thead className="bg-[var(--table-head)] text-[var(--text-muted)]">
                    <tr>
                      <th className="px-2 py-1.5 text-left">行</th>
                      <th className="text-left">品项</th>
                      <th className="text-right">数量</th>
                      <th className="text-right">单价</th>
                      <th className="text-right">行金额</th>
                    </tr>
                  </thead>
                  <tbody>
                    {lines.map((ln) => (
                      <tr key={ln.line_no} className="border-t" style={{ borderColor: "var(--line)" }}>
                        <td className="px-2 py-1.5 tabular-nums">{ln.line_no}</td>
                        <td>
                          <span className="font-mono text-[var(--accent)]">{ln.item_code}</span>
                          <span className="ml-1 text-[var(--text-muted)]">{ln.item_name}</span>
                        </td>
                        <td className="text-right tabular-nums">
                          {formatQtyUnit(ln.qty, ln.unit)}
                          <span className="ml-1 text-[10px] text-[var(--text-muted)]">({formatUnit(ln.unit)})</span>
                        </td>
                        <td className="text-right tabular-nums">{renderMoney(ln.unit_price)}</td>
                        <td className="text-right tabular-nums">{renderMoney(ln.line_amount)}</td>
                      </tr>
                    ))}
                    {!lines.length && !data && (
                      <tr>
                        <td colSpan={5} className="px-2 py-4 text-center text-[var(--text-muted)]">
                          加载明细…
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
              <p className="mt-2 text-[10px] text-[var(--text-muted)]">
                排程仍以订单头品项 {o?.item_code ?? "—"} 为锚；多行明细用于 MIS 采购视图演示。
              </p>
            </>
          )}

          {tab === "breakdown" && data && (
            <div className="space-y-4 text-xs">
              {(data.kitting.shortages ?? []).length > 0 && (
                <ul className="list-disc pl-4 text-rose-400">
                  {data.kitting.shortages!.map((s, i) => (
                    <li key={i}>
                      缺 {s.item_code} {s.shortage_board} 版
                    </li>
                  ))}
                </ul>
              )}
              <section>
                <h3 className="font-medium">工单 ({data.work_orders.length})</h3>
                <ul className="mt-1 space-y-1">
                  {data.work_orders.map((w) => (
                    <li key={w.wo_no}>
                      {w.wo_no} · {w.wo_type} · {w.qty_board_plan} 版
                    </li>
                  ))}
                </ul>
              </section>
              <Link to="/schedule" className="text-[var(--accent)] underline">
                打开生产排程
              </Link>
            </div>
          )}
        </div>

        <div
          className="flex shrink-0 flex-wrap gap-2 border-t px-4 py-3"
          style={{ borderColor: "var(--line)" }}
        >
          {canChange && (
            <button
              type="button"
              className="rounded border border-sky-700 bg-sky-950/50 px-3 py-1.5 text-xs text-sky-200"
              onClick={goChange}
            >
              变更
            </button>
          )}
          {canDelete && (
            <button
              type="button"
              disabled={busy}
              className="rounded border border-rose-800 bg-rose-950/40 px-3 py-1.5 text-xs text-rose-200 disabled:opacity-40"
              onClick={() => void doDelete()}
            >
              作废 / 删除
            </button>
          )}
          <button
            type="button"
            className="ml-auto rounded border px-3 py-1.5 text-xs"
            style={{ borderColor: "var(--line)" }}
            onClick={onClose}
          >
            关闭
          </button>
        </div>
      </div>
    </div>
  );
}
