import { createPortal } from "react-dom";
import { GROUPS } from "../constants/groups";
import type { ScheduleResult, Wo } from "../types/schedule";
import type { HeadcountWarning, OrderImpact } from "./AdjustImpactModal";

function groupLabel(code: string): string {
  return GROUPS.find((g) => g.code === code)?.name ?? code;
}

function ordersForCompare(
  impacts: OrderImpact[],
  triggerOrderNo: string | null,
  baseline: ScheduleResult,
  proposed: ScheduleResult,
): string[] {
  const set = new Set(impacts.map((o) => o.order_no));
  if (triggerOrderNo) set.add(triggerOrderNo);
  if (set.size === 0) {
    for (const w of baseline.wos) {
      const n = proposed.wos.find((x) => x.wo_no === w.wo_no);
      if (
        n &&
        (w.plan_start !== n.plan_start || w.plan_end !== n.plan_end)
      ) {
        set.add(w.source_order_no);
      }
    }
  }
  if (set.size === 0 && triggerOrderNo) set.add(triggerOrderNo);
  return Array.from(set).sort((a, b) => {
    if (a === triggerOrderNo) return -1;
    if (b === triggerOrderNo) return 1;
    return a.localeCompare(b);
  });
}

function wosByOrder(result: ScheduleResult, orderNo: string): Wo[] {
  return result.wos
    .filter((w) => w.source_order_no === orderNo)
    .sort((a, b) => a.wo_no.localeCompare(b.wo_no));
}

function taskSummary(result: ScheduleResult, woNo: string): string {
  const rows = result.tasks
    .filter((t) => t.wo_no === woNo)
    .sort((a, b) => a.task_date.localeCompare(b.task_date));
  if (rows.length === 0) return "无任务块";
  return rows
    .map(
      (t) =>
        `${t.task_date.slice(5)} ${groupLabel(t.group_code)} ${t.qty_board}版`,
    )
    .join(" · ");
}

type Props = {
  open: boolean;
  busy?: boolean;
  triggerOrderNo: string | null;
  baseline: ScheduleResult | null;
  proposed: ScheduleResult | null;
  diffSummary: string;
  diffEntries: { change_type: string; wo_no: string; message: string }[];
  orderImpacts: OrderImpact[];
  headcountWarnings: HeadcountWarning[];
  previewError?: string | null;
  onRevert: () => void;
  onKeep: () => void;
};

function OrderColumn({
  title,
  side,
  orderNo,
  impact,
  result,
  triggerOrderNo,
}: {
  title: string;
  side: "before" | "after";
  orderNo: string;
  impact: OrderImpact | undefined;
  result: ScheduleResult | null;
  triggerOrderNo: string | null;
}) {
  const isTrigger = orderNo === triggerOrderNo;
  const wos = result ? wosByOrder(result, orderNo) : [];
  const planStart =
    side === "before" ? impact?.plan_start_before : impact?.plan_start_after;
  const planEnd =
    side === "before" ? impact?.plan_end_before : impact?.plan_end_after;

  return (
    <div
      className={`rounded-lg border p-3 ${
        isTrigger
          ? "border-sky-600/80 bg-sky-950/30"
          : "border-slate-800 bg-slate-950/40"
      }`}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-semibold text-slate-100">{orderNo}</span>
        {isTrigger && (
          <span className="text-[10px] text-sky-400">本次触发</span>
        )}
      </div>
      <p className="mt-1 text-[11px] text-slate-500">
        订单交期（锚）{impact?.due_date ?? "—"}
      </p>
      <p className="mt-2 text-xs text-slate-300">
        计划开工 <span className="text-slate-100">{planStart ?? "—"}</span>
      </p>
      <p className="text-xs text-slate-300">
        计划完工 <span className="text-slate-100">{planEnd ?? "—"}</span>
      </p>
      <ul className="mt-3 space-y-2 border-t border-slate-800 pt-2 text-[11px]">
        {wos.map((w) => (
          <li key={w.wo_no} className="text-slate-400">
            <span className={w.wo_type === "SEMI" ? "text-violet-300" : "text-slate-200"}>
              {w.item_code}
            </span>
            <span className="text-slate-600"> ({w.wo_type === "SEMI" ? "半成品" : "成品"})</span>
            <div className="mt-0.5 leading-snug text-slate-500">
              {result ? taskSummary(result, w.wo_no) : "—"}
            </div>
          </li>
        ))}
        {wos.length === 0 && <li className="text-slate-600">无工单</li>}
      </ul>
      <p className="mt-2 text-[10px] text-slate-600">{title}</p>
    </div>
  );
}

