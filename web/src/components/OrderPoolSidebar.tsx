import { useMemo, useState } from "react";
import type { KitCheck } from "../types/kit";
import type { OrderRow, SchedulePhase } from "../types/schedule";
import { sortByDueAsc } from "../utils/orderCommitments";
import { OrderPool } from "./OrderPool";

const TABS: { id: SchedulePhase; label: string }[] = [
  { id: "PENDING", label: "待排程" },
  { id: "IN_SCHEDULING", label: "排程中" },
  { id: "IN_PRODUCTION", label: "生产中" },
  { id: "COMPLETED", label: "已完结" },
];

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  orders: OrderRow[];
  pendingSelected: Set<string>;
  today: string;
  boardFilterOrderNo: string | null;
  onTogglePending: (orderNo: string) => void;
  onDueChange: (orderNo: string, due: string) => void;
  onBoardFilter: (orderNo: string | null) => void;
  onReloadSeed: () => void;
  onShowBom: (order: OrderRow) => void;
  onShowKit?: (orderNo: string) => void;
  kitByOrder?: Map<string, KitCheck>;
  onSelectAllPending: () => void;
  onClearPending: () => void;
  onAddToPool: () => void;
  onRemoveFromPool: (orderNo: string) => void;
  onTrialPool: () => void;
  onPublishPool: () => void;
  poolCount: number;
  busy: boolean;
};

