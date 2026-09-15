import type { KitCheck } from "../types/kit";

type Props = {
  check: KitCheck | null;
  onClose: () => void;
};

export function KitDetailDrawer({ check, onClose }: Props) {
  if (!check) return null;
  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/60 p-3 sm:items-center"
      role="dialog"
      onClick={onClose}
    >
      <div
        className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-lg border border-slate-700 bg-slate-900 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-slate-800 px-4 py-3">
          <div>
            <h3 className="text-sm font-semibold text-slate-100">
              齐套 · {check.order_no}
            </h3>
            <p className="text-[11px] text-slate-500">
              {check.is_kitted ? "已齐套" : "未齐套"}
              {check.kit_ready_date ? ` · 齐套日 ${check.kit_ready_date}` : ""}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded border border-slate-600 px-2 py-1 text-xs text-slate-300"
          >
            关闭
          </button>
        </div>
        <div className="p-4 text-xs">
          <p className="text-slate-400">
            计划开工 {check.finished_plan_start ?? "—"}
          </p>
          <table className="mt-3 w-full border-collapse">
            <thead className="text-slate-500">
              <tr>
                <th className="py-1 text-left">子件</th>
                <th className="py-1 text-right">毛</th>
                <th className="py-1 text-right">占库</th>
                <th className="py-1 text-right">工单</th>
                <th className="py-1 text-right">缺</th>
              </tr>
            </thead>
            <tbody className="text-slate-300">
              {check.lines.map((ln) => (
                <tr key={ln.line_no} className="border-t border-slate-800">
                  <td className="py-1">
                    {ln.component_item_code}{" "}
                    <span className="text-slate-500">{ln.component_role}</span>
                  </td>
                  <td className="py-1 text-right">{ln.gross_board}</td>
                  <td className="py-1 text-right">{ln.from_stock}</td>
                  <td className="py-1 text-right">{ln.net_wo_board}</td>
                  <td className="py-1 text-right text-rose-400">
                    {ln.shortage_board > 0 ? ln.shortage_board : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
