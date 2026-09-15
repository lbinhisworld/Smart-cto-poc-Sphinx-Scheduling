import { useCallback, useEffect, useState } from "react";
import { fetchBomCatalog, fetchBomDesign, fetchBomExplode } from "../api/client";
import type { BomCatalog, BomDesign, BomExplode } from "../types/bom";
import { DEMO_TODAY } from "../constants/groups";
import { BomDiagram } from "./BomDiagram";
import { OPS_PANEL, OpsDarkPage } from "./OpsDarkPage";

export function BomExplorerPage() {
  const [catalog, setCatalog] = useState<BomCatalog | null>(null);
  const [selected, setSelected] = useState("P2");
  const [design, setDesign] = useState<BomDesign | null>(null);
  const [explodeQty, setExplodeQty] = useState(200);
  const [explode, setExplode] = useState<BomExplode | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const loadCatalog = useCallback(async () => {
    const c = await fetchBomCatalog();
    setCatalog(c);
    setSelected((prev) => {
      if (c.items.some((i) => i.item_code === prev)) return prev;
      return c.items[0]?.item_code ?? prev;
    });
  }, []);

  useEffect(() => {
    setError(null);
    loadCatalog().catch((e) => setError(String(e)));
  }, [loadCatalog]);

  useEffect(() => {
    if (!catalog) return;
    let cancelled = false;
    setBusy(true);
    setError(null);
    Promise.all([
      fetchBomDesign(selected),
      fetchBomExplode(selected, explodeQty, "BOX", catalog.today ?? DEMO_TODAY),
    ])
      .then(([d, e]) => {
        if (!cancelled) {
          setDesign(d);
          setExplode(e);
        }
      })
      .catch((err) => {
        if (!cancelled) setError(String(err));
      })
      .finally(() => {
        if (!cancelled) setBusy(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selected, explodeQty, catalog]);

  return (
    <OpsDarkPage>
      <div className={`${OPS_PANEL} px-4 py-3`}>
        <h2 className="text-sm font-semibold">工艺 / BOM · 设计态</h2>
        <p className="mt-1 text-xs text-slate-400">
          子件扇入成品（半成品并列、外购齐套；成品单节点）。种子版本{" "}
          {catalog?.seed_version ?? "—"} · 基准日 {catalog?.today ?? DEMO_TODAY}
        </p>
      </div>

      {error && (
        <div
          className="rounded border border-rose-800 bg-rose-950/80 px-3 py-2 text-xs text-rose-200"
          role="alert"
        >
          <p>{error}</p>
          <p className="mt-2 text-rose-300/80">
            重启后端后会自动对齐 9 单演示种子；订单池也可点「重新加载演示数据」。
          </p>
        </div>
      )}

      <div className="flex min-h-0 flex-1 flex-col gap-3 lg:flex-row">
        <aside
          className={`${OPS_PANEL} lg:w-72 shrink-0 overflow-y-auto p-3`}
        >
          {catalog?.catalog.map((block) => (
            <div key={block.key} className="mb-4 last:mb-0">
              <p className="text-[11px] font-medium text-slate-300">{block.desc}</p>
              <ul className="mt-2 space-y-1">
                {block.items.map((it) => (
                  <li key={it.item_code}>
                    <button
                      type="button"
                      onClick={() => setSelected(it.item_code)}
                      className={`w-full rounded px-2 py-1.5 text-left text-xs ${
                        selected === it.item_code
                          ? "bg-slate-800 text-slate-100 ring-1 ring-sky-600"
                          : "text-slate-400 hover:bg-slate-800/90"
                      }`}
                    >
                      <span className="font-medium text-slate-200">{it.item_code}</span>
                      <span className="block truncate text-[10px] text-slate-500">
                        {it.item_name}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </aside>

        <main className={`${OPS_PANEL} min-w-0 flex-1 overflow-y-auto p-4`}>
          {busy && !design && (
            <p className="text-xs text-slate-500">加载中…</p>
          )}
          {design && (
            <>
              <div className="mb-3 flex flex-wrap items-end gap-3 rounded-lg border border-slate-700 bg-slate-950 px-3 py-2">
                <label className="text-xs text-slate-300">
                  试算订货量（盒）
                  <input
                    type="number"
                    min={1}
                    className="ml-2 w-24 rounded border border-slate-600 bg-slate-900 px-2 py-1 text-slate-100"
                    value={explodeQty}
                    onChange={(e) => setExplodeQty(Number(e.target.value) || 1)}
                  />
                </label>
                <span className="text-[10px] text-slate-500">
                  下方「数量展开」随输入刷新；「工艺路线」为固定主数据
                </span>
              </div>
              <BomDiagram design={design} explode={explode} />
            </>
          )}
        </main>
      </div>
    </OpsDarkPage>
  );
}
