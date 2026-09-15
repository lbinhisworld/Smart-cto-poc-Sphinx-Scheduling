export type OrderImpact = {
  order_no: string;
  due_date: string | null;
  plan_start_before: string | null;
  plan_end_before: string | null;
  plan_start_after: string | null;
  plan_end_after: string | null;
  is_trigger: boolean;
};

export type HeadcountWarning = {
  code: string;
  level: string;
  message: string;
  task_id?: number | null;
  wo_no?: string | null;
  group_code?: string | null;
  work_date?: string | null;
};

type Props = {
  open: boolean;
  onClose: () => void;
  triggerOrderNo: string | null;
  diffSummary: string;
  diffEntries: { change_type: string; wo_no: string; message: string }[];
  orderImpacts: OrderImpact[];
  headcountWarnings: HeadcountWarning[];
  busy?: boolean;
};

export function AdjustImpactModal({
  open,
  onClose,
  triggerOrderNo,
  diffSummary,
  diffEntries,
  orderImpacts,
  headcountWarnings,
  busy,
}: Props) {
  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 p-4"
      role="dialog"
      aria-labelledby="adjust-impact-title"
    >
      <div className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-lg border border-slate-700 bg-slate-900 shadow-xl">
        <div className="sticky top-0 flex items-center justify-between border-b border-slate-800 bg-slate-900/95 px-4 py-3">
          <div>
            <h3 id="adjust-impact-title" className="text-sm font-semibold text-slate-100">
              调整影响预览
            </h3>
            {triggerOrderNo && (
              <p className="text-[11px] text-sky-400">触发订单 {triggerOrderNo}</p>
            )}
          </div>
          <button
            type="button"
            disabled={busy}
            onClick={onClose}
            className="rounded border border-slate-600 px-2 py-1 text-xs text-slate-300 hover:bg-slate-800"
          >
            知道了
          </button>
        </div>

        <div className="space-y-4 p-4 text-xs">
          <section>
            <p className="font-medium text-slate-200">计划变化摘要</p>
            <p className="mt-1 text-slate-400">{diffSummary || "与上次排产结果相比无工单日期变化"}</p>
            {diffEntries.length > 0 && (
              <ul className="mt-2 max-h-32 space-y-1 overflow-y-auto text-slate-500">
                {diffEntries.map((e, i) => (
                  <li key={`${e.wo_no}-${i}`}>
                    [{e.change_type}] {e.message}
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section>
            <p className="font-medium text-slate-200">涉及订单（订单交期不变）</p>
            <p className="mt-0.5 text-[10px] text-slate-600">
              对比项为计划开工/完工日；是否超交期见冲突面板。
            </p>
            <ul className="mt-2 space-y-2">
              {orderImpacts.map((o) => (
                <li
                  key={o.order_no}
                  className={`rounded border p-2 ${
                    o.is_trigger
                      ? "border-sky-600 bg-sky-950/40"
                      : "border-slate-800 bg-slate-950/50"
                  }`}
                >
                  <span className="font-medium text-slate-200">{o.order_no}</span>
                  {o.is_trigger && (
                    <span className="ml-1 text-[10px] text-sky-400">本次调整</span>
                  )}
                  <div className="mt-1 text-slate-500">
                    订单交期（锚）{o.due_date ?? "—"}
                  </div>
                  <div className="mt-1 text-slate-400">
                    计划完工 {o.plan_end_before ?? "—"} →{" "}
                    <span className="text-slate-200">{o.plan_end_after ?? "—"}</span>
                  </div>
                  <div className="text-slate-500">
                    计划开工 {o.plan_start_before ?? "—"} → {o.plan_start_after ?? "—"}
                  </div>
                </li>
              ))}
              {orderImpacts.length === 0 && (
                <li className="text-slate-500">仅工时/人力变化，计划日未变</li>
              )}
            </ul>
          </section>

          {headcountWarnings.length > 0 && (
            <section>
              <p className="font-medium text-amber-300">人手 / 产能提示</p>
              <ul className="mt-2 space-y-1 text-amber-200/90">
                {headcountWarnings.map((w, i) => (
                  <li key={i}>{w.message}</li>
                ))}
              </ul>
            </section>
          )}
        </div>
      </div>
    </div>
  );
}
