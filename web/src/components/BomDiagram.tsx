import type { BomComponentLine, BomDesign, BomExplode, BomNode } from "../types/bom";
import type { ScheduleResult, Wo } from "../types/schedule";
import { groupAccent } from "../utils/groupStyle";
import { formatSphLine, formatUomChainLine, uomLabel } from "../utils/uomLabels";

type Props = {
  design: BomDesign;
  explode?: BomExplode | null;
  instanceWos?: Wo[];
  compact?: boolean;
};

type NodeKind = "semi" | "purchased" | "finished";

function kindOfLine(role: string): Exclude<NodeKind, "finished"> {
  return role === "PURCHASED" ? "purchased" : "semi";
}

function edgeCaption(line: BomComponentLine): string {
  const qty = `${line.qty_per_parent}${uomLabel(line.qty_basis_uom)}/盒`;
  if (line.role === "PURCHASED") {
    return line.lead_time_days
      ? `${qty} · 提前 ${line.lead_time_days} 天`
      : `${qty} · 齐套`;
  }
  if (line.lead_time_days != null) {
    return `${qty} · 提前 ${line.lead_time_days} 天`;
  }
  return qty;
}

function routeChildLines(design: BomDesign): BomComponentLine[] {
  const listed = [...(design.components ?? [])].sort((a, b) => a.line_no - b.line_no);
  if (listed.length > 0) return listed;
  if (design.semi && design.edge) {
    return [
      {
        line_no: 1,
        role: "SEMI",
        node: design.semi,
        qty_per_parent: design.edge.semi_board_per_box ?? 0,
        qty_basis_uom: "BOARD",
        lead_time_days: design.edge.lead_time_days,
      },
    ];
  }
  return [];
}

function NodeCard({
  node,
  kind,
  compact,
}: {
  node: BomNode;
  kind: NodeKind;
  compact?: boolean;
}) {
  const purchased = kind === "purchased";
  const style = purchased
    ? {
        border: "border-dashed border-slate-500",
        bg: "bg-slate-900",
        badge: "bg-slate-700 text-slate-200",
      }
    : groupAccent(node.group_code);
  const role =
    kind === "semi" ? "半成品" : kind === "purchased" ? "外购 · 齐套" : "成品";
  const lowConf = !purchased && node.sph?.confidence === "LOW";
  return (
    <div
      className={`rounded-lg border-2 p-3 ${style.border} ${style.bg} ${
        lowConf ? "border-dashed" : ""
      } ${compact ? "p-2 text-[11px]" : "text-xs"}`}
    >
      <div className="flex flex-wrap items-center gap-1.5">
        <span className={`rounded px-1.5 py-0.5 text-[10px] ${style.badge}`}>
          {purchased ? "外购件" : node.group_label}
        </span>
        <span className="text-slate-500">{role}</span>
        {lowConf && (
          <span className="text-amber-400" title="标准产能未校准，结果仅供参考">
            ❓
          </span>
        )}
      </div>
      <p className={`mt-1 font-semibold text-slate-100 ${compact ? "text-xs" : ""}`}>
        {node.item_code}
        <span className="ml-1 font-normal text-slate-400">{node.item_name}</span>
      </p>
      {purchased ? (
        <p className="mt-1 text-slate-500">不生成工单 · 只参与齐套占库</p>
      ) : (
        <p className="mt-1 text-slate-500">
          色 {node.color} · 损耗 {(node.loss_rate * 100).toFixed(0)}%
        </p>
      )}
      <ul className="mt-1 space-y-0.5 text-slate-400">
        {node.uom_chain.map((line) => (
          <li key={line}>{formatUomChainLine(line)}</li>
        ))}
      </ul>
      {!purchased && node.sph && (
        <p className="mt-1.5 text-slate-300">{formatSphLine(node.sph)}</p>
      )}
      {node.stock_board != null && (
        <p className="mt-1 text-violet-300/90">库存 {node.stock_board} 版</p>
      )}
    </div>
  );
}

