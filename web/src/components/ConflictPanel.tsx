import { useState } from "react";
import type {
  Conflict,
  ConflictLevel,
  OrderRow,
  ScheduleTrace,
  Wo,
  WoTask,
} from "../types/schedule";
import {
  CONFLICT_LEVEL_GUIDE,
  conflictCodeLabel,
  conflictMetricNote,
  conflictRowKey,
  formatConflictMessage,
  suggestLabel,
} from "../utils/conflictLabels";
import {
  conflictDisplayRowKey,
  groupConflictsByOrder,
  mergedItemCodes,
} from "../utils/conflictGroups";
import { shortLabel } from "../utils/dates";
import { ScheduleProcessTab } from "./ScheduleProcessTab";

const LEVEL_ORDER: ConflictLevel[] = ["RED", "YELLOW", "GREY", "BLUE"];

const LEVEL_STYLE: Record<
  ConflictLevel,
  {
    label: string;
    badge: string;
    dot: string;
    card: string;
    cardSelected: string;
    metric: string;
  }
> = {
  RED: {
    label: "红色",
    badge: "bg-rose-600",
    dot: "🔴",
    card: "border-rose-600/50 bg-rose-950/45 hover:border-rose-500/80",
    cardSelected: "border-rose-400 ring-1 ring-rose-500/60 bg-rose-950/70",
    metric: "text-rose-200/90",
  },
  YELLOW: {
    label: "黄色",
    badge: "bg-amber-500",
    dot: "🟡",
    card: "border-amber-600/45 bg-amber-950/35 hover:border-amber-500/70",
    cardSelected: "border-amber-400 ring-1 ring-amber-500/50 bg-amber-950/55",
    metric: "text-amber-100/90",
  },
  GREY: {
    label: "灰色",
    badge: "bg-slate-500",
    dot: "⚪",
    card: "border-slate-600/50 bg-slate-900/55 hover:border-slate-500/70",
    cardSelected: "border-slate-400 ring-1 ring-slate-500/50 bg-slate-900/80",
    metric: "text-slate-300/90",
  },
  BLUE: {
    label: "蓝色",
    badge: "bg-sky-600",
    dot: "🔵",
    card: "border-sky-600/45 bg-sky-950/35 hover:border-sky-500/70",
    cardSelected: "border-sky-400 ring-1 ring-sky-500/50 bg-sky-950/55",
    metric: "text-sky-100/90",
  },
};

function dueShort(due: string | null): string | null {
  if (!due) return null;
  return /^\d{4}-\d{2}-\d{2}$/.test(due) ? shortLabel(due) : due;
}

function woTypeLabel(woType: string | null): string | null {
  if (woType === "SEMI") return "半成品工单";
  if (woType === "FINISHED") return "成品工单";
  return null;
}

type Props = {
  conflicts: Conflict[];
  orders: OrderRow[];
  wos: Wo[];
  tasks: WoTask[];
  selectedKey: string | null;
  onPick: (c: Conflict, key: string) => void;
  trace?: ScheduleTrace | null;
  onReplay?: () => void;
};

