import { shortLabel } from "../utils/dates";

export type OrderRow = {
  order_no: string;
  customer: string;
  sales_name: string;
  item_code: string;
  due_date: string;
  remain_days: number;
  amount: number | null;
  kitting_rate_pct: number | null;
  order_status: string;
};

export function renderDocLink(value: string) {
  return (
    <span className="cursor-pointer font-mono text-[var(--accent)] hover:underline">
      {value}
    </span>
  );
}

export function renderMoney(value: number | null) {
  if (value == null) return <span className="text-[var(--text-muted)]">—</span>;
  return (
    <span className="tabular-nums">
      ¥{value.toLocaleString("zh-CN", { minimumFractionDigits: 2 })}
    </span>
  );
}

export function renderTrafficLight(remain: number) {
  const dot =
    remain <= 2 ? "bg-red-500" : remain <= 6 ? "bg-amber-400" : "bg-emerald-500";
  return (
    <span className="inline-flex items-center gap-1 tabular-nums">
      <span className={`inline-block h-2 w-2 rounded-full ${dot}`} />
      {remain} 天
    </span>
  );
}

export function renderProgress(pct: number | null) {
  const v = pct ?? 0;
  const bar =
    v < 50 ? "bg-red-400" : v < 90 ? "bg-amber-400" : "bg-emerald-500";
  return (
    <span className="inline-flex min-w-[88px] items-center gap-2">
      <span className="h-1.5 flex-1 overflow-hidden rounded bg-[var(--line)]">
        <span className={`block h-full ${bar}`} style={{ width: `${v}%` }} />
      </span>
      <span className="tabular-nums text-xs">{v}%</span>
    </span>
  );
}

export function renderStatusTag(status: string) {
  const map: Record<string, string> = {
    CONFIRMED: "bg-sky-950 text-sky-300 ring-1 ring-sky-800",
    SCHEDULED: "bg-emerald-950 text-emerald-300 ring-1 ring-emerald-800",
    CLOSED: "bg-slate-800 text-slate-400 ring-1 ring-slate-700",
  };
  const cls = map[status] ?? "bg-slate-800 text-slate-400 ring-1 ring-slate-700";
  return (
    <span className={`rounded px-2 py-0.5 text-[11px] ${cls}`}>{status}</span>
  );
}

export function renderDate(iso: string) {
  const expired = iso < "2026-09-15";
  return (
    <span className={expired ? "text-rose-400" : ""}>
      {/^\d{4}-\d{2}-\d{2}$/.test(iso) ? shortLabel(iso) : iso}
    </span>
  );
}
