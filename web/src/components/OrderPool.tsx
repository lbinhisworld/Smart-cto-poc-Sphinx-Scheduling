import type { KitCheck } from "../types/kit";
import type { OrderRow } from "../types/schedule";
import { daysUntil } from "../utils/dates";
import { uomLabel } from "../utils/uomLabels";

type Props = {
  orders: OrderRow[];
  selected: Set<string>;
  today: string;
  boardFilterOrderNo: string | null;
  onToggle: (orderNo: string) => void;
  onDueChange: (orderNo: string, due: string) => void;
  onBoardFilter: (orderNo: string | null) => void;
  onReloadSeed: () => void;
  onShowBom: (order: OrderRow) => void;
  onShowKit?: (orderNo: string) => void;
  kitByOrder?: Map<string, KitCheck>;
  busy: boolean;
  /** 侧栏内嵌时隐藏重复标题 */
  embedded?: boolean;
  showCheckbox?: boolean;
  dueReadOnly?: boolean;
  onRemoveFromPool?: (orderNo: string) => void;
};

function dueTone(days: number): string {
  if (days < 0) return "text-rose-400";
  if (days <= 4) return "text-amber-400";
  return "text-emerald-400";
}

export function OrderPool({
  orders,
  selected,
  today,
  boardFilterOrderNo,
  onToggle,
  onDueChange,
  onBoardFilter,
  onReloadSeed,
  onShowKit,
  onShowBom,
  kitByOrder,
  busy,
  embedded = false,
  showCheckbox = true,
  dueReadOnly = false,
  onRemoveFromPool,
}: Props) {
  return (
    <section className={embedded ? "" : "rounded-lg border border-slate-800 bg-slate-900/50 p-3"}>
      {!embedded && (
        <>
          <h2 className="text-sm font-semibold text-slate-200">订单池</h2>
          <p className="mt-1 text-xs text-slate-500">
            共 {orders.length} 单 · 勾选参与倒排 · 「看板」仅显示该单任务
          </p>
        </>
      )}
      {embedded && (
        <p className="mb-2 text-[10px] text-slate-500">
          勾选参与倒排 · 「看板」仅显示该单任务
        </p>
      )}
      {!embedded && (
        <button
          type="button"
          disabled={busy}
          onClick={onReloadSeed}
          className="mt-2 w-full rounded border border-slate-600 py-1.5 text-[11px] text-slate-300 hover:bg-slate-800 disabled:opacity-40"
        >
          重导演示数据
        </button>
      )}
      <ul className={`space-y-2 ${embedded ? "" : "mt-3 max-h-[70vh] overflow-y-auto"}`}>
        {orders.map((o) => {
          const days = daysUntil(o.due_date, today);
          const filtering = boardFilterOrderNo === o.order_no;
          const kit = kitByOrder?.get(o.order_no);
          return (
            <li
              key={o.order_no}
              className={`rounded border p-2 text-xs ${
                filtering
                  ? "border-sky-500 bg-sky-950/40"
                  : "border-slate-800 bg-slate-950/50"
              }`}
            >
              <label
                className={`flex items-start gap-2 ${showCheckbox ? "cursor-pointer" : ""}`}
              >
                {showCheckbox && (
                  <input
                    type="checkbox"
                    className="mt-0.5"
                    checked={selected.has(o.order_no)}
                    disabled={busy}
                    onChange={() => onToggle(o.order_no)}
                  />
                )}
                <span className="flex-1">
                  <span className="font-medium text-slate-100">{o.order_no}</span>
                  <span className="text-slate-500"> · {o.item_code}</span>
                  {o.bom_route?.item_name && (
                    <span className="text-slate-600"> {o.bom_route.item_name}</span>
                  )}
                  <div className="text-slate-400">
                    {o.qty_order}
                    {uomLabel(o.unit)}
                    {o.sales_name ? (
                      <span className="text-sky-400/90"> · 销售 {o.sales_name}</span>
                    ) : null}
                  </div>
                  <div className="text-slate-500">{o.customer}</div>
                </span>
              </label>
              {o.bom_route?.summary_text && (
                <p className="mt-1.5 leading-snug text-violet-300/90">
                  工艺：{o.bom_route.summary_text}
                </p>
              )}
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <span className="text-slate-500">交期</span>
                <input
                  type="date"
                  disabled={busy || dueReadOnly}
                  className="rounded border border-slate-700 bg-slate-900 px-1 py-0.5 text-slate-200 disabled:opacity-60"
                  value={o.due_date}
                  onChange={(e) => onDueChange(o.order_no, e.target.value)}
                />
                <span className={dueTone(days)}>余 {days} 天</span>
              </div>
              {kit && (
                <p className="mt-1 text-[10px]">
                  齐套{" "}
                  <span className={kit.is_kitted ? "text-emerald-400" : "text-amber-400"}>
                    {kit.is_kitted ? "✓" : "✗"}
                  </span>
                  {kit.kit_ready_date && (
                    <span className="text-slate-500"> · {kit.kit_ready_date}</span>
                  )}
                </p>
              )}
              <div className="mt-2 flex flex-wrap gap-1">
                {kit && onShowKit && (
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => onShowKit(o.order_no)}
                    className="flex-1 rounded border border-amber-700/50 px-2 py-1 text-[11px] text-amber-200 hover:bg-amber-950/40"
                  >
                    齐套详情
                  </button>
                )}
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => onShowBom(o)}
                  className="flex-1 rounded border border-violet-700/60 px-2 py-1 text-[11px] text-violet-200 hover:bg-violet-950/50"
                >
                  BOM / 工艺
                </button>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => onBoardFilter(filtering ? null : o.order_no)}
                  className={`flex-1 rounded px-2 py-1 text-[11px] ${
                    filtering
                      ? "bg-sky-700 text-white"
                      : "border border-slate-600 text-slate-300 hover:bg-slate-800"
                  }`}
                >
                  {filtering ? "看板：全部" : "看板：此单"}
                </button>
                {onRemoveFromPool && (
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => onRemoveFromPool(o.order_no)}
                    className="flex-1 rounded border border-rose-800/60 px-2 py-1 text-[11px] text-rose-300 hover:bg-rose-950/40"
                  >
                    移出排程池
                  </button>
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