function ExplodeSection({ explode }: { explode: BomExplode }) {
  if (!explode.computable && explode.message) {
    return <p className="text-xs text-rose-400">{explode.message}</p>;
  }
  if (!explode.computable || !explode.steps) return null;
  const hasLines = Boolean(explode.line_details?.length);
  /** 多行 BOM 时 steps 仅保留换算+成品版；行明细用 line_details，避免与 steps 重复 */
  const headSteps = hasLines ? explode.steps.slice(0, 2) : explode.steps;
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-950 p-3 text-xs">
      <p className="font-medium text-slate-200">
        数量展开 · {explode.qty_order}
        {explode.unit_label ?? uomLabel(explode.unit)}
      </p>
      <p className="mt-0.5 text-[10px] text-slate-500">
        先按订货单位换算到「版」，再算损耗与半成品（与倒排引擎一致）
      </p>
      <ol className="mt-2 list-decimal space-y-1 pl-4 text-slate-400">
        {headSteps.map((s) => (
          <li key={s}>{s}</li>
        ))}
      </ol>
      {hasLines ? (
        <ul className="mt-2 space-y-1 border-t border-slate-800 pt-2 text-[11px] text-slate-400">
          <li className="text-[10px] text-slate-500">BOM 行展开</li>
          {explode.line_details!.map((ln) => (
            <li key={ln.line_no}>
              <span className="text-slate-500">行{ln.line_no}</span>{" "}
              {ln.component_item_code}{" "}
              <span className="text-slate-600">
                ({ln.role === "SEMI" ? "半成品" : "外购"})
              </span>
              · 毛 {ln.gross_board} 版 · 占库 {ln.from_stock}
              {ln.role === "SEMI" ? (
                <span
                  className={
                    ln.net_board > 0 ? " text-violet-300" : " text-emerald-400"
                  }
                >
                  {" "}
                  · 净工单 {ln.net_board} 版
                </span>
              ) : ln.shortage_board > 0 ? (
                <span className=" text-amber-400"> · 缺 {ln.shortage_board} 版</span>
              ) : (
                <span className=" text-emerald-400"> · 齐套</span>
              )}
            </li>
          ))}
        </ul>
      ) : (
        explode.semi && (
          <p
            className={`mt-2 font-medium ${
              explode.semi.generates_semi_wo ? "text-violet-300" : "text-emerald-400"
            }`}
          >
            {explode.semi.generates_semi_wo
              ? `将生成半成品工单 ${explode.semi.net_board} 版`
              : "库存已覆盖，不生成半成品工单"}
          </p>
        )
      )}
    </div>
  );
}

function FanInConnectors({
  lines,
  compact,
}: {
  lines: BomComponentLine[];
  compact?: boolean;
}) {
  const n = lines.length;
  const vbH = n * 100;
  const mid = vbH / 2;
  return (
    <div className="relative hidden min-h-full w-36 shrink-0 lg:block xl:w-44">
      <svg
        className="absolute inset-0 h-full w-full text-slate-500"
        viewBox={`0 0 100 ${vbH}`}
        preserveAspectRatio="none"
        aria-hidden
      >
        {lines.map((_, i) => {
          const y = (i + 0.5) * 100;
          return (
            <path
              key={i}
              d={`M 0 ${y} C 42 ${y} 48 ${mid} 86 ${mid}`}
              fill="none"
              stroke="currentColor"
              strokeWidth="1.4"
              vectorEffect="non-scaling-stroke"
            />
          );
        })}
      </svg>
      <div className="absolute inset-0 flex flex-col">
        {lines.map((line) => (
          <div key={line.line_no} className="flex flex-1 items-center">
            <span
              className={`max-w-[6.5rem] rounded border border-slate-700 bg-slate-800 px-1 py-0.5 leading-tight text-slate-300 ${
                compact ? "text-[8px]" : "text-[9px]"
              }`}
            >
              {edgeCaption(line)}
            </span>
          </div>
        ))}
      </div>
      <span
        className="absolute right-0 top-1/2 -translate-y-1/2 text-xl text-slate-400"
        aria-hidden
      >
        →
      </span>
    </div>
  );
}

