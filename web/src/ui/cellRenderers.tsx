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
  schedule_phase?: string;
  line_count?: number;
  lines_summary?: string;
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

/** 员工在职状态 */
export function renderHrEmpStatusTag(status: string) {
  const map: Record<string, string> = {
    ACTIVE: "bg-emerald-950 text-emerald-200 ring-1 ring-emerald-700",
    LEAVE: "bg-slate-700 text-slate-300 ring-1 ring-slate-600",
  };
  const label = status === "ACTIVE" ? "在职" : status === "LEAVE" ? "休假" : status;
  const cls = map[status] ?? "bg-slate-800 text-slate-300 ring-1 ring-slate-600";
  return (
    <span className={`inline-block rounded-md px-2 py-0.5 text-[11px] font-medium leading-tight ${cls}`}>
      {label}
    </span>
  );
}

/** 劳动合同续签状态 */
export function renderContractStatusTag(status: string) {
  const map: Record<string, { cls: string; label: string }> = {
    OK: { cls: "bg-emerald-950 text-emerald-200 ring-1 ring-emerald-700", label: "正常" },
    DUE_SOON: { cls: "bg-amber-950 text-amber-200 ring-1 ring-amber-700", label: "一个月内续签" },
    EXPIRED: { cls: "bg-rose-950 text-rose-200 ring-1 ring-rose-700", label: "续签过期" },
  };
  const item = map[status] ?? { cls: "bg-slate-800 text-slate-300 ring-1 ring-slate-600", label: status };
  return (
    <span className={`inline-block rounded-md px-2 py-0.5 text-[11px] font-medium leading-tight ${item.cls}`}>
      {item.label}
    </span>
  );
}

export function formatRenewalCountdown(days: number | null | undefined): string {
  if (days == null) return "—";
  if (days > 0) return `还有 ${days} 天`;
  if (days === 0) return "今天到期";
  return `已过期 ${Math.abs(days)} 天`;
}

export function renderRenewalCountdown(days: number | null | undefined) {
  if (days == null) return <span className="text-[var(--text-muted)]">—</span>;
  const cls = days < 0 ? "text-rose-400" : days <= 30 ? "text-amber-300" : "text-emerald-300";
  return <span className={`tabular-nums font-medium ${cls}`}>{formatRenewalCountdown(days)}</span>;
}

/** 考勤打卡类型 */
export function renderPunchTypeTag(punchType: string) {
  const map: Record<string, string> = {
    上班: "bg-sky-950 text-sky-200 ring-1 ring-sky-700",
    下班: "bg-violet-950 text-violet-200 ring-1 ring-violet-700",
  };
  const cls = map[punchType] ?? "bg-slate-800 text-slate-300 ring-1 ring-slate-600";
  return (
    <span className={`inline-block rounded-md px-2 py-0.5 text-[11px] font-medium leading-tight ${cls}`}>
      {punchType}
    </span>
  );
}

/** 产品列：轮次用琥珀色文字（第 N 轮），其余保持默认色 */
export function renderSampleProductDesc(desc: string, roundNo?: number | null) {
  const text = desc?.trim() || "";
  if (!text && roundNo != null && roundNo > 0) {
    return <span className="text-amber-300/95">第{roundNo}轮</span>;
  }
  if (!text) return <span className="text-[var(--text-muted)]">—</span>;
  const parts = text.split(/(第\d+轮[^·]*)/g).filter(Boolean);
  if (parts.length <= 1 && roundNo != null && roundNo > 0 && !/第\d+轮/.test(text)) {
    return (
      <>
        {text}{" "}
        <span className="font-medium text-amber-300/95">第{roundNo}轮</span>
      </>
    );
  }
  return (
    <>
      {parts.map((part, i) =>
        /^第\d+轮/.test(part) ? (
          <span key={i} className="font-medium text-amber-300/95">
            {part}
          </span>
        ) : (
          <span key={i}>{part}</span>
        ),
      )}
    </>
  );
}

/** 打样流程阶段 · 圆角彩色标签 */
export function renderSampleStageTag(stage: string) {
  const map: Record<string, string> = {
    申请: "bg-sky-950 text-sky-200 ring-1 ring-sky-700",
    打样: "bg-amber-950 text-amber-200 ring-1 ring-amber-700",
    寄样: "bg-violet-950 text-violet-200 ring-1 ring-violet-700",
    客户反馈: "bg-orange-950 text-orange-200 ring-1 ring-orange-700",
    结案: "bg-emerald-950 text-emerald-200 ring-1 ring-emerald-700",
  };
  const cls = map[stage] ?? "bg-slate-800 text-slate-300 ring-1 ring-slate-600";
  return (
    <span className={`inline-block rounded-md px-2 py-0.5 text-[11px] font-medium leading-tight ${cls}`}>
      {stage}
    </span>
  );
}

/** CRM 商机漏斗阶段 · 圆角彩色标签 */
export function renderOppStageTag(stage: string) {
  const map: Record<string, string> = {
    线索: "bg-slate-700/90 text-slate-100 ring-1 ring-slate-500/60",
    商机: "bg-sky-950 text-sky-200 ring-1 ring-sky-700",
    方案: "bg-violet-950 text-violet-200 ring-1 ring-violet-700",
    报价: "bg-amber-950 text-amber-200 ring-1 ring-amber-700",
    谈判: "bg-orange-950 text-orange-200 ring-1 ring-orange-700",
    成交: "bg-emerald-950 text-emerald-200 ring-1 ring-emerald-700",
  };
  const cls = map[stage] ?? "bg-slate-800 text-slate-300 ring-1 ring-slate-600";
  return (
    <span className={`inline-block rounded-md px-2 py-0.5 text-[11px] font-medium leading-tight ${cls}`}>
      {stage}
    </span>
  );
}

const SCHEDULE_PHASE_LABEL: Record<string, { cls: string; label: string }> = {
  PENDING: { cls: "bg-sky-950 text-sky-300 ring-1 ring-sky-800", label: "待排程" },
  IN_SCHEDULING: { cls: "bg-amber-950 text-amber-200 ring-1 ring-amber-700", label: "排程中" },
  IN_PRODUCTION: { cls: "bg-emerald-950 text-emerald-300 ring-1 ring-emerald-800", label: "生产中" },
  COMPLETED: { cls: "bg-slate-800 text-slate-400 ring-1 ring-slate-700", label: "已完结" },
};

export function renderSchedulePhaseTag(phase: string | undefined) {
  const key = phase || "PENDING";
  const item = SCHEDULE_PHASE_LABEL[key] ?? {
    cls: "bg-slate-800 text-slate-400 ring-1 ring-slate-700",
    label: key,
  };
  return (
    <span className={`rounded px-2 py-0.5 text-[11px] ${item.cls}`}>{item.label}</span>
  );
}

export function renderStatusTag(status: string) {
  const map: Record<string, { cls: string; label: string }> = {
    CONFIRMED: { cls: "bg-sky-950 text-sky-300 ring-1 ring-sky-800", label: "已确认" },
    SCHEDULED: { cls: "bg-amber-950 text-amber-200 ring-1 ring-amber-700", label: "已进排程" },
    CLOSED: { cls: "bg-slate-800 text-slate-400 ring-1 ring-slate-700", label: "已关闭" },
    CANCELLED: { cls: "bg-rose-950 text-rose-300 ring-1 ring-rose-800", label: "已作废" },
  };
  const item = map[status] ?? { cls: "bg-slate-800 text-slate-400 ring-1 ring-slate-700", label: status };
  return (
    <span className={`rounded px-2 py-0.5 text-[11px] ${item.cls}`}>{item.label}</span>
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
