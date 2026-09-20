import { forwardRef, useImperativeHandle, useMemo, useRef } from "react";
import {
  FENCE_DAYS,
  workCenterLabel,
  type DeptCode,
  type GroupCode,
} from "../constants/groups";
import type {
  Conflict,
  ConflictLevel,
  OrderRow,
  ScheduleResult,
  WoTask,
} from "../types/schedule";
import { addDays, dateRange, isWeekend, shortLabel } from "../utils/dates";
import { cellUtilization } from "../utils/capacity";
import { taskOverHeadcount, warningsByCell } from "../utils/cellValidation";
import { boardDateColumns } from "../utils/conflictFocus";
import { colineGroupAt, colinePointKey, colinePointSet } from "../utils/coline";
import { buildOrderBoardRows } from "../utils/orderBoardRows";
import { DueFlag } from "./DueFlag";
import { TaskBlock } from "./TaskBlock";
import type { ConflictCellPulse } from "./ScheduleBoard";

export type OrderScheduleBoardHandle = {
  scrollToOrderCell: (orderNo: string, date: string) => void;
};

type Props = {
  today: string;
  orders: OrderRow[];
  selectedOrderNos: Set<string>;
  boardFilterOrderNo: string | null;
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

const CELL_PULSE_CLASS: Record<ConflictLevel, string> = {
  RED: "conflict-cell-pulse-red",
  YELLOW: "conflict-cell-pulse-yellow",
  GREY: "conflict-cell-pulse-grey",
  BLUE: "conflict-cell-pulse-blue",
};

export const OrderScheduleBoard = forwardRef<OrderScheduleBoardHandle, Props>(
  function OrderScheduleBoard(
    {
      today,
      orders,
      selectedOrderNos,
      boardFilterOrderNo,
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
      scrollToOrderCell(orderNo: string, date: string) {
        const root = scrollRootRef.current;
        const el = root?.querySelector(
          `[data-order-cell="${orderNo}|${date}"]`,
        );
        el?.scrollIntoView({
          behavior: "smooth",
          block: "center",
          inline: "center",
        });
      },
    }));

    const orderRows = useMemo(
      () =>
        buildOrderBoardRows(
          orders,
          selectedOrderNos,
          result,
          boardFilterOrderNo,
        ),
      [orders, selectedOrderNos, result, boardFilterOrderNo],
    );

    const dates = useMemo(() => {
      const base = boardDateColumns(today, tasks, conflicts, dateRange);
      const set = new Set(base);
      for (const row of orderRows) set.add(row.order.due_date);
      return [...set].sort();
    }, [today, tasks, conflicts, orderRows]);

    const woMap = useMemo(
      () => new Map(result?.wos.map((w) => [w.wo_no, w]) ?? []),
      [result],
    );
    const colineKeys = useMemo(() => colinePointSet(result), [result]);

    const conflictWos = useMemo(
      () =>
        new Set(
          conflicts.filter((c) => c.wo_no).map((c) => c.wo_no as string),
        ),
      [conflicts],
    );

    const byOrderDate = useMemo(() => {
      const map = new Map<string, WoTask[]>();
      for (const t of tasks) {
        const wo = woMap.get(t.wo_no);
        const ono = wo?.source_order_no;
        if (!ono) continue;
        const key = `${ono}|${t.task_date}`;
        if (!map.has(key)) map.set(key, []);
        map.get(key)!.push(t);
      }
      return map;
    }, [tasks, woMap]);

    const byWcCell = useMemo(() => {
      const map = new Map<string, WoTask[]>();
      for (const t of tasks) {
        const key = `${t.dept ?? "FINISHED_DEPT"}|${t.group_code}|${t.task_date}`;
        if (!map.has(key)) map.set(key, []);
        map.get(key)!.push(t);
      }
      return map;
    }, [tasks]);

    const wcCellWarnings = useMemo(() => warningsByCell(tasks), [tasks]);

    return (
      <div className="flex min-h-0 flex-1 flex-col">
        <p className="mb-2 shrink-0 text-[11px] text-slate-500">
          订单视图 · 行=订单 · 列=日期 · 交期列 🚩 · 一部组是并行产线 · 二部片材可流向一部三组
        </p>
        <div
          ref={scrollRootRef}
          className="min-h-0 flex-1 overflow-auto rounded-lg border border-slate-800 bg-slate-900/30"
        >
          <table className="w-full border-separate border-spacing-0 text-sm">
            <thead className="[&_th]:bg-slate-900">
              <tr>
                <th className="sticky left-0 top-0 z-[35] min-w-[140px] border border-slate-800 px-2 py-2 text-left text-slate-300 shadow-[0_1px_0_0_rgb(30_41_59),1px_0_0_0_rgb(30_41_59)]">
                  订单 \\ 日期
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
              {orderRows.length === 0 ? (
                <tr>
                  <td
                    colSpan={dates.length + 1}
                    className="border border-slate-800 px-4 py-8 text-center text-xs text-slate-500"
                  >
                    请在订单池勾选参与倒排的订单
                  </td>
                </tr>
              ) : (
                orderRows.map((row) => {
                  const { order, scheduled, planStart, planEnd } = row;
                  return (
                    <tr
                      key={order.order_no}
                      className={scheduled ? "" : "opacity-75"}
                    >
                      <th className="sticky left-0 z-[15] border border-slate-800 bg-slate-900 px-2 py-2 text-left text-xs shadow-[1px_0_0_0_rgb(30_41_59)]">
                        <div className="font-medium text-slate-100">
                          {order.order_no}
                          <span className="font-normal text-slate-500">
                            {" "}
                            · {order.item_code}
                          </span>
                        </div>
                        {order.sales_name && (
                          <div className="text-[10px] text-sky-400/90">
                            销售 {order.sales_name}
                          </div>
                        )}
                        <div className="max-w-[132px] truncate text-[10px] text-slate-500">
                          {order.customer}
                        </div>
                        {scheduled && planStart && planEnd ? (
                          <div className="mt-1 text-[10px] text-emerald-500/90">
                            {planStart.slice(5)} → {planEnd.slice(5)}
                          </div>
                        ) : (
                          <div className="mt-1 text-[10px] text-slate-600">
                            未排产
                          </div>
                        )}
                      </th>
                      {dates.map((d) => {
                        const key = `${order.order_no}|${d}`;
                        const cellTasks = byOrderDate.get(key) ?? [];
                        const isDue = d === order.due_date;
                        const weekend = isWeekend(d);
                        const inFence =
                          d >= today && d <= addDays(today, FENCE_DAYS);
                        const pulsing =
                          conflictPulse?.orderNo === order.order_no &&
                          conflictPulse.date === d;
                        return (
                          <td
                            key={key}
                            data-order-cell={key}
                            className={`relative align-top border border-slate-800 p-1 min-w-[88px] ${
                              weekend ? "bg-slate-900/60" : "bg-slate-950/40"
                            } ${inFence ? "border-l-2 border-l-amber-600/70" : ""} ${
                              isDue ? "bg-rose-950/20" : ""
                            } ${pulsing && conflictPulse ? CELL_PULSE_CLASS[conflictPulse.level] : ""}`}
                          >
                            {isDue && <DueFlag dueDate={order.due_date} />}
                            <div className="min-h-[52px]">
                              {cellTasks.map((task) => {
                                const dept = (task.dept ??
                                  "FINISHED_DEPT") as DeptCode;
                                const group = task.group_code as GroupCode;
                                const wcKey = `${dept}|${group}|${task.task_date}`;
                                const wcTasks = byWcCell.get(wcKey) ?? [];
                                const wcUtil = cellUtilization(wcTasks);
                                const wcWarns =
                                  wcCellWarnings.get(wcKey) ?? [];
                                return (
                                  <TaskBlock
                                    key={task.task_id}
                                    task={task}
                                    wo={woMap.get(task.wo_no)}
                                    conflictCodes={conflictWos}
                                    selected={selectedTaskId === task.task_id}
                                    draggable={false}
                                    showWorkCenter
                                    workCenterLabel={workCenterLabel(
                                      dept,
                                      group,
                                    )}
                                    capacityUtilization={wcUtil}
                                    capacityWarnings={wcWarns}
                                    overHeadcount={taskOverHeadcount(task)}
                                    coline={Boolean(
                                      woMap.get(task.wo_no)?.item_code &&
                                        colineKeys.has(
                                          colinePointKey(
                                            dept,
                                            group,
                                            d,
                                            woMap.get(task.wo_no)!.item_code,
                                          ),
                                        ),
                                    )}
                                    colineLabel={(() => {
                                      const item = woMap.get(task.wo_no)?.item_code;
                                      if (!item) return null;
                                      const g = colineGroupAt(result, dept, group, d, item);
                                      return g
                                        ? `${g.item_code} · ${g.order_nos.length}单 · 共 ${g.qty_board} 版`
                                        : null;
                                    })()}
                                    onSelect={() => {
                                      onSelectTask(task.task_id);
                                      onOpenCellDetail(
                                        dept,
                                        group,
                                        d,
                                        task.task_id,
                                      );
                                    }}
                                    onCrewChange={(crew) =>
                                      onCrewChange(task.task_id, crew)
                                    }
                                  />
                                );
                              })}
                            </div>
                          </td>
                        );
                      })}
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    );
  },
);
