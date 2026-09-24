import { useCallback, useEffect, useMemo, useState } from "react";
import { cleanItemDisplayName } from "../utils/itemDisplayName";
import { fetchBomCatalog, fetchBomDesign, fetchBomExplode, requestWithRole } from "../api/client";
import { useAuth } from "../shell/auth";
import type { BomCatalog, BomDesign, BomExplode } from "../types/bom";
import { DEMO_TODAY } from "../constants/groups";
import { useGuidedDemoSeedReload } from "../hooks/guidedDemoSeed";
import { BomDiagram } from "./BomDiagram";
import { OPS_PANEL, OpsDarkPage } from "./OpsDarkPage";

type ProductLabor = {
  item_code: string;
  plan_version: number;
  hours_man_planned: number;
  cost_planned: number;
  order_count: number;
};

export function BomExplorerPage() {
  const auth = useAuth();
  const [catalog, setCatalog] = useState<BomCatalog | null>(null);
  const [productLabor, setProductLabor] = useState<ProductLabor | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [design, setDesign] = useState<BomDesign | null>(null);
  const [explodeQty, setExplodeQty] = useState(200);
  const [explode, setExplode] = useState<BomExplode | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const productSeedReload = useGuidedDemoSeedReload("product");

  const loadCatalog = useCallback(async () => {
    const c = await fetchBomCatalog();
    setCatalog(c);
    setSelected((prev) => {
      if (prev && c.items.some((i) => i.item_code === prev)) return prev;
      return c.items[0]?.item_code ?? null;
    });
  }, []);

  useEffect(() => {
    setError(null);
    loadCatalog().catch((e) => setError(String(e)));
  }, [loadCatalog, productSeedReload]);

  useEffect(() => {
    if (!catalog || !selected) return;
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

  useEffect(() => {
    if (!auth.role || !selected) return;
    requestWithRole<ProductLabor>(
      `/api/hr/labor-cost/product/${encodeURIComponent(selected)}`,
      auth.role,
    )
      .then(setProductLabor)
      .catch(() => setProductLabor(null));
  }, [selected, auth.role]);

  const finishedProducts = useMemo(() => catalog?.items ?? [], [catalog?.items]);
  const selectedProduct = useMemo(
    () => finishedProducts.find((p) => p.item_code === selected) ?? null,
    [finishedProducts, selected],
  );

  return (
    <OpsDarkPage>
      <div className={`${OPS_PANEL} px-4 py-3`}>
        <h2 className="text-sm font-semibold">工艺 / BOM · 设计态</h2>
        <p className="mt-1 text-xs text-slate-400">
          选左侧<strong className="font-normal text-slate-300">成品</strong>
          查看 BOM 与工艺路线（半成品、外购件扇入成品）。默认工作中心为手工/模具/浇注三组，不是完整工序清单。种子{" "}
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
            演示线模式下请在本页顶栏先点「生成数据」；若仍报错请确认后端已重启（8000 端口）。
          </p>
        </div>
      )}

      <div className="flex min-h-0 flex-1 flex-col gap-3 lg:flex-row">
        <aside className={`${OPS_PANEL} lg:w-80 shrink-0 overflow-y-auto p-3`}>
          <div className="mb-3 rounded-lg border border-slate-700/80 bg-slate-950/60 px-2.5 py-2 text-[10px] leading-relaxed text-slate-400">
            <p className="text-[11px] font-medium text-slate-300">列表怎么读</p>
            <ul className="mt-1.5 list-inside list-disc space-y-0.5">
              <li>
                第一行 <span className="text-slate-200">中文品名</span> = 对客户说的产品名
              </li>
              <li>
                <span className="font-mono text-slate-300">P1、P2…</span> = 内部品项编码，不是工序名
              </li>
              <li>标签「一部·××组」= 默认倒排工作中心，不是 ERP 工序号</li>
            </ul>
          </div>
          <p className="text-[11px] font-medium text-slate-300">
            成品列表
            <span className="ml-1 font-normal text-slate-500">（{finishedProducts.length}）</span>
          </p>
          {finishedProducts.length === 0 ? (
            <p className="mt-2 text-[11px] text-slate-500">暂无成品主数据，请先在演示线第 2 步「生成数据」。</p>
          ) : (
            <ul className="mt-2 space-y-1">
              {finishedProducts.map((it) => {
                const name = cleanItemDisplayName(it.item_name);
                const active = selected === it.item_code;
                return (
                  <li key={it.item_code}>
                    <button
                      type="button"
                      onClick={() => setSelected(it.item_code)}
                      className={`w-full rounded-lg border px-2.5 py-2 text-left transition ${
                        active
                          ? "border-sky-600/80 bg-slate-800 ring-1 ring-sky-600/50"
                          : "border-transparent hover:border-slate-700 hover:bg-slate-800/80"
                      }`}
                    >
                      <span className="block text-sm font-medium leading-snug text-slate-100">{name}</span>
                      <span className="mt-1 flex flex-wrap items-center gap-1.5 text-[10px] text-slate-500">
                        <span className="font-mono text-slate-400">{it.item_code}</span>
                        <span className="rounded bg-slate-800 px-1.5 py-0.5 text-slate-400">{it.group_label}</span>
                        {it.needs_semi ? (
                          <span className="rounded bg-violet-950/80 px-1.5 py-0.5 text-violet-300/90">含半成品</span>
                        ) : null}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </aside>

        <main className={`${OPS_PANEL} min-w-0 flex-1 overflow-y-auto p-4`}>
          {!selected && !error && (
            <p className="text-xs text-slate-400">
              暂无产品主数据。演示线第 2 步请点顶栏「生成数据」写入 5 条故事线品项后再浏览 BOM。
            </p>
          )}
          {busy && !design && selected && (
            <p className="text-xs text-slate-500">加载中…</p>
          )}
          {design && (
            <>
              {selectedProduct && (
                <div className="mb-3 rounded-lg border border-slate-700 bg-slate-900/80 px-3 py-2.5">
                  <p className="text-base font-semibold text-slate-100">
                    {cleanItemDisplayName(selectedProduct.item_name)}
                  </p>
                  <p className="mt-1 text-[11px] text-slate-400">
                    品项编码{" "}
                    <span className="font-mono text-slate-300">{selectedProduct.item_code}</span>
                    <span className="mx-2 text-slate-600">·</span>
                    默认工作中心 {selectedProduct.group_label}
                    {selectedProduct.needs_semi ? " · 需先排二部半成品" : " · 无半成品层"}
                  </p>
                </div>
              )}
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
              {productLabor && productLabor.plan_version > 0 && (
                <div className="mb-3 rounded-lg border border-violet-800/60 bg-violet-950/30 px-3 py-2 text-xs text-violet-100">
                  <p className="font-medium text-violet-200">
                    计划人工成本（成品 {productLabor.item_code} · 计划 v
                    {productLabor.plan_version}）
                  </p>
                  <p className="mt-1 text-violet-200/90">
                    计划 {productLabor.hours_man_planned.toFixed(2)} 人·时 · 约{" "}
                    {productLabor.cost_planned.toFixed(2)} 元（标准单价）
                    {productLabor.order_count > 0 && (
                      <span className="text-violet-300/70">
                        {" "}
                        · 当前计划含 {productLabor.order_count} 张订单分摊
                      </span>
                    )}
                  </p>
                  <p className="mt-1 text-[10px] text-violet-400/80">
                    量产人·时×标准单价，打样已剔除；先「一键倒排」发布计划后才有数
                  </p>
                </div>
              )}
              <BomDiagram design={design} explode={explode} />
            </>
          )}
        </main>
      </div>
    </OpsDarkPage>
  );
}
