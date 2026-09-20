import type { DeptCode, GroupCode } from "../constants/groups";
import type { ConflictLevel } from "../types/schedule";
import {
  formatDateRange,
  type WoNodeStory,
} from "../utils/orderDeliveryStory";

const BORDER: Record<ConflictLevel, string> = {
  RED: "border-l-rose-500",
  YELLOW: "border-l-amber-400",
  GREY: "border-l-slate-500",
  BLUE: "border-l-teal-400",
};

type Props = {
  nodes: WoNodeStory[];
  onOpenNode: (node: WoNodeStory) => void;
};

export function WoNodeStrip({ nodes, onOpenNode }: Props) {
  if (nodes.length === 0) {
    return (
      <p className="text-xs text-slate-500">本单尚未生成工单或未参与本次倒排。</p>
    );
  }
  return (
    <div className="flex items-stretch gap-1 overflow-x-auto pb-1">
      {nodes.map((node, i) => (
        <div key={node.woNo} className="flex shrink-0 items-center gap-1">
          {i > 0 ? (
            <span className="px-1 text-slate-500" aria-hidden>
              →
            </span>
          ) : null}
          <button
            type="button"
            onClick={() => onOpenNode(node)}
            className={`min-w-[168px] max-w-[220px] rounded-lg border border-slate-700 bg-slate-900/80 px-2.5 py-2 text-left text-[11px] hover:border-sky-600 ${
              node.conflictLevel
                ? `border-l-4 ${BORDER[node.conflictLevel]}`
                : "border-l-4 border-l-slate-700"
            }`}
          >
            <p className="font-medium text-slate-100">{node.workCenterLabel}</p>
            <p className="text-slate-400">
              {formatDateRange(node.dateFrom, node.dateTo)}
            </p>
            <p className="mt-0.5 text-slate-200">
              {node.itemCode} · 计划 {node.qtyScheduled}/{node.qtyBoardPlan} 版
            </p>
            {node.qtyBoardDone > 0 ? (
              <p className="text-emerald-400/90">已完工 {node.qtyBoardDone} 版</p>
            ) : null}
            {node.unplacedRemaining > 0 ? (
              <p className="text-rose-300">未排余量 {node.unplacedRemaining} 版</p>
            ) : null}
            <p className="mt-0.5 text-slate-500">
              墙钟 {node.hoursWall.toFixed(1)}h · 人工 ¥{node.costPlanned.toFixed(0)}
            </p>
            <div className="mt-1 flex flex-wrap gap-1">
              {node.coline ? (
                <span className="rounded bg-teal-950 px-1 text-[9px] text-teal-200">
                  共线
                </span>
              ) : null}
              {node.woType === "SEMI" ? (
                <span className="rounded bg-violet-950 px-1 text-[9px] text-violet-200">
                  半成品
                </span>
              ) : null}
            </div>
          </button>
        </div>
      ))}
    </div>
  );
}

export type WoNodeOpenPayload = {
  dept: DeptCode;
  group: GroupCode;
  date: string;
  taskId: number | null;
};

export function nodeToCellFocus(node: WoNodeStory): WoNodeOpenPayload | null {
  if (!node.openCellDate) return null;
  return {
    dept: node.dept,
    group: node.groupCode,
    date: node.openCellDate,
    taskId: node.primaryTaskId,
  };
}
