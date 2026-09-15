export type KitLine = {
  line_no: number;
  component_item_code: string;
  component_role: string;
  gross_board: number;
  from_stock: number;
  net_wo_board: number;
  shortage_board: number;
  ready_date?: string | null;
};

export type KitCheck = {
  order_no: string;
  finished_wo_no: string;
  kit_ready_date: string | null;
  is_kitted: boolean;
  finished_plan_start: string | null;
  lines: KitLine[];
};

export type KitAllocation = {
  order_no: string;
  component_item_code: string;
  qty_board: number;
  line_no?: number | null;
};
