import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { requestWithRole } from "../../api/client";
import { renderMoney, renderStatusTag } from "../../ui/cellRenderers";
import { formatUnit } from "../../utils/uomDisplay";
import { useGuidedDemoSeedReload } from "../../hooks/guidedDemoSeed";
import { useAuth } from "../../shell/auth";

type QuoteLine = {
  item_code?: string | null;
  item_name: string;
  image_ref?: string;
  spec?: string;
  process_label?: string;
  category?: string;
  unit_price_tax_in: number | null;
  moq?: number | null;
  qty: number;
  uom: string;
  mold_fee: number | null;
  rebate_qty?: number | null;
  rebate_uom?: string | null;
  note?: string;
  line_total?: number | null;
};

type Quote = {
  code: string;
  customer_code: string;
  sample_code?: string | null;
  total_amount: number | null;
  status: string;
  owner_sales: string;
  tax_rate?: number;
  valid_until?: string | null;
  contract_no?: string | null;
  order_no?: string | null;
  note?: string;
  lines: QuoteLine[];
};

type Customer = { code: string; name: string; owner_sales: string };
type CatalogItem = { item_code: string; item_name: string; group_label?: string };
type ContractOption = { contract_no: string; title: string; status: string };

const QUOTE_UI_TABS = ["全部", "未发出", "谈判中", "已确认", "需重新报价"] as const;

function quoteUiTab(q: Quote): (typeof QUOTE_UI_TABS)[number] {
  const note = q.note || "";
  const st = (q.status || "").toUpperCase();
  if (note.includes("需重新报价")) return "需重新报价";
  if (st === "DRAFT") return "未发出";
  if (st === "SUBMITTED") return "谈判中";
  if (st === "APPROVED" || st === "CONVERTED") return "已确认";
  return "未发出";
}

const PROCESS_FROM_GROUP: Record<string, string> = {
  手工组: "手工",
  模具组: "模具",
  浇注组: "浇注",
};

function emptyLine(): QuoteLine {
  return {
    item_code: "",
    item_name: "",
    image_ref: "",
    spec: "",
    process_label: "",
    category: "",
    unit_price_tax_in: 0,
    moq: null,
    qty: 1,
    uom: "BOX",
    mold_fee: 0,
    rebate_qty: null,
    rebate_uom: "BOX",
    note: "",
  };
}

