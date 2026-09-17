import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { requestWithRole } from "../../api/client";
import { useAuth } from "../../shell/auth";

const ANCHOR_FROM = "2026-09-01";
const ANCHOR_TO = "2026-09-30";

type Cell = {
  qty_plan: number | null;
  qty_actual: number | null;
  box_kg: number | null;
  missing_kg: boolean;
};

type DetailData = {
  dates: string[];
  caliber: string;
  groups: {
    group_code: string;
    group_label: string;
    categories: {
      category: string;
      units: { display_uom: string; display_uom_label: string; cells: Record<string, Cell> }[];
    }[];
  }[];
};

type DailyDay = {
  box_kg: number | null;
  inbound_box_kg: number | null;
  variance_box_kg: number | null;
  issues: Record<string, number>;
  headcount: number | null;
  hours_normal: number | null;
  hours_ot: number | null;
  hours_direct: number | null;
  hours_indirect: number | null;
  hours_total: number | null;
  by_uom: Record<string, number | null>;
  box_per_hour: number | null;
  missing_kg: boolean;
};

type DailyData = {
  dates: string[];
  days: Record<string, DailyDay>;
  period: { box_kg: number | null; hours_direct: number | null; box_per_hour: number | null };
  caliber: string;
};

type EffData = DailyData & {
  groups: {
    group_code: string;
    group_label: string;
    box_kg: number | null;
    hours_direct: number | null;
    box_per_hour: number | null;
  }[];
};

const ISSUE_LABEL: Record<string, string> = {
  INTERNAL: "内部领装",
  RD: "研发领用",
  SALES: "业务领用",
  QC: "品控领用",
};

function fmt(n: number | null | undefined, digits = 2) {
  if (n == null) return "—";
  return n.toFixed(digits);
}

function fmtQty(n: number | null | undefined) {
  if (n == null) return "—";
  return String(Math.round(n));
}

function TabBtn({
  id,
  active,
  onClick,
  children,
}: {
  id: string;
  active: boolean;
  onClick: () => void;
  children: string;
}) {
  return (
    <button
      type="button"
      data-tab={id}
      className={`rounded-md px-3 py-1.5 text-sm ${
        active ? "bg-[var(--accent)] text-white" : "text-[var(--text-muted)] hover:text-[var(--accent)]"
      }`}
      onClick={onClick}
    >
      {children}
    </button>
  );
}

export function Dept1StatsPage() {
  const { role } = useAuth();
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") || "detail";
  const dateFrom = params.get("from") || ANCHOR_FROM;
  const dateTo = params.get("to") || ANCHOR_TO;
  const setTab = (next: string) => {
    const n = new URLSearchParams(params);
    n.set("tab", next);
    setParams(n, { replace: true });
  };

  return (
    <div className="px-6 py-4">
      <h2 className="text-lg font-semibold">一部产能统计</h2>
      <p className="mt-1 text-xs text-[var(--text-muted)]">
        报工派生 · 盒/H 只用直接工时 · 每品项克重折公斤 · 未报工格空
      </p>
      <nav className="mt-3 flex flex-wrap gap-3 text-sm">
        <Link to="/modules/production/time-report" className="text-[var(--accent)] underline">
          组×日报工
        </Link>
        <Link to="/modules/hr/labor-cost" className="text-[var(--text-muted)] hover:text-[var(--accent)]">
          生产成本
        </Link>
      </nav>
      <div className="mt-4 flex flex-wrap items-end gap-3">
        <label className="text-xs text-[var(--text-muted)]">
          从
          <input
            type="date"
            className="ml-2 rounded border px-2 py-1 text-sm"
            style={{ borderColor: "var(--line)", background: "var(--bg-card)" }}
            value={dateFrom}
            onChange={(e) => {
              const n = new URLSearchParams(params);
              n.set("from", e.target.value);
              setParams(n, { replace: true });
            }}
          />
        </label>
        <label className="text-xs text-[var(--text-muted)]">
          到
          <input
            type="date"
            className="ml-2 rounded border px-2 py-1 text-sm"
            style={{ borderColor: "var(--line)", background: "var(--bg-card)" }}
            value={dateTo}
            onChange={(e) => {
              const n = new URLSearchParams(params);
              n.set("to", e.target.value);
              setParams(n, { replace: true });
            }}
          />
        </label>
        <div className="flex gap-1">
          <TabBtn id="detail" active={tab === "detail"} onClick={() => setTab("detail")}>
            日产出明细
          </TabBtn>
          <TabBtn id="daily" active={tab === "daily"} onClick={() => setTab("daily")}>
            一部日结
          </TabBtn>
          <TabBtn id="efficiency" active={tab === "efficiency"} onClick={() => setTab("efficiency")}>
            盒当量与效率
          </TabBtn>
        </div>
      </div>
      {tab === "detail" && <DetailTab role={role} dateFrom={dateFrom} dateTo={dateTo} />}
      {tab === "daily" && <DailyTab role={role} dateFrom={dateFrom} dateTo={dateTo} />}
      {tab === "efficiency" && <EffTab role={role} dateFrom={dateFrom} dateTo={dateTo} />}
    </div>
  );
}

