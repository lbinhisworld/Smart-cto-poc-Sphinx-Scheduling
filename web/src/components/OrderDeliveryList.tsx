import { useMemo, useState } from "react";
import type { Conflict, OrderRow, ScheduleResult, WoTask } from "../types/schedule";
import { buildOrderDeliveryStories } from "../utils/orderDeliveryStory";
import { OrderDeliveryCard } from "./OrderDeliveryCard";
import type { WoNodeOpenPayload } from "./WoNodeStrip";
import {
  OrderScheduleBoard,
  type OrderScheduleBoardHandle,
} from "./OrderScheduleBoard";
import type { ConflictCellPulse } from "./ScheduleBoard";
import type { DeptCode, GroupCode } from "../constants/groups";
import { forwardRef, useImperativeHandle, useRef } from "react";

export type OrderDeliveryListHandle = {
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
  onFilterOrder?: (orderNo: string | null) => void;
};

type TabId = "feasible" | "late";

export const OrderDeliveryList = forwardRef<OrderDeliveryListHandle, Props>(
  function OrderDeliveryList(props, ref) {
    const {
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
      onFilterOrder,
    } = props;

    const [tab, setTab] = useState<TabId>("feasible");
    const [showClassicMatrix, setShowClassicMatrix] = useState(false);
    const classicRef = useRef<OrderScheduleBoardHandle>(null);

    useImperativeHandle(ref, () => ({
      scrollToOrderCell(orderNo: string, date: string) {
        if (showClassicMatrix) {
          classicRef.current?.scrollToOrderCell(orderNo, date);
        }
      },
    }));

    const buckets = useMemo(
      () =>
        buildOrderDeliveryStories(
          orders,
          selectedOrderNos,
          result,
          tasks,
          conflicts,
        ),
      [orders, selectedOrderNos, result, tasks, conflicts],
    );

    const list = tab === "feasible" ? buckets.feasible : buckets.late;

    const openNode = (payload: WoNodeOpenPayload) => {
      onOpenCellDetail(
        payload.dept,
        payload.group,
        payload.date,
        payload.taskId ?? undefined,
      );
      if (payload.taskId) onSelectTask(payload.taskId);
    };

    return (
      <div className="flex min-h-0 flex-1 flex-col gap-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="inline-flex rounded border border-slate-600 p-0.5 text-xs">
            <button
              type="button"
              className={`rounded px-2 py-1 ${
                tab === "feasible"
                  ? "bg-slate-700 text-slate-100"
                  : "text-slate-500 hover:text-slate-300"
              }`}
              onClick={() => setTab("feasible")}
            >
              交期内可满足 ({buckets.feasible.length})
            </button>
            <button
              type="button"
              className={`rounded px-2 py-1 ${
                tab === "late"
                  ? "bg-slate-700 text-slate-100"
                  : "text-slate-500 hover:text-slate-300"
              }`}
              onClick={() => setTab("late")}
            >
              无法满足交期 ({buckets.late.length})
            </button>
          </div>
          <button
            type="button"
            className="text-[11px] text-sky-400 hover:underline"
            onClick={() => setShowClassicMatrix((v) => !v)}
          >
            {showClassicMatrix ? "收起经典订单×日期矩阵" : "展开经典订单×日期矩阵"}
          </button>
        </div>

        <p className="text-[11px] leading-relaxed text-slate-500">
          按订单查看工单路径（半成品 → 成品）。点击节点可打开格子详情。派工视图仍为组×日产能表。
        </p>

        <div className="min-h-0 flex-1 space-y-3 overflow-y-auto pr-1">
          {list.length === 0 ? (
            <p className="text-xs text-slate-500">
              当前 Tab 暂无订单。请先倒排，或切换 Tab / 检查排程池勾选。
            </p>
          ) : (
            list.map((story) => (
              <OrderDeliveryCard
                key={story.headerOrderNo}
                story={story}
                today={today}
                onOpenNode={openNode}
                onSelectOrder={onFilterOrder}
                selected={boardFilterOrderNo === story.headerOrderNo}
              />
            ))
          )}
        </div>

        {buckets.unscheduled.length > 0 ? (
          <section className="shrink-0 rounded-lg border border-dashed border-slate-700 bg-slate-950/40 px-3 py-2">
            <p className="text-xs font-medium text-slate-400">
              未参与本次计划 ({buckets.unscheduled.length})
            </p>
            <ul className="mt-1 space-y-0.5 text-[11px] text-slate-500">
              {buckets.unscheduled.map((s) => (
                <li key={s.headerOrderNo}>
                  {s.headerOrderNo} · 交期 {s.order.due_date} · {s.lineSummary}
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        {showClassicMatrix ? (
          <div className="max-h-[40vh] shrink-0 overflow-hidden rounded-lg border border-slate-800">
            <OrderScheduleBoard
              ref={classicRef}
              today={today}
              orders={orders}
              selectedOrderNos={selectedOrderNos}
              boardFilterOrderNo={boardFilterOrderNo}
              result={result}
              tasks={tasks}
              conflicts={conflicts}
              selectedTaskId={selectedTaskId}
              onSelectTask={onSelectTask}
              onOpenCellDetail={onOpenCellDetail}
              onCrewChange={onCrewChange}
              conflictPulse={conflictPulse}
            />
          </div>
        ) : null}
      </div>
    );
  },
);
