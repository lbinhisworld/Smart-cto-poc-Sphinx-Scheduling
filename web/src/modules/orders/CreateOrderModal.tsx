import { useEffect, useMemo, useState } from "react";
import { requestWithRole } from "../../api/client";
import { formatUnit } from "../../utils/uomDisplay";
import { useAuth } from "../../shell/auth";

type Customer = { code: string; name: string; owner_sales: string };
type ContractOption = { contract_no: string; title: string; status: string; pending_total: number };
type CatalogItem = {
  item_code: string;
  item_name: string;
  group_label?: string;
};

type DraftLine = {
  item_code: string;
  item_name: string;
  qty: number;
  unit: string;
};

type CtpLineResult = {
  item_code: string;
  product_label: string;
  qty: number;
  unit: string;
  feasible: boolean;
  plan_end: string | null;
  earliest_delivery: string | null;
  red_conflicts: { code: string; message: string }[];
  sales?: { headline?: string };
};

type CtpOrderResult = {
  feasible: boolean;
  requested_due: string;
  plan_end: string | null;
  earliest_delivery: string | null;
  note?: string;
  lines: CtpLineResult[];
  sales?: { headline?: string; status?: string; can_meet_due_date?: boolean };
};

type Props = {
  open: boolean;
  onClose: () => void;
  onCreated: (orderNo: string) => void;
};