export function OrderPoolSidebar({
  open,
  onOpenChange,
  orders,
  pendingSelected,
  today,
  boardFilterOrderNo,
  onTogglePending,
  onDueChange,
  onBoardFilter,
  onReloadSeed,
  onShowBom,
  onShowKit,
  kitByOrder,
  onSelectAllPending,
  onClearPending,
  onAddToPool,
  onRemoveFromPool,
  onTrialPool,
  onPublishPool,
  poolCount,
  busy,
}: Props) {
  const [tab, setTab] = useState<SchedulePhase>("PENDING");

  const counts = useMemo(() => {
    const m: Record<SchedulePhase, number> = {
      PENDING: 0,
      IN_SCHEDULING: 0,
      IN_PRODUCTION: 0,
      COMPLETED: 0,
    };
    for (const o of orders) {
      const p = (o.schedule_phase ?? "PENDING") as SchedulePhase;
      if (p in m) m[p] += 1;
    }
    return m;
  }, [orders]);

  const tabOrders = useMemo(() => {
    const filtered = orders.filter(
      (o) => (o.schedule_phase ?? "PENDING") === tab,
    );
    return sortByDueAsc(filtered);
  }, [orders, tab]);

  return (
    <>
      {!open && (
        <button
          type="button"
          onClick={() => onOpenChange(true)}
          className="hidden lg:flex shrink-0 flex-col items-center justify-center gap-2 rounded-lg border border-slate-800 bg-slate-900/80 px-1.5 py-4 text-[10px] text-slate-400 hover:bg-slate-800 hover:text-slate-200 w-11"
          title="展开订单池"
        >
          <span className="text-lg leading-none text-slate-300">≡</span>
          <span className="writing-vertical-rl tracking-wider">订单池</span>
          <span className="rounded bg-slate-800 px-1 py-0.5 text-[9px] text-emerald-400">
            池 {poolCount}
          </span>
        </button>
      )}

      {open && (
        <div
          className="fixed inset-0 z-40 bg-black/50 lg:hidden"
          aria-hidden
          onClick={() => onOpenChange(false)}
        />
      )}

      <aside
        className={`z-50 flex max-h-[85vh] shrink-0 flex-col border-slate-800 bg-slate-950 transition-[width,transform] duration-200 ease-out lg:max-h-none ${
          open
            ? "fixed bottom-0 left-0 top-24 w-[min(100vw,20rem)] border-r shadow-xl lg:static lg:top-auto lg:w-72 lg:shadow-none"
            : "pointer-events-none fixed -translate-x-full w-0 overflow-hidden lg:static lg:translate-x-0 lg:w-0 lg:border-0"
        }`}
      >
        <div className="flex items-center justify-between gap-2 border-b border-slate-800 px-3 py-2 lg:rounded-t-lg lg:border lg:border-b-0 lg:border-slate-800 lg:bg-slate-900/50">
          <div className="min-w-0">
            <p className="text-sm font-semibold text-slate-200">订单池</p>
            <p className="truncate text-[10px] text-slate-500">
              排程中 {poolCount} 单 · 整池同进退
              {boardFilterOrderNo && (
                <span className="ml-1 text-sky-400">· 看板 {boardFilterOrderNo}</span>
              )}
            </p>
          </div>
          <button
            type="button"
            onClick={() => onOpenChange(false)}
            className="shrink-0 rounded border border-slate-600 px-2 py-1 text-[11px] text-slate-300 hover:bg-slate-800"
          >
            收起
          </button>
        </div>

        <div className="flex gap-0.5 border-b border-slate-800 px-2 py-1.5 lg:border-x lg:border-slate-800 lg:bg-slate-900/30">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setTab(t.id)}
              className={`flex-1 rounded px-1 py-1 text-[10px] leading-tight ${
                tab === t.id
                  ? "bg-slate-700 text-slate-100"
                  : "text-slate-500 hover:bg-slate-800 hover:text-slate-300"
              }`}
            >
              {t.label}
              <span className="ml-0.5 text-slate-600">{counts[t.id]}</span>
            </button>
          ))}
        </div>

        <div className="space-y-2 border-b border-slate-800 px-3 py-2 lg:border lg:border-t-0 lg:border-slate-800 lg:bg-slate-900/30">
          {tab === "PENDING" && (
            <>
              <div className="flex gap-1">
                <button
                  type="button"
                  disabled={busy || tabOrders.length === 0}
                  onClick={onSelectAllPending}
                  className="flex-1 rounded border border-slate-700 py-1 text-[11px] text-slate-300 hover:bg-slate-800 disabled:opacity-40"
                >
                  全选
                </button>
                <button
                  type="button"
                  disabled={busy || pendingSelected.size === 0}
                  onClick={onClearPending}
                  className="flex-1 rounded border border-slate-700 py-1 text-[11px] text-slate-300 hover:bg-slate-800 disabled:opacity-40"
                >
                  清空
                </button>
              </div>
              <button
                type="button"
                disabled={busy || pendingSelected.size === 0}
                onClick={onAddToPool}
                className="w-full rounded bg-sky-700 py-1.5 text-[11px] font-medium text-white hover:bg-sky-600 disabled:opacity-40"
              >
                加入排程中 ({pendingSelected.size})
              </button>
            </>
          )}
          {tab === "IN_SCHEDULING" && (
            <>
              <button
                type="button"
                disabled={busy || poolCount === 0}
                onClick={onTrialPool}
                className="w-full rounded border border-slate-600 py-1.5 text-[11px] text-slate-200 hover:bg-slate-800 disabled:opacity-40"
              >
                试排（整池）
              </button>
              <button
                type="button"
                disabled={busy || poolCount === 0}
                onClick={onPublishPool}
                className="w-full rounded bg-emerald-700 py-1.5 text-[11px] font-medium text-white hover:bg-emerald-600 disabled:opacity-40"
              >
                保存发布
              </button>
              <p className="text-[10px] text-slate-500">
                E1/E2 红冲突禁止发布；黄/灰可带预警发布。
              </p>
            </>
          )}
          {tab === "IN_PRODUCTION" && (
            <p className="text-[10px] text-amber-400/90">
              生产中改交期走改单/插单，不会自动回到待排程。
            </p>
          )}
          <button
            type="button"
            disabled={busy}
            onClick={onReloadSeed}
            title="从 seed/seed_data.json 覆盖订单与主数据（演示用）"
            className="w-full rounded border border-slate-600 py-1.5 text-[11px] text-slate-300 hover:border-slate-500 hover:bg-slate-800 disabled:opacity-40"
          >
            重导演示数据
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto p-3 lg:rounded-b-lg lg:border lg:border-t-0 lg:border-slate-800 lg:bg-slate-900/50">
          {tabOrders.length === 0 ? (
            <p className="text-center text-xs text-slate-600 py-8">暂无订单</p>
          ) : (
            <OrderPool
              orders={tabOrders}
              selected={pendingSelected}
              busy={busy}
              today={today}
              boardFilterOrderNo={boardFilterOrderNo}
              onBoardFilter={onBoardFilter}
              onReloadSeed={onReloadSeed}
              onShowBom={onShowBom}
              onShowKit={onShowKit}
              kitByOrder={kitByOrder}
              onToggle={onTogglePending}
              onDueChange={onDueChange}
              embedded
              showCheckbox={tab === "PENDING"}
              dueReadOnly={tab === "COMPLETED"}
              onRemoveFromPool={
                tab === "IN_SCHEDULING" ? onRemoveFromPool : undefined
              }
            />
          )}
        </div>
      </aside>
    </>
  );
}