export function QuotesPage() {
  const auth = useAuth();
  const role = auth.role;
  const [allRows, setAllRows] = useState<Quote[]>([]);
  const [uiTab, setUiTab] = useState<(typeof QUOTE_UI_TABS)[number]>("全部");
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState<Quote | "new" | null>(null);

  const tabCounts = useMemo(() => {
    const c: Record<string, number> = Object.fromEntries(QUOTE_UI_TABS.map((t) => [t, 0]));
    for (const q of allRows) {
      c["全部"] += 1;
      const t = quoteUiTab(q);
      c[t] += 1;
    }
    return c;
  }, [allRows]);

  const rows = useMemo(() => {
    if (uiTab === "全部") return allRows;
    return allRows.filter((q) => quoteUiTab(q) === uiTab);
  }, [allRows, uiTab]);

  const demoSeedReload = useGuidedDemoSeedReload("quote");
  const load = useCallback(() => {
    if (!role) return;
    setError(null);
    requestWithRole<Quote[]>("/api/crm/quotes", role)
      .then(setAllRows)
      .catch((e) => setError(String(e)));
  }, [role]);

  useEffect(() => {
    load();
  }, [load, demoSeedReload]);

  return (
    <div className="px-6 py-4">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h2 className="text-lg font-semibold">报价</h2>
          <p className="text-xs text-[var(--text-muted)]">
            一单一议 · 11 列手工填报 · 批准后转销售订单（V1 不做自动计价）
          </p>
        </div>
        <div className="flex gap-2">
          <Link to="/orders" className="rounded border px-2 py-1 text-xs" style={{ borderColor: "var(--line)" }}>
            销售订单
          </Link>
          {(role === "GM" || role === "SALES" || role === "SALES_MGR") && (
            <button
              type="button"
              className="rounded bg-[var(--accent)] px-2 py-1 text-xs font-medium text-slate-950"
              onClick={() => setOpen("new")}
            >
              新建报价
            </button>
          )}
        </div>
      </div>
      {error && <p className="mt-2 text-xs text-rose-400">{error}</p>}
      <div className="mt-3 flex flex-wrap gap-2 text-xs">
        {QUOTE_UI_TABS.map((t) => (
          <button
            key={t}
            type="button"
            className={`rounded-full border px-2 py-0.5 ${uiTab === t ? "border-[var(--accent)] text-[var(--accent)]" : ""}`}
            style={{ borderColor: "var(--line)" }}
            onClick={() => setUiTab(t)}
          >
            {t} ({tabCounts[t] ?? 0})
          </button>
        ))}
      </div>
      <div className="mt-4 overflow-x-auto rounded-lg border" style={{ borderColor: "var(--line)" }}>
        <table className="w-full min-w-[880px] border-collapse text-xs">
          <thead className="bg-[var(--table-head)] text-[var(--text-muted)]">
            <tr>
              <th className="px-3 py-2 text-left">报价号</th>
              <th className="px-3 py-2 text-left">客户</th>
              <th className="px-3 py-2 text-left">状态</th>
              <th className="px-3 py-2 text-right">含税合计</th>
              <th className="px-3 py-2 text-left">销售</th>
              <th className="px-3 py-2 text-left">订单</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((q) => (
              <tr
                key={q.code}
                className="cursor-pointer border-t hover:bg-[var(--table-row-hover)]"
                style={{ borderColor: "var(--line)" }}
                onClick={() => setOpen(q)}
              >
                <td className="px-3 py-2 font-mono text-[var(--accent)]">{q.code}</td>
                <td className="px-3 py-2">{q.customer_code}</td>
                <td className="px-3 py-2">{renderStatusTag(q.status)}</td>
                <td className="px-3 py-2 text-right">{renderMoney(q.total_amount)}</td>
                <td className="px-3 py-2">{q.owner_sales || "—"}</td>
                <td className="px-3 py-2 font-mono">{q.order_no ?? "—"}</td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={6} className="px-3 py-8 text-center text-[var(--text-muted)]">
                  暂无报价
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      {open && (
        <QuoteDrawer
          initial={open === "new" ? null : open}
          onClose={() => setOpen(null)}
          onChanged={() => {
            load();
            setOpen(null);
          }}
        />
      )}
    </div>
  );
}

function QuoteDrawer({
  initial,
  onClose,
  onChanged,
}: {
  initial: Quote | null;
  onClose: () => void;
  onChanged: () => void;
}) {
  const auth = useAuth();
  const role = auth.role;
  const canWrite = role === "GM" || role === "SALES" || role === "SALES_MGR";
  const canApprove = role === "GM" || role === "SALES_MGR";
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [catalog, setCatalog] = useState<CatalogItem[]>([]);
  const [contracts, setContracts] = useState<ContractOption[]>([]);
  const [code, setCode] = useState(initial?.code ?? "");
  const [status, setStatus] = useState(initial?.status ?? "DRAFT");
  const [customerCode, setCustomerCode] = useState(initial?.customer_code ?? "");
  const [note, setNote] = useState(initial?.note ?? "");
  const [lines, setLines] = useState<QuoteLine[]>(
    initial?.lines?.length ? initial.lines.map((l) => ({ ...emptyLine(), ...l })) : [emptyLine()],
  );
  const [contractNo, setContractNo] = useState("");
  const [dueDate, setDueDate] = useState("2026-10-01");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const draft = status === "DRAFT";

  useEffect(() => {
    if (!role) return;
    requestWithRole<Customer[]>("/api/crm/customers", role).then(setCustomers);
    fetch("/api/bom")
      .then((r) => r.json())
      .then((j) => setCatalog(j.data?.items ?? []));
  }, [role]);

  useEffect(() => {
    if (!role || !customerCode) {
      setContracts([]);
      return;
    }
    requestWithRole<ContractOption[]>(
      `/api/crm/contracts?customer_code=${encodeURIComponent(customerCode)}&status=ACTIVE`,
      role,
    ).then(setContracts);
  }, [role, customerCode]);

  const total = useMemo(
    () =>
      lines.reduce((s, l) => s + (Number(l.qty) || 0) * (Number(l.unit_price_tax_in) || 0) + (Number(l.mold_fee) || 0), 0),
    [lines],
  );

  const patchLine = (i: number, patch: Partial<QuoteLine>) => {
    setLines((prev) => prev.map((l, idx) => (idx === i ? { ...l, ...patch } : l)));
  };

  const pickItem = (i: number, itemCode: string) => {
    const item = catalog.find((c) => c.item_code === itemCode);
    patchLine(i, {
      item_code: itemCode,
      item_name: item?.item_name ?? "",
      process_label: PROCESS_FROM_GROUP[item?.group_label ?? ""] || item?.group_label || "",
    });
  };

  const payloadLines = () =>
    lines.map((l) => ({
      item_code: l.item_code || null,
      item_name: l.item_name,
      image_ref: l.image_ref || "",
      spec: l.spec || "",
      process_label: l.process_label || "",
      category: l.category || "",
      unit_price_tax_in: Number(l.unit_price_tax_in) || 0,
      moq: l.moq == null || l.moq === ("" as unknown) ? null : Number(l.moq),
      qty: Number(l.qty) || 0,
      uom: l.uom || "BOX",
      mold_fee: Number(l.mold_fee) || 0,
      rebate_qty: l.rebate_qty == null ? null : Number(l.rebate_qty),
      rebate_uom: l.rebate_uom || null,
      note: l.note || "",
    }));

  const save = async () => {
    if (!role) return;
    if (!customerCode) {
      setErr("请选择客户");
      return;
    }
    setBusy(true);
    setErr(null);
    try {
      if (!code) {
        const data = await requestWithRole<Quote>("/api/crm/quotes", role, {
          method: "POST",
          body: JSON.stringify({
            customer_code: customerCode,
            owner_sales: auth.userName,
            note,
            lines: payloadLines(),
          }),
        });
        setCode(data.code);
        setStatus(data.status);
      } else {
        await requestWithRole<Quote>(`/api/crm/quotes/${encodeURIComponent(code)}`, role, {
          method: "PUT",
          body: JSON.stringify({
            customer_code: customerCode,
            note,
            lines: payloadLines(),
          }),
        });
      }
      onChanged();
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  };

  const act = async (path: string) => {
    if (!role || !code) return;
    setBusy(true);
    setErr(null);
    try {
      const data = await requestWithRole<Quote>(path, role, { method: "POST" });
      setStatus(data.status);
      onChanged();
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  };

  const convert = async () => {
    if (!role || !code) return;
    if (!contractNo) {
      setErr("转订单需选择 ACTIVE 合同");
      return;
    }
    setBusy(true);
    setErr(null);
    try {
      await requestWithRole("/api/mis/orders/from-quote?today=2026-09-15", role, {
        method: "POST",
        body: JSON.stringify({
          quote_code: code,
          contract_no: contractNo,
          due_date: dueDate,
          sales_name: auth.userName,
        }),
      });
      onChanged();
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[80] flex justify-end bg-black/50" role="dialog" onClick={onClose}>
      <div
        className="flex h-full w-full max-w-6xl flex-col overflow-hidden shadow-2xl"
        style={{ background: "var(--bg-card)" }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between border-b px-4 py-3" style={{ borderColor: "var(--line)" }}>
          <div>
            <p className="font-semibold">{code || "新建报价"}</p>
            <p className="text-xs text-[var(--text-muted)]">产品报价表 · 含税单价 · 达计量仅记录</p>
            {initial && (
              <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-xs md:grid-cols-4">
                <div>
                  <dt className="text-[var(--text-muted)]">客户</dt>
                  <dd>{customers.find((c) => c.code === customerCode)?.name ?? customerCode}</dd>
                </div>
                <div>
                  <dt className="text-[var(--text-muted)]">关联打样</dt>
                  <dd>{initial.sample_code ?? "—"}</dd>
                </div>
                <div>
                  <dt className="text-[var(--text-muted)]">税率</dt>
                  <dd>{initial.tax_rate != null ? `${Math.round(Number(initial.tax_rate) * 100)}%` : "13%"}</dd>
                </div>
                <div>
                  <dt className="text-[var(--text-muted)]">有效期至</dt>
                  <dd>{initial.valid_until ?? "—"}</dd>
                </div>
                <div>
                  <dt className="text-[var(--text-muted)]">业务员</dt>
                  <dd>{initial.owner_sales}</dd>
                </div>
                <div>
                  <dt className="text-[var(--text-muted)]">合同/订单</dt>
                  <dd>
                    {initial.contract_no ?? "—"} / {initial.order_no ?? "—"}
                  </dd>
                </div>
              </dl>
            )}
          </div>
          <div className="flex items-center gap-2">
            {code && (
              <>
                <a
                  href={`/api/crm/quotes/${encodeURIComponent(code)}/print`}
                  target="_blank"
                  rel="noreferrer"
                  className="rounded border px-2 py-1 text-xs text-[var(--accent)]"
                  style={{ borderColor: "var(--line)" }}
                >
                  打印 HTML
                </a>
                <a
                  href={`/api/crm/quotes/${encodeURIComponent(code)}/pdf`}
                  className="rounded border px-2 py-1 text-xs text-[var(--accent)]"
                  style={{ borderColor: "var(--line)" }}
                >
                  下载 PDF
                </a>
              </>
            )}
            <button type="button" className="text-sm text-[var(--text-muted)]" onClick={onClose}>
              关闭
            </button>
          </div>
        </div>
        <div className="min-h-0 flex-1 overflow-auto p-4 text-sm">
          {err && <p className="mb-2 text-xs text-rose-400">{err}</p>}
          <div className="grid gap-3 sm:grid-cols-3">
            <label className="text-xs">
              <span className="text-[var(--text-muted)]">客户 *</span>
              <select
                className="mt-1 w-full rounded border px-2 py-1.5"
                style={{ borderColor: "var(--line)", background: "var(--bg-body)" }}
                value={customerCode}
                disabled={!draft}
                onChange={(e) => setCustomerCode(e.target.value)}
              >
                <option value="">请选择</option>
                {customers.map((c) => (
                  <option key={c.code} value={c.code}>
                    {c.code} · {c.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-xs">
              <span className="text-[var(--text-muted)]">状态</span>
              <div className="mt-1.5">{renderStatusTag(status)}</div>
            </label>
            <label className="text-xs">
              <span className="text-[var(--text-muted)]">合计（含税+模具费）</span>
              <div className="mt-1.5">{renderMoney(total)}</div>
            </label>
            <label className="text-xs sm:col-span-3">
              <span className="text-[var(--text-muted)]">备注</span>
              <input
                className="mt-1 w-full rounded border px-2 py-1.5"
                style={{ borderColor: "var(--line)", background: "var(--bg-body)" }}
                value={note}
                disabled={!draft}
                onChange={(e) => setNote(e.target.value)}
              />
            </label>
          </div>

          <p className="mt-4 text-xs font-medium text-[var(--text-muted)]">产品报价表明细</p>
          <div className="mt-2 overflow-x-auto rounded border" style={{ borderColor: "var(--line)" }}>
            <table className="w-full min-w-[1400px] text-[11px]">
              <thead className="bg-[var(--table-head)] text-[var(--text-muted)]">
                <tr>
                  <th className="px-1 py-1.5 text-left">产品编号</th>
                  <th className="text-left">产品样图</th>
                  <th className="text-left">产品名称</th>
                  <th className="text-left">规格</th>
                  <th className="text-left">工艺</th>
                  <th className="text-left">归类</th>
                  <th className="text-right">含税单价</th>
                  <th className="text-right">起订量 / 需求量</th>
                  <th className="text-right">模具费用</th>
                  <th className="text-right">达计量 / 返还</th>
                  <th className="text-left">备注</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {lines.map((l, i) => (
                  <tr key={i} className="border-t align-top" style={{ borderColor: "var(--line)" }}>
                    <td className="px-1 py-1">
                      <select
                        className="w-24 rounded border px-1 py-0.5"
                        style={{ borderColor: "var(--line)", background: "var(--bg-body)" }}
                        value={l.item_code ?? ""}
                        disabled={!draft}
                        onChange={(e) => pickItem(i, e.target.value)}
                      >
                        <option value="">新品</option>
                        {catalog.map((it) => (
                          <option key={it.item_code} value={it.item_code}>
                            {it.item_code}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="py-1">
                      {l.image_ref ? (
                        <img src={l.image_ref} alt="" className="h-10 w-10 rounded object-cover" />
                      ) : (
                        <span className="text-[var(--text-muted)]">—</span>
                      )}
                      {draft && (
                        <input
                          type="file"
                          accept="image/*"
                          className="mt-1 block w-24 text-[10px]"
                          onChange={(e) => {
                            const f = e.target.files?.[0];
                            if (!f) return;
                            const reader = new FileReader();
                            reader.onload = () => patchLine(i, { image_ref: String(reader.result || "") });
                            reader.readAsDataURL(f);
                          }}
                        />
                      )}
                    </td>
                    <td className="py-1">
                      <input
                        className="w-28 rounded border px-1 py-0.5"
                        style={{ borderColor: "var(--line)", background: "var(--bg-body)" }}
                        value={l.item_name}
                        disabled={!draft}
                        onChange={(e) => patchLine(i, { item_name: e.target.value })}
                      />
                    </td>
                    <td className="py-1">
                      <input
                        className="w-28 rounded border px-1 py-0.5"
                        style={{ borderColor: "var(--line)", background: "var(--bg-body)" }}
                        value={l.spec ?? ""}
                        disabled={!draft}
                        onChange={(e) => patchLine(i, { spec: e.target.value })}
                      />
                    </td>
                    <td className="py-1">
                      <input
                        className="w-16 rounded border px-1 py-0.5"
                        style={{ borderColor: "var(--line)", background: "var(--bg-body)" }}
                        value={l.process_label ?? ""}
                        disabled={!draft}
                        onChange={(e) => patchLine(i, { process_label: e.target.value })}
                      />
                    </td>
                    <td className="py-1">
                      <input
                        className="w-16 rounded border px-1 py-0.5"
                        style={{ borderColor: "var(--line)", background: "var(--bg-body)" }}
                        value={l.category ?? ""}
                        disabled={!draft}
                        onChange={(e) => patchLine(i, { category: e.target.value })}
                      />
                    </td>
                    <td className="py-1 text-right">
                      <input
                        type="number"
                        min={0}
                        className="w-20 rounded border px-1 py-0.5 text-right"
                        style={{ borderColor: "var(--line)", background: "var(--bg-body)" }}
                        value={l.unit_price_tax_in ?? 0}
                        disabled={!draft}
                        onChange={(e) => patchLine(i, { unit_price_tax_in: Number(e.target.value) })}
                      />
                    </td>
                    <td className="py-1 text-right">
                      <div className="flex items-center justify-end gap-1">
                        <input
                          type="number"
                          min={0}
                          className="w-14 rounded border px-1 py-0.5 text-right"
                          style={{ borderColor: "var(--line)", background: "var(--bg-body)" }}
                          placeholder="起订"
                          value={l.moq ?? ""}
                          disabled={!draft}
                          onChange={(e) =>
                            patchLine(i, { moq: e.target.value === "" ? null : Number(e.target.value) })
                          }
                        />
                        <span className="text-[var(--text-muted)]">/</span>
                        <input
                          type="number"
                          min={1}
                          className="w-14 rounded border px-1 py-0.5 text-right"
                          style={{ borderColor: "var(--line)", background: "var(--bg-body)" }}
                          value={l.qty || ""}
                          disabled={!draft}
                          onChange={(e) => patchLine(i, { qty: Number.parseInt(e.target.value, 10) || 0 })}
                        />
                        <select
                          className="rounded border px-0.5 py-0.5"
                          style={{ borderColor: "var(--line)", background: "var(--bg-body)" }}
                          value={l.uom}
                          disabled={!draft}
                          onChange={(e) => patchLine(i, { uom: e.target.value })}
                        >
                          {["BOX", "PCS", "BOARD"].map((u) => (
                            <option key={u} value={u}>
                              {formatUnit(u)}
                            </option>
                          ))}
                        </select>
                      </div>
                    </td>
                    <td className="py-1 text-right">
                      <input
                        type="number"
                        min={0}
                        className="w-20 rounded border px-1 py-0.5 text-right"
                        style={{ borderColor: "var(--line)", background: "var(--bg-body)" }}
                        value={l.mold_fee ?? 0}
                        disabled={!draft}
                        onChange={(e) => patchLine(i, { mold_fee: Number(e.target.value) })}
                      />
                    </td>
                    <td className="py-1 text-right">
                      <input
                        type="number"
                        min={0}
                        className="w-16 rounded border px-1 py-0.5 text-right"
                        style={{ borderColor: "var(--line)", background: "var(--bg-body)" }}
                        placeholder="达计量"
                        value={l.rebate_qty ?? ""}
                        disabled={!draft}
                        onChange={(e) =>
                          patchLine(i, { rebate_qty: e.target.value === "" ? null : Number(e.target.value) })
                        }
                      />
                    </td>
                    <td className="py-1">
                      <input
                        className="w-24 rounded border px-1 py-0.5"
                        style={{ borderColor: "var(--line)", background: "var(--bg-body)" }}
                        value={l.note ?? ""}
                        disabled={!draft}
                        onChange={(e) => patchLine(i, { note: e.target.value })}
                      />
                    </td>
                    <td className="py-1">
                      {draft && (
                        <button type="button" className="text-rose-400" onClick={() => setLines((p) => p.filter((_, j) => j !== i))}>
                          删
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {draft && (
            <button
              type="button"
              className="mt-2 rounded border px-2 py-1 text-xs"
              style={{ borderColor: "var(--line)" }}
              onClick={() => setLines((p) => [...p, emptyLine()])}
            >
              加一行
            </button>
          )}

          {status === "APPROVED" && (
            <div className="mt-4 grid gap-2 rounded border p-3 sm:grid-cols-2" style={{ borderColor: "var(--line)" }}>
              <label className="text-xs">
                <span className="text-[var(--text-muted)]">转订单 · 合同</span>
                <select
                  className="mt-1 w-full rounded border px-2 py-1.5"
                  style={{ borderColor: "var(--line)", background: "var(--bg-body)" }}
                  value={contractNo}
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
              <label className="text-xs">
                <span className="text-[var(--text-muted)]">交期</span>
                <input
                  type="date"
                  className="mt-1 w-full rounded border px-2 py-1.5"
                  style={{ borderColor: "var(--line)", background: "var(--bg-body)" }}
                  value={dueDate}
                  onChange={(e) => setDueDate(e.target.value)}
                />
              </label>
            </div>
          )}
        </div>
        <div className="flex flex-wrap justify-end gap-2 border-t px-4 py-3" style={{ borderColor: "var(--line)" }}>
          {canWrite && draft && (
            <button type="button" disabled={busy} className="rounded border px-3 py-1.5 text-xs" style={{ borderColor: "var(--line)" }} onClick={() => void save()}>
              保存草稿
            </button>
          )}
          {canWrite && draft && code && (
            <button type="button" disabled={busy} className="rounded border px-3 py-1.5 text-xs" style={{ borderColor: "var(--line)" }} onClick={() => void act(`/api/crm/quotes/${code}/submit`)}>
              提交
            </button>
          )}
          {canApprove && status === "SUBMITTED" && (
            <>
              {(role === "GM" || role === "SALES_MGR") && (
                <button
                  type="button"
                  disabled={busy}
                  className="rounded border px-3 py-1.5 text-xs text-amber-300"
                  style={{ borderColor: "var(--line)" }}
                  onClick={() => void act(`/api/crm/quotes/${code}/requote`)}
                >
                  需重新报价
                </button>
              )}
              <button type="button" disabled={busy} className="rounded bg-emerald-700 px-3 py-1.5 text-xs text-white" onClick={() => void act(`/api/crm/quotes/${code}/approve`)}>
                批准
              </button>
            </>
          )}
          {canApprove && (status === "DRAFT" || status === "SUBMITTED" || status === "APPROVED") && code && (
            <button type="button" disabled={busy} className="rounded border px-3 py-1.5 text-xs text-rose-400" style={{ borderColor: "var(--line)" }} onClick={() => void act(`/api/crm/quotes/${code}/void`)}>
              作废
            </button>
          )}
          {canWrite && status === "APPROVED" && (
            <button type="button" disabled={busy} className="rounded bg-[var(--accent)] px-3 py-1.5 text-xs font-medium text-slate-950" onClick={() => void convert()}>
              转销售订单
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
