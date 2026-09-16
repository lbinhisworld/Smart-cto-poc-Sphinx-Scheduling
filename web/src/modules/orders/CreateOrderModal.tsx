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

  useEffect(() => {
    if (!open || !role) return;
    setErr(null);
    setPick(new Set());
    setLines([]);
    setContractNo("");
    setContracts([]);
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
                        min={0.01}
                        step={1}
                        className="w-20 rounded border px-1 py-0.5 text-right"
                        style={{ borderColor: "var(--line)", background: "var(--bg-body)" }}
                        value={l.qty}
                        onChange={(e) =>
                          updateLine(l.item_code, { qty: Number(e.target.value) || 0 })
                        }
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
            保存后订单为「已确认 / 待排产」(schedule_phase=PENDING)，可在列表「待排产」视图查看。
          </p>
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