export function ConflictPanel({
  conflicts,
  orders,
  wos,
  tasks,
  selectedKey,
  onPick,
  trace,
  onReplay,
}: Props) {
  const [tab, setTab] = useState<"list" | "process">("list");
  const counts = LEVEL_ORDER.map((lv) => ({
    lv,
    n: conflicts.filter((c) => c.level === lv).length,
  }));
  const groups = groupConflictsByOrder(conflicts, orders, wos, tasks);
  const woByNo = new Map(wos.map((w) => [w.wo_no, w]));

  const rowSelected = (rowKey: string, memberKeys: string[]) =>
    selectedKey === rowKey || (selectedKey != null && memberKeys.includes(selectedKey));

  return (
    <aside className="flex h-full min-h-[280px] flex-col rounded-lg border border-slate-800 bg-slate-900">
      <div className="border-b border-slate-800 px-3 py-2">
        <div className="flex gap-1 text-[11px]">
          <button
            type="button"
            className={`rounded px-2 py-0.5 ${tab === "list" ? "bg-slate-800 text-slate-100" : "text-slate-500"}`}
            onClick={() => setTab("list")}
          >
            清单
          </button>
          <button
            type="button"
            className={`rounded px-2 py-0.5 ${tab === "process" ? "bg-slate-800 text-violet-200" : "text-slate-500"}`}
            onClick={() => setTab("process")}
          >
            过程
          </button>
        </div>
        <h2 className="mt-1.5 text-sm font-semibold text-slate-200">
          {tab === "list" ? "冲突面板" : "排产过程"}
        </h2>
        <p className="mt-1 text-xs text-slate-400">
          {counts.map(({ lv, n }) => (
            <span key={lv} className="mr-2">
              {LEVEL_STYLE[lv].dot} {n}
            </span>
          ))}
        </p>
        <p className="mt-1 text-[10px] text-slate-500">
          {tab === "list" ? "按订单分组 · 找对应销售协商" : "回放倒排记录 · 策略卡需人确认"}
        </p>
        {trace?.events.some((e) => e.kind === "coline_summary") ? (
          <p className="mt-1 text-[10px] text-teal-300/90">
            {trace.events.find((e) => e.kind === "coline_summary")?.message}
          </p>
        ) : null}
        {tab === "list" && (
        <details className="mt-2 text-[10px] text-slate-400">
          <summary className="cursor-pointer select-none text-slate-500 hover:text-slate-300">
            各级别说明
          </summary>
          <ul className="mt-1.5 space-y-2 pl-0.5">
            {LEVEL_ORDER.map((lv) => (
              <li key={lv}>
                <span className="font-medium text-slate-300">
                  {CONFLICT_LEVEL_GUIDE[lv].title}
                </span>
                <span className="text-slate-500">（{CONFLICT_LEVEL_GUIDE[lv].codes}）</span>
                <p className="text-slate-500 leading-snug">
                  {CONFLICT_LEVEL_GUIDE[lv].meaning}
                </p>
              </li>
            ))}
          </ul>
        </details>
        )}
      </div>
      {tab === "process" ? (
        <ScheduleProcessTab
          trace={trace}
          conflicts={conflicts}
          orders={orders}
          onReplay={onReplay}
        />
      ) : (
      <div className="flex-1 overflow-y-auto p-2 space-y-3">
        {groups.length === 0 && (
          <p className="text-xs text-slate-500 px-1">暂无冲突</p>
        )}
        {groups.map((g) => {
          const due = dueShort(g.dueDate);
          return (
            <section
              key={g.key}
              className="rounded-md border border-slate-800/80 bg-slate-950/40 p-2"
            >
              <header className="mb-1.5">
                {g.orderNo ? (
                  <>
                    <p className="text-xs font-semibold text-slate-100">
                      {g.orderNo}
                      <span className="ml-1.5 font-normal text-violet-300">
                        销售 {g.salesName}
                      </span>
                    </p>
                    <p className="mt-0.5 truncate text-[10px] text-slate-400">
                      {[g.customer, g.itemCode, due ? `交期 ${due}` : null]
                        .filter(Boolean)
                        .join(" · ")}
                    </p>
                  </>
                ) : g.crossOrderLabels.length > 0 ? (
                  <>
                    <p className="text-xs font-semibold text-slate-100">
                      组日产能 · 多单
                    </p>
                    <p className="mt-0.5 text-[10px] leading-snug text-violet-300/90">
                      {g.crossOrderLabels.join(" · ")}
                    </p>
                  </>
                ) : (
                  <p className="text-xs font-semibold text-slate-400">未关联订单</p>
                )}
              </header>
              <ul className="space-y-1">
                {g.rows.map((row) => {
                  const c = row.conflict;
                  const rowKey = conflictDisplayRowKey(row);
                  const memberKeys = (row.merged ?? [{ conflict: c, index: row.index, woType: row.woType }]).map(
                    (m) => conflictRowKey(m.conflict, m.index),
                  );
                  const metric = conflictMetricNote(c);
                  const selected = rowSelected(rowKey, memberKeys);
                  const typeHint = woTypeLabel(row.woType);
                  const merged = row.merged && row.merged.length > 1;
                  const itemCodes = mergedItemCodes(row, woByNo);
                  const singleItem =
                    !merged && c.wo_no ? woByNo.get(c.wo_no)?.item_code : null;
                  return (
                    <li key={rowKey}>
                      <button
                        type="button"
                        onClick={() => onPick(c, rowKey)}
                        className={`w-full rounded border px-2 py-1.5 text-left text-xs transition ${
                          selected
                            ? LEVEL_STYLE[c.level].cardSelected
                            : LEVEL_STYLE[c.level].card
                        }`}
                      >
                        <span className="font-medium text-slate-100">
                          {conflictCodeLabel(c.code)}
                        </span>
                        {typeHint && (
                          <span className="ml-1 text-[10px] text-slate-500">
                            {typeHint}
                          </span>
                        )}
                        {merged && itemCodes.length > 0 && (
                          <span className="ml-1 text-[10px] text-sky-300/90">
                            ×{row.merged!.length}（{itemCodes.join(" · ")}）
                          </span>
                        )}
                        {!merged && singleItem && singleItem !== g.itemCode && (
                          <span className="ml-1 text-[10px] text-sky-300/90">
                            {singleItem}
                          </span>
                        )}
                        <p className="mt-0.5 text-slate-300/90 leading-snug">
                          {formatConflictMessage(c.message)}
                        </p>
                        {metric && (
                          <p
                            className={`mt-1 font-mono text-[10px] ${LEVEL_STYLE[c.level].metric}`}
                          >
                            {metric}
                          </p>
                        )}
                        {suggestLabel(c.suggest) && (
                          <p className="mt-1 text-[10px] text-emerald-400/90">
                            建议：{suggestLabel(c.suggest)}
                          </p>
                        )}
                        {merged ? (
                          <div className="mt-1.5 flex flex-wrap gap-1">
                            {row.merged!.map((m) => {
                              const code =
                                (m.conflict.wo_no
                                  ? woByNo.get(m.conflict.wo_no)?.item_code
                                  : null) ?? m.conflict.wo_no ?? "?";
                              const chipKey = conflictRowKey(m.conflict, m.index);
                              return (
                                <span
                                  key={chipKey}
                                  role="button"
                                  tabIndex={0}
                                  className={`rounded px-1.5 py-0.5 text-[10px] ${
                                    selectedKey === chipKey
                                      ? "bg-slate-700 text-slate-100 ring-1 ring-slate-500"
                                      : "bg-slate-800/80 text-slate-400 hover:text-slate-200"
                                  }`}
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    onPick(m.conflict, chipKey);
                                  }}
                                  onKeyDown={(e) => {
                                    if (e.key === "Enter" || e.key === " ") {
                                      e.preventDefault();
                                      e.stopPropagation();
                                      onPick(m.conflict, chipKey);
                                    }
                                  }}
                                >
                                  {code}
                                </span>
                              );
                            })}
                          </div>
                        ) : null}
                        <p className="mt-1 text-[10px] text-slate-500">
                          {merged
                            ? "点卡片定位首条工单；点子件定位对应工单"
                            : "点击定位看板单元格"}
                        </p>
                      </button>
                    </li>
                  );
                })}
              </ul>
            </section>
          );
        })}
      </div>
      )}
    </aside>
  );
}
