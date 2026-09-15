import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ObjectTable } from "../../ui/ObjectTable";
import {
  renderDate,
  renderMoney,
  renderProgress,
  renderStatusTag,
  renderTrafficLight,
  type OrderRow,
} from "../../ui/cellRenderers";
import { useAuth } from "../../shell/auth";
import { OrderDetailDrawer } from "./OrderDetailDrawer";

type ApiData = {
  view: string;
  stats: { total: number; pending_schedule: number; avg_kitting: number; near_due: number };
  rows: OrderRow[];
  field_perm: { amount_hidden: boolean };
};

export function OrdersPage() {
  const auth = useAuth();
  const navigate = useNavigate();
  const [view, setView] = useState("all");
  const [search, setSearch] = useState("");
  const [data, setData] = useState<ApiData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [detailNo, setDetailNo] = useState<string | null>(null);
  const [poolBusy, setPoolBusy] = useState(false);

  const load = useCallback(() => {
    setError(null);
    fetch(`/api/mis/orders?view=${encodeURIComponent(view)}`, {
      headers: auth.headers(),
    })
      .then(async (r) => {
        if (!r.ok) throw new Error(await r.text());
        return r.json();
      })
      .then((j) => setData(j.data))
      .catch((e) => setError(String(e)));
  }, [auth, view]);

  useEffect(() => {
    load();
  }, [load]);

  const filtered = useMemo(() => {
    const rows = data?.rows ?? [];
    const q = search.trim().toLowerCase();
    if (!q) return rows;
    return rows.filter(
      (r) =>
        r.order_no.toLowerCase().includes(q) ||
        r.customer.toLowerCase().includes(q) ||
        r.item_code.toLowerCase().includes(q),
    );
  }, [data, search]);

  const toggle = (no: string) => {
    setSelected((prev) => {
      const n = new Set(prev);
      if (n.has(no)) n.delete(no);
      else n.add(no);
      return n;
    });
  };

  const addToPool = async () => {
    const order_nos = [...selected];
    if (order_nos.length === 0) return;
    setPoolBusy(true);
    setError(null);
    try {
      const r = await fetch("/api/mis/orders/scheduling-pool", {
        method: "POST",
        headers: { ...auth.headers(), "Content-Type": "application/json" },
        body: JSON.stringify({ order_nos }),
      });
      const j = await r.json();
      if (j.code !== 0) throw new Error(j.message || "加入失败");
      setSelected(new Set());
      setView("pending_schedule");
      load();
    } catch (e) {
      setError(String(e));
    } finally {
      setPoolBusy(false);
    }
  };

  const columns = useMemo(() => {
    const canSelect = auth.role === "GM" || auth.role === "PMC";
    const cols = [
      ...(canSelect
        ? [
            {
              key: "sel",
              label: "",
              width: 36,
              render: (r: OrderRow) => (
                <input
                  type="checkbox"
                  checked={selected.has(r.order_no)}
                  onChange={() => toggle(r.order_no)}
                />
              ),
            },
          ]
        : []),
      {
        key: "order_no",
        label: "订单号",
        width: 120,
        render: (r: OrderRow) => (
          <button
            type="button"
            className="font-mono text-[var(--accent)] hover:underline"
            onClick={() => setDetailNo(r.order_no)}
          >
            {r.order_no}
          </button>
        ),
      },
      { key: "customer", label: "客户", render: (r: OrderRow) => r.customer },
      {
        key: "amount",
        label: "金额",
        align: "right" as const,
        render: (r: OrderRow) => renderMoney(r.amount),
      },
      {
        key: "due_date",
        label: "交期",
        render: (r: OrderRow) => renderDate(r.due_date),
      },
      {
        key: "remain_days",
        label: "剩余天数",
        align: "center" as const,
        render: (r: OrderRow) => renderTrafficLight(r.remain_days),
      },
      {
        key: "kitting",
        label: "齐套率",
        render: (r: OrderRow) => renderProgress(r.kitting_rate_pct),
      },
      {
        key: "status",
        label: "状态",
        render: (r: OrderRow) => renderStatusTag(r.order_status),
      },
      { key: "sales", label: "销售", render: (r: OrderRow) => r.sales_name },
    ];
    if (data?.field_perm.amount_hidden) {
      return cols.filter((c) => c.key !== "amount");
    }
    return cols;
  }, [auth.role, data?.field_perm.amount_hidden, selected]);

  const stats = data?.stats;
  const canPool = auth.role === "GM" || auth.role === "PMC";

  return (
    <div>
      {error && (
        <p className="px-6 pt-4 text-sm text-red-600" role="alert">
          {error}
        </p>
      )}
      {auth.role === "SALES" && (
        <p className="px-6 pt-2 text-xs text-[var(--text-muted)]">
          数据权限演示：仅显示名下订单；金额字段已隐藏。
        </p>
      )}
      <ObjectTable
        title="销售订单"
        views={[
          { id: "all", label: "全部", count: stats?.total },
          { id: "pending_schedule", label: "待排产池", count: stats?.pending_schedule },
          { id: "near_due", label: "临期7天", count: stats?.near_due },
          { id: "low_kitting", label: "齐套不足" },
        ]}
        activeView={view}
        onViewChange={setView}
        stats={[
          { label: "订单总数", value: stats?.total ?? "—" },
          { label: "待排产", value: stats?.pending_schedule ?? "—" },
          { label: "平均齐套率", value: stats ? `${stats.avg_kitting}%` : "—" },
          { label: "临期7天", value: stats?.near_due ?? "—" },
        ]}
        search={search}
        onSearchChange={setSearch}
        columns={columns}
        rows={filtered}
        rowKey={(r) => r.order_no}
        toolbar={
          canPool ? (
            <>
              <button
                type="button"
                disabled={poolBusy || selected.size === 0}
                className="rounded border px-2 py-1 text-xs disabled:opacity-40"
                style={{ borderColor: "var(--line)" }}
                onClick={addToPool}
              >
                批量加入排产池
              </button>
              <Link
                to="/schedule"
                className="rounded border px-2 py-1 text-xs"
                style={{ borderColor: "var(--line)" }}
                onClick={(e) => {
                  if (selected.size > 0) {
                    e.preventDefault();
                    void addToPool().then(() => navigate("/schedule"));
                  }
                }}
              >
                一键倒排 →
              </Link>
            </>
          ) : undefined
        }
      />
      {selected.size > 0 && canPool && (
        <p className="px-6 text-xs text-[var(--text-muted)]">已选 {selected.size} 张单</p>
      )}
      <OrderDetailDrawer orderNo={detailNo} onClose={() => setDetailNo(null)} />
    </div>
  );
}
