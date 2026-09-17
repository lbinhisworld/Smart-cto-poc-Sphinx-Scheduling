import { useEffect, useState } from "react";
import { fetchCellDetail } from "../api/client";
import {
  type DeptCode,
  type GroupCode,
  workCenterLabel,
} from "../constants/groups";
import type { ScheduleResult } from "../types/schedule";
import { OccupancyLedger } from "./NarrationBar";
import { shortLabel } from "../utils/dates";

export type CellDetailFocus = {
  dept: DeptCode;
  group: GroupCode;
  date: string;
  focusTaskId: number | null;
};

type Metrics = Record<string, string>;

type DetailPayload = {
  group_code: string;
  task_date: string;
  focus_task_id: number | null;
  is_workday: boolean;
  headcount: number;
  orders: {
    order_no: string;
    customer: string;
    sales_name?: string;
    item_code: string;
    wo_nos: string[];
    qty_board_in_cell: number;
  }[];
  tasks: {
    task_id: number;
    wo_no: string;
    source_order_no: string;
    item_code: string;
    qty_board: number;
    hours_wall: string;
    hours_man: string;
    crew_plan: number;
  }[];
  cell_metrics: Metrics;
  task_metrics: Metrics | null;
};

type Props = {
  focus: CellDetailFocus | null;
  today: string;
  planVersion: number;
  result: ScheduleResult | null;
  liveTasks: ScheduleResult["tasks"];
  /** 订单池中的销售姓名（API 未带时补全） */
  orderSalesByNo?: Map<string, string>;
  onClose: () => void;
};

function pct(raw: string | undefined): string {
  if (!raw) return "—";
  const n = Number(raw);
  if (Number.isNaN(n)) return raw;
  return `${Math.round(n * 1000) / 10}%`;
}

function MetricsBlock({
  title,
  metrics,
}: {
  title: string;
  metrics: Metrics | null;
}) {
  if (!metrics) return null;
  return (
    <section className="rounded border border-slate-800 bg-slate-950/50 p-3">
      <h4 className="mb-2 text-xs font-semibold text-sky-400">{title}</h4>
      <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
        <dt className="text-slate-500">墙钟工时</dt>
        <dd className="text-slate-200">{metrics.wall_clock_hours} h</dd>
        <dt className="text-slate-500">人·时合计</dt>
        <dd className="text-slate-200">{metrics.hours_man} h</dd>
        <dt className="text-slate-500">产能利用率</dt>
        <dd className="text-slate-200">{pct(metrics.capacity_utilization)}</dd>
        <dt className="text-slate-500">人·时利用率</dt>
        <dd className="text-slate-200">{pct(metrics.labor_utilization)}</dd>
      </dl>
      <p className="mt-2 text-[10px] leading-snug text-slate-500">
        {metrics.capacity_formula}
      </p>
      <p className="mt-1 text-[10px] leading-snug text-slate-500">
        {metrics.labor_formula}
      </p>
    </section>
  );
}

