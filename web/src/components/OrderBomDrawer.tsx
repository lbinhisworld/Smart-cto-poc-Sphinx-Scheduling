import { useEffect, useState } from "react";
import { fetchBomDesign, fetchBomExplode } from "../api/client";
import type { BomDesign, BomExplode } from "../types/bom";
import type { OrderRow, ScheduleResult } from "../types/schedule";
import { BomDiagram, wosForOrder } from "./BomDiagram";

type Props = {
  order: OrderRow | null;
  today: string;
  result: ScheduleResult | null;
  onClose: () => void;
};

export function OrderBomDrawer({ order, today, result, onClose }: Props) {
  const [design, setDesign] = useState<BomDesign | null>(null);
  const [explode, setExplode] = useState<BomExplode | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!order) {
      setDesign(null);
      setExplode(null);
      return;
    }
    let cancelled = false;
    setError(null);
    Promise.all([
      fetchBomDesign(order.item_code),
      fetchBomExplode(order.item_code, order.qty_order, order.unit, today),
    ])
      .then(([d, e]) => {
        if (!cancelled) {
          setDesign(d);
          setExplode(e);
        }
      })
      .catch((err) => {
        if (!cancelled) setError(String(err));
      });
    return () => {
      cancelled = true;
    };
  }, [order, today]);

  if (!order) return null;

  const instanceWos = wosForOrder(result, order.order_no);

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/60 p-3 sm:items-center"
      role="dialog"
      aria-labelledby="bom-drawer-title"
    >
      <div className="max-h-[90vh] w-full max-w-4xl overflow-y-auto rounded-lg border border-slate-700 bg-slate-900 shadow-xl">
        <div className="sticky top-0 flex items-center justify-between border-b border-slate-800 bg-slate-900/95 px-4 py-3">
          <div>
            <h3 id="bom-drawer-title" className="text-sm font-semibold text-slate-100">
              BOM / 工艺 · {order.order_no}
            </h3>
            <p className="text-[11px] text-slate-500">
              {order.item_code} · {order.qty_order}
              {order.unit}
              {order.sales_name ? ` · 销售 ${order.sales_name}` : ""}
            </p>
            <p className="text-[10px] text-slate-600">{order.customer}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded border border-slate-600 px-2 py-1 text-xs text-slate-300 hover:bg-slate-800"
          >
            关闭
          </button>
        </div>
        <div className="p-4">
          {error && <p className="mb-2 text-xs text-rose-400">{error}</p>}
          {design ? (
            <BomDiagram
              design={design}
              explode={explode}
              instanceWos={instanceWos}
              compact
            />
          ) : (
            <p className="text-xs text-slate-500">加载中…</p>
          )}
          {result && instanceWos.length === 0 && (
            <p className="mt-3 text-[11px] text-slate-600">
              尚未倒排：实例工单将在「一键倒排」后显示。
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
