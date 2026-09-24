import { useState } from "react";
import { useAuth } from "../../shell/auth";

type Props = {
  recordType: "线索" | "商机" | "客户";
  customerCode?: string | null;
  leadCode?: string | null;
  opportunityId?: number | null;
  onSaved?: () => void;
};

export function FollowAddForm({ recordType, customerCode, leadCode, opportunityId, onSaved }: Props) {
  const auth = useAuth();
  const [content, setContent] = useState("");
  const [custCode, setCustCode] = useState(customerCode ?? "");
  const [nextDate, setNextDate] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const submit = async () => {
    if (!content.trim()) {
      setErr("请填写跟进内容");
      return;
    }
    setBusy(true);
    setErr(null);
    try {
      const r = await fetch("/api/crm/follows?today=2026-09-15", {
        method: "POST",
        headers: { ...auth.headers(), "Content-Type": "application/json" },
        body: JSON.stringify({
          record_type: recordType,
          content: content.trim(),
          customer_code: customerCode || custCode || null,
          lead_code: leadCode || null,
          opportunity_id: opportunityId ?? null,
          next_follow_date: nextDate || null,
        }),
      });
      const j = await r.json();
      if (!r.ok || j.code !== 0) throw new Error(j.detail || j.message);
      setContent("");
      setNextDate("");
      onSaved?.();
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mt-3 space-y-2 rounded border p-3 text-xs" style={{ borderColor: "var(--line)" }}>
      <p className="font-medium">新建跟进</p>
      {!customerCode && recordType === "客户" && (
        <input
          className="w-full rounded border px-2 py-1"
          style={{ borderColor: "var(--line)", background: "var(--bg-body)" }}
          placeholder="客户编码，如 C-001"
          value={custCode}
          onChange={(e) => setCustCode(e.target.value)}
        />
      )}
      <textarea
        className="w-full rounded border p-2"
        style={{ borderColor: "var(--line)", background: "var(--bg-body)" }}
        rows={3}
        placeholder="跟进内容"
        value={content}
        onChange={(e) => setContent(e.target.value)}
      />
      <label className="block">
        下次跟进日
        <input type="date" className="ml-2 rounded border px-2 py-1" style={{ borderColor: "var(--line)" }} value={nextDate} onChange={(e) => setNextDate(e.target.value)} />
      </label>
      {err && <p className="text-rose-400">{err}</p>}
      <button type="button" disabled={busy} className="rounded bg-[var(--accent)] px-3 py-1 text-slate-950 disabled:opacity-50" onClick={() => void submit()}>
        {busy ? "保存中…" : "保存跟进"}
      </button>
    </div>
  );
}

export function FollowTimeline({
  rows,
}: {
  rows: { id: number; follow_date: string; record_type: string; content: string; owner_sales?: string }[];
}) {
  if (rows.length === 0) return <p className="text-xs text-[var(--text-muted)]">暂无跟进</p>;
  return (
    <ul className="space-y-2 text-xs">
      {rows.map((f) => (
        <li key={f.id} className="rounded border p-2" style={{ borderColor: "var(--line)" }}>
          <p className="text-[var(--text-muted)]">
            {f.follow_date} · {f.record_type}
            {f.owner_sales ? ` · ${f.owner_sales}` : ""}
          </p>
          <p>{f.content}</p>
        </li>
      ))}
    </ul>
  );
}
