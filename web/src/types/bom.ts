export type BomSph = {
  sph_value: number;
  sph_basis: string;
  sph_uom: string;
  crew_std: number;
  confidence: string;
  source: string;
  label: string;
};

export type BomNode = {
  item_code: string;
  item_name: string;
  is_semi: boolean;
  group_code: string;
  group_label: string;
  color: string;
  loss_rate: number;
  computable: boolean;
  uom_chain: string[];
  sph: BomSph | null;
  stock_board: number | null;
};

export type BomEdge = {
  semi_board_per_box: number | null;
  lead_time_days: number;
  dep_type: string;
  changeover_min: number;
  label: string;
};

export type BomComponentLine = {
  line_no: number;
  role: string;
  node: BomNode;
  qty_per_parent: number;
  qty_basis_uom: string;
  lead_time_days?: number;
};

export type BomDesign = {
  item_code: string;
  pattern: "SINGLE_LAYER" | "TWO_LAYER" | "MULTI_BOM";
  finished: BomNode;
  semi: BomNode | null;
  edge: BomEdge | null;
  components?: BomComponentLine[];
};

export type BomExplode = {
  item_code: string;
  computable: boolean;
  message?: string;
  qty_order?: number;
  unit?: string;
  unit_label?: string;
  qty_board_before_loss?: number;
  finished_plan_board?: number;
  semi?: {
    semi_item_code: string;
    gross_board: number;
    stock_available: number;
    net_board: number;
    generates_semi_wo: boolean;
  } | null;
  steps?: string[];
  line_details?: {
    line_no: number;
    component_item_code: string;
    role: string;
    gross_board: number;
    from_stock: number;
    net_board: number;
    shortage_board: number;
  }[];
};

export type BomCatalog = {
  seed_version?: string;
  today?: string;
  catalog: {
    key: string;
    desc: string;
    items: { item_code: string; item_name: string }[];
    semi_items: { item_code: string; item_name: string }[];
  }[];
  items: {
    item_code: string;
    item_name: string;
    group_code: string;
    group_label: string;
    needs_semi: boolean;
  }[];
};