export function SandboxCompareView({
  open,
  busy,
  triggerOrderNo,
  baseline,
  proposed,
  diffSummary,
  diffEntries,
  orderImpacts,
  headcountWarnings,
  previewError,
  onRevert,
  onKeep,
}: Props) {
  if (!open || !baseline || !proposed) return null;

  const orderNos = ordersForCompare(
    orderImpacts,
    triggerOrderNo,
    baseline,
    proposed,
  );
  const impactMap = new Map(orderImpacts.map((o) => [o.order_no, o]));

  const panel = (
    <div className="fixed inset-0 z-[100] flex flex-col bg-slate-950/95">
      <header className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-b border-slate-800 px-4 py-3">
        <div>
          <h2 className="text-base font-semibold text-slate-100">试排沙箱 · 调整对比</h2>
          <p className="mt-0.5 text-xs text-slate-500">
            左：变动前（上次倒排基准） · 右：当前调整后 · 仅展示相关订单
            {triggerOrderNo && (
              <span className="ml-2 text-sky-400">触发 {triggerOrderNo}</span>
            )}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            disabled={busy}
            onClick={onRevert}
            className="rounded border border-rose-700/70 px-3 py-1.5 text-sm text-rose-200 hover:bg-rose-950/50 disabled:opacity-40"
          >
            撤销本次调整
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={onKeep}
            className="rounded bg-emerald-700 px-3 py-1.5 text-sm text-white hover:bg-emerald-600 disabled:opacity-40"
          >
            保留调整并继续
          </button>
        </div>
      </header>

      {busy && (
        <div className="shrink-0 border-b border-sky-900/40 bg-sky-950/30 px-4 py-2 text-xs text-sky-200">
          正在试算工时与关联计划…
        </div>
      )}
      {previewError && (
        <div className="shrink-0 border-b border-rose-900/50 bg-rose-950/40 px-4 py-2 text-xs text-rose-200">
          {previewError}
        </div>
      )}

      <div className="shrink-0 border-b border-slate-800 bg-slate-900/50 px-4 py-2 text-xs">
        <p className="text-slate-300">{diffSummary || "计划工单日期无变化（可能仅人力/工时变化）"}</p>
        {diffEntries.length > 0 && (
          <ul className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-slate-500">
            {diffEntries.map((e, i) => (
              <li key={`${e.wo_no}-${i}`}>
                [{e.change_type}] {e.message}
              </li>
            ))}
          </ul>
        )}
      </div>

      {headcountWarnings.length > 0 && (
        <div className="shrink-0 border-b border-amber-900/40 bg-amber-950/20 px-4 py-2 text-xs text-amber-200/90">
          <p className="font-medium text-amber-300">
            本次触达组×日的产能 / 人手提示
            <span className="ml-2 font-normal text-amber-200/70">
              （不含未改动的其他日期；全计划冲突请看右侧冲突面板）
            </span>
          </p>
          <ul className="mt-1 space-y-0.5">
            {headcountWarnings.map((w, i) => (
              <li key={i}>
                {w.message.replaceAll("MOLD", "模具组").replaceAll("MANUAL", "手工组").replaceAll("POURING", "浇注组").replaceAll("SEMI", "二部半成品组")}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="grid min-h-0 flex-1 grid-cols-1 gap-0 lg:grid-cols-2">
        <div className="flex min-h-0 flex-col border-b border-slate-800 lg:border-b-0 lg:border-r">
          <div className="shrink-0 bg-slate-900/80 px-4 py-2 text-sm font-medium text-slate-400">
            变动前
          </div>
          <div className="flex-1 space-y-3 overflow-y-auto p-4">
            {orderNos.map((no) => (
              <OrderColumn
                key={`b-${no}`}
                title="基准快照"
                side="before"
                orderNo={no}
                impact={impactMap.get(no)}
                result={baseline}
                triggerOrderNo={triggerOrderNo}
              />
            ))}
          </div>
        </div>
        <div className="flex min-h-0 flex-col">
          <div className="shrink-0 bg-slate-900/80 px-4 py-2 text-sm font-medium text-emerald-400/90">
            调整后（含本次修改）
          </div>
          <div className="flex-1 space-y-3 overflow-y-auto p-4">
            {orderNos.map((no) => (
              <OrderColumn
                key={`a-${no}`}
                title="试排预览（未落库）"
                side="after"
                orderNo={no}
                impact={impactMap.get(no)}
                result={proposed}
                triggerOrderNo={triggerOrderNo}
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  );

  return createPortal(panel, document.body);
}
