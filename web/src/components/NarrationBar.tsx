import { useEffect } from "react";
import type { TraceEvent, ScheduleTrace } from "../types/schedule";
import {
  occupancyLedger,
  queuedFinishedOrders,
  SORT_MODE_LABEL,
  TRACE_ACTS,
} from "../utils/scheduleTrace";
import { workCenterLabel, type DeptCode, type GroupCode } from "../constants/groups";
import { headerOrderNo } from "../utils/coline";
import { shortLabel } from "../utils/dates";

type Props = {
  trace: ScheduleTrace;
  index: number;
  playing: boolean;
  salesByOrder?: Map<string, string>;
  onIndex: (i: number) => void;
  onPlaying: (p: boolean) => void;
  onClose: () => void;
};

export function OccupancyLedger({
  events,
  index,
  dept,
  group,
  date,
}: {
  events: TraceEvent[];
  index: number;
  dept?: string | null;
  group?: string | null;
  date?: string | null;
}) {
  const { cap, rows, leftover } = occupancyLedger(events, index, dept, group, date);
  if (!date || !group || rows.length === 0) return null;
  const wc =
    dept && group
      ? workCenterLabel(dept as DeptCode, group as GroupCode)
      : group;
  return (
    <div className="rounded border border-slate-800 bg-slate-950/60 px-2 py-1.5 text-[11px]">
      <p className="font-medium text-slate-300">
        占用账 · {wc} · {/^\d{4}-\d{2}-\d{2}$/.test(date) ? shortLabel(date) : date}
        {cap != null && (
          <span className="ml-2 font-normal text-slate-500">
            日产能 {cap} 版 · 剩余 {leftover} 版
          </span>
        )}
      </p>
      <ol className="mt-1 space-y-0.5 text-slate-400">
        {rows.map((r, i) => (
          <li key={`${r.orderNo}-${i}`}>
            {i + 1}. {r.orderNo} {r.itemCode} 吃 {r.qty} 版
            <span className="text-slate-600"> → 累计占 {r.occupiedAfter}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}

export function QueueLane({
  events,
  index,
  sortMode,
  salesByOrder,
}: {
  events: TraceEvent[];
  index: number;
  sortMode: string;
  salesByOrder?: Map<string, string>;
}) {
  const rows = queuedFinishedOrders(events, index);
  if (rows.length === 0) return null;
  const arrivedCount = rows.filter((r) => r.arrived).length;
  const rule = SORT_MODE_LABEL[sortMode] ?? sortMode;
  return (
    <div className="rounded border border-amber-900/50 bg-slate-950/60 px-2 py-1.5 text-[11px]">
      <p className="font-medium text-amber-200/90">
        排队中 · {rule}
        <span className="ml-2 font-normal text-slate-500">
          已入列 {arrivedCount} / {rows.length} 张成品单
        </span>
      </p>
      <ol className="mt-1.5 space-y-1">
        {rows.map((r) => {
          if (!r.arrived) {
            return (
              <li
                key={`pending-${r.rank}`}
                className="flex items-baseline gap-x-2 rounded border border-dashed border-slate-800 px-1.5 py-1 text-slate-600"
              >
                <span className="w-5 shrink-0 tabular-nums">{r.rank}</span>
                <span>待入列…</span>
              </li>
            );
          }
          const sales =
            salesByOrder?.get(r.orderNo)?.trim() ||
            salesByOrder?.get(headerOrderNo(r.orderNo))?.trim() ||
            "未填";
          return (
            <li
              key={`${r.rank}-${r.orderNo}`}
              className={`flex flex-wrap items-baseline gap-x-2 rounded px-1.5 py-1 ${
                r.justArrived
                  ? "queue-lane-enter bg-amber-950/70 ring-1 ring-amber-400/70 text-amber-50"
                  : "bg-slate-900/70 text-slate-300"
              }`}
            >
              <span className="w-5 shrink-0 tabular-nums text-slate-500">
                {r.rank}
              </span>
              <span className="font-mono font-semibold text-slate-100">
                {r.orderNo}
              </span>
              <span className={r.justArrived ? "text-amber-200" : "text-slate-400"}>
                销售 {sales}
              </span>
              {r.dueDate && (
                <span className="text-slate-500">
                  交期 {/^\d{4}-\d{2}-\d{2}$/.test(r.dueDate) ? shortLabel(r.dueDate) : r.dueDate}
                </span>
              )}
              {r.itemCode && (
                <span className="text-slate-600">{r.itemCode}</span>
              )}
              {r.justArrived && (
                <span className="ml-auto text-[10px] font-medium text-amber-300">
                  刚入列
                </span>
              )}
            </li>
          );
        })}
      </ol>
    </div>
  );
}

export function NarrationBar({
  trace,
  index,
  playing,
  salesByOrder,
  onIndex,
  onPlaying,
  onClose,
}: Props) {
  const events = trace.events;
  const ev = events[index] ?? null;
  const last = Math.max(events.length - 1, 0);

  useEffect(() => {
    if (!playing || events.length === 0) return;
    const delay =
      ev?.kind === "skip_day"
        ? 30
        : ev?.kind === "place"
          ? 480
          : ev?.kind === "queue_rank"
            ? 720
            : 260;
    const t = window.setTimeout(() => {
      if (index >= last) {
        onPlaying(false);
        return;
      }
      onIndex(index + 1);
    }, delay);
    return () => window.clearTimeout(t);
  }, [playing, index, last, ev?.kind, events.length, onIndex, onPlaying]);

  return (
    <div className="shrink-0 rounded-lg border border-violet-900/50 bg-slate-900/80 px-3 py-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-xs font-semibold text-violet-200">倒排讲解回放</p>
          <p className="text-[10px] text-slate-500">
            策略 {SORT_MODE_LABEL[trace.sort_mode] ?? trace.sort_mode} · 已算出结果，正在按记录放慢演示
          </p>
        </div>
        <div className="flex flex-wrap gap-1">
          <button
            type="button"
            className="rounded border border-slate-600 px-2 py-0.5 text-[11px] text-slate-300 hover:bg-slate-800"
            onClick={() => {
              onPlaying(false);
              onIndex(Math.max(0, index - 1));
            }}
          >
            上一步
          </button>
          <button
            type="button"
            className="rounded bg-violet-700 px-2 py-0.5 text-[11px] text-white hover:bg-violet-600"
            onClick={() => onPlaying(!playing)}
          >
            {playing ? "暂停" : "播放"}
          </button>
          <button
            type="button"
            className="rounded border border-slate-600 px-2 py-0.5 text-[11px] text-slate-300 hover:bg-slate-800"
            onClick={() => {
              onPlaying(false);
              onIndex(Math.min(last, index + 1));
            }}
          >
            下一步
          </button>
          <button
            type="button"
            className="rounded border border-slate-600 px-2 py-0.5 text-[11px] text-slate-300 hover:bg-slate-800"
            onClick={() => {
              onPlaying(false);
              onIndex(last);
            }}
          >
            跳到结果
          </button>
          <button
            type="button"
            className="rounded border border-slate-700 px-2 py-0.5 text-[11px] text-slate-500 hover:bg-slate-800"
            onClick={onClose}
          >
            结束讲解
          </button>
        </div>
      </div>
      <div className="mt-2 flex flex-wrap gap-1">
        {TRACE_ACTS.map((a) => {
          const active = ev?.act === a.id;
          return (
            <button
              key={a.id}
              type="button"
              title={a.hint}
              onClick={() => {
                onPlaying(false);
                const i = events.findIndex((e) => e.act === a.id);
                if (i >= 0) onIndex(i);
              }}
              className={`rounded px-2 py-0.5 text-[10px] ${
                active
                  ? "bg-violet-700 text-white"
                  : "border border-slate-700 text-slate-500 hover:text-slate-300"
              }`}
            >
              {a.label}
            </button>
          );
        })}
      </div>
      <p className="mt-2 text-xs leading-snug text-slate-200">
        {ev?.message ?? "—"}
      </p>
      {ev?.act === "QUEUE" && (
        <div className="mt-2">
          <QueueLane
            events={events}
            index={index}
            sortMode={trace.sort_mode}
            salesByOrder={salesByOrder}
          />
        </div>
      )}
      <div className="mt-2">
        <OccupancyLedger
          events={events}
          index={index}
          dept={ev?.dept}
          group={ev?.group_code}
          date={ev?.task_date}
        />
      </div>
    </div>
  );
}
