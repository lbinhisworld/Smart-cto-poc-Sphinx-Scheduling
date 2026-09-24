import { useEffect, useState } from "react";
import { useAuth } from "../../shell/auth";

type Report = {
  summary: Record<string, number>;
  stage_distribution: Record<string, number>;
  industry_distribution: Record<string, number>;
  source_distribution: Record<string, number>;
  new_trend: { month: string; count: number }[];
  convert_trend: { month: string; count: number }[];
};

export function LeadReportPage() {
  const auth = useAuth();
  const [data, setData] = useState<Report | null>(null);
  const [drill, setDrill] = useState<{ bucket: string; rows: { code: string; contact_name: string; company_name: string }[] } | null>(null);

  useEffect(() => {
    fetch("/api/crm/leads/report?today=2026-09-15", { headers: auth.headers() })
      .then((r) => r.json())
      .then((j) => setData(j.data));
  }, [auth]);

  const openDrill = (bucket: string) => {
    fetch(`/api/crm/leads/report/drill?bucket=${encodeURIComponent(bucket)}`, { headers: auth.headers() })
      .then((r) => r.json())
      .then((j) => setDrill({ bucket, rows: j.data ?? [] }));
  };

  if (!data) return <p className="p-4 text-sm text-[var(--text-muted)]">加载线索报表…</p>;

  return (
    <div className="space-y-6 p-4">
      <div>
        <h1 className="text-lg font-semibold">销售线索报表</h1>
        <p className="text-xs text-[var(--text-muted)]">拜访七档漏斗仍在商机大盘，本页只统计线索</p>
      </div>
      <div className="grid gap-3 sm:grid-cols-5">
        {Object.entries(data.summary).map(([k, v]) => (
          <button
            key={k}
            type="button"
            className="rounded border p-3 text-left hover:border-[var(--accent)]"
            style={{ borderColor: "var(--line)" }}
            onClick={() => openDrill(k)}
          >
            <p className="text-xs text-[var(--text-muted)]">{k}</p>
            <p className="text-2xl font-semibold tabular-nums">{v}</p>
          </button>
        ))}
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        {(["stage_distribution", "industry_distribution", "source_distribution"] as const).map((key) => (
          <div key={key} className="rounded border p-3 text-xs" style={{ borderColor: "var(--line)" }}>
            <p className="mb-2 font-medium">
              {key === "stage_distribution" ? "跟进阶段" : key === "industry_distribution" ? "行业" : "来源"}
            </p>
            <ul className="space-y-1">
              {Object.entries(data[key]).map(([k, n]) => (
                <li key={k} className="flex justify-between">
                  <button type="button" className="text-[var(--accent)] underline" onClick={() => openDrill(k)}>
                    {k}
                  </button>
                  <span>{n}</span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded border p-3 text-xs" style={{ borderColor: "var(--line)" }}>
          <p className="mb-2 font-medium">新增线索趋势（按月）</p>
          {data.new_trend.map((p) => (
            <div key={p.month} className="flex justify-between py-0.5">
              <span>{p.month}</span>
              <span>{p.count}</span>
            </div>
          ))}
        </div>
        <div className="rounded border p-3 text-xs" style={{ borderColor: "var(--line)" }}>
          <p className="mb-2 font-medium">线索转化趋势（按月）</p>
          {data.convert_trend.map((p) => (
            <div key={p.month} className="flex justify-between py-0.5">
              <span>{p.month}</span>
              <span>{p.count}</span>
            </div>
          ))}
        </div>
      </div>
      {drill && (
        <div className="rounded border p-3 text-xs" style={{ borderColor: "var(--line)" }}>
          <div className="mb-2 flex justify-between">
            <p className="font-medium">明细 · {drill.bucket}</p>
            <button type="button" onClick={() => setDrill(null)}>关闭</button>
          </div>
          <ul className="space-y-1">
            {drill.rows.map((r) => (
              <li key={r.code}>
                {r.contact_name} · {r.company_name} <span className="font-mono text-[var(--text-muted)]">{r.code}</span>
              </li>
            ))}
            {drill.rows.length === 0 && <li className="text-[var(--text-muted)]">无</li>}
          </ul>
        </div>
      )}
    </div>
  );
}
