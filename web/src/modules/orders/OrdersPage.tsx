import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { formatUnit } from "../../utils/uomDisplay";
import { ObjectTable } from "../../ui/ObjectTable";
import {
  renderDate,
  renderMoney,
  renderProgress,
  renderSchedulePhaseTag,
  renderTrafficLight,
  type OrderRow,
} from "../../ui/cellRenderers";
import { useAuth } from "../../shell/auth";
import { CreateOrderModal } from "./CreateOrderModal";
import { OrderDetailDrawer } from "./OrderDetailDrawer";

type ApiData = {
  view: string;
  stats: {
    total: number;
    pending?: number;
    in_scheduling?: number;
    in_production?: number;
    pending_schedule: number;
    avg_kitting: number;
    near_due: number;
  };
  rows: OrderRow[];
  field_perm: { amount_hidden: boolean };
};

const ORDER_VIEWS = new Set([
  "all",
  "pending",
  "in_scheduling",
  "pending_schedule",
  "in_production",
  "near_due",
  "low_kitting",
]);

export function OrdersPage() {
  const auth = useAuth();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const initialView = searchParams.get("view");
  const [view, setView] = useState(() =>
    initialView && ORDER_VIEWS.has(initialView) ? initialView : "all",
  );
  const [search, setSearch] = useState("");
  const [data, setData] = useState<ApiData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [detailNo, setDetailNo] = useState<string | null>(null);
  const [poolBusy, setPoolBusy] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);

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

  useEffect(() => {
    const v = searchParams.get("view");
    if (v && ORDER_VIEWS.has(v) && v !== view) setView(v);
  }, [searchParams, view]);

  useEffect(() => {
    const n = searchParams.get("dueNegotiate") || searchParams.get("order");
    if (n) setDetailNo(n);
  }, [searchParams]);

  const onViewChange = (id: string) => {
    setView(id);
    const next = new URLSearchParams(searchParams);
    if (id === "all") next.delete("view");
    else next.set("view", id);
    setSearchParams(next, { replace: true });
  };

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
      setView("in_scheduling");
      load();
    } catch (e) {
      setError(String(e));
    } finally {
      setPoolBusy(false);
    }
  };

  const canChange =
    auth.role === "GM" || auth.role === "SALES" || auth.role === "SALES_MGR" || auth.role === "PMC";
  const canDelete = auth.role === "GM" || auth.role === "PMC" || auth.role === "SALES_MGR";

  const formatSummary = (raw: string) =>
    raw.replace(/\bBOX\b/g, formatUnit("BOX")).replace(/\bPCS\b/g, formatUnit("PCS"));

  const cancelOrder = useCallback(
    async (orderNo: string) => {
      if (!window.confirm(`确认作废 ${orderNo}？`)) return;
      try {
        const r = await fetch(`/api/mis/orders/${encodeURIComponent(orderNo)}`, {
          method: "DELETE",
          headers: auth.headers(),
        });
        const j = await r.json();
        if (!r.ok) throw new Error(j.detail || j.message);
        load();
      } catch (e) {
        setError(String(e));
      }
    },
    [auth, load],
  );

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
        key: "lines",
        label: "产品清单",
        render: (r: OrderRow) => (
          <button
            type="button"
            className="max-w-[220px] truncate text-left text-xs text-[var(--text-body)] hover:text-[var(--accent)]"
            title={r.lines_summary}
            onClick={() => setDetailNo(r.order_no)}
          >
            {r.lines_summary ? formatSummary(r.lines_summary) : r.item_code}
            {(r.line_count ?? 1) > 1 && (
              <span className="ml-1 text-[var(--text-muted)]">({r.line_count}行)</span>
            )}
          </button>
        ),
      },
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
        label: "排程阶段",
        render: (r: OrderRow) => renderSchedulePhaseTag(r.schedule_phase),
      },
      { key: "sales", label: "销售", render: (r: OrderRow) => r.sales_name },
      {
        key: "actions",
        label: "操作",
        width: 120,
        render: (r: OrderRow) => (
          <span className="flex flex-wrap gap-1 text-[11px]">
            <button
              type="button"
              className="text-[var(--accent)] hover:underline"
              onClick={() => setDetailNo(r.order_no)}
            >
              明细
            </button>
            {canChange && (
              <Link
                to={`/changes?order=${encodeURIComponent(r.order_no)}&due=${r.due_date}`}
                className="text-sky-400 hover:underline"
              >
                变更
              </Link>
            )}
            {canDelete && (
              <button
                type="button"
                className="text-rose-400 hover:underline"
                onClick={() => void cancelOrder(r.order_no)}
              >
                删除
              </button>
            )}
          </span>
        ),
      },
    ];
    if (data?.field_perm.amount_hidden) {
      return cols.filter((c) => c.key !== "amount");
    }
    return cols;
  }, [
    auth.role,
    canChange,
    canDelete,
    cancelOrder,
    data?.field_perm.amount_hidden,
    selected,
  ]);

  const stats = data?.stats;
  const canPool = auth.role === "GM" || auth.role === "PMC";
  const canCreate =
    auth.role === "GM" || auth.role === "SALES" || auth.role === "SALES_MGR" || auth.role === "PMC";

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
          { id: "pending", label: "待排程", count: stats?.pending ?? stats?.pending_schedule },
          { id: "in_scheduling", label: "排程中", count: stats?.in_scheduling },
          { id: "in_production", label: "生产中", count: stats?.in_production },
          { id: "near_due", label: "临期7天", count: stats?.near_due },
          { id: "low_kitting", label: "齐套不足" },
        ]}
        activeView={view}
        onViewChange={onViewChange}
        stats={[
          { label: "订单总数", value: stats?.total ?? "—" },
          { label: "待排程", value: stats?.pending ?? stats?.pending_schedule ?? "—" },
          { label: "排程中", value: stats?.in_scheduling ?? "—" },
          { label: "平均齐套率", value: stats ? `${stats.avg_kitting}%` : "—" },
          { label: "临期7天", value: stats?.near_due ?? "—" },
        ]}
        search={search}
        onSearchChange={setSearch}
        columns={columns}
        rows={filtered}
        rowKey={(r) => r.order_no}
        toolbar={
          <>
            {(auth.role === "GM" || auth.role === "SALES" || auth.role === "SALES_MGR" || auth.role === "FIN") && (
              <Link
                to="/orders/quotes"
                className="rounded border px-2 py-1 text-xs"
                style={{ borderColor: "var(--line)" }}
              >
                产品报价
              </Link>
            )}
            {canCreate && (
              <button
                type="button"
                className="rounded bg-[var(--accent)] px-2 py-1 text-xs font-medium text-slate-950"
                onClick={() => setCreateOpen(true)}
              >
                新建订单
              </button>
            )}
            {canPool ? (
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
            ) : null}
          </>
        }
      />
      <CreateOrderModal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={(orderNo) => {
          setView("pending");
          onViewChange("pending");
          load();
          setDetailNo(orderNo);
        }}
      />
      {selected.size > 0 && canPool && (
        <p className="px-6 text-xs text-[var(--text-muted)]">已选 {selected.size} 张单</p>
      )}
      <OrderDetailDrawer
        orderNo={detailNo}
        onClose={() => setDetailNo(null)}
        onChanged={() => load()}
        initialTab={searchParams.get("dueNegotiate") ? "due" : "detail"}
      />
    </div>
  );
}
