import { DEMO_TODAY, HORIZON_DAYS } from "../constants/groups";

function parseYmd(s: string): Date {
  const [y, m, d] = s.split("-").map(Number);
  return new Date(y, m - 1, d);
}

function formatYmd(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export function addDays(ymd: string, delta: number): string {
  const d = parseYmd(ymd);
  d.setDate(d.getDate() + delta);
  return formatYmd(d);
}

export function dateRange(today: string = DEMO_TODAY): string[] {
  const out: string[] = [];
  for (let i = -1; i <= HORIZON_DAYS; i += 1) {
    out.push(addDays(today, i));
  }
  return out;
}

export function isWeekend(ymd: string): boolean {
  const d = parseYmd(ymd);
  const w = d.getDay();
  return w === 0 || w === 6;
}

export function shortLabel(ymd: string): string {
  const d = parseYmd(ymd);
  return `${d.getMonth() + 1}/${d.getDate()}`;
}

export function daysUntil(due: string, today: string): number {
  const a = parseYmd(today).getTime();
  const b = parseYmd(due).getTime();
  return Math.round((b - a) / (86400000));
}
