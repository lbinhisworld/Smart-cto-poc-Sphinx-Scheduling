import { SampleDetailPanel } from "./crm360Panels";

type Props = {
  sampleCode: string | null;
  onClose: () => void;
};

/** 样品列表页独立侧滑（与 CRM360 内嵌面板同源） */
export function SampleDetailDrawer({ sampleCode, onClose }: Props) {
  if (!sampleCode) return null;

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
          <p className="font-semibold">打样详情</p>
          <button type="button" className="text-sm text-[var(--text-muted)]" onClick={onClose}>
            关闭
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto p-4">
          <SampleDetailPanel sampleCode={sampleCode} />
        </div>
      </div>
    </div>
  );
}
