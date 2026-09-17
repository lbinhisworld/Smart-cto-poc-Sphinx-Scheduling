import { useDroppable } from "@dnd-kit/core";
import { forwardRef, useImperativeHandle, useRef, type ReactNode } from "react";
import {
  FENCE_DAYS,
  wcKey,
  WORK_CENTERS,
  type DeptCode,
  type GroupCode,
} from "../constants/groups";
import type {
  Conflict,
  ConflictLevel,
  ScheduleResult,
  WoTask,
} from "../types/schedule";
import { addDays, dateRange, isWeekend, shortLabel } from "../utils/dates";
import { cellUtilization } from "../utils/capacity";
import { taskOverHeadcount, warningsByCell } from "../utils/cellValidation";
import { boardDateColumns } from "../utils/conflictFocus";
import { colineGroupAt, colinePointKey, colinePointSet } from "../utils/coline";
import { CapacityBar } from "./CapacityBar";
import { TaskBlock } from "./TaskBlock";

export type ConflictCellPulse = {
  dept?: string;
  group?: string;
  date: string;
  orderNo?: string;
  level: ConflictLevel;
};

const CELL_PULSE_CLASS: Record<ConflictLevel, string> = {
  RED: "conflict-cell-pulse-red",
  YELLOW: "conflict-cell-pulse-yellow",
  GREY: "conflict-cell-pulse-grey",
  BLUE: "conflict-cell-pulse-blue",
};

type Props = {
  today: string;
  result: ScheduleResult | null;
  tasks: WoTask[];
  conflicts: Conflict[];
  selectedTaskId: number | null;
  onSelectTask: (id: number | null) => void;
  onOpenCellDetail: (
    dept: DeptCode,
    group: GroupCode,
    date: string,
    focusTaskId?: number,
  ) => void;
  onCrewChange: (taskId: number, crew: number) => void;
  conflictPulse: ConflictCellPulse | null;
};

function DroppableCell({
  dept,
  group,
  date,
  today,
  children,
  utilization,
  cellWarnings,
  onCellBackgroundClick,
  pulseLevel,
}: {
  dept: DeptCode;
  group: GroupCode;
  date: string;
  today: string;
  children: ReactNode;
  utilization: number;
  cellWarnings: string[];
  onCellBackgroundClick: () => void;
  pulseLevel: ConflictLevel | null;
}) {
  const id = wcKey(dept, group) + `|${date}`;
  const { setNodeRef, isOver } = useDroppable({ id, data: { dept, group, date } });
  const weekend = isWeekend(date);
  const inFence = date >= today && date <= addDays(today, FENCE_DAYS);
  return (
    <td
      ref={setNodeRef}
      data-schedule-cell={`${dept}|${group}|${date}`}
      className={`align-top border border-slate-800 p-1 min-w-[88px] cursor-pointer ${
        weekend ? "bg-slate-900/60" : "bg-slate-950/40"
      } ${inFence ? "border-l-2 border-l-amber-600/70" : ""} ${
        isOver ? "ring-2 ring-sky-500/60" : ""
      } ${pulseLevel ? CELL_PULSE_CLASS[pulseLevel] : ""}`}
      onClick={onCellBackgroundClick}
      title="点击查看本格详情"
    >
      <div className="min-h-[52px]">{children}</div>
      <CapacityBar utilization={utilization} warnings={cellWarnings} />
    </td>
  );
}

export type ScheduleBoardHandle = {
  scrollToCell: (dept: string, group: string, date: string) => void;
};

