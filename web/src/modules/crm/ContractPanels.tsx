import { useEffect, useState } from "react";
import { requestWithRole } from "../../api/client";
import { renderMoney, renderStatusTag } from "../../ui/cellRenderers";
import { useAuth } from "../../shell/auth";

export type ContractDetail = {
  contract_no: string;
  customer_code: string;
  customer_name: string;
  title: string;
  status: string;
  contract_amount: number;
  received_total: number;
  pending_total: number;
  signed_date: string | null;
  plans: {
    id: number;
    line_no: number;
    milestone: string;
    condition_type: string;
    plan_date: string;
    plan_amount: number;
    status: string;
  }[];
  receipts: {
    id: number;
    receipt_date: string;
    amount: number;
    method: string;
    ref_no: string;
  }[];
  orders: { order_no: string; item_code: string; due_date: string; amount: number; order_status: string }[];
};

type PlanDraft = {
  line_no: number;
  milestone: string;
  condition_type: string;
  plan_date: string;
  plan_amount: string;
};

export function ContractDetailPanel({
  contractNo,
  onOpenOrder,
}: {
  contractNo: string;
  onOpenOrder: (orderNo: string) => void;
}) {
  const auth = useAuth();
  const role = auth.role;
  const [data, setData] = useState<ContractDetail | null>(null);

  useEffect(() => {
    if (!role) return;
    requestWithRole<ContractDetail>(`/api/crm/contracts/${encodeURIComponent(contractNo)}`, role).then(
      setData,
    );
  }, [role, contractNo]);

  if (!data) return <p className="text-xs text-[var(--text-muted)]">加载合同…</p>;

  return (
    <div className="space-y-4 text-sm">
      <section className="rounded-lg border p-3" style={{ borderColor: "var(--line)" }}>
        <p className="font-mono text-base font-semibold">{data.contract_no}</p>
        <p className="mt-1">{data.title}</p>
        <div className="mt-2 flex flex-wrap gap-2 text-xs">
          {renderStatusTag(data.status)}
          <span className="text-[var(--text-muted)]">{data.customer_name}</span>
        </div>
        <dl className="mt-3 grid grid-cols-2 gap-2 text-xs">
          <div>
            <dt className="text-[var(--text-muted)]">合同金额</dt>
            <dd>{renderMoney(data.contract_amount)}</dd>
          </div>
          <div>
            <dt className="text-[var(--text-muted)]">已回款</dt>
            <dd>{renderMoney(data.received_total)}</dd>
          </div>
          <div>
            <dt className="text-[var(--text-muted)]">待回款</dt>
            <dd>{renderMoney(data.pending_total)}</dd>
          </div>
          <div>
            <dt className="text-[var(--text-muted)]">签订日</dt>
            <dd>{data.signed_date ?? "—"}</dd>
          </div>
        </dl>
      </section>

      <section>
        <p className="text-xs font-medium text-[var(--text-muted)]">回款计划</p>
        <table className="mt-2 w-full text-xs">
          <thead className="text-[var(--text-muted)]">
            <tr>
              <th className="py-1 text-left">里程碑</th>
              <th className="text-left">计划日</th>
              <th className="text-right">金额</th>
              <th className="text-left">状态</th>
            </tr>
          </thead>
          <tbody>
            {data.plans.map((p) => (
              <tr key={p.id} className="border-t" style={{ borderColor: "var(--line)" }}>
                <td className="py-1">{p.milestone}</td>
                <td>{p.plan_date}</td>
                <td className="text-right">{renderMoney(p.plan_amount)}</td>
                <td>{p.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section>
        <p className="text-xs font-medium text-[var(--text-muted)]">回款记录</p>
        <ul className="mt-2 space-y-1 text-xs">
          {data.receipts.length === 0 && <li className="text-[var(--text-muted)]">暂无登记</li>}
          {data.receipts.map((r) => (
            <li key={r.id}>
              {r.receipt_date} · {renderMoney(r.amount)} · {r.method} {r.ref_no && `· ${r.ref_no}`}
            </li>
          ))}
        </ul>
      </section>

      <section>
        <p className="text-xs font-medium text-[var(--text-muted)]">关联订单</p>
        <ul className="mt-2 space-y-1 text-xs">
          {data.orders.map((o) => (
            <li key={o.order_no}>
              <button type="button" className="text-[var(--accent)] hover:underline" onClick={() => onOpenOrder(o.order_no)}>
                {o.order_no}
              </button>{" "}
              · {o.item_code} · {renderMoney(o.amount)}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

export function CreateContractPanel({
  customerCode,
  onCreated,
  onCancel,
}: {
  customerCode: string;
  onCreated: (contractNo: string) => void;
  onCancel: () => void;
}) {
  const auth = useAuth();
  const role = auth.role;
  const [title, setTitle] = useState("");
  const [amount, setAmount] = useState("");
  const [signedDate, setSignedDate] = useState("2026-09-15");
  const [plans, setPlans] = useState<PlanDraft[]>([
    { line_no: 1, milestone: "签约预付款", condition_type: "ON_SIGN", plan_date: "2026-09-20", plan_amount: "" },
  ]);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const save = async () => {
    if (!role) return;
    const contractAmount = Number(amount);
    if (!title || !contractAmount) {
      setErr("请填写标题与合同金额");
      return;
    }
    setBusy(true);
    setErr(null);
    try {
      const body = {
        customer_code: customerCode,
        title,
        contract_amount: contractAmount,
        status: "ACTIVE",
        signed_date: signedDate,
        plans: plans.map((p) => ({
          ...p,
          plan_amount: Number(p.plan_amount || 0),
        })),
      };
      const data = await requestWithRole<ContractDetail>("/api/crm/contracts", role, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      onCreated(data.contract_no);
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-3 text-sm">
      {err && <p className="text-xs text-rose-400">{err}</p>}
      <label className="block text-xs">
        <span className="text-[var(--text-muted)]">合同名称</span>
        <input className="mt-1 w-full rounded border px-2 py-1" value={title} onChange={(e) => setTitle(e.target.value)} />
      </label>
      <label className="block text-xs">
        <span className="text-[var(--text-muted)]">合同金额</span>
        <input
          type="number"
          className="mt-1 w-full rounded border px-2 py-1"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
        />
      </label>
      <label className="block text-xs">
        <span className="text-[var(--text-muted)]">签订日</span>
        <input type="date" className="mt-1 w-full rounded border px-2 py-1" value={signedDate} onChange={(e) => setSignedDate(e.target.value)} />
      </label>
      <p className="text-xs font-medium text-[var(--text-muted)]">回款计划（合计须等于合同金额）</p>
      {plans.map((p, idx) => (
        <div key={p.line_no} className="grid gap-2 rounded border p-2 text-xs" style={{ borderColor: "var(--line)" }}>
          <input
            placeholder="里程碑"
            value={p.milestone}
            onChange={(e) =>
              setPlans((prev) => prev.map((x, i) => (i === idx ? { ...x, milestone: e.target.value } : x)))
            }
          />
          <div className="grid grid-cols-2 gap-2">
            <input type="date" value={p.plan_date} onChange={(e) => setPlans((prev) => prev.map((x, i) => (i === idx ? { ...x, plan_date: e.target.value } : x)))} />
            <input
              type="number"
              placeholder="计划金额"
              value={p.plan_amount}
              onChange={(e) => setPlans((prev) => prev.map((x, i) => (i === idx ? { ...x, plan_amount: e.target.value } : x)))}
            />
          </div>
        </div>
      ))}
      <button
        type="button"
        className="text-xs text-[var(--accent)]"
        onClick={() =>
          setPlans((prev) => [
            ...prev,
            {
              line_no: prev.length + 1,
              milestone: "",
              condition_type: "CUSTOM",
              plan_date: signedDate,
              plan_amount: "",
            },
          ])
        }
      >
        + 增加计划行
      </button>
      <div className="flex gap-2 pt-2">
        <button type="button" className="rounded border px-3 py-1 text-xs" onClick={onCancel}>
          取消
        </button>
        <button type="button" disabled={busy} className="rounded bg-[var(--accent)] px-3 py-1 text-xs text-slate-950" onClick={() => void save()}>
          保存合同
        </button>
      </div>
    </div>
  );
}
