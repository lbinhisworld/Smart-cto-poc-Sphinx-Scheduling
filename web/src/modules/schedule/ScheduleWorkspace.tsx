import {
  DndContext,
  DragEndEvent,
  PointerSensor,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  fetchConflicts,
  fetchOrdersDetailed,
  interactivePreview,
  patchOrderDue,
  publishSchedulingPool,
  scheduleApply,
  scheduleRun,
  scheduleWhatIf,
  updateSchedulingPool,
  fetchPlan,
  fetchPlanKitStatus,
  reloadDemoSeed,
} from "../../api/client";
import { KitDetailDrawer } from "../../components/KitDetailDrawer";
import { StockCenterPage } from "../../pages/StockCenterPage";
import type { KitAllocation, KitCheck } from "../../types/kit";
import type { HeadcountWarning, OrderImpact } from "../../components/AdjustImpactModal";
import { SandboxCompareView } from "../../components/SandboxCompareView";
import { BomExplorerPage } from "../../components/BomExplorerPage";
import {
  CellDetailDrawer,
  type CellDetailFocus,
} from "../../components/CellDetailDrawer";
import { ConflictPanel } from "../../components/ConflictPanel";
import { NarrationBar } from "../../components/NarrationBar";
import { OrderBomDrawer } from "../../components/OrderBomDrawer";
import { OrderPoolSidebar } from "../../components/OrderPoolSidebar";
import {
  TrialConflictModal,
  TrialSuccessModal,
} from "../../components/ScheduleTrialModals";
import {
  OrderScheduleBoard,
  type OrderScheduleBoardHandle,
} from "../../components/OrderScheduleBoard";
import {
  ScheduleBoard,
  type ConflictCellPulse,
  type ScheduleBoardHandle,
} from "../../components/ScheduleBoard";
import { DEMO_TODAY, type DeptCode, type GroupCode } from "../../constants/groups";
import type {
  Conflict,
  OrderRow,
  ScheduleResult,
  ScheduleTrace,
  WoTask,
} from "../../types/schedule";
import { revealedTaskIds } from "../../utils/scheduleTrace";
import {
  affectedCells,
  filterHeadcountWarnings,
} from "../../utils/affectedCells";
import { resolveConflictCell } from "../../utils/conflictFocus";
import {
  commitmentsFromResult,
  poolHasBlockingRed,
  type OrderCommitment,
} from "../../utils/orderCommitments";

function cloneTasks(tasks: WoTask[]): WoTask[] {
  return tasks.map((t) => ({ ...t }));
}

function mergeTasksIntoResult(
  base: ScheduleResult,
  proposedTasks: WoTask[],
): ScheduleResult {
  return { ...base, tasks: cloneTasks(proposedTasks) };
}

function orderNoForTask(
  result: ScheduleResult | null,
  task: WoTask,
): string | null {
  if (!result) return null;
  return result.wos.find((w) => w.wo_no === task.wo_no)?.source_order_no ?? null;
}