export function CreateOrderModal({ open, onClose, onCreated }: Props) {
  const auth = useAuth();
  const role = auth.role;
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [catalog, setCatalog] = useState<CatalogItem[]>([]);
  const [customerCode, setCustomerCode] = useState("");
  const [contractNo, setContractNo] = useState("");
  const [contracts, setContracts] = useState<ContractOption[]>([]);
  const [dueDate, setDueDate] = useState("2026-09-28");
  const [pick, setPick] = useState<Set<string>>(new Set());
  const [lines, setLines] = useState<DraftLine[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [filter, setFilter] = useState("");
  const [ctpBusy, setCtpBusy] = useState(false);
  const [ctp, setCtp] = useState<CtpOrderResult | null>(null);
  const [ctpStamp, setCtpStamp] = useState<string | null>(null);

  useEffect(() => {
    if (!open || !role) return;
    setErr(null);
    setPick(new Set());
    setLines([]);
    setContractNo("");
    setContracts([]);
    setCtp(null);
    setCtpStamp(null);
    requestWithRole<Customer[]>("/api/crm/customers", role).then(setCustomers);
    fetch("/api/bom")
      .then((r) => r.json())
      .then((j) => setCatalog(j.data?.items ?? []));
  }, [open, role]);

  useEffect(() => {
    if (!role || !customerCode) {
      setContracts([]);
      setContractNo("");
      return;
    }
    requestWithRole<ContractOption[]>(
      `/api/crm/contracts?customer_code=${encodeURIComponent(customerCode)}&status=ACTIVE`,
      role,
    ).then((list) => {
      setContracts(list);
      setContractNo(list[0]?.contract_no ?? "");
    });
  }, [role, customerCode]);

  const filteredCatalog = useMemo(() => {
    const q = filter.trim().toLowerCase();
    if (!q) return catalog;
    return catalog.filter(
      (i) =>
        i.item_code.toLowerCase().includes(q) ||
        i.item_name.toLowerCase().includes(q),
    );
  }, [catalog, filter]);

  const addPicked = () => {
    const next: DraftLine[] = [...lines];
    for (const code of pick) {
      if (next.some((l) => l.item_code === code)) continue;
      const item = catalog.find((c) => c.item_code === code);
      if (!item) continue;
      next.push({
        item_code: item.item_code,
        item_name: item.item_name,
        qty: 1,
        unit: "BOX",
      });
    }
    setLines(next);
    setPick(new Set());
  };

  const updateLine = (code: string, patch: Partial<DraftLine>) => {
    setLines((prev) => prev.map((l) => (l.item_code === code ? { ...l, ...patch } : l)));
  };

  const removeLine = (code: string) => {
    setLines((prev) => prev.filter((l) => l.item_code !== code));
  };

  const draftStamp = useMemo(
    () => JSON.stringify({ dueDate, lines: lines.map((l) => ({ item_code: l.item_code, qty: l.qty, unit: l.unit })) }),
    [dueDate, lines],
  );
  const ctpStale = Boolean(ctp && ctpStamp && ctpStamp !== draftStamp);

  const runCtp = async () => {
    if (!role) return;
    if (lines.length === 0) {
      setErr("请先加入明细再预检");
      return;
    }
    if (lines.some((l) => !Number.isInteger(l.qty) || l.qty < 1)) {
      setErr("数量必须为正整数（盒/版/枚均为整数单位）");
      return;
    }
    setCtpBusy(true);
    setErr(null);
    try {
      const r = await fetch("/api/crm/ctp?today=2026-09-15", {
        method: "POST",
        headers: { ...auth.headers(), "Content-Type": "application/json" },
        body: JSON.stringify({
          due_date: dueDate,
          lines: lines.map((l) => ({ item_code: l.item_code, qty: l.qty, unit: l.unit })),
        }),
      });
      const j = await r.json();
      if (!r.ok || j.code !== 0) throw new Error(j.detail || j.message || "预检失败");
      setCtp(j.data as CtpOrderResult);
      setCtpStamp(draftStamp);
    } catch (e) {
      setErr(String(e));
    } finally {
      setCtpBusy(false);
    }
  };

  const save = async () => {
    if (!role) return;
    if (!customerCode) {
      setErr("请选择关联客户");
      return;
    }
    if (!contractNo) {
      setErr("请选择关联合同（需 ACTIVE 合同）");
      return;
    }
    if (lines.length === 0) {
      setErr("请添加至少一行产品");
      return;
    }
    if (lines.some((l) => !Number.isInteger(l.qty) || l.qty < 1)) {
      setErr("数量必须为正整数（盒/版/枚均为整数单位）");
      return;
    }
    setBusy(true);
    setErr(null);
    try {
      const r = await fetch("/api/mis/orders?today=2026-09-15", {
        method: "POST",
        headers: {
          ...auth.headers(),
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          customer_code: customerCode,
          contract_no: contractNo,
          due_date: dueDate,
          sales_name: auth.userName,
          lines: lines.map((l) => ({
            item_code: l.item_code,
            qty: l.qty,
            unit: l.unit,
          })),
        }),
      });
      const text = await r.text();
      const j = text ? JSON.parse(text) : {};
      if (!r.ok || j.code !== 0) throw new Error(j.detail || j.message || text);
      onCreated(j.data.order_no as string);
      onClose();
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/55 p-4">
      <div
        className="flex max-h-[90vh] w-full max-w-3xl flex-col overflow-hidden rounded-lg border shadow-xl"
        style={{ borderColor: "var(--line)", background: "var(--bg-card)" }}
      >
        <div className="flex items-center justify-between border-b px-4 py-3" style={{ borderColor: "var(--line)" }}>
          <h3 className="font-semibold">新建销售订单</h3>
          <button type="button" className="text-sm text-[var(--text-muted)]" onClick={onClose}>
            关闭
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto p-4 text-sm">
          {err && <p className="mb-3 text-xs text-rose-400">{err}</p>}

          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block text-xs">
              <span className="text-[var(--text-muted)]">关联客户 *</span>
              <select
                className="mt-1 w-full rounded border px-2 py-1.5"
                style={{ borderColor: "var(--line)", background: "var(--bg-body)" }}
                value={customerCode}
                onChange={(e) => setCustomerCode(e.target.value)}
              >
                <option value="">请选择客户</option>
                {customers.map((c) => (
                  <option key={c.code} value={c.code}>
                    {c.code} · {c.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-xs">
              <span className="text-[var(--text-muted)]">关联合同 *</span>
              <select
                className="mt-1 w-full rounded border px-2 py-1.5"
                style={{ borderColor: "var(--line)", background: "var(--bg-body)" }}
                value={contractNo}
                disabled={!customerCode}
                onChange={(e) => setContractNo(e.target.value)}
              >
                <option value="">请选择合同</option>
                {contracts.map((c) => (
                  <option key={c.contract_no} value={c.contract_no}>
                    {c.contract_no} · {c.title}
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-xs sm:col-span-2">
              <span className="text-[var(--text-muted)]">交期 *</span>
              <input
                type="date"
                className="mt-1 w-full rounded border px-2 py-1.5"
                style={{ borderColor: "var(--line)", background: "var(--bg-body)" }}
                value={dueDate}
                onChange={(e) => setDueDate(e.target.value)}
              />
            </label>
          </div>

          <p className="mt-4 text-xs font-medium text-[var(--text-muted)]">产品库（多选后加入下方明细）</p>
          <input
            className="mt-1 w-full rounded border px-2 py-1 text-xs"
            style={{ borderColor: "var(--line)", background: "var(--bg-body)" }}
            placeholder="筛选品号 / 名称"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          />
          <div
            className="mt-2 max-h-36 overflow-y-auto rounded border text-xs"
            style={{ borderColor: "var(--line)" }}
          >
            <table className="w-full">
              <thead className="sticky top-0 bg-[var(--table-head)] text-[var(--text-muted)]">
                <tr>
                  <th className="w-8 px-2 py-1" />
                  <th className="py-1 text-left">品号</th>
                  <th className="py-1 text-left">名称</th>
                  <th className="py-1 text-left">工艺组</th>
                </tr>
              </thead>
              <tbody>
                {filteredCatalog.map((item) => (
                  <tr key={item.item_code} className="border-t" style={{ borderColor: "var(--line)" }}>
                    <td className="px-2 py-1">
                      <input
                        type="checkbox"
                        checked={pick.has(item.item_code)}
                        onChange={() => {
                          setPick((prev) => {
                            const n = new Set(prev);
                            if (n.has(item.item_code)) n.delete(item.item_code);
                            else n.add(item.item_code);
                            return n;
                          });
                        }}
                      />
                    </td>
                    <td className="font-mono text-[var(--accent)]">{item.item_code}</td>
                    <td>{item.item_name}</td>
                    <td className="text-[var(--text-muted)]">{item.group_label ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <button
            type="button"
            className="mt-2 rounded border px-3 py-1 text-xs"
            style={{ borderColor: "var(--line)" }}
            disabled={pick.size === 0}
            onClick={addPicked}
          >
            加入明细 ({pick.size})
          </button>

          <p className="mt-4 text-xs font-medium text-[var(--text-muted)]">订单明细（子表）</p>
          <div className="mt-2 overflow-x-auto rounded border" style={{ borderColor: "var(--line)" }}>
            <table className="w-full text-xs">
              <thead className="bg-[var(--table-head)] text-[var(--text-muted)]">
                <tr>
                  <th className="px-2 py-1 text-left">品项</th>
                  <th className="text-right">数量</th>
                  <th className="text-left">单位</th>
                  <th className="w-12" />
                </tr>
              </thead>
              <tbody>
                {lines.map((l) => (
                  <tr key={l.item_code} className="border-t" style={{ borderColor: "var(--line)" }}>
                    <td className="px-2 py-1">
                      <span className="font-mono">{l.item_code}</span> {l.item_name}
                    </td>
                    <td className="py-1 text-right">
                      <input
                        type="number"
                        min={1}
                        step={1}
                        inputMode="numeric"
                        className="w-20 rounded border px-1 py-0.5 text-right"
                        style={{ borderColor: "var(--line)", background: "var(--bg-body)" }}
                        value={l.qty || ""}
                        onChange={(e) => {
                          const n = Number.parseInt(e.target.value, 10);
                          updateLine(l.item_code, {
                            qty: Number.isFinite(n) && n > 0 ? n : 0,
                          });
                        }}
                      />
                    </td>
                    <td className="py-1">
                      <select
                        className="rounded border px-1 py-0.5"
                        style={{ borderColor: "var(--line)", background: "var(--bg-body)" }}
                        value={l.unit}
                        onChange={(e) => updateLine(l.item_code, { unit: e.target.value })}
                      >
                        {["BOX", "PCS", "BOARD", "PACK"].map((u) => (
                          <option key={u} value={u}>
                            {formatUnit(u)}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="py-1 text-center">
                      <button
                        type="button"
                        className="text-rose-400"
                        onClick={() => removeLine(l.item_code)}
                      >
                        删
                      </button>
                    </td>
                  </tr>
                ))}
                {lines.length === 0 && (
                  <tr>
                    <td colSpan={4} className="px-2 py-6 text-center text-[var(--text-muted)]">
                      从上方产品库勾选后点击「加入明细」
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          <p className="mt-2 text-[10px] text-[var(--text-muted)]">
            保存后订单为「已确认 / 待排产」(schedule_phase=PENDING)，可在列表「待排产」视图查看。预检不落库、不拦截保存。
          </p>

          <div className="mt-4 rounded border px-3 py-2" style={{ borderColor: "var(--line)" }}>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-xs font-medium">CTP 预检测</p>
              <button
                type="button"
                disabled={ctpBusy || lines.length === 0}
                className="rounded border px-3 py-1 text-xs disabled:opacity-40"
                style={{ borderColor: "var(--line)" }}
                onClick={() => void runCtp()}
              >
                {ctpBusy ? "试算中…" : "CTP 预检测"}
              </button>
            </div>
            <p className="mt-1 text-[10px] text-[var(--text-muted)]">
              全部明细 + 整单交期一次倒排（同行组共享产能），可反复改量后再检。
            </p>
            {ctp && (
              <div className="mt-2 text-xs">
                {ctpStale && (
                  <p className="mb-1 text-amber-300">明细或交期已改，上次结果已过期，请再预检。</p>
                )}
                <p className={ctp.feasible ? "text-emerald-300" : "text-rose-300"}>
                  {ctp.sales?.headline || (ctp.feasible ? "整单可行" : "整单交期有风险")}
                </p>
                <p className="mt-1 text-[var(--text-muted)]">
                  目标 {ctp.requested_due}
                  {ctp.plan_end ? ` · 最晚计划完工 ${ctp.plan_end}` : ""}
                  {ctp.earliest_delivery ? ` · 建议不早于 ${ctp.earliest_delivery}` : ""}
                </p>
                <table className="mt-2 w-full text-[11px]">
                  <thead className="text-[var(--text-muted)]">
                    <tr>
                      <th className="py-1 text-left">品项</th>
                      <th className="text-right">数量</th>
                      <th className="text-left">结论</th>
                      <th className="text-left">计划完工</th>
                    </tr>
                  </thead>
                  <tbody>
                    {ctp.lines.map((ln) => (
                      <tr key={ln.item_code} className="border-t" style={{ borderColor: "var(--line)" }}>
                        <td className="py-1">{ln.product_label || ln.item_code}</td>
                        <td className="text-right tabular-nums">
                          {ln.qty}
                          {formatUnit(ln.unit)}
                        </td>
                        <td className={ln.feasible ? "text-emerald-300" : "text-rose-300"}>
                          {ln.feasible ? "可满足" : ln.sales?.headline || "交期不足"}
                        </td>
                        <td>{ln.plan_end ?? ln.earliest_delivery ?? "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>

        <div className="flex justify-end gap-2 border-t px-4 py-3" style={{ borderColor: "var(--line)" }}>
          <button type="button" className="rounded border px-3 py-1.5 text-xs" style={{ borderColor: "var(--line)" }} onClick={onClose}>
            取消
          </button>
          <button
            type="button"
            disabled={busy}
            className="rounded bg-[var(--accent)] px-4 py-1.5 text-xs font-medium text-slate-950 disabled:opacity-40"
            onClick={() => void save()}
          >
            保存订单
          </button>
        </div>
      </div>
    </div>
  );
}
