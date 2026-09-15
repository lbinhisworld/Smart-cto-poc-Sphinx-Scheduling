import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../../shell/auth";

type LogRow = {
  id: number;
  direction: string;
  doc_type: string;
  doc_no: string;
  status: string;
  message: string;
  created_at: string | null;
};

type Template = {
  key: string;
  label: string;
};

export function KingdeeSyncPage() {
  const auth = useAuth();
  const [logs, setLogs] = useState<LogRow[]>([]);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [busy, setBusy] = useState(false);
  const [lastOrder, setLastOrder] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    const h = auth.headers();
    Promise.all([
      fetch("/api/kingdee/logs", { headers: h }).then((r) => r.json()),
      fetch("/api/kingdee/templates", { headers: h }).then((r) => r.json()),
    ])
      .then(([lr, tr]) => {
        setLogs(lr.data ?? []);
        setTemplates(tr.data ?? []);
      })
      .catch((e) => setError(String(e)));
  }, [auth]);

  useEffect(() => {
    load();
  }, [load]);

  const push = async (templateKey: string) => {
    setBusy(true);
    setError(null);
    try {
      const r = await fetch("/api/kingdee/simulate-push", {
        method: "POST",
        headers: { ...auth.headers(), "Content-Type": "application/json" },
        body: JSON.stringify({ template_key: templateKey }),
      });
      const j = await r.json();
      if (j.code !== 0) throw new Error(j.message || "推送失败");
      setLastOrder(j.data.order_no);
      load();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="px-6 py-4">
      <h2 className="text-lg font-semibold">金蝶 K/3 同步工作台（Push 模拟）</h2>
      <p className="mt-1 text-sm text-[var(--text-muted)]">
        演示金蝶主动推送销售订单 → 自动算料齐套 → 进入待排产（非轮询 Pull）
      </p>

      <div className="mt-4 flex flex-wrap gap-2">
        {templates.map((t) => (
          <button
            key={t.key}
            type="button"
            disabled={busy}
            onClick={() => push(t.key)}
            className="rounded border px-3 py-2 text-sm hover:border-[var(--accent)]"
            style={{ borderColor: "var(--line)", background: "var(--bg-card)" }}
          >
            模拟推送：{t.label ?? t.key}
          </button>
        ))}
      </div>

      {lastOrder && (
        <p className="mt-3 text-sm">
          最新订单{" "}
          <Link to="/orders" className="text-[var(--accent)] underline">
            {lastOrder}
          </Link>
          {" · "}
          <Link to="/schedule" className="text-[var(--accent)] underline">
            去排程
          </Link>
        </p>
      )}
      {error && (
        <p className="mt-2 text-sm text-red-600" role="alert">
          {error}
        </p>
      )}

      <div
        className="mt-6 overflow-x-auto rounded border"
        style={{ borderColor: "var(--line)", background: "var(--bg-card)" }}
      >
        <table className="w-full min-w-[640px] text-[13px]">
          <thead style={{ background: "var(--table-head)" }}>
            <tr>
              <th className="px-3 py-2 text-left font-medium text-[var(--text-muted)]">时间</th>
              <th className="px-3 py-2 text-left font-medium text-[var(--text-muted)]">方向</th>
              <th className="px-3 py-2 text-left font-medium text-[var(--text-muted)]">单号</th>
              <th className="px-3 py-2 text-left font-medium text-[var(--text-muted)]">状态</th>
              <th className="px-3 py-2 text-left font-medium text-[var(--text-muted)]">说明</th>
            </tr>
          </thead>
          <tbody>
            {logs.map((r) => (
              <tr key={r.id} className="border-t" style={{ borderColor: "var(--line)" }}>
                <td className="px-3 py-2">{r.created_at?.slice(0, 19) ?? "—"}</td>
                <td className="px-3 py-2">{r.direction}</td>
                <td className="px-3 py-2 font-mono">{r.doc_no}</td>
                <td className="px-3 py-2">{r.status}</td>
                <td className="px-3 py-2 text-[var(--text-muted)]">{r.message}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