export function ScheduleWorkspace() {
  const [today] = useState(DEMO_TODAY);
  const [orders, setOrders] = useState<OrderRow[]>([]);
  const [pendingSelected, setPendingSelected] = useState<Set<string>>(new Set());
  const [trialSuccessOpen, setTrialSuccessOpen] = useState(false);
  const [trialConflictOpen, setTrialConflictOpen] = useState(false);
  const [trialCommitments, setTrialCommitments] = useState<OrderCommitment[]>(
    [],
  );
  const [trialYellowNote, setTrialYellowNote] = useState(false);
  const [planVersion, setPlanVersion] = useState(0);
  const [result, setResult] = useState<ScheduleResult | null>(null);
  const [tasks, setTasks] = useState<WoTask[]>([]);
  const [conflicts, setConflicts] = useState<Conflict[]>([]);
  const [previewMode, setPreviewMode] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedTaskId, setSelectedTaskId] = useState<number | null>(null);
  const [cellDetailFocus, setCellDetailFocus] = useState<CellDetailFocus | null>(
    null,
  );
  const [highlightWo, setHighlightWo] = useState<string | null>(null);
  const [selectedConflictKey, setSelectedConflictKey] = useState<string | null>(
    null,
  );
  const boardRef = useRef<ScheduleBoardHandle>(null);
  const orderBoardRef = useRef<OrderScheduleBoardHandle>(null);
  const [boardLayout, setBoardLayout] = useState<"dispatch" | "order">(
    "dispatch",
  );
  const conflictPulseTimer = useRef<ReturnType<typeof setTimeout> | null>(
    null,
  );
  const [conflictPulse, setConflictPulse] = useState<ConflictCellPulse | null>(
    null,
  );
  const [boardFilterOrderNo, setBoardFilterOrderNo] = useState<string | null>(
    null,
  );
  const [lastTrace, setLastTrace] = useState<ScheduleTrace | null>(null);
  const [replayActive, setReplayActive] = useState(false);
  const [replayIndex, setReplayIndex] = useState(0);
  const [replayPlaying, setReplayPlaying] = useState(false);
  const [explainOnTrial, setExplainOnTrial] = useState(true);
  const [dbHint, setDbHint] = useState<string>("");
  const [mainView, setMainView] = useState<"board" | "bom" | "stock">("board");
  const [kitChecks, setKitChecks] = useState<KitCheck[]>([]);
  const [kitAllocations, setKitAllocations] = useState<KitAllocation[]>([]);
  const [kitDrawerOrder, setKitDrawerOrder] = useState<string | null>(null);
  const [bomOrder, setBomOrder] = useState<OrderRow | null>(null);
  const [orderPoolOpen, setOrderPoolOpen] = useState(true);
  const [baselineSnapshot, setBaselineSnapshot] = useState<ScheduleResult | null>(
    null,
  );
  const [sandboxOpen, setSandboxOpen] = useState(false);
  const [sandboxBaseline, setSandboxBaseline] = useState<ScheduleResult | null>(
    null,
  );
  const [sandboxProposed, setSandboxProposed] = useState<ScheduleResult | null>(
    null,
  );
  const [impactDiffSummary, setImpactDiffSummary] = useState("");
  const [impactDiffEntries, setImpactDiffEntries] = useState<
    { change_type: string; wo_no: string; message: string }[]
  >([]);
  const [impactOrders, setImpactOrders] = useState<OrderImpact[]>([]);
  const [impactHeadcount, setImpactHeadcount] = useState<HeadcountWarning[]>(
    [],
  );
  const [impactTriggerOrder, setImpactTriggerOrder] = useState<string | null>(
    null,
  );
  const [sandboxPreviewError, setSandboxPreviewError] = useState<string | null>(
    null,
  );
  const baselineRef = useRef<ScheduleResult | null>(null);
  const crewPreviewTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    baselineRef.current = baselineSnapshot;
  }, [baselineSnapshot]);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
  );

  const loadOrders = useCallback(async () => {
    const data = await fetchOrdersDetailed();
    setOrders(data.orders);
    setPendingSelected(new Set());
    const db = data.db_file ?? "";
    const n = data.orders_in_db ?? data.orders.length;
    setDbHint(db ? `库 ${n} 单 · ${db}` : `库 ${n} 单`);
  }, []);

  useEffect(() => {
    loadOrders().catch((e) => setError(String(e)));
  }, [loadOrders]);

  const poolOrderNos = useMemo(
    () =>
      orders
        .filter((o) => (o.schedule_phase ?? "PENDING") === "IN_SCHEDULING")
        .map((o) => o.order_no)
        .sort(),
    [orders],
  );

  const boardOrderNos = useMemo(() => {
    const s = new Set<string>();
    for (const o of orders) {
      const p = o.schedule_phase ?? "PENDING";
      if (p === "IN_SCHEDULING" || p === "IN_PRODUCTION") s.add(o.order_no);
    }
    return s;
  }, [orders]);

  const orderNos = poolOrderNos;

  const woNosForFilter = useMemo(() => {
    if (!boardFilterOrderNo || !result) return null;
    return new Set(
      result.wos
        .filter((w) => w.source_order_no === boardFilterOrderNo)
        .map((w) => w.wo_no),
    );
  }, [boardFilterOrderNo, result]);

  const displayTasks = useMemo(() => {
    let list = woNosForFilter
      ? tasks.filter((t) => woNosForFilter.has(t.wo_no))
      : tasks;
    if (replayActive && lastTrace) {
      const ids = revealedTaskIds(lastTrace.events, replayIndex);
      list = list.filter((t) => ids.has(t.task_id));
    }
    return list;
  }, [tasks, woNosForFilter, replayActive, lastTrace, replayIndex]);

  const replayEvent = replayActive && lastTrace ? lastTrace.events[replayIndex] : null;
  const replayPulse: ConflictCellPulse | null =
    replayEvent?.task_date && replayEvent.group_code
      ? {
          dept: replayEvent.dept ?? "FINISHED_DEPT",
          group: replayEvent.group_code,
          date: replayEvent.task_date,
          orderNo: replayEvent.order_no ?? undefined,
          level: "BLUE",
        }
      : null;

  const startReplay = useCallback((trace: ScheduleTrace | null | undefined) => {
    if (!trace?.events.length) {
      setError("本次排程没有讲解记录，请重新倒排或试排。");
      return;
    }
    setLastTrace(trace);
    setReplayActive(true);
    setReplayIndex(0);
    setReplayPlaying(true);
    setOrderPoolOpen(false);
  }, []);

  const endReplay = useCallback(() => {
    setReplayActive(false);
    setReplayPlaying(false);
  }, []);

  const openCellDetail = useCallback(
    (dept: DeptCode, group: GroupCode, date: string, focusTaskId?: number) => {
      setCellDetailFocus({
        dept,
        group,
        date,
        focusTaskId: focusTaskId ?? null,
      });
    },
    [],
  );

  const orderSalesByNo = useMemo(() => {
    const m = new Map<string, string>();
    for (const o of orders) {
      if (o.sales_name?.trim()) m.set(o.order_no, o.sales_name.trim());
    }
    return m;
  }, [orders]);

  const highlightOrderNo = highlightWo
    ? result?.wos.find((w) => w.wo_no === highlightWo)?.source_order_no ?? null
    : null;

  const kitByOrder = useMemo(() => {
    const m = new Map<string, KitCheck>();
    for (const k of kitChecks) m.set(k.order_no, k);
    return m;
  }, [kitChecks]);

  const kitDrawerCheck = useMemo(
    () => kitChecks.find((k) => k.order_no === kitDrawerOrder) ?? null,
    [kitChecks, kitDrawerOrder],
  );

  const displayConflicts = useMemo(() => {
    if (!boardFilterOrderNo || !result) return conflicts;
    const wos = new Set(
      result.wos
        .filter((w) => w.source_order_no === boardFilterOrderNo)
        .map((w) => w.wo_no),
    );
    return conflicts.filter((c) => c.wo_no && wos.has(c.wo_no));
  }, [conflicts, boardFilterOrderNo, result]);

  const applyResult = useCallback(
    async (data: { plan_version: number; result: ScheduleResult }) => {
      setPlanVersion(data.plan_version);
      if (data.plan_version > 0) {
        setOrderPoolOpen(false);
      }
      setResult(data.result);
      setBaselineSnapshot(data.result);
      setTasks(cloneTasks(data.result.tasks));
      setConflicts(data.result.conflicts);
      if (data.result.trace) setLastTrace(data.result.trace);
      if (data.result.kit_checks) {
        setKitChecks(data.result.kit_checks);
        setKitAllocations(data.result.kit_allocations ?? []);
      } else if (data.plan_version > 0) {
        const k = await fetchPlanKitStatus(data.plan_version);
        setKitChecks(k.kit_checks);
        setKitAllocations(k.kit_allocations);
      }
      if (data.plan_version > 0) {
        const c = await fetchConflicts(data.plan_version);
        setConflicts(c.conflicts);
      }
    },
    [],
  );

  const runOfficial = async () => {
    setBusy(true);
    setError(null);
    setPreviewMode(false);
    try {
      const data = await scheduleRun(orderNos, today);
      await applyResult(data);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const finishTrialUi = useCallback(
    (scheduleResult: ScheduleResult) => {
      const commits = commitmentsFromResult(scheduleResult, orderNos);
      setTrialCommitments(commits);
      const blocking = poolHasBlockingRed(scheduleResult, orderNos);
      const yellow = commits.some((c) => c.has_yellow_conflict);
      setTrialYellowNote(yellow && !blocking);
      if (blocking) setTrialConflictOpen(true);
      else setTrialSuccessOpen(true);
    },
    [orderNos],
  );

  const runWhatIf = async () => {
    if (orderNos.length === 0) {
      setError("排程中池为空，请先从「待排程」加入订单。");
      return;
    }
    setBusy(true);
    setError(null);
    setTrialSuccessOpen(false);
    setTrialConflictOpen(false);
    try {
      const data = await scheduleWhatIf(orderNos, today);
      setPreviewMode(true);
      setResult(data.result);
      setBaselineSnapshot(data.result);
      setTasks(cloneTasks(data.result.tasks));
      setConflicts(data.result.conflicts);
      if (data.result.trace) setLastTrace(data.result.trace);
      if (data.result.kit_checks) {
        setKitChecks(data.result.kit_checks);
        setKitAllocations(data.result.kit_allocations ?? []);
      }
      if (explainOnTrial && data.result.trace?.events.length) {
        startReplay(data.result.trace);
      } else {
        finishTrialUi(data.result);
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const runPublish = async () => {
    if (orderNos.length === 0) {
      setError("排程中池为空。");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const out = await publishSchedulingPool({ today, order_nos: orderNos });
      if (!out.published) {
        setResult(out.result);
        setBaselineSnapshot(out.result);
        setTasks(cloneTasks(out.result.tasks));
        setConflicts(out.result.conflicts);
        setTrialCommitments(out.commitments);
        setTrialConflictOpen(true);
        setPreviewMode(true);
        return;
      }
      setPreviewMode(false);
      setTrialSuccessOpen(false);
      setTrialConflictOpen(false);
      await applyResult({
        plan_version: out.plan_version,
        result: out.result,
      });
      await loadOrders();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const onAddToPool = async () => {
    const nos = [...pendingSelected];
    if (!nos.length) return;
    setBusy(true);
    setError(null);
    try {
      await updateSchedulingPool("add", nos);
      setPendingSelected(new Set());
      await loadOrders();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const onRemoveFromPool = async (orderNo: string) => {
    setBusy(true);
    setError(null);
    try {
      await updateSchedulingPool("remove", [orderNo]);
      await loadOrders();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const openSandboxForProposed = useCallback(
    (proposedTasks: WoTask[], triggerTaskId: number) => {
      const base = baselineRef.current;
      if (!base) {
        setError("请先点击「一键倒排」生成基准计划，再拖拽或改人数。");
        return false;
      }
      const triggerTask = proposedTasks.find((t) => t.task_id === triggerTaskId);
      setSandboxPreviewError(null);
      setImpactDiffSummary("");
      setImpactDiffEntries([]);
      setImpactOrders([]);
      setImpactHeadcount([]);
      setImpactTriggerOrder(
        triggerTask ? orderNoForTask(base, triggerTask) : null,
      );
      setSandboxBaseline(base);
      setSandboxProposed(mergeTasksIntoResult(base, proposedTasks));
      setSandboxOpen(true);
      setPreviewMode(true);
      return true;
    },
    [],
  );

  const runInteractiveAdjust = useCallback(
    async (proposedTasks: WoTask[], triggerTaskId: number) => {
      const base = baselineRef.current;
      if (!base) return;
      if (!openSandboxForProposed(proposedTasks, triggerTaskId)) return;
      setBusy(true);
      setError(null);
      try {
        const data = await interactivePreview({
          today,
          order_nos: orderNos,
          baseline_wos: base.wos,
          baseline_tasks: base.tasks,
          proposed_wos: base.wos,
          proposed_tasks: proposedTasks,
          trigger_task_id: triggerTaskId,
        });
        setTasks(cloneTasks(data.result.tasks));
        setResult({
          ...base,
          wos: data.result.wos,
          tasks: data.result.tasks,
        });
        setConflicts(data.conflicts);
        setImpactDiffSummary(data.diff.summary_text);
        setImpactDiffEntries(data.diff.entries);
        setImpactOrders(data.order_impacts);
        const cells = affectedCells(
          base.tasks,
          data.result.tasks,
          triggerTaskId,
        );
        setImpactHeadcount(
          filterHeadcountWarnings(
            data.headcount_warnings,
            cells,
            data.result.tasks,
          ),
        );
        setImpactTriggerOrder(data.trigger_order_no);
        setSandboxBaseline(data.baseline ?? base);
        setSandboxProposed(data.result);
        setSandboxOpen(true);
        setSandboxPreviewError(null);
      } catch (e) {
        const msg = String(e);
        setSandboxPreviewError(msg);
        setError(msg);
      } finally {
        setBusy(false);
      }
    },
    [openSandboxForProposed, orderNos, today],
  );

  const applyPlan = async () => {
    setBusy(true);
    setError(null);
    try {
      const data = await scheduleApply(orderNos, today);
      setPreviewMode(false);
      await applyResult(data);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const discardPreview = () => {
    setPreviewMode(false);
    if (planVersion > 0) {
      fetchPlan(planVersion)
        .then((data) => {
          setResult(data.result);
          setBaselineSnapshot(data.result);
          setTasks(cloneTasks(data.result.tasks));
          setConflicts(data.result.conflicts);
        })
        .catch((e) => setError(String(e)));
    } else {
      setResult(null);
      setBaselineSnapshot(null);
      setTasks([]);
      setConflicts([]);
    }
    setSandboxOpen(false);
    setSandboxBaseline(null);
    setSandboxProposed(null);
    setSandboxPreviewError(null);
  };

  const revertSandbox = () => {
    if (baselineSnapshot) {
      setTasks(cloneTasks(baselineSnapshot.tasks));
      setResult(baselineSnapshot);
      setConflicts(baselineSnapshot.conflicts);
    }
    setSandboxOpen(false);
    setSandboxBaseline(null);
    setSandboxProposed(null);
    setSandboxPreviewError(null);
  };

  const keepSandbox = () => {
    setSandboxOpen(false);
    setSandboxPreviewError(null);
  };

  const onReloadSeed = async () => {
    setBusy(true);
    setError(null);
    try {
      const r = await reloadDemoSeed();
      if (r.orders_in_db < 12) {
        throw new Error(
          `重导后仍只有 ${r.orders_in_db} 单（期望 12）。库：${r.db_file}。请确认已重启后端。`,
        );
      }
      setPlanVersion(0);
      setResult(null);
      setBaselineSnapshot(null);
      setTasks([]);
      setConflicts([]);
      setBoardFilterOrderNo(null);
      setOrderPoolOpen(true);
      await loadOrders();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const onDueChange = async (orderNo: string, due: string) => {
    setBusy(true);
    setError(null);
    try {
      await patchOrderDue(orderNo, due);
      setOrders((prev) =>
        prev.map((o) => (o.order_no === orderNo ? { ...o, due_date: due } : o)),
      );
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const onDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || !active.data.current?.task) return;
    const task = active.data.current.task as WoTask;
    const overId = String(over.id);
    const parts = overId.split("|");
    if (parts.length < 3) return;
    const [dept, group, date] = parts as [DeptCode, GroupCode, string];
    if (
      (task.dept ?? "FINISHED_DEPT") === dept &&
      task.group_code === group &&
      task.task_date === date
    ) {
      return;
    }
    const proposed = tasks.map((t) =>
      t.task_id === task.task_id
        ? { ...t, dept, group_code: group, task_date: date }
        : t,
    );
    setTasks(proposed);
    void runInteractiveAdjust(proposed, task.task_id);
  };

  const onCrewChange = (taskId: number, crew: number) => {
    setPreviewMode(true);
    const proposed = tasks.map((t) =>
      t.task_id === taskId ? { ...t, crew_plan: crew } : t,
    );
    setTasks(proposed);
    if (crewPreviewTimer.current) clearTimeout(crewPreviewTimer.current);
    crewPreviewTimer.current = setTimeout(() => {
      void runInteractiveAdjust(proposed, taskId);
    }, 450);
  };

  const onConflictPick = (c: Conflict, key: string) => {
    setSelectedConflictKey(key);
    setHighlightWo(c.wo_no);

    const target = resolveConflictCell(c, result);
    if (target) {
      if (conflictPulseTimer.current) {
        clearTimeout(conflictPulseTimer.current);
      }
      const orderNo =
        c.wo_no && result
          ? result.wos.find((w) => w.wo_no === c.wo_no)?.source_order_no
          : undefined;
      const pulse: ConflictCellPulse = {
        dept: target.dept,
        group: target.group,
        date: target.date,
        orderNo:
          boardLayout === "order" && orderNo ? orderNo : undefined,
        level: c.level,
      };
      setConflictPulse(null);
      requestAnimationFrame(() => {
        setConflictPulse(pulse);
        if (boardLayout === "order" && orderNo) {
          orderBoardRef.current?.scrollToOrderCell(orderNo, target.date);
        } else if (target.dept && target.group) {
          boardRef.current?.scrollToCell(
            target.dept,
            target.group,
            target.date,
          );
        }
      });
      conflictPulseTimer.current = setTimeout(() => {
        setConflictPulse(null);
        conflictPulseTimer.current = null;
      }, 3400);
      setSelectedTaskId(target.focusTaskId);
      return;
    }

    if (c.task_id) setSelectedTaskId(c.task_id);
  };

  return (
    <div className="min-h-screen flex flex-col bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 bg-slate-900 px-4 py-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-lg font-semibold tracking-tight">
              斯芬克斯 · 排产看板
            </h1>
            <p className="text-xs text-slate-500">
              演示基准日 {today}
              {planVersion > 0 && (
                <span className="ml-2 text-slate-400">
                  计划版本 v{planVersion}
                </span>
              )}
              {previewMode && (
                <span className="ml-2 text-amber-400">试排 / 本地调整预览</span>
              )}
              {boardFilterOrderNo && (
                <span className="ml-2 text-sky-400">
                  看板筛选 {boardFilterOrderNo}
                </span>
              )}
              {planVersion === 0 && (
                <span className="ml-2 text-slate-500">
                  请点击「一键倒排」生成看板任务
                </span>
              )}
              {dbHint && (
                <span className="mt-1 block text-[10px] text-slate-600 truncate max-w-xl">
                  {dbHint}
                </span>
              )}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => setMainView("board")}
              className={`rounded px-3 py-1.5 text-sm ${
                mainView === "board"
                  ? "bg-slate-700 text-white"
                  : "border border-slate-600 text-slate-400 hover:bg-slate-800"
              }`}
            >
              排产看板
            </button>
            <button
              type="button"
              onClick={() => setMainView("bom")}
              className={`rounded px-3 py-1.5 text-sm ${
                mainView === "bom"
                  ? "bg-violet-800 text-white"
                  : "border border-violet-800/50 text-violet-300 hover:bg-violet-950"
              }`}
            >
              工艺 / BOM
            </button>
            <button
              type="button"
              onClick={() => setMainView("stock")}
              className={`rounded px-3 py-1.5 text-sm ${
                mainView === "stock"
                  ? "bg-emerald-800 text-white"
                  : "border border-emerald-800/50 text-emerald-300 hover:bg-emerald-950"
              }`}
            >
              库存中心
            </button>
            {mainView === "board" && !orderPoolOpen && (
              <button
                type="button"
                onClick={() => setOrderPoolOpen(true)}
                className="rounded border border-slate-600 px-3 py-1.5 text-sm text-slate-200 hover:bg-slate-800"
              >
                订单池 · 排程中 {poolOrderNos.length}
                {boardFilterOrderNo && (
                  <span className="ml-1 text-sky-400">· {boardFilterOrderNo}</span>
                )}
              </button>
            )}
            {mainView === "board" && (
              <>
            <span className="inline-flex rounded border border-slate-600 p-0.5 text-xs">
              <button
                type="button"
                onClick={() => setBoardLayout("dispatch")}
                className={`rounded px-2 py-1 ${
                  boardLayout === "dispatch"
                    ? "bg-slate-700 text-slate-100"
                    : "text-slate-500 hover:text-slate-300"
                }`}
              >
                派工视图
              </button>
              <button
                type="button"
                onClick={() => setBoardLayout("order")}
                className={`rounded px-2 py-1 ${
                  boardLayout === "order"
                    ? "bg-slate-700 text-slate-100"
                    : "text-slate-500 hover:text-slate-300"
                }`}
              >
                订单视图
              </button>
            </span>
            <button
              type="button"
              disabled={busy || orderNos.length === 0}
              onClick={runOfficial}
              className="rounded bg-emerald-600 px-3 py-1.5 text-sm font-medium hover:bg-emerald-500 disabled:opacity-40"
              title="整池正式倒排并落库（不改变 Tab 阶段）"
            >
              一键倒排
            </button>
            <button
              type="button"
              disabled={busy || orderNos.length === 0}
              onClick={runWhatIf}
              className="rounded border border-slate-600 px-3 py-1.5 text-sm hover:bg-slate-800 disabled:opacity-40"
            >
              试排
            </button>
            <label className="flex items-center gap-1 text-[11px] text-slate-400">
              <input
                type="checkbox"
                checked={explainOnTrial}
                onChange={(e) => setExplainOnTrial(e.target.checked)}
              />
              试排后讲解回放
            </label>
            <button
              type="button"
              disabled={busy || !lastTrace?.events.length}
              onClick={() => startReplay(lastTrace)}
              className="rounded border border-violet-700 px-3 py-1.5 text-sm text-violet-200 hover:bg-violet-950 disabled:opacity-40"
              title="算完再放慢演示，不重新计算"
            >
              回放刚才的倒排
            </button>
            <button
              type="button"
              disabled={busy || orderNos.length === 0}
              onClick={runPublish}
              className="rounded border border-sky-600 px-3 py-1.5 text-sm text-sky-300 hover:bg-sky-950 disabled:opacity-40"
            >
              保存发布
            </button>
            <button
              type="button"
              disabled={busy || orderNos.length === 0}
              onClick={applyPlan}
              className="rounded border border-slate-600 px-3 py-1.5 text-sm text-slate-400 hover:bg-slate-800 disabled:opacity-40"
              title="试排预览落库（不发布到生产中）"
            >
              应用试排
            </button>
            {previewMode && (
              <button
                type="button"
                disabled={busy}
                onClick={discardPreview}
                className="rounded border border-slate-600 px-3 py-1.5 text-sm text-slate-400 hover:bg-slate-800"
              >
                丢弃预览
              </button>
            )}
              </>
            )}
          </div>
        </div>
        {error && (
          <p className="mt-2 text-xs text-rose-400" role="alert">
            {error}
          </p>
        )}
      </header>

      {mainView === "bom" ? (
        <BomExplorerPage />
      ) : mainView === "stock" ? (
        <StockCenterPage planAllocations={kitAllocations} />
      ) : (
      <div className="flex flex-1 flex-col lg:flex-row gap-2 p-3 min-h-0">
        <OrderPoolSidebar
          open={orderPoolOpen}
          onOpenChange={setOrderPoolOpen}
          orders={orders}
          pendingSelected={pendingSelected}
          busy={busy}
          today={today}
          boardFilterOrderNo={boardFilterOrderNo}
          onBoardFilter={setBoardFilterOrderNo}
          onReloadSeed={onReloadSeed}
          onShowBom={setBomOrder}
          onShowKit={setKitDrawerOrder}
          kitByOrder={kitByOrder}
          poolCount={poolOrderNos.length}
          onSelectAllPending={() =>
            setPendingSelected(
              new Set(
                orders
                  .filter((o) => (o.schedule_phase ?? "PENDING") === "PENDING")
                  .map((o) => o.order_no),
              ),
            )
          }
          onClearPending={() => setPendingSelected(new Set())}
          onTogglePending={(no) =>
            setPendingSelected((prev) => {
              const next = new Set(prev);
              if (next.has(no)) next.delete(no);
              else next.add(no);
              return next;
            })
          }
          onAddToPool={() => void onAddToPool()}
          onRemoveFromPool={(no) => void onRemoveFromPool(no)}
          onTrialPool={() => void runWhatIf()}
          onPublishPool={() => void runPublish()}
          onDueChange={onDueChange}
        />

        <div className="flex flex-1 flex-col lg:flex-row gap-3 min-w-0 min-h-0">
          <main className="flex flex-1 min-w-0 min-h-0 flex-col gap-3">
            {replayActive && lastTrace && (
              <NarrationBar
                trace={lastTrace}
                index={replayIndex}
                playing={replayPlaying}
                salesByOrder={orderSalesByNo}
                onIndex={setReplayIndex}
                onPlaying={setReplayPlaying}
                onClose={endReplay}
              />
            )}
            {boardLayout === "dispatch" ? (
              <DndContext sensors={sensors} onDragEnd={onDragEnd}>
                <div className="flex min-h-0 flex-1 flex-col">
                  <ScheduleBoard
                    ref={boardRef}
                    today={today}
                    result={result}
                    tasks={displayTasks}
                    conflicts={displayConflicts}
                    selectedTaskId={selectedTaskId}
                    onSelectTask={setSelectedTaskId}
                    onOpenCellDetail={openCellDetail}
                    onCrewChange={onCrewChange}
                    conflictPulse={replayActive ? replayPulse : conflictPulse}
                  />
                </div>
              </DndContext>
            ) : (
              <div className="flex min-h-0 flex-1 flex-col">
                <OrderScheduleBoard
                  ref={orderBoardRef}
                  today={today}
                  orders={orders}
                  selectedOrderNos={boardOrderNos}
                  boardFilterOrderNo={boardFilterOrderNo}
                  result={result}
                  tasks={displayTasks}
                  conflicts={displayConflicts}
                  selectedTaskId={selectedTaskId}
                  onSelectTask={setSelectedTaskId}
                  onOpenCellDetail={openCellDetail}
                  onCrewChange={onCrewChange}
                  conflictPulse={replayActive ? replayPulse : conflictPulse}
                />
              </div>
            )}
            {highlightWo && (
              <p className="text-xs text-slate-500">
                已定位工单 <span className="text-sky-400">{highlightWo}</span>
                {highlightOrderNo && (
                  <span>
                    {" · "}
                    {highlightOrderNo}
                    {orderSalesByNo.get(highlightOrderNo)
                      ? ` · 销售 ${orderSalesByNo.get(highlightOrderNo)}`
                      : ""}
                  </span>
                )}
              </p>
            )}
          </main>

          <div className="lg:w-80 shrink-0 min-h-[200px] lg:min-h-0">
            <ConflictPanel
              conflicts={displayConflicts}
              orders={orders}
              wos={result?.wos ?? []}
              tasks={tasks}
              selectedKey={selectedConflictKey}
              onPick={onConflictPick}
            />
          </div>
        </div>
      </div>
      )}

      <CellDetailDrawer
        focus={cellDetailFocus}
        today={today}
        planVersion={planVersion}
        result={result}
        liveTasks={tasks}
        orderSalesByNo={orderSalesByNo}
        onClose={() => setCellDetailFocus(null)}
      />

      <KitDetailDrawer
        check={kitDrawerCheck}
        onClose={() => setKitDrawerOrder(null)}
      />

      <OrderBomDrawer
        order={bomOrder}
        today={today}
        result={result}
        onClose={() => setBomOrder(null)}
      />

      <TrialSuccessModal
        open={trialSuccessOpen}
        commitments={trialCommitments}
        yellowNote={trialYellowNote}
        busy={busy}
        onClose={() => setTrialSuccessOpen(false)}
        onPublish={() => void runPublish()}
      />
      <TrialConflictModal
        open={trialConflictOpen}
        conflicts={conflicts}
        commitments={trialCommitments}
        salesByOrder={orderSalesByNo}
        onClose={() => setTrialConflictOpen(false)}
        onAdjust={() => {
          setTrialConflictOpen(false);
          setOrderPoolOpen(false);
        }}
      />

      <SandboxCompareView
        open={sandboxOpen}
        busy={busy}
        triggerOrderNo={impactTriggerOrder}
        baseline={sandboxBaseline}
        proposed={sandboxProposed}
        diffSummary={impactDiffSummary}
        diffEntries={impactDiffEntries}
        orderImpacts={impactOrders}
        headcountWarnings={impactHeadcount}
        previewError={sandboxPreviewError}
        onRevert={revertSandbox}
        onKeep={keepSandbox}
      />
    </div>
  );
}
export default ScheduleWorkspace;
