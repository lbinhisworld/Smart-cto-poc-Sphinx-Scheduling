import type {
  Conflict,
  ConflictLevel,
  OrderRow,
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
import { groupConflictsByOrder } from "../utils/conflictGroups";
import { shortLabel } from "../utils/dates";

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
};

export function ConflictPanel({
  conflicts,
  orders,
  wos,
  tasks,
  selectedKey,
  onPick,
}: Props) {
  const counts = LEVEL_ORDER.map((lv) => ({
    lv,
    n: conflicts.filter((c) => c.level === lv).length,
  }));
  const groups = groupConflictsByOrder(conflicts, orders, wos, tasks);

  return (
    <aside className="flex h-full min-h-[280px] flex-col rounded-lg border border-slate-800 bg-slate-900">
      <div className="border-b border-slate-800 px-3 py-2">
        <h2 className="text-sm font-semibold text-slate-200">冲突面板</h2>
        <p className="mt-1 text-xs text-slate-400">
          {counts.map(({ lv, n }) => (
            <span key={lv} className="mr-2">
              {LEVEL_STYLE[lv].dot} {n}
            </span>
          ))}
        </p>
        <p className="mt-1 text-[10px] text-slate-500">
          按订单分组 · 找对应销售协商
        </p>
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
      </div>
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
                {g.items.map(({ conflict: c, index, woType }) => {
                  const key = conflictRowKey(c, index);
                  const metric = conflictMetricNote(c);
                  const selected = selectedKey === key;
                  const typeHint = woTypeLabel(woType);
                  return (
                    <li key={key}>
                      <button
                        type="button"
                        onClick={() => onPick(c, key)}
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
                        <p className="mt-1 text-[10px] text-slate-500">
                          点击定位看板单元格
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
    </aside>
  );
}