function FanInRoute({
  lines,
  finished,
  changeoverMin,
  compact,
}: {
  lines: BomComponentLine[];
  finished: BomNode;
  changeoverMin?: number;
  compact?: boolean;
}) {
  return (
    <div
      className="flex flex-col gap-3 lg:flex-row lg:items-stretch"
      role="img"
      aria-label={`${lines.length} 个子件汇入成品 ${finished.item_code}`}
    >
      <div className="flex flex-1 flex-col gap-2">
        {lines.map((line) => (
          <div key={line.line_no}>
            <NodeCard
              node={line.node}
              kind={kindOfLine(line.role)}
              compact={compact}
            />
            <p
              className={`mt-0.5 text-slate-500 lg:hidden ${
                compact ? "text-[9px]" : "text-[10px]"
              }`}
            >
              行{line.line_no} · {edgeCaption(line)} ↓
            </p>
          </div>
        ))}
      </div>
      <FanInConnectors lines={lines} compact={compact} />
      <div className="flex flex-1 flex-col justify-center">
        <p className="mb-1 text-center text-[11px] text-slate-400 lg:hidden">
          ↓ 汇入成品
        </p>
        <NodeCard node={finished} kind="finished" compact={compact} />
        {changeoverMin != null && (
          <p className={`mt-1 text-slate-500 ${compact ? "text-[9px]" : "text-[10px]"}`}>
            换线 {changeoverMin} 分钟
          </p>
        )}
      </div>
    </div>
  );
}

function RouteSection({
  design,
  compact,
}: {
  design: BomDesign;
  compact?: boolean;
}) {
  const lines = routeChildLines(design);
  const childCount = lines.length;

  return (
    <div>
      <p
        className={`mb-2 font-medium text-slate-400 ${
          compact ? "text-[10px]" : "text-xs"
        }`}
      >
        工艺路线 · 设计态
        {childCount > 0 ? (
          <span className="ml-1 text-sky-400/90">
            · {childCount} 个子件 → {design.finished.item_code}
          </span>
        ) : (
          <span className="ml-1 text-slate-500">· 单层成品</span>
        )}
      </p>
      {childCount > 0 ? (
        <>
          <FanInRoute
            lines={lines}
            finished={design.finished}
            changeoverMin={design.edge?.changeover_min}
            compact={compact}
          />
          <p className={`mt-2 text-slate-500 ${compact ? "text-[9px]" : "text-[10px]"}`}>
            倒排：各子件就绪（半成品完工 + 提前期，外购齐套）取最晚 → 成品可开工
          </p>
        </>
      ) : (
        <div className="max-w-md">
          <NodeCard node={design.finished} kind="finished" compact={compact} />
          {design.edge && (
            <p className="mt-2 text-[11px] text-slate-500">{design.edge.label}</p>
          )}
        </div>
      )}
    </div>
  );
}

function InstanceStrip({ wos }: { wos: Wo[] }) {
  if (wos.length === 0) return null;
  return (
    <div className="mt-3 rounded border border-slate-700 bg-slate-950 p-2 text-[11px]">
      <p className="font-medium text-slate-300">排产实例（工单）</p>
      <ul className="mt-1 space-y-1">
        {wos.map((w) => (
          <li key={w.wo_no} className="text-slate-400">
            <span className={w.wo_type === "SEMI" ? "text-violet-300" : "text-sky-300"}>
              {w.wo_no}
            </span>
            {" · "}
            {w.item_code} {w.qty_board_plan} 版
            {w.plan_start && w.plan_end && (
              <span className="text-slate-500">
                {" "}
                · {w.plan_start} → {w.plan_end}
              </span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function BomDiagram({ design, explode, instanceWos, compact }: Props) {
  return (
    <div className={compact ? "space-y-2" : "space-y-4"}>
      {design.routing_note ? (
        <p className="text-[11px] leading-relaxed text-slate-500">{design.routing_note}</p>
      ) : null}
      {explode && <ExplodeSection explode={explode} />}
      <RouteSection design={design} compact={compact} />
      {instanceWos && <InstanceStrip wos={instanceWos} />}
    </div>
  );
}

export function wosForOrder(result: ScheduleResult | null, orderNo: string): Wo[] {
  if (!result) return [];
  return result.wos
    .filter((w) => w.source_order_no === orderNo)
    .sort((a, b) => {
      if (a.wo_type === b.wo_type) return a.wo_no.localeCompare(b.wo_no);
      return a.wo_type === "SEMI" ? -1 : 1;
    });
}
