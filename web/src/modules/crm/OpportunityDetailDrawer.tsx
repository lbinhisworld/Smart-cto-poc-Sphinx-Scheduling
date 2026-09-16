import { OpportunityDetailPanel } from "./crm360Panels";

type Props = {
  oppId: number | null;
  onClose: () => void;
};

/** 商机列表 · 右侧侧滑详情（含关联打样过程） */
export function OpportunityDetailDrawer({ oppId, onClose }: Props) {
  if (oppId == null) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/45" role="dialog" onClick={onClose}>
      <div
        className="flex h-full w-full max-w-xl flex-col overflow-hidden shadow-xl"
        style={{ background: "var(--bg-card)" }}
        onClick={(e) => e.stopPropagation()}
      >
        <div
          className="flex items-center justify-between border-b px-4 py-3"
          style={{ borderColor: "var(--line)" }}
        >
          <p className="font-semibold">商机详情</p>
          <button type="button" className="text-sm text-[var(--text-muted)]" onClick={onClose}>
            关闭
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto p-4">
          <OpportunityDetailPanel oppId={oppId} />
        </div>
      </div>
    </div>
  );
}
