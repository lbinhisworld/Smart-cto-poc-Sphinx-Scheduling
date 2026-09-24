import { useEffect, useMemo, useState } from "react";
import { useAuth } from "../shell/auth";
import type { Conflict, OrderRow, ScheduleTrace } from "../types/schedule";
import {
  headerOrderNo,
  localBriefText,
  projectProcessBubbles,
  redAssists,
} from "../utils/processNarration";

type OpenNeg = {
  id: number;
  order_no: string;
  status: string;
  suggested_due: string | null;
  sales_proposed_due: string | null;
  brief_text: string;
};

type Props = {
  trace: ScheduleTrace | null | undefined;
  conflicts: Conflict[];
  orders: OrderRow[];
  onReplay?: () => void;
};

export function ScheduleProcessTab({ trace, conflicts, orders, onReplay }: Props) {
  const auth = useAuth();
  const role = auth.role;
  const bubbles = useMemo(
    () => projectProcessBubbles(trace, conflicts, orders),
    [trace, conflicts, orders],
  );
  const assists = useMemo(
    () => redAssists(conflicts, orders, trace?.events ?? []),
    [conflicts, orders, trace],
  );
  const [open, setOpen] = useState<OpenNeg[]>([]);
  const [briefFor, setBriefFor] = useState<(typeof assists)[0] | null>(null);
  const [briefText, setBriefText] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [applyId, setApplyId] = useState<number | null>(null);
  const [earliest, setEarliest] = useState<{
    title?: string;
    deliverable?: boolean;
    note?: string;
    sales_sentences?: string[];
    suggested_due?: string;
    stuck?: string;
    hours_wall?: string;
    hours_man?: string;
    tasks?: { task_date: string; qty_board: number; group_code: string }[];
  } | null>(null);

  const loadOpen = () => {
    fetch("/api/due-negotiations", { headers: auth.headers() })
      .then((r) => r.json())
      .then((j) => setOpen(j.data?.items ?? []))
      .catch(() => setOpen([]));
  };

  useEffect(() => {
    loadOpen();
  }, [auth.role]);

  const canPmc = role === "PMC" || role === "GM";

  const openBrief = async (a: (typeof assists)[0]) => {
    const order = orders.find((o) => headerOrderNo(o.order_no) === headerOrderNo(a.orderNo));
    const suggested = a.suggestedDue || order?.due_date || null;
    const card = { ...a, orderNo: headerOrderNo(a.orderNo), suggestedDue: suggested };
    setErr(null);
    setEarliest(null);
    setBriefFor(card);
    setBriefText(
      localBriefText({
        orderNo: card.orderNo,
        suggestedDue: card.suggestedDue,
        reason: card.reason,
        customer: order?.customer,
        salesName: order?.sales_name,
        itemCode: order?.item_code,
        oldDue: order?.due_date,
      }),
    );
    if (!suggested) {
      setErr("没有最快可完成日，请先在口径里手工写建议日后再发。");
      return;
    }
    try {
      const r = await fetch("/api/schedule/assist/brief/preview", {
        method: "POST",
        headers: { ...auth.headers(), "Content-Type": "application/json" },
        body: JSON.stringify({
          order_no: card.orderNo,
          suggested_due: suggested,
          conflict_code: card.code,
          reason: card.reason,
        }),
      });
      const j = await r.json().catch(() => ({}));
      if (r.ok && j.code === 0 && j.data?.brief_text) {
        setBriefText(j.data.brief_text);
        setBriefFor({ ...card, suggestedDue: j.data.suggested_due || suggested });
        if (j.data.can_negotiate === false) {
          setErr("系统最快不晚于客户交期，交期本身够，不要发给销售。");
        }
      } else if (!r.ok) {
        setErr(
          typeof j.detail === "string"
            ? j.detail
            : "预览接口不可用（后端需重启）。已用本地口径，仍可发送。",
        );
      }
    } catch {
      setErr("预览接口连不上。已用本地口径，仍可发送。");
    }
    try {
      const er = await fetch("/api/schedule/earliest-plan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ order_no: card.orderNo, today: "2026-09-15" }),
      });
      const ej = await er.json().catch(() => ({}));
      if (er.ok && ej.code === 0 && ej.data?.eligible) {
        setEarliest(ej.data);
        if (ej.data.deliverable && Array.isArray(ej.data.sales_sentences)) {
          const extra = ej.data.sales_sentences.join("\n");
          setBriefText((prev) => (prev.includes("建议交期不早于") ? prev : `${prev}\n${extra}`));
        }
      }
    } catch {
      setEarliest(null);
    }
  };

  const sendBrief = async () => {
    if (!briefFor?.suggestedDue) return;
    setBusy(true);
    setErr(null);
    try {
      const r = await fetch("/api/schedule/assist/brief", {
        method: "POST",
        headers: { ...auth.headers(), "Content-Type": "application/json" },
        body: JSON.stringify({
          order_no: headerOrderNo(briefFor.orderNo),
          suggested_due: briefFor.suggestedDue,
          conflict_code: briefFor.code,
          reason: briefFor.reason,
          brief_text: briefText,
        }),
      });
      const j = await r.json();
      if (!r.ok || j.code !== 0) throw new Error(j.detail || j.message || "发送失败");
      setBriefFor(null);
      loadOpen();
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  };

  const applyDue = async (neg: OpenNeg) => {
    setBusy(true);
    setErr(null);
    setApplyId(neg.id);
    try {
      const r = await fetch(`/api/orders/${encodeURIComponent(neg.order_no)}/due-negotiate/apply`, {
        method: "POST",
        headers: { ...auth.headers(), "Content-Type": "application/json" },
        body: JSON.stringify({ request_id: neg.id, today: "2026-09-15" }),
      });
      const j = await r.json();
      if (!r.ok || j.code !== 0) throw new Error(j.detail || j.message || "改锚失败");
      loadOpen();
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
      setApplyId(null);
    }
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex items-center justify-between px-3 pb-2">
        <p className="text-[10px] text-slate-500">算完再播 · 不现场重算</p>
        {onReplay && (
          <button type="button" className="text-[10px] text-violet-300 underline" onClick={onReplay}>
            同步看板回放
          </button>
        )}
      </div>
      <div className="min-h-0 flex-1 space-y-2 overflow-y-auto px-2 pb-2">
        {bubbles.map((b) => (
          <div
            key={b.id}
            className={`whitespace-pre-wrap rounded-lg px-2.5 py-1.5 text-[11px] leading-snug ${
              b.tone === "alert"
                ? "border border-rose-800/70 bg-rose-950/40 text-rose-100"
                : b.tone === "coline"
                  ? "border border-teal-700/70 bg-teal-950/40 text-teal-100"
                  : b.tone === "place"
                    ? "border border-sky-900/60 bg-sky-950/30 text-slate-200"
                    : "border border-slate-800 bg-slate-950/50 text-slate-300"
            }`}
          >
            {b.text}
          </div>
        ))}

        {assists.map((a) => {
          const neg = open.find((x) => x.order_no === a.orderNo);
          const canAskSales = a.kind === "NEGOTIATE";
          return (
            <div
              key={a.orderNo}
              className="rounded-lg border border-amber-800/50 bg-amber-950/25 px-2.5 py-2 text-[11px]"
            >
              <p className="font-medium text-amber-100">策略建议 · {a.orderNo}</p>
              <p className="mt-0.5 whitespace-pre-wrap text-slate-400">{a.message}</p>
              {!canAskSales && (
                <p className="mt-1 text-emerald-300/90">
                  系统最快{a.suggestedDue ? ` ${a.suggestedDue}` : ""}不晚于客户交期，交期本身够。不要找销售改交期。
                </p>
              )}
              <div className="mt-2 flex flex-col gap-1">
                <button
                  type="button"
                  disabled={!canAskSales || Boolean(neg && neg.status === "PENDING_SALES")}
                  className="rounded border border-emerald-700 bg-emerald-950/40 px-2 py-1 text-left text-emerald-200 hover:bg-emerald-900/50 disabled:opacity-40"
                  onClick={() => {
                    if (!canAskSales) return;
                    if (!canPmc) {
                      setErr("请切换到 PMC 或总经理后再发口径（销售只能回确认日）");
                      return;
                    }
                    void openBrief(a);
                  }}
                >
                  {neg?.status === "PENDING_SALES"
                    ? `已发出协商（${neg.status}）`
                    : canAskSales
                      ? "协商交期 · 生成给销售的口径"
                      : "协商交期（交期够，不发送）"}
                </button>
                <button
                  type="button"
                  disabled
                  className="rounded border border-slate-700 px-2 py-1 text-left text-slate-500"
                >
                  加班 / 加人（下一期）
                </button>
                <button
                  type="button"
                  disabled
                  className="rounded border border-slate-700 px-2 py-1 text-left text-slate-500"
                >
                  保本单挤别人（下一期）
                </button>
              </div>
            </div>
          );
        })}

        {open
          .filter((n) => n.status === "SALES_REPLIED")
          .map((n) => (
            <div
              key={`apply-${n.id}`}
              className="rounded-lg border border-sky-700/60 bg-sky-950/30 px-2.5 py-2 text-[11px]"
            >
              <p className="font-medium text-sky-100">销售已回 · {n.order_no}</p>
              <p className="mt-0.5 text-slate-400">
                客户确认日 {n.sales_proposed_due}。改锚后请再点倒排，系统不会自动重排。
              </p>
              {canPmc && (
                <button
                  type="button"
                  disabled={busy && applyId === n.id}
                  className="mt-2 rounded bg-sky-800 px-2 py-1 text-sky-50"
                  onClick={() => void applyDue(n)}
                >
                  确认改锚为 {n.sales_proposed_due}
                </button>
              )}
            </div>
          ))}
      </div>

      {err && !briefFor && (
        <p className="border-t border-rose-900 px-3 py-1.5 text-[11px] text-rose-300">{err}</p>
      )}

      {briefFor && (
        <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/60 p-4">
          <div
            className="w-full max-w-md rounded-lg border border-slate-700 bg-slate-900 p-4 shadow-2xl"
            role="dialog"
          >
            <p className="text-sm font-medium text-slate-100">口径卡 · {briefFor.orderNo}</p>
            {earliest && (
              <div className="mt-2 rounded border border-amber-800/60 bg-amber-950/40 p-2 text-[11px] text-amber-50">
                <p className="font-medium">{earliest.title}</p>
                <p className="mt-1 text-amber-100/90">
                  {earliest.stuck} · 建议不早于 {earliest.suggested_due} · 墙钟 {earliest.hours_wall} h · 人·时{" "}
                  {earliest.hours_man}
                </p>
                {earliest.note ? <p className="mt-1 text-rose-200">{earliest.note}</p> : null}
                {earliest.tasks && earliest.tasks.length > 0 && (
                  <ul className="mt-1 space-y-0.5 text-slate-300">
                    {earliest.tasks.slice(0, 6).map((t) => (
                      <li key={`${t.task_date}-${t.group_code}-${t.qty_board}`}>
                        {t.task_date} · {t.group_code} · {t.qty_board} 版
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
            {err && <p className="mt-2 text-[11px] text-amber-300">{err}</p>}
            <label className="mt-2 block text-[10px] text-slate-400">
              建议不早于
              <input
                type="date"
                className="mt-0.5 block w-full rounded border border-slate-700 bg-slate-950 px-2 py-1 text-xs text-slate-100"
                value={briefFor.suggestedDue ?? ""}
                onChange={(e) =>
                  setBriefFor({ ...briefFor, suggestedDue: e.target.value || null })
                }
              />
            </label>
            <textarea
              className="mt-2 h-36 w-full rounded border border-slate-700 bg-slate-950 p-2 text-xs text-slate-200"
              value={briefText}
              onChange={(e) => setBriefText(e.target.value)}
            />
            <p className="mt-2 text-[10px] text-slate-500">
              确认后写入销售待办 + 企微模拟 S6，不改客户交期。
            </p>
            <div className="mt-3 flex gap-2">
              <button
                type="button"
                disabled={
                  busy ||
                  !briefFor.suggestedDue ||
                  briefFor.kind !== "NEGOTIATE"
                }
                className="rounded bg-emerald-700 px-3 py-1.5 text-xs text-white disabled:opacity-40"
                onClick={() => void sendBrief()}
              >
                确认发给销售
              </button>
              <button
                type="button"
                className="rounded border border-slate-600 px-3 py-1.5 text-xs text-slate-300"
                onClick={() => {
                  setBriefFor(null);
                  setErr(null);
                }}
              >
                取消
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