export function CellDetailDrawer({
  focus,
  today,
  planVersion,
  result,
  liveTasks,
  orderSalesByNo,
  onClose,
}: Props) {
  const [detail, setDetail] = useState<DetailPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!focus) {
      setDetail(null);
      return;
    }
    if (!result) {
      setError("请先「一键倒排」生成计划后再查看详情。");
      setDetail(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchCellDetail({
      today,
      dept: focus.dept,
      group_code: focus.group,
      task_date: focus.date,
      focus_task_id: focus.focusTaskId ?? undefined,
      plan_version: planVersion > 0 ? planVersion : undefined,
      tasks: liveTasks,
      result: result ?? undefined,
    })
      .then((d) => {
        if (!cancelled) setDetail(d);
      })
      .catch((e) => {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : String(e));
          setDetail(null);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [focus, today, planVersion, result, liveTasks]);

  if (!focus) return null;

  const modeLabel =
    focus.focusTaskId != null ? "本任务" : "本格合计";

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/60 p-3 sm:items-center"
      role="dialog"
      aria-labelledby="cell-detail-title"
      onClick={onClose}
    >
      <div
        className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-lg border border-slate-700 bg-slate-900 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="sticky top-0 flex items-center justify-between border-b border-slate-800 bg-slate-900/95 px-4 py-3">
          <div>
            <h3 id="cell-detail-title" className="text-sm font-semibold text-slate-100">
              {workCenterLabel(focus.dept, focus.group)} · {shortLabel(focus.date)}
            </h3>
            <p className="text-[11px] text-slate-500">{modeLabel}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded border border-slate-600 px-2 py-1 text-xs text-slate-300 hover:bg-slate-800"
          >
            关闭
          </button>
        </div>
        <div className="space-y-3 p-4">
          {loading && <p className="text-xs text-slate-400">加载中…</p>}
          {error && <p className="text-xs text-rose-400">{error}</p>}
          {detail && (
            <>
              <section>
                <h4 className="mb-2 text-xs font-semibold text-slate-300">关联订单（按品项）</h4>
                {detail.orders.length === 0 ? (
                  <p className="text-xs text-slate-500">本格暂无任务</p>
                ) : (
                  <ul className="space-y-2">
                    {(() => {
                      const byItem = new Map<string, typeof detail.orders>();
                      for (const o of detail.orders) {
                        const k = o.item_code || "?";
                        if (!byItem.has(k)) byItem.set(k, []);
                        byItem.get(k)!.push(o);
                      }
                      return [...byItem.entries()].map(([item, rows]) => {
                        const coline = rows.length > 1;
                        return (
                          <li key={item}>
                            <p
                              className={`mb-1 text-[10px] font-medium ${
                                coline ? "text-teal-200" : "text-slate-400"
                              }`}
                            >
                              {item}
                              {coline
                                ? ` · 共线 ${rows.length} 单 · 仍分属各单 WO`
                                : ""}
                            </p>
                            <ul className="space-y-1">
                              {rows.map((o) => {
                                const sales =
                                  o.sales_name?.trim() ||
                                  orderSalesByNo?.get(o.order_no)?.trim() ||
                                  "";
                                return (
                                  <li
                                    key={o.order_no}
                                    className={`rounded border px-2 py-1.5 text-xs ${
                                      coline
                                        ? "border-teal-800/80 bg-teal-950/30"
                                        : "border-slate-800"
                                    }`}
                                  >
                                    <div className="font-medium text-slate-100">
                                      {o.order_no}
                                    </div>
                                    {sales ? (
                                      <div className="text-[10px] text-sky-400/90">
                                        销售 {sales}
                                      </div>
                                    ) : null}
                                    <div className="text-[10px] text-slate-500">
                                      {o.customer || "—"} · 本格 {o.qty_board_in_cell} 版
                                    </div>
                                  </li>
                                );
                              })}
                            </ul>
                          </li>
                        );
                      });
                    })()}
                  </ul>
                )}
              </section>

              {focus.focusTaskId != null && detail.task_metrics ? (
                <MetricsBlock title="本任务指标" metrics={detail.task_metrics} />
              ) : null}

              {result?.trace?.events?.length ? (
                <OccupancyLedger
                  events={result.trace.events}
                  index={result.trace.events.length - 1}
                  dept={focus.dept}
                  group={focus.group}
                  date={focus.date}
                />
              ) : null}

              <MetricsBlock title="本格合计指标" metrics={detail.cell_metrics} />

              {detail.tasks.length > 1 && (
                <section>
                  <h4 className="mb-1 text-xs font-semibold text-slate-400">
                    本格任务 ({detail.tasks.length})
                  </h4>
                  <ul className="max-h-32 overflow-y-auto text-[10px] text-slate-500">
                    {detail.tasks.map((t) => (
                      <li key={t.task_id}>
                        {t.item_code} {t.qty_board}版 · {t.hours_wall}h ·{" "}
                        {t.source_order_no}
                      </li>
                    ))}
                  </ul>
                </section>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
