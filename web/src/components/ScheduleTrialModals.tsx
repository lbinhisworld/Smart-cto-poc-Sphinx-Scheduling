import type { Conflict } from "../types/schedule";
import type { OrderCommitment } from "../utils/orderCommitments";
import { formatConflictMessage } from "../utils/conflictLabels";

type SuccessProps = {
  open: boolean;
  commitments: OrderCommitment[];
  onClose: () => void;
  onPublish: () => void;
  busy: boolean;
  yellowNote: boolean;
};

export function TrialSuccessModal({
  open,
  commitments,
  onClose,
  onPublish,
  busy,
  yellowNote,
}: SuccessProps) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 p-4">
      <div className="max-h-[85vh] w-full max-w-md overflow-y-auto rounded-lg border border-slate-700 bg-slate-900 p-4 shadow-xl">
        <h3 className="text-sm font-semibold text-emerald-400">试排成功</h3>
        <p className="mt-1 text-xs text-slate-500">
          以下为计划完工日（可承诺销售参考，客户交期锚不变）
        </p>
        {yellowNote && (
          <p className="mt-2 text-xs text-amber-400">
            存在黄色软冲突，允许发布但请带预警告知客户。
          </p>
        )}
        <ul className="mt-3 space-y-2 text-xs">
          {commitments.map((c) => (
            <li
              key={c.order_no}
              className="rounded border border-slate-800 px-2 py-1.5"
            >
              <span className="font-medium text-slate-100">{c.order_no}</span>
              <div className="text-slate-400">
                计划完工{" "}
                <span className="text-emerald-300">
                  {c.promised_finish ?? "—"}
                </span>
                {c.plan_start && (
                  <span className="text-slate-600"> · 开工 {c.plan_start}</span>
                )}
              </div>
              {c.has_red_conflict && (
                <span className="text-rose-400">含 E1/E2，不可直接发布</span>
              )}
            </li>
          ))}
        </ul>
        <div className="mt-4 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded border border-slate-600 px-3 py-1.5 text-xs text-slate-300"
          >
            关闭
          </button>
          <button
            type="button"
            disabled={busy || commitments.some((c) => c.has_red_conflict)}
            onClick={onPublish}
            className="rounded bg-sky-600 px-3 py-1.5 text-xs font-medium text-white disabled:opacity-40"
          >
            保存发布
          </button>
        </div>
      </div>
    </div>
  );
}

type ConflictProps = {
  open: boolean;
  conflicts: Conflict[];
  commitments: OrderCommitment[];
  salesByOrder?: Map<string, string>;
  onClose: () => void;
  onAdjust: () => void;
};

export function TrialConflictModal({
  open,
  conflicts,
  commitments,
  salesByOrder,
  onClose,
  onAdjust,
}: ConflictProps) {
  if (!open) return null;
  const reds = conflicts.filter((c) => c.level === "RED");
  const yellows = conflicts.filter((c) => c.level === "YELLOW");
  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 p-4">
      <div className="max-h-[85vh] w-full max-w-lg overflow-y-auto rounded-lg border border-rose-800/60 bg-slate-900 p-4 shadow-xl">
        <h3 className="text-sm font-semibold text-rose-400">试排发现冲突</h3>
        <p className="mt-1 text-xs text-slate-500">
          存在 E1/E2 时禁止发布（可强确认流程二期）；请先去调整或走插单策略。
        </p>
        {reds.length > 0 && (
          <ul className="mt-2 max-h-32 space-y-1 overflow-y-auto text-[11px] text-rose-300">
            {reds.slice(0, 8).map((c, i) => (
              <li key={i}>{formatConflictMessage(c.message)}</li>
            ))}
          </ul>
        )}
        {yellows.length > 0 && (
          <p className="mt-2 text-[11px] text-amber-400">
            另有 {yellows.length} 条黄色预警，调整后仍可带预警发布。
          </p>
        )}
        <ul className="mt-3 space-y-1 text-xs text-slate-500">
          {commitments.map((c) => (
            <li key={c.order_no}>
              {c.order_no}
              {salesByOrder?.get(c.order_no)
                ? ` · 销售 ${salesByOrder.get(c.order_no)}`
                : ""}
              {" · "}计划完工 {c.promised_finish ?? "—"}
            </li>
          ))}
        </ul>
        <div className="mt-4 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded border border-slate-600 px-3 py-1.5 text-xs text-slate-300"
          >
            关闭
          </button>
          <button
            type="button"
            onClick={onAdjust}
            className="rounded bg-violet-700 px-3 py-1.5 text-xs text-white"
          >
            去调整（看板 / 沙箱）
          </button>
        </div>
      </div>
    </div>
  );
}
