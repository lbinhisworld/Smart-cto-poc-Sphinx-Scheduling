import { useDraggable } from "@dnd-kit/core";
import { CSS } from "@dnd-kit/utilities";
import { CapacityBar } from "./CapacityBar";
import type { Wo, WoTask } from "../types/schedule";
import { hoursOf } from "../utils/capacity";

type Props = {
  task: WoTask;
  wo: Wo | undefined;
  conflictCodes: Set<string>;
  selected: boolean;
  onSelect: () => void;
  onCrewChange: (crew: number) => void;
  overHeadcount?: boolean;
  draggable?: boolean;
  showWorkCenter?: boolean;
  workCenterLabel?: string;
  /** 该任务所属工作中心×日的组日利用率（订单视图） */
  capacityUtilization?: number;
  capacityWarnings?: string[];
};

export function TaskBlock({
  task,
  wo,
  conflictCodes,
  selected,
  onSelect,
  onCrewChange,
  overHeadcount = false,
  draggable = true,
  showWorkCenter = false,
  workCenterLabel: wcLabel,
  capacityUtilization,
  capacityWarnings,
}: Props) {
  const id = `task-${task.task_id}`;
  const { attributes, listeners, setNodeRef, transform, isDragging } =
    useDraggable({ id, data: { task }, disabled: !draggable });

  const style = {
    transform: CSS.Translate.toString(transform),
    opacity: isDragging ? 0.5 : 1,
  };

  const hasConflict = conflictCodes.has(task.wo_no);
  const semi = wo?.wo_type === "SEMI";

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`mb-1 rounded border px-1.5 py-1 text-xs shadow-sm ${
        draggable ? "cursor-grab active:cursor-grabbing" : "cursor-pointer"
      } ${
        selected
          ? "border-sky-400 bg-sky-950/80"
          : hasConflict || overHeadcount
            ? "border-rose-500/80 bg-rose-950/40"
            : semi
              ? "border-violet-500/60 bg-violet-950/50"
              : "border-slate-600 bg-slate-800/90"
      }`}
      onClick={(e) => {
        e.stopPropagation();
        onSelect();
      }}
      {...(draggable ? { ...listeners, ...attributes } : {})}
    >
      {showWorkCenter && wcLabel && (
        <div className="mb-0.5 truncate text-[9px] text-slate-500">{wcLabel}</div>
      )}
      <div className="font-medium text-slate-100">
        {wo?.item_code ?? task.wo_no}{" "}
        <span className="text-slate-400">{task.qty_board}版</span>
      </div>
      <div className="flex items-center justify-between gap-1 text-[10px] text-slate-400">
        <span>{hoursOf(task).toFixed(1)} 小时</span>
        <label className="flex items-center gap-0.5" onClick={(e) => e.stopPropagation()}>
          人力
          <input
            type="number"
            min={1}
            max={9}
            title={overHeadcount ? "超过组在编人数" : undefined}
            className={`w-8 rounded px-0.5 text-center text-slate-200 ${
              overHeadcount ? "bg-rose-950 ring-1 ring-rose-500" : "bg-slate-900"
            }`}
            value={task.crew_plan}
            onChange={(e) => onCrewChange(Number(e.target.value) || 1)}
          />
        </label>
      </div>
      {capacityUtilization != null && (
        <CapacityBar
          utilization={capacityUtilization}
          warnings={capacityWarnings}
        />
      )}
    </div>
  );
}