function DetailTab({
  role,
  dateFrom,
  dateTo,
}: {
  role: string | null;
  dateFrom: string;
  dateTo: string;
}) {
  const [data, setData] = useState<DetailData | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const load = useCallback(() => {
    if (!role) return;
    setErr(null);
    requestWithRole<DetailData>(
      `/api/prod-stats/dept1/detail?date_from=${dateFrom}&date_to=${dateTo}`,
      role,
    )
      .then(setData)
      .catch((e) => setErr(String(e)));
  }, [role, dateFrom, dateTo]);
  useEffect(() => {
    load();
  }, [load]);

  const dates = data?.dates ?? [];
  const rows = useMemo(() => {
    if (!data) return [];
    const out: {
      key: string;
      groupLabel: string;
      groupRowspan: number | null;
      band: number;
      category: string;
      categoryRowspan: number | null;
      uomLabel: string;
      cells: Record<string, Cell>;
    }[] = [];
    data.groups.forEach((g, gi) => {
      const unitRows = g.categories.flatMap((cat) => cat.units.map((u) => ({ cat: cat.category, u })));
      const groupSpan = unitRows.length;
      const catStart = new Map<string, number>();
      for (const cat of g.categories) {
        catStart.set(cat.category, cat.units.length);
      }
      const seenCat = new Set<string>();
      unitRows.forEach(({ cat, u }, i) => {
        const catSpan = seenCat.has(cat) ? null : (catStart.get(cat) ?? 1);
        if (catSpan != null) seenCat.add(cat);
        out.push({
          key: `${g.group_code}-${cat}-${u.display_uom}`,
          groupLabel: g.group_label,
          groupRowspan: i === 0 ? groupSpan : null,
          band: gi % 2,
          category: cat,
          categoryRowspan: catSpan,
          uomLabel: u.display_uom_label,
          cells: u.cells,
        });
      });
    });
    return out;
  }, [data]);

  return (
    <div className="mt-4">
      {err && <p className="text-sm text-red-600">{err}</p>}
      {data && <p className="mb-2 text-xs text-[var(--text-muted)]">{data.caliber}</p>}
      <div className="overflow-x-auto rounded-lg border" style={{ borderColor: "var(--line)" }}>
        <table className="w-full min-w-[720px] border-collapse text-xs">
          <thead className="bg-[var(--table-head)] text-[var(--text-muted)]">
            <tr>
              <th className="px-2 py-2 text-left">组</th>
              <th className="text-left">类</th>
              <th className="text-left">单位</th>
              {dates.map((d) => (
                <th key={d} className="px-2 text-right tabular-nums">
                  {d.slice(5)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const bg =
                r.band === 0
                  ? "var(--bg-card)"
                  : "color-mix(in srgb, var(--accent) 10%, var(--bg-card))";
              return (
                <tr key={r.key} className="border-t" style={{ borderColor: "var(--line)", background: bg }}>
                  {r.groupRowspan != null && (
                    <td
                      rowSpan={r.groupRowspan}
                      className="border-r px-2 py-2 text-center align-middle font-medium"
                      style={{ borderColor: "var(--line)", background: bg }}
                    >
                      {r.groupLabel}
                    </td>
                  )}
                  {r.categoryRowspan != null && (
                    <td
                      rowSpan={r.categoryRowspan}
                      className="px-2 py-1 align-middle"
                      style={{ background: bg }}
                    >
                      {r.category}
                    </td>
                  )}
                  <td className="px-2 py-1">{r.uomLabel}</td>
                  {dates.map((d) => {
                    const c = r.cells[d];
                    return (
                      <td key={d} className="px-2 py-1 text-right tabular-nums">
                        <div>{fmtQty(c?.qty_actual)}</div>
                        {c?.qty_plan != null && (
                          <div className="text-[10px] text-[var(--text-muted)]">计 {fmtQty(c.qty_plan)}</div>
                        )}
                        {c?.missing_kg && <div className="text-[10px] text-amber-700">未维护克重</div>}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function DailyTab({
  role,
  dateFrom,
  dateTo,
}: {
  role: string | null;
  dateFrom: string;
  dateTo: string;
}) {
  const [data, setData] = useState<DailyData | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [itemCode, setItemCode] = useState("P1");
  const [qtyBoard, setQtyBoard] = useState("");
  const [workDate, setWorkDate] = useState(dateFrom);
  const canInbound = role === "GM" || role === "PMC" || role === "WH";

  const load = useCallback(() => {
    if (!role) return;
    requestWithRole<DailyData>(`/api/prod-stats/dept1/daily?date_from=${dateFrom}&date_to=${dateTo}`, role)
      .then(setData)
      .catch((e) => setErr(String(e)));
  }, [role, dateFrom, dateTo]);
  useEffect(() => {
    load();
  }, [load]);

  const submitInbound = async () => {
    if (!role) return;
    const qty = Math.ceil(Number(qtyBoard));
    if (!Number.isFinite(qty) || qty < 0) return;
    await requestWithRole(`/api/prod-stats/dept1/inbound`, role, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ work_date: workDate, item_code: itemCode, qty_board: qty }),
    });
    setQtyBoard("");
    load();
  };

  const uoms = useMemo(() => {
    const s = new Set<string>();
    for (const d of data?.dates ?? []) {
      Object.keys(data?.days[d]?.by_uom ?? {}).forEach((k) => s.add(k));
    }
    return [...s];
  }, [data]);

  return (
    <div className="mt-4">
      {err && <p className="text-sm text-red-600">{err}</p>}
      {data && (
        <p className="mb-2 text-xs text-[var(--text-muted)]">
          {data.caliber} · 区间盒/H {fmt(data.period.box_per_hour)}
        </p>
      )}
      {canInbound && (
        <div
          className="mb-3 flex flex-wrap items-end gap-2 rounded-lg border p-3 text-xs"
          style={{ borderColor: "var(--line)", background: "var(--bg-card)" }}
        >
          <span className="text-[var(--text-muted)]">入库（mock）</span>
          <input type="date" value={workDate} onChange={(e) => setWorkDate(e.target.value)} className="rounded border px-2 py-1" />
          <input
            value={itemCode}
            onChange={(e) => setItemCode(e.target.value)}
            className="w-24 rounded border px-2 py-1"
            placeholder="品项"
          />
          <input
            value={qtyBoard}
            onChange={(e) => setQtyBoard(e.target.value)}
            className="w-24 rounded border px-2 py-1"
            placeholder="入库版数"
          />
          <button type="button" className="rounded bg-[var(--accent)] px-3 py-1 text-white" onClick={() => void submitInbound()}>
            登记
          </button>
        </div>
      )}
      <div className="overflow-x-auto rounded-lg border" style={{ borderColor: "var(--line)" }}>
        <table className="w-full min-w-[800px] text-xs">
          <thead className="bg-[var(--table-head)] text-[var(--text-muted)]">
            <tr>
              <th className="px-2 py-2 text-left">项目</th>
              {(data?.dates ?? []).map((d) => (
                <th key={d} className="px-2 text-right">
                  {d.slice(5)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {(
              [
                ["产能合计(kg)", (x: DailyDay) => fmt(x.box_kg)],
                ["入库合计(kg)", (x: DailyDay) => fmt(x.inbound_box_kg)],
                ["入库差异(kg)", (x: DailyDay) => fmt(x.variance_box_kg)],
                ...Object.entries(ISSUE_LABEL).map(
                  ([k, label]) => [label, (x: DailyDay) => fmt(x.issues[k] ?? 0)] as const,
                ),
                ["出勤人数", (x: DailyDay) => (x.headcount == null ? "—" : String(x.headcount))],
                ["正常工时", (x: DailyDay) => fmt(x.hours_normal)],
                ["加班工时", (x: DailyDay) => fmt(x.hours_ot)],
                ["直接工时", (x: DailyDay) => fmt(x.hours_direct)],
                ["间接工时", (x: DailyDay) => fmt(x.hours_indirect)],
                ["总工时", (x: DailyDay) => fmt(x.hours_total)],
                ...uoms.map((u) => [`按${u}`, (x: DailyDay) => fmtQty(x.by_uom[u] ?? null)] as const),
                ["盒/H", (x: DailyDay) => fmt(x.box_per_hour)],
              ] as [string, (x: DailyDay) => string][]
            ).map(([label, pick]) => (
              <tr key={label} className="border-t" style={{ borderColor: "var(--line)" }}>
                <td className="px-2 py-1">{label}</td>
                {(data?.dates ?? []).map((d) => (
                  <td key={d} className="px-2 text-right tabular-nums">
                    {data?.days[d] ? pick(data.days[d]) : "—"}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function EffTab({
  role,
  dateFrom,
  dateTo,
}: {
  role: string | null;
  dateFrom: string;
  dateTo: string;
}) {
  const [data, setData] = useState<EffData | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    if (!role) return;
    requestWithRole<EffData>(
      `/api/prod-stats/dept1/efficiency?date_from=${dateFrom}&date_to=${dateTo}`,
      role,
    )
      .then(setData)
      .catch((e) => setErr(String(e)));
  }, [role, dateFrom, dateTo]);

  return (
    <div className="mt-4">
      {err && <p className="text-sm text-red-600">{err}</p>}
      {data && (
        <>
          <p className="mb-3 text-xs text-[var(--text-muted)]">{data.caliber} · 分母不含间接</p>
          <div className="grid gap-3 lg:grid-cols-3">
            <Card title="区间盒当量(kg)" value={fmt(data.period.box_kg)} />
            <Card title="区间直接工时" value={fmt(data.period.hours_direct)} />
            <Card title="区间盒/H" value={fmt(data.period.box_per_hour)} />
          </div>
          <div className="mt-4 overflow-x-auto rounded-lg border" style={{ borderColor: "var(--line)" }}>
            <table className="w-full text-xs">
              <thead className="bg-[var(--table-head)] text-[var(--text-muted)]">
                <tr>
                  <th className="px-3 py-2 text-left">组</th>
                  <th className="text-right">盒当量(kg)</th>
                  <th className="text-right">直接工时</th>
                  <th className="text-right">盒/H</th>
                </tr>
              </thead>
              <tbody>
                {data.groups.map((g) => (
                  <tr key={g.group_code} className="border-t" style={{ borderColor: "var(--line)" }}>
                    <td className="px-3 py-2">{g.group_label}</td>
                    <td className="text-right tabular-nums">{fmt(g.box_kg)}</td>
                    <td className="text-right tabular-nums">{fmt(g.hours_direct)}</td>
                    <td className="text-right tabular-nums">{fmt(g.box_per_hour)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <DailyTrendChart dates={data.dates} days={data.days} />
          <div className="mt-4 overflow-x-auto rounded-lg border" style={{ borderColor: "var(--line)" }}>
            <table className="w-full min-w-[640px] text-xs">
              <thead className="bg-[var(--table-head)] text-[var(--text-muted)]">
                <tr>
                  <th className="px-2 py-2 text-left">日期</th>
                  <th className="text-right">盒当量</th>
                  <th className="text-right">直接工时</th>
                  <th className="text-right">盒/H</th>
                </tr>
              </thead>
              <tbody>
                {data.dates.map((d) => {
                  const day = data.days[d];
                  return (
                    <tr key={d} className="border-t" style={{ borderColor: "var(--line)" }}>
                      <td className="px-2 py-1">{d}</td>
                      <td className="text-right tabular-nums">{fmt(day?.box_kg)}</td>
                      <td className="text-right tabular-nums">{fmt(day?.hours_direct)}</td>
                      <td className="text-right tabular-nums">{fmt(day?.box_per_hour)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

const TREND_SERIES = [
  { key: "box_kg" as const, label: "盒当量", color: "#38bdf8" },
  { key: "hours_direct" as const, label: "直接工时", color: "#e8b86d" },
  { key: "box_per_hour" as const, label: "盒/H", color: "#6fcf97" },
];

function DailyTrendChart({ dates, days }: { dates: string[]; days: Record<string, DailyDay> }) {
  const [hover, setHover] = useState<number | null>(null);
  const plotDates = useMemo(() => {
    const has = dates
      .map((d, i) => ({ d, i, ok: TREND_SERIES.some((s) => days[d]?.[s.key] != null) }))
      .filter((x) => x.ok);
    if (has.length === 0) return [] as string[];
    return dates.slice(has[0].i, has[has.length - 1].i + 1);
  }, [dates, days]);

  const w = 800;
  const h = 240;
  const pad = { top: 18, right: 12, bottom: 32, left: 12 };
  const plotW = w - pad.left - pad.right;
  const plotH = h - pad.top - pad.bottom;
  const n = plotDates.length;
  const xAt = (i: number) => pad.left + (n <= 1 ? plotW / 2 : (i / (n - 1)) * plotW);

  const series = TREND_SERIES.map((s) => {
    const values = plotDates.map((d) => days[d]?.[s.key] ?? null);
    const nums = values.filter((v): v is number => v != null);
    const rawMax = nums.length ? Math.max(...nums) : 1;
    const rawMin = nums.length ? Math.min(...nums) : 0;
    const padY = (rawMax - rawMin) * 0.12 || rawMax * 0.08 || 1;
    const max = rawMax + padY;
    const min = Math.max(0, rawMin - padY);
    const span = max - min || 1;
    const yAt = (v: number) => pad.top + (1 - (v - min) / span) * plotH;
    const segs: string[] = [];
    let buf: string[] = [];
    values.forEach((v, i) => {
      if (v == null) {
        if (buf.length) {
          segs.push(buf.join(" "));
          buf = [];
        }
        return;
      }
      buf.push(`${buf.length ? "L" : "M"}${xAt(i).toFixed(1)},${yAt(v).toFixed(1)}`);
    });
    if (buf.length) segs.push(buf.join(" "));
    return { ...s, values, yAt, segs };
  });

  const labelEvery = n > 14 ? 2 : 1;
  const hi = hover != null && hover >= 0 && hover < n ? hover : null;

  if (n === 0) {
    return (
      <div className="mt-4 rounded-lg border p-6 text-xs text-[var(--text-muted)]" style={{ borderColor: "var(--line)" }}>
        所选日期内还没有已报工数据，无法画趋势
      </div>
    );
  }

  return (
    <div className="mt-4 rounded-lg border p-3" style={{ borderColor: "var(--line)", background: "var(--bg-card)" }}>
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs text-[var(--text-muted)]">
          按日趋势（{plotDates[0].slice(5)}–{plotDates[n - 1].slice(5)}）· 各线按自身高低铺满，周末空档断开
        </p>
        <div className="flex flex-wrap gap-4 text-xs">
          {series.map((s) => (
            <span key={s.key} className="inline-flex items-center gap-1.5">
              <span className="inline-block h-0.5 w-5 rounded" style={{ background: s.color }} />
              <span style={{ color: s.color }}>{s.label}</span>
            </span>
          ))}
        </div>
      </div>
      <svg viewBox={`0 0 ${w} ${h}`} className="h-60 w-full" onMouseLeave={() => setHover(null)}>
        {[0, 0.25, 0.5, 0.75, 1].map((t) => {
          const y = pad.top + (1 - t) * plotH;
          return (
            <line key={t} x1={pad.left} x2={w - pad.right} y1={y} y2={y} stroke="var(--line)" strokeWidth="1" />
          );
        })}
        {plotDates.map((d, i) =>
          i % labelEvery === 0 || i === n - 1 ? (
            <text key={d} x={xAt(i)} y={h - 10} textAnchor="middle" fill="var(--text-muted)" fontSize="10">
              {d.slice(5)}
            </text>
          ) : null,
        )}
        {series.map((s) =>
          s.segs.map((d) => (
            <path
              key={`${s.key}-${d}`}
              d={d}
              fill="none"
              stroke={s.color}
              strokeWidth="2.2"
              strokeLinejoin="round"
              strokeLinecap="round"
            />
          )),
        )}
        {series.map((s) =>
          s.values.map((v, i) =>
            v == null ? null : (
              <circle key={`${s.key}-${i}`} cx={xAt(i)} cy={s.yAt(v)} r={hi === i ? 4 : 2.5} fill={s.color} />
            ),
          ),
        )}
        {plotDates.map((d, i) => (
          <rect
            key={`hit-${d}`}
            x={xAt(i) - Math.max(plotW / n / 2, 6)}
            y={pad.top}
            width={Math.max(plotW / n, 12)}
            height={plotH}
            fill="transparent"
            onMouseEnter={() => setHover(i)}
          />
        ))}
        {hi != null && (
          <line
            x1={xAt(hi)}
            x2={xAt(hi)}
            y1={pad.top}
            y2={pad.top + plotH}
            stroke="var(--text-muted)"
            strokeDasharray="3 3"
          />
        )}
      </svg>
      <p className="mt-1 min-h-[1.25rem] text-xs tabular-nums text-[var(--text-muted)]">
        {hi == null
          ? "鼠标移到日期上看三个数"
          : (
            <>
              {plotDates[hi]}
              {series.map((s) => (
                <span key={s.key} className="ml-3" style={{ color: s.color }}>
                  {s.label} {fmt(s.values[hi])}
                </span>
              ))}
            </>
          )}
      </p>
    </div>
  );
}

function Card({ title, value }: { title: string; value: string }) {
  return (
    <div className="rounded-lg border p-4" style={{ borderColor: "var(--line)", background: "var(--bg-card)" }}>
      <p className="text-xs text-[var(--text-muted)]">{title}</p>
      <p className="mt-1 text-2xl font-semibold tabular-nums">{value}</p>
    </div>
  );
}
