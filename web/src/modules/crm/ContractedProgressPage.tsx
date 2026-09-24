import { useEffect, useState } from "react";
import { useAuth } from "../../shell/auth";

type Tag = { label: string; tone: string };
type Row = {
  order_no: string;
  line_no: number;
  item_code: string;
  item_name: string;
  spec: string;
  sales_qty: number;
  unit: string;
  unit_price: number;
  line_amount: number;
  suggest_price: number | null;
  discount_label: string;
  suggest_amount: number | null;
  shipped_qty: number;
  pending_ship_qty: number;
  scheduled_qty: number;
  inbound_qty: number;
  pending_inbound_qty: number;
  return_qty: number;
  cost_label?: string;
  tags: Record<"contract" | "schedule" | "purchase" | "material" | "produce" | "inbound", Tag>;
};

const TAG_KEYS = ["contract", "schedule", "purchase", "material", "produce", "inbound"] as const;

function Pill({ tag }: { tag: Tag }) {
  const done = tag.tone === "done";
  return (
    <span
      className="inline-block rounded px-2 py-0.5 text-xs"
      style={{
        background: done ? "rgba(14, 165, 233, 0.18)" : "rgba(245, 158, 11, 0.2)",
        color: done ? "#0369a1" : "#b45309",
      }}
    >
      {tag.label}
    </span>
  );
}

function money(n: number | null) {
  return n == null ? "-" : n.toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export function ContractedProgressPage() {
  const auth = useAuth();
  const [rows, setRows] = useState<Row[]>([]);
  const [open, setOpen] = useState<Row | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/crm/contracted-progress", { headers: auth.headers() })
      .then((r) => r.json())
      .then((j) => setRows(j.data ?? []))
      .catch((e) => setError(String(e)));
  }, [auth]);

  return (
    <div className="p-4">
      <h1 className="text-lg font-semibold">签约产品生产进度</h1>
      <p className="mt-1 text-xs text-[var(--text-muted)]">
        一行一个签约产品。蓝是已完成，琥珀是未开始或进行中。采购、回料、发货在金蝶同步到达前保持未采购、未回料、未发货。
      </p>
      {error && <p className="mt-2 text-sm text-rose-500">{error}</p>}
      <div className="mt-4 overflow-auto rounded border" style={{ borderColor: "var(--line)" }}>
        <table className="min-w-full text-left text-xs">
          <thead className="text-[var(--text-muted)]">
            <tr>
              {["序号", "订单", "产品编码", "产品名称", "规格型号", "销售数量", "合同状态", "排产情况", "采购情况", "回料情况", "投产情况", "生产入库", "操作"].map((h) => (
                <th key={h} className="whitespace-nowrap px-2 py-2 font-medium">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={`${row.order_no}-${row.line_no}`} className="border-t" style={{ borderColor: "var(--line)" }}>
                <td className="px-2 py-2">{i + 1}</td>
                <td className="px-2 py-2 font-mono">{row.order_no}</td>
                <td className="px-2 py-2 font-mono">{row.item_code}</td>
                <td className="px-2 py-2">{row.item_name}</td>
                <td className="px-2 py-2">{row.spec || "-"}</td>
                <td className="px-2 py-2 tabular-nums">{row.sales_qty}{row.unit}</td>
                {TAG_KEYS.map((key) => (
                  <td key={key} className="px-2 py-2"><Pill tag={row.tags[key]} /></td>
                ))}
                <td className="px-2 py-2">
                  <button type="button" className="text-[var(--accent)]" onClick={() => setOpen(row)}>查看</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {open && (
        <div className="fixed inset-0 z-40 flex justify-end bg-black/30" onClick={() => setOpen(null)}>
          <aside
            className="h-full w-full max-w-xl overflow-auto p-4"
            style={{ background: "var(--bg-card)" }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between">
              <h2 className="text-base font-semibold">查看</h2>
              <button type="button" onClick={() => setOpen(null)}>关闭</button>
            </div>
            <p className="mt-2 font-mono text-xs">{open.order_no} · {open.item_name}</p>
            <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
              <div><dt className="text-xs text-[var(--text-muted)]">建议售价</dt><dd>{money(open.suggest_price)}</dd></div>
              <div><dt className="text-xs text-[var(--text-muted)]">建议折扣</dt><dd>{open.discount_label}</dd></div>
              <div><dt className="text-xs text-[var(--text-muted)]">销售单价</dt><dd>{money(open.unit_price)}</dd></div>
              <div><dt className="text-xs text-[var(--text-muted)]">销售金额小计</dt><dd>{money(open.line_amount)}</dd></div>
              {open.cost_label && (
                <div><dt className="text-xs text-[var(--text-muted)]">成本总额</dt><dd>{open.cost_label}</dd></div>
              )}
              <div><dt className="text-xs text-[var(--text-muted)]">建议售价小计</dt><dd>{money(open.suggest_amount)}</dd></div>
              <div><dt className="text-xs text-[var(--text-muted)]">已发货数量</dt><dd>{open.shipped_qty}</dd></div>
              <div><dt className="text-xs text-[var(--text-muted)]">待发货数量</dt><dd>{open.pending_ship_qty}</dd></div>
              <div><dt className="text-xs text-[var(--text-muted)]">已排产数量</dt><dd>{open.scheduled_qty}</dd></div>
              <div><dt className="text-xs text-[var(--text-muted)]">已生产入库数量</dt><dd>{open.inbound_qty}</dd></div>
              <div><dt className="text-xs text-[var(--text-muted)]">待生产入库数量</dt><dd>{open.pending_inbound_qty}</dd></div>
              <div><dt className="text-xs text-[var(--text-muted)]">退货数量</dt><dd>{open.return_qty}</dd></div>
            </dl>
            <h3 className="mt-6 text-sm font-semibold">生产进度</h3>
            <dl className="mt-3 grid grid-cols-2 gap-3 text-sm">
              <div><dt className="text-xs text-[var(--text-muted)]">合同状态</dt><dd className="mt-1"><Pill tag={open.tags.contract} /></dd></div>
              <div><dt className="text-xs text-[var(--text-muted)]">排产情况</dt><dd className="mt-1"><Pill tag={open.tags.schedule} /></dd></div>
              <div className="col-span-2"><dt className="text-xs text-[var(--text-muted)]">产品信息</dt><dd>{open.item_name}{open.spec ? ` ${open.spec}` : ""}</dd></div>
              <div><dt className="text-xs text-[var(--text-muted)]">采购情况</dt><dd className="mt-1"><Pill tag={open.tags.purchase} /></dd></div>
              <div><dt className="text-xs text-[var(--text-muted)]">回料情况</dt><dd className="mt-1"><Pill tag={open.tags.material} /></dd></div>
              <div><dt className="text-xs text-[var(--text-muted)]">投产情况</dt><dd className="mt-1"><Pill tag={open.tags.produce} /></dd></div>
              <div><dt className="text-xs text-[var(--text-muted)]">生产入库</dt><dd className="mt-1"><Pill tag={open.tags.inbound} /></dd></div>
            </dl>
          </aside>
        </div>
      )}
    </div>
  );
}