export const ScheduleBoard = forwardRef<ScheduleBoardHandle, Props>(function ScheduleBoard(
  {
    today,
    result,
    tasks,
    conflicts,
    selectedTaskId,
    onSelectTask,
    onOpenCellDetail,
    onCrewChange,
    conflictPulse,
  },
  ref,
) {
  const scrollRootRef = useRef<HTMLDivElement>(null);
  useImperativeHandle(ref, () => ({
    scrollToCell(dept: string, group: string, date: string) {
      const root = scrollRootRef.current;
      const el = root?.querySelector(
        `[data-schedule-cell="${dept}|${group}|${date}"]`,
      );
      el?.scrollIntoView({ behavior: "smooth", block: "center", inline: "center" });
    },
  }));
  const dates = boardDateColumns(today, tasks, conflicts, dateRange);
  const woMap = new Map(result?.wos.map((w) => [w.wo_no, w]) ?? []);
  const colineKeys = colinePointSet(result);
  const conflictWos = new Set(
    conflicts.filter((c) => c.wo_no).map((c) => c.wo_no as string),
  );

  const byCell = new Map<string, WoTask[]>();
  for (const t of tasks) {
    const key = `${t.dept ?? "FINISHED_DEPT"}|${t.group_code}|${t.task_date}`;
    if (!byCell.has(key)) byCell.set(key, []);
    byCell.get(key)!.push(t);
  }

  const cellWarningText = warningsByCell(tasks);

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div
        ref={scrollRootRef}
        className="min-h-0 flex-1 overflow-auto rounded-lg border border-slate-800 bg-slate-900"
      >
        <table className="w-full border-separate border-spacing-0 text-sm">
          <thead className="[&_th]:bg-slate-900">
            <tr>
              <th className="sticky left-0 top-0 z-[35] border border-slate-800 px-2 py-2 text-left text-slate-300 shadow-[0_1px_0_0_rgb(30_41_59),1px_0_0_0_rgb(30_41_59)]">
                工作中心 \\ 日期
              </th>
              {dates.map((d) => (
                <th
                  key={d}
                  className={`sticky top-0 z-[30] border border-slate-800 px-1 py-2 text-center text-xs font-normal shadow-[0_1px_0_0_rgb(30_41_59)] ${
                    d === today ? "text-sky-400" : "text-slate-400"
                  }`}
                >
                  {shortLabel(d)}
                  {d === today && <div className="text-[10px]">今天</div>}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {WORK_CENTERS.map((wc) => (
              <tr key={wcKey(wc.dept, wc.code)}>
                <th className="sticky left-0 z-[15] border border-slate-800 bg-slate-900 px-2 py-2 text-left text-slate-200 whitespace-nowrap shadow-[1px_0_0_0_rgb(30_41_59)]">
                  {wc.name}
                </th>
                {dates.map((d) => {
                  const key = `${wc.dept}|${wc.code}|${d}`;
                  const cellTasks = byCell.get(key) ?? [];
                  const util = cellUtilization(cellTasks);
                  const cellWarns = cellWarningText.get(key) ?? [];
                  const pulsing =
                    !conflictPulse?.orderNo &&
                    conflictPulse?.dept === wc.dept &&
                    conflictPulse?.group === wc.code &&
                    conflictPulse?.date === d;
                  return (
                    <DroppableCell
                      key={key}
                      dept={wc.dept}
                      group={wc.code}
                      date={d}
                      today={today}
                      utilization={util}
                      cellWarnings={cellWarns}
                      pulseLevel={pulsing ? conflictPulse.level : null}
                      onCellBackgroundClick={() =>
                        onOpenCellDetail(wc.dept, wc.code, d)
                      }
                    >
                      {cellTasks.map((task) => {
                        const wo = woMap.get(task.wo_no);
                        const item = wo?.item_code ?? "";
                        const coline = Boolean(
                          item &&
                            colineKeys.has(
                              colinePointKey(wc.dept, wc.code, d, item),
                            ),
                        );
                        const grp = coline
                          ? colineGroupAt(result, wc.dept, wc.code, d, item)
                          : undefined;
                        return (
                        <TaskBlock
                          key={task.task_id}
                          task={task}
                          wo={wo}
                          conflictCodes={conflictWos}
                          selected={selectedTaskId === task.task_id}
                          overHeadcount={taskOverHeadcount(task)}
                          coline={coline}
                          colineLabel={
                            grp
                              ? `${grp.item_code} · ${grp.order_nos.length}单 · 共 ${grp.qty_board} 版`
                              : null
                          }
                          onSelect={() => {
                            onSelectTask(task.task_id);
                            onOpenCellDetail(wc.dept, wc.code, d, task.task_id);
                          }}
                          onCrewChange={(crew) => onCrewChange(task.task_id, crew)}
                        />
                        );
                      })}
                    </DroppableCell>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
});
