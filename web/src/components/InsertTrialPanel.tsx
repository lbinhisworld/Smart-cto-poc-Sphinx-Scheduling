import { useState } from "react";
import { useAuth } from "../shell/auth";

type Strategy = {
  strategy: string;
  diff: { summary_text?: string };
};

type ApplyPayload = {
  plan_version: number;
  result: unknown;
};

type Props = {
  today: string;
  defaultOrderNo?: string;
  onApplied?: (data: ApplyPayload) => void | Promise<void>;
};

export function InsertTrialPanel({ today, defaultOrderNo = "SO-004", onApplied }: Props) {
  const auth = useAuth();
  const [orderNo, setOrderNo] = useState(defaultOrderNo);
  const [open, setOpen] = useState(false);
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const trial = async () => {
    setBusy(true);
    setError(null);
    try {
      const r = await fetch("/api/schedule/insert", {
        method: "POST",
        headers: { ...auth.headers(), "Content-Type": "application/json" },
        body: JSON.stringify({ order_no: orderNo, today, reason: "演示插单" }),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || j.message || r.statusText);
      const payload = j.data ?? j;
      setStrategies(payload.strategies ?? []);
      setOpen(true);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const apply = async (strategy: string) => {
    setBusy(true);
    try {
      const r = await fetch("/api/schedule/insert/apply", {
        method: "POST",
        headers: { ...auth.headers(), "Content-Type": "application/json" },
        body: JSON.stringify({
          order_no: orderNo,
          today,
          strategy,
          reason: "演示插单应用",
          requester: auth.userName,
        }),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || j.message || r.statusText);
      const payload = (j.data ?? j) as ApplyPayload;
      setOpen(false);
      await onApplied?.(payload);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <button
        type="button"
        disabled={busy}
        onClick={() => void trial()}
        className="rounded border border-violet-700 px-3 py-1.5 text-sm text-violet-200 hover:bg-violet-950 disabled:opacity-40"
      >
        插单试排
      </button>
      {error && <span className="ml-2 text-xs text-rose-400">{error}</span>}
      {open && (
        <div className="fixed inset-0 z-[90] flex items-center justify-center bg-black/60 p-4">
          <div className="max-h-[80vh] w-full max-w-lg overflow-y-auto rounded-lg border border-slate-700 bg-slate-900 p-4 text-sm">
            <p className="font-semibold">插单四策略 · {orderNo}</p>
            <p className="mt-1 text-xs text-slate-400">
              确认后该单进入排程中。保存发布沿用这一版计划，不再整池重算。
            </p>
            <input
              className="mt-2 w-full rounded border border-slate-600 bg-slate-950 px-2 py-1 text-xs"
              value={orderNo}
              onChange={(e) => setOrderNo(e.target.value)}
            />
            <ul className="mt-3 space-y-2">
              {strategies.map((s) => (
                <li key={s.strategy} className="rounded border border-slate-800 p-2">
                  <p className="font-medium">策略 {s.strategy}</p>
                  <p className="text-xs text-slate-400">{s.diff?.summary_text ?? "—"}</p>
                  <button
                    type="button"
                    className="mt-1 rounded bg-violet-800 px-2 py-0.5 text-xs"
                    disabled={busy}
                    onClick={() => void apply(s.strategy)}
                  >
                    确认，进入排程
                  </button>
                </li>
              ))}
            </ul>
            <button
              type="button"
              className="mt-3 text-xs text-slate-400 underline"
              onClick={() => setOpen(false)}
            >
              关闭
            </button>
          </div>
        </div>
      )}
    </>
  );
}
