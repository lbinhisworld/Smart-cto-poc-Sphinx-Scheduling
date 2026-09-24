import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useGuidedDemoSeedReload } from "../../hooks/guidedDemoSeed";
import { useAuth } from "../../shell/auth";

type PlanRow = {
  order_no: string;
  contract_no: string;
  customer: string;
  sales_name: string;
  line_no: number;
  milestone: string;
  plan_amount: number;
  plan_date: string;
  actual_amount: number;
  actual_date: string | null;
  status_label: string;
  condition_note?: string;
  kingdee_refs?: string[];
};

export function PaymentsPage() {
  const auth = useAuth();
  const demoSeedReload = useGuidedDemoSeedReload("contract_payment");
  const [rows, setRows] = useState<PlanRow[]>([]);

  useEffect(() => {
    fetch("/api/crm/payment-plans?today=2026-09-15", { headers: auth.headers() })
      .then((r) => r.json())
      .then((j) => setRows(j.data ?? []));
  }, [auth, demoSeedReload]);

  return (
    <div className="p-4">
      <h1 className="text-lg font-semibold">回款计划</h1>
      <p className="mt-1 text-xs text-[var(--text-muted)]">
        与合同计划同一批行 · 实际回款来自金蝶同步 · 订单详情「回款信息」页签数据一致
      </p>
      <div className="mt-4 overflow-auto rounded border" style={{ borderColor: "var(--line)" }}>
        <table className="min-w-full text-left text-xs">
          <thead className="text-[var(--text-muted)]">
            <tr>
              {["订单", "客户", "期数", "计划金额", "计划日期", "实际金额", "实际日期", "状态", "金蝶单号"].map((h) => (
                <th key={h} className="px-2 py-2">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i} className="border-t" style={{ borderColor: "var(--line)" }}>
                <td className="px-2 py-2">
                  <Link to={`/orders?open=${encodeURIComponent(r.order_no)}`} className="font-mono text-[var(--accent)]">
                    {r.order_no}
                  </Link>
                </td>
                <td className="px-2 py-2">{r.customer}</td>
                <td className="px-2 py-2">{r.milestone || r.line_no}</td>
                <td className="px-2 py-2 tabular-nums">{r.plan_amount}</td>
                <td className="px-2 py-2">{r.plan_date}</td>
                <td className="px-2 py-2 tabular-nums">{r.actual_amount || "—"}</td>
                <td className="px-2 py-2">{r.actual_date ?? "—"}</td>
                <td className="px-2 py-2">{r.status_label}</td>
                <td className="px-2 py-2 font-mono text-[10px]">{(r.kingdee_refs ?? []).join(", ") || "—"}</td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={9} className="px-2 py-6 text-center text-[var(--text-muted)]">
                  暂无挂合同的订单回款计划
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
