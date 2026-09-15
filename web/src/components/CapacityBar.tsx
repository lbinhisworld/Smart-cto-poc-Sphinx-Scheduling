/** 组×日墙钟产能条（与派工视图单元格底栏一致） */
export function CapacityBar({
  utilization,
  warnings = [],
}: {
  utilization: number;
  warnings?: string[];
}) {
  const overCap = utilization > 1 || warnings.length > 0;
  return (
    <div
      className={`mt-1 h-1 rounded-full overflow-hidden bg-slate-800 ${
        overCap ? "ring-1 ring-rose-500" : ""
      }`}
      title={
        warnings.length
          ? warnings.join("；")
          : `产能 ${Math.round(utilization * 100)}%`
      }
    >
      <div
        className={`h-full ${overCap ? "bg-rose-500" : "bg-emerald-600"}`}
        style={{ width: `${Math.min(100, utilization * 100)}%` }}
      />
    </div>
  );
}
