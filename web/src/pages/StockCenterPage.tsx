import { useCallback, useEffect, useMemo, useState } from "react";
import {
  fetchStock,
  patchStockQty,
  syncStockErpMock,
  type StockItem,
} from "../api/client";
import {
  OPS_PANEL,
  OPS_TABLE_HEAD,
  OPS_TABLE_ROW,
  OPS_TABLE_WRAP,
  OpsDarkPage,
} from "../components/OpsDarkPage";

type Props = {
  planAllocations?: { component_item_code: string; qty_board: number; order_no: string }[];
};

export function StockCenterPage({ planAllocations = [] }: Props) {
  const [items, setItems] = useState<StockItem[]>([]);
  const [dbFile, setDbFile] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState<Record<string, string>>({});

  const load = useCallback(async () => {
    setError(null);
    const data = await fetchStock();
    setItems(data.items);
    setDbFile(data.db_file ?? "");
    setDraft({});
  }, []);

  useEffect(() => {
    load().catch((e) => setError(String(e)));
  }, [load]);

  const allocSum = useMemo(() => {
    const m = new Map<string, number>();
    for (const a of planAllocations) {
      m.set(a.component_item_code, (m.get(a.component_item_code) ?? 0) + a.qty_board);
    }
    return m;
  }, [planAllocations]);

  const onSave = async (code: string) => {
    const raw = draft[code];
    if (raw === undefined) return;
    setBusy(true);
    try {
      await patchStockQty(code, Number(raw));
      await load();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const onSync = async () => {
    setBusy(true);
    setError(null);
    try {
      await syncStockErpMock("merge");
      await load();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <OpsDarkPage>
      <div className={`${OPS_PANEL} px-4 py-3`}>
        <h2 className="text-sm font-semibold">库存中心</h2>
        <p className="mt-1 text-xs text-slate-400">
          演示数据 · 本地可改数量；生产环境由 ERP 只读同步（不写回 ERP）。
          {dbFile ? ` · ${dbFile}` : ""}
        </p>
        <div className="mt-2 flex flex-wrap gap-2">
          <button
            type="button"
            disabled={busy}
            onClick={() => onSync().catch((e) => setError(String(e)))}
            className="rounded border border-sky-700 bg-sky-950 px-3 py-1 text-xs text-sky-200 hover:bg-sky-900 disabled:opacity-50"
          >
            模拟 ERP 同步
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() => load().catch((e) => setError(String(e)))}
            className="rounded border border-slate-600 px-3 py-1 text-xs text-slate-300 hover:bg-slate-800"
          >
            刷新
          </button>
        </div>
      </div>

      {error && (
        <p className="rounded border border-rose-800 bg-rose-950/80 px-3 py-2 text-xs text-rose-200">
          {error}
        </p>
      )}

      <div className={OPS_TABLE_WRAP}>
        <table className="w-full text-xs">
          <thead className={OPS_TABLE_HEAD}>
            <tr>
              <th className="px-3 py-2 text-left font-medium">品项</th>
              <th className="px-3 py-2 text-left font-medium">名称</th>
              <th className="px-3 py-2 text-right font-medium">可用（版）</th>
              <th className="px-3 py-2 text-right font-medium">计划占用</th>
              <th className="px-3 py-2 text-left font-medium">来源</th>
              <th className="px-3 py-2 text-left font-medium">操作</th>
            </tr>
          </thead>
          <tbody>
            {items.map((row) => {
              const used = allocSum.get(row.item_code) ?? 0;
              const val = draft[row.item_code] ?? String(row.qty_available);
              return (
                <tr key={row.item_code} className={OPS_TABLE_ROW}>
                  <td className="px-3 py-2 font-medium text-slate-100">{row.item_code}</td>
                  <td className="px-3 py-2 text-slate-400">{row.item_name}</td>
                  <td className="px-3 py-2 text-right">
                    <input
                      className="w-24 rounded border border-slate-600 bg-slate-950 px-2 py-0.5 text-right text-slate-100"
                      value={val}
                      onChange={(e) =>
                        setDraft((d) => ({ ...d, [row.item_code]: e.target.value }))
                      }
                    />
                  </td>
                  <td className="px-3 py-2 text-right text-emerald-300/90">
                    {used > 0 ? used : "—"}
                  </td>
                  <td className="px-3 py-2 text-slate-500">{row.source}</td>
                  <td className="px-3 py-2">
                    <button
                      type="button"
                      disabled={busy || draft[row.item_code] === undefined}
                      onClick={() => onSave(row.item_code)}
                      className="rounded border border-slate-600 px-2 py-0.5 text-[10px] text-slate-300 hover:bg-slate-800 disabled:opacity-40"
                    >
                      保存
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </OpsDarkPage>
  );
}
