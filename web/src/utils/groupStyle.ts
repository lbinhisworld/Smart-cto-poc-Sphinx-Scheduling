import type { GroupCode } from "../constants/groups";

export function groupAccent(code: string): {
  border: string;
  bg: string;
  badge: string;
} {
  const map: Record<GroupCode, { border: string; bg: string; badge: string }> = {
    MANUAL: {
      border: "border-emerald-600/80",
      bg: "bg-slate-900",
      badge: "bg-emerald-900 text-emerald-100",
    },
    MOLD: {
      border: "border-sky-600/80",
      bg: "bg-slate-900",
      badge: "bg-sky-900 text-sky-100",
    },
    POURING: {
      border: "border-amber-600/80",
      bg: "bg-slate-900",
      badge: "bg-amber-900 text-amber-100",
    },
  };
  return map[code as GroupCode] ?? {
    border: "border-slate-600",
    bg: "bg-slate-900",
    badge: "bg-slate-700 text-slate-200",
  };
}
