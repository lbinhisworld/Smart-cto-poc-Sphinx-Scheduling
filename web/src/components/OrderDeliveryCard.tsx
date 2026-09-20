import { useEffect, useState } from "react";
import { requestWithRole } from "../api/client";
import { useAuth } from "../shell/auth";
import type { OrderDeliveryStory } from "../utils/orderDeliveryStory";
import { nodeToCellFocus, WoNodeStrip, type WoNodeOpenPayload } from "./WoNodeStrip";
import type { WoNodeStory } from "../utils/orderDeliveryStory";

type BreakdownLine = {
  line_no: number;
  item_code: string;
  qty: number;
  unit: string;
};

type Props = {
  story: OrderDeliveryStory;
  today: string;
  onOpenNode: (payload: WoNodeOpenPayload) => void;
  onSelectOrder?: (headerOrderNo: string) => void;
  selected?: boolean;
};

export function OrderDeliveryCard({
  story,
  today: _today,
  onOpenNode,
  onSelectOrder,
  selected,
}: Props) {
  const auth = useAuth();
  const [lines, setLines] = useState<string[] | null>(null);
  const { order, feasibility, planDeliveryDate, earliestFinish, nodes } = story;

  useEffect(() => {
    if (!auth.role) return;
    let cancelled = false;
    requestWithRole<{ lines: BreakdownLine[] }>(
      `/api/mis/orders/${encodeURIComponent(story.headerOrderNo)}/breakdown`,
      auth.role,
    )
      .then((d) => {
        if (cancelled) return;
        const texts =
          d.lines?.map(
            (ln) => `${ln.item_code} × ${ln.qty} ${ln.unit}`,
          ) ?? [];
        setLines(texts.length ? texts : null);
      })
      .catch(() => {
        if (!cancelled) setLines(null);
      });
    return () => {
      cancelled = true;
    };
  }, [auth.role, story.headerOrderNo]);

  const lineSummary =
    lines && lines.length > 0
      ? lines.length === 1
        ? lines[0]
        : `${lines.slice(0, 3).join("；")}${lines.length > 3 ? ` 等 ${lines.length} 行` : ""}`
      : story.lineSummary;

  const statusBadge =
    feasibility === "late"
      ? { text: "无法满足交期", cls: "bg-rose-950 text-rose-200 ring-rose-800" }
      : feasibility === "feasible"
        ? { text: "交期内可满足", cls: "bg-emerald-950 text-emerald-200 ring-emerald-800" }
        : { text: "未排程", cls: "bg-slate-800 text-slate-300 ring-slate-600" };

  const handleNode = (node: WoNodeStory) => {
    const focus = nodeToCellFocus(node);
    if (focus) onOpenNode(focus);
  };

  return (
    <article
      className={`rounded-xl border px-4 py-3 ${
        selected
          ? "border-sky-600 bg-slate-900/90 ring-1 ring-sky-700/50"
          : "border-slate-700 bg-slate-900/60"
      }`}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <button
            type="button"
            className="text-left"
            onClick={() => onSelectOrder?.(story.headerOrderNo)}
          >
            <h3 className="text-sm font-semibold text-slate-100">
              {story.headerOrderNo}
            </h3>
          </button>
          <p className="text-xs text-slate-400">
            销售 {order.sales_name || "—"} · {order.customer}
          </p>
          <p className="mt-1 text-[11px] text-slate-300">明细 {lineSummary}</p>
        </div>
        <div className="text-right text-xs">
          <span
            className={`inline-block rounded px-2 py-0.5 ring-1 ${statusBadge.cls}`}
          >
            {statusBadge.text}
          </span>
          <p className="mt-2 text-slate-400">客户交期 {order.due_date}</p>
          <p className="text-slate-300">
            计划交付 {planDeliveryDate ?? "—"}
          </p>
          {earliestFinish && feasibility === "late" ? (
            <p className="text-rose-300/90">最快可完成 {earliestFinish}</p>
          ) : null}
        </div>
      </div>
      <div className="mt-3">
        <WoNodeStrip nodes={nodes} onOpenNode={handleNode} />
      </div>
      <p className="mt-2 text-[10px] text-slate-600">
        节点版数为倒排计划；已完工版数来自报工（如有）。客户交期仅人工可改。
      </p>
    </article>
  );
}
