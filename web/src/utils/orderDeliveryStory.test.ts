import { describe, expect, it } from "vitest";
import type { OrderRow, ScheduleResult, Wo, WoTask } from "../types/schedule";
import {
  buildOrderDeliveryStories,
  classifyOrderFeasibility,
} from "./orderDeliveryStory";
import { headerOrderNo } from "./coline";

function order(partial: Partial<OrderRow> & Pick<OrderRow, "order_no">): OrderRow {
  return {
    customer: "测",
    sales_name: "",
    item_code: "X",
    qty_order: 1,
    unit: "版",
    due_date: "2026-09-30",
    ready_date: null,
    customer_level: 1,
    amount: 0,
    is_urgent: false,
    ...partial,
  };
}

function wo(partial: Partial<Wo> & Pick<Wo, "wo_no" | "source_order_no">): Wo {
  return {
    wo_type: "FINISHED",
    item_code: "P1",
    group_code: "MOLD",
    qty_board_plan: 100,
    due_date: "2026-09-30",
    plan_start: "2026-09-20",
    plan_end: "2026-09-25",
    crew_plan: 1,
    is_locked: false,
    parent_wo_no: null,
    ...partial,
  };
}

const tasks002: WoTask[] = [
  {
    task_id: 1,
    wo_no: "WO-S2",
    dept: "SEMI_DEPT",
    group_code: "MOLD",
    task_date: "2026-09-18",
    qty_board: 50,
    hours_wall: 8,
    hours_man: 8,
    crew_plan: 1,
  },
  {
    task_id: 2,
    wo_no: "WO-P2",
    dept: "FINISHED_DEPT",
    group_code: "MOLD",
    task_date: "2026-09-22",
    qty_board: 50,
    hours_wall: 8,
    hours_man: 8,
    crew_plan: 1,
  },
];

const result002: ScheduleResult = {
  wos: [
    wo({
      wo_no: "WO-S2",
      wo_type: "SEMI",
      source_order_no: "SO-002",
      item_code: "S2",
      plan_start: "2026-09-18",
      plan_end: "2026-09-18",
    }),
    wo({
      wo_no: "WO-P2",
      source_order_no: "SO-002",
      item_code: "P2",
      plan_start: "2026-09-22",
      plan_end: "2026-09-25",
    }),
  ],
  tasks: tasks002,
  dependencies: [{ pred_wo_no: "WO-S2", succ_wo_no: "WO-P2" }],
  conflicts: [],
};

describe("classifyOrderFeasibility", () => {
  it("SO-002 is feasible when plan ends on or before due", () => {
    const o = order({ order_no: "SO-002", due_date: "2026-09-30" });
    expect(classifyOrderFeasibility(o, result002, [])).toBe("feasible");
  });

  it("SO-004 is late on E2 RED on finished WO", () => {
    const o = order({ order_no: "SO-004", due_date: "2026-09-23" });
    const res: ScheduleResult = {
      wos: [
        wo({
          wo_no: "WO-F4",
          source_order_no: "SO-004",
          plan_end: "2026-09-28",
        }),
      ],
      tasks: [],
      dependencies: [],
      conflicts: [
        {
          code: "E2",
          level: "RED",
          wo_no: "WO-F4",
          task_id: null,
          message: "交期不可行",
          suggest: "EARLIEST:2026-09-29",
        },
      ],
    };
    expect(classifyOrderFeasibility(o, res, res.conflicts)).toBe("late");
  });

  it("marks unscheduled when no WO for header", () => {
    const o = order({ order_no: "SO-999" });
    expect(classifyOrderFeasibility(o, result002, [])).toBe("unscheduled");
  });
});

describe("buildOrderDeliveryStories", () => {
  it("SO-002: feasible tab, SEMI before FINISHED", () => {
    const orders = [order({ order_no: "SO-002", due_date: "2026-09-30" })];
    const sel = new Set(["SO-002"]);
    const { feasible, late } = buildOrderDeliveryStories(
      orders,
      sel,
      result002,
      tasks002,
      [],
    );
    expect(late).toHaveLength(0);
    expect(feasible).toHaveLength(1);
    expect(feasible[0].nodes.map((n) => n.woNo)).toEqual(["WO-S2", "WO-P2"]);
  });

  it("SO-303: three SEMI then FINISHED in dependency order", () => {
    const orders = [order({ order_no: "SO-303", due_date: "2026-10-15" })];
    const w303: Wo[] = [
      wo({
        wo_no: "WO-S3A",
        wo_type: "SEMI",
        source_order_no: "SO-303",
        item_code: "SA",
        plan_start: "2026-09-10",
        plan_end: "2026-09-12",
      }),
      wo({
        wo_no: "WO-S3B",
        wo_type: "SEMI",
        source_order_no: "SO-303",
        item_code: "SB",
        plan_start: "2026-09-11",
        plan_end: "2026-09-13",
      }),
      wo({
        wo_no: "WO-S3C",
        wo_type: "SEMI",
        source_order_no: "SO-303",
        item_code: "SC",
        plan_start: "2026-09-12",
        plan_end: "2026-09-14",
      }),
      wo({
        wo_no: "WO-F303",
        source_order_no: "SO-303",
        item_code: "PF",
        plan_start: "2026-09-20",
        plan_end: "2026-09-25",
      }),
    ];
    const deps = [
      { pred_wo_no: "WO-S3A", succ_wo_no: "WO-F303" },
      { pred_wo_no: "WO-S3B", succ_wo_no: "WO-F303" },
      { pred_wo_no: "WO-S3C", succ_wo_no: "WO-F303" },
    ];
    const res: ScheduleResult = {
      wos: w303,
      tasks: [],
      dependencies: deps,
      conflicts: [],
    };
    const { feasible } = buildOrderDeliveryStories(
      orders,
      new Set(["SO-303"]),
      res,
      [],
      [],
    );
    expect(feasible[0].nodes.map((n) => n.woNo)).toEqual([
      "WO-S3A",
      "WO-S3B",
      "WO-S3C",
      "WO-F303",
    ]);
  });

  it("merges expanded lines under one header card", () => {
    expect(headerOrderNo("SO-S001#L1")).toBe("SO-S001");
    const orders = [
      order({ order_no: "SO-S001", due_date: "2026-09-30" }),
      order({ order_no: "SO-S001#L1", due_date: "2026-09-30", item_code: "L1" }),
    ];
    const res: ScheduleResult = {
      wos: [
        wo({ wo_no: "WO-L1", source_order_no: "SO-S001#L1", item_code: "L1" }),
        wo({ wo_no: "WO-H", source_order_no: "SO-S001", item_code: "H" }),
      ],
      tasks: [],
      dependencies: [],
      conflicts: [],
    };
    const buckets = buildOrderDeliveryStories(
      orders,
      new Set(["SO-S001", "SO-S001#L1"]),
      res,
      [],
      [],
    );
    expect(buckets.feasible).toHaveLength(1);
    expect(buckets.feasible[0].headerOrderNo).toBe("SO-S001");
    expect(buckets.feasible[0].nodes).toHaveLength(2);
  });
});
