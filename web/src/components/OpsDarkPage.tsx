/** 排程 / BOM / 库存共用深色页面底（不透明，叠在门户壳上也不发灰） */
export function OpsDarkPage({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-full flex-1 flex-col gap-3 bg-slate-950 p-3 text-slate-100">
      {children}
    </div>
  );
}

export const OPS_PANEL =
  "rounded-lg border border-slate-800 bg-slate-900 text-slate-100";

export const OPS_TABLE_WRAP =
  "flex-1 overflow-auto rounded-lg border border-slate-800 bg-slate-900";

export const OPS_TABLE_HEAD = "sticky top-0 bg-slate-800 text-slate-300";

export const OPS_TABLE_ROW =
  "border-t border-slate-800 bg-slate-900 text-slate-200 hover:bg-slate-800/80";
