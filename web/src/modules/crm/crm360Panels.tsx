import { useEffect, useState, type ReactNode } from "react";
import { requestWithRole } from "../../api/client";
import {
  renderDate,
  renderMoney,
  renderOppStageTag,
  renderProgress,
  renderSampleProductDesc,
  renderSampleStageTag,
  renderStatusTag,
} from "../../ui/cellRenderers";
import { useAuth } from "../../shell/auth";

export type Customer360Data = {
  customer: {
    code: string;
    name: string;
    channel_l1: string;
    channel_l2: string;
    owner_sales: string;
    level: number;
    duplicate_flag: boolean;
  };
  samples: {
    code: string;
    item_draft_name: string;
    current_stage: string;
    round_no: number;
    due_date: string | null;
  }[];
  opportunities: {
    id: number;
    name: string;
    stage: string;
    amount: number;
    expect_close_date: string | null;
  }[];
  orders: {
    order_no: string;
    item_code: string;
    due_date: string;
    order_status: string;
    amount?: number;
    schedule_phase?: string;
    contract_no?: string | null;
  }[];
  contracts: {
    contract_no: string;
    title: string;
    status: string;
    contract_amount: number;
    received_total: number;
    pending_total: number;
  }[];
  payment_summary: { received: number; pending: number; contract_total: number };
};

export function Customer360Panel({
  data,
  onOpenSample,
  onOpenOpportunity,
  onOpenOrder,
  onOpenContract,
  onNewContract,
}: {
  data: Customer360Data;
  onOpenSample: (code: string) => void;
  onOpenOpportunity: (id: number) => void;
  onOpenOrder: (orderNo: string) => void;
  onOpenContract: (contractNo: string) => void;
  onNewContract: () => void;
}) {
  const c = data.customer;
  const pay = data.payment_summary;
  return (
    <div className="space-y-4 text-sm">
      <div className="grid grid-cols-2 gap-2 text-xs">
        <div className="rounded-lg border p-3" style={{ borderColor: "var(--line)", background: "var(--bg-card)" }}>
          <p className="text-[var(--text-muted)]">累计回款</p>
          <p className="mt-1 text-lg font-semibold">{renderMoney(pay.received)}</p>
        </div>
        <div className="rounded-lg border p-3" style={{ borderColor: "var(--line)", background: "var(--bg-card)" }}>
          <p className="text-[var(--text-muted)]">待回款</p>
          <p className="mt-1 text-lg font-semibold">{renderMoney(pay.pending)}</p>
        </div>
      </div>

      <section className="rounded-lg border p-3 text-xs" style={{ borderColor: "var(--line)" }}>
        <p className="font-mono text-base font-semibold">
          {c.code} · {c.name}
        </p>
        {c.duplicate_flag && <p className="mt-1 text-amber-400">疑似重复客户</p>}
        <dl className="mt-3 grid grid-cols-2 gap-2">
          <div>
            <dt className="text-[var(--text-muted)]">渠道</dt>
            <dd>
              {c.channel_l1} / {c.channel_l2}
            </dd>
          </div>
          <div>
            <dt className="text-[var(--text-muted)]">负责销售</dt>
            <dd>{c.owner_sales}</dd>
          </div>
          <div>
            <dt className="text-[var(--text-muted)]">客户等级</dt>
            <dd>L{c.level}</dd>
          </div>
        </dl>
      </section>

      <div className="flex items-center justify-end">
        <button type="button" className="text-xs text-[var(--accent)] hover:underline" onClick={onNewContract}>
          新建合同
        </button>
      </div>
      <SubTable
        title="历史合同"
        empty="暂无合同"
        headers={["合同号", "标题", "金额", "已回/待回", "状态"]}
        hasData={(data.contracts ?? []).length > 0}
      >
        {(data.contracts ?? []).map((ct) => (
          <tr
            key={ct.contract_no}
            className="cursor-pointer border-t hover:bg-[var(--table-hover)]"
            style={{ borderColor: "var(--line)" }}
            onClick={() => onOpenContract(ct.contract_no)}
          >
            <td className="px-2 py-1.5 font-mono text-[var(--accent)]">{ct.contract_no}</td>
            <td className="py-1.5">{ct.title}</td>
            <td className="py-1.5 text-right">{renderMoney(ct.contract_amount)}</td>
            <td className="py-1.5 text-right text-[10px] tabular-nums">
              {renderMoney(ct.received_total)} / {renderMoney(ct.pending_total)}
            </td>
            <td className="py-1.5">{renderStatusTag(ct.status)}</td>
          </tr>
        ))}
      </SubTable>

      <SubTable
        title="打样历史"
        empty="暂无打样"
        headers={["样品号", "产品", "阶段", "节点"]}
        hasData={data.samples.length > 0}
      >
        {data.samples.map((s) => (
          <tr
            key={s.code}
            className="cursor-pointer border-t hover:bg-[var(--table-hover)]"
            style={{ borderColor: "var(--line)" }}
            onClick={() => onOpenSample(s.code)}
          >
            <td className="px-2 py-1.5 font-mono text-[var(--accent)]">{s.code}</td>
            <td className="py-1.5">{s.item_draft_name}</td>
            <td className="py-1.5">{renderSampleStageTag(s.current_stage)}</td>
            <td className="py-1.5 tabular-nums">{s.due_date ?? "—"}</td>
          </tr>
        ))}
      </SubTable>

      <SubTable
        title="商机历史"
        empty="暂无商机"
        headers={["商机", "阶段", "金额", "预计成交"]}
        hasData={data.opportunities.length > 0}
      >
        {data.opportunities.map((o) => (
          <tr
            key={o.id}
            className="cursor-pointer border-t hover:bg-[var(--table-hover)]"
            style={{ borderColor: "var(--line)" }}
            onClick={() => onOpenOpportunity(o.id)}
          >
            <td className="px-2 py-1.5">{o.name}</td>
            <td className="py-1.5">{renderOppStageTag(o.stage)}</td>
            <td className="py-1.5 text-right tabular-nums">{o.amount.toLocaleString()}</td>
            <td className="py-1.5 tabular-nums">{o.expect_close_date ?? "—"}</td>
          </tr>
        ))}
      </SubTable>

      <SubTable
        title="订单历史"
        empty="暂无订单"
        headers={["订单号", "品项", "交期", "状态"]}
        hasData={data.orders.length > 0}
      >
        {data.orders.map((o) => (
          <tr
            key={o.order_no}
            className="cursor-pointer border-t hover:bg-[var(--table-hover)]"
            style={{ borderColor: "var(--line)" }}
            onClick={() => onOpenOrder(o.order_no)}
          >
            <td className="px-2 py-1.5 font-mono text-[var(--accent)]">{o.order_no}</td>
            <td className="py-1.5">{o.item_code}</td>
            <td className="py-1.5">{renderDate(o.due_date)}</td>
            <td className="py-1.5">{renderStatusTag(o.order_status)}</td>
          </tr>
        ))}
      </SubTable>
    </div>
  );
}

function SubTable({
  title,
  empty,
  headers,
  children,
  hasData,
}: {
  title: string;
  empty: string;
  headers: string[];
  children: ReactNode;
  hasData: boolean;
}) {
  return (
    <section>
      <h3 className="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">{title}</h3>
      <div className="mt-1 overflow-x-auto rounded border" style={{ borderColor: "var(--line)" }}>
        <table className="w-full text-xs">
          <thead className="bg-[var(--table-head)] text-[var(--text-muted)]">
            <tr>
              {headers.map((h) => (
                <th key={h} className="px-2 py-1.5 text-left first:pl-2">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {hasData ? (
              children
            ) : (
              <tr>
                <td colSpan={headers.length} className="px-2 py-4 text-center text-[var(--text-muted)]">
                  {empty}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export type SampleDetail = {
  code: string;
  item_draft_name: string;
  current_stage: string;
  round_no: number;
  owner_sales: string;
  due_date: string | null;
  customer: { code: string; name: string };
  steps: {
    step_no: number;
    stage: string;
    event_date: string;
    product_desc: string;
    situation_desc: string;
    evidence_text?: string;
    evidence_images?: string[];
    is_final?: boolean;
    round_no?: number | null;
  }[];
  step_stages?: string[];
};

export function SampleDetailBody({ data }: { data: SampleDetail }) {
  return (
    <div className="space-y-3 text-xs">
      <p className="font-mono text-base font-semibold">{data.code}</p>
      <p className="text-[var(--text-muted)]">
        {data.item_draft_name} · 第 {data.round_no} 轮 · 当前{" "}
        <span className="text-amber-300">{data.current_stage}</span>
      </p>
      <p className="text-[var(--text-muted)]">
        客户 {data.customer.code} {data.customer.name} · 销售 {data.owner_sales}
      </p>
      <h4 className="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">打样过程</h4>
      <table className="w-full rounded border" style={{ borderColor: "var(--line)" }}>
        <thead className="bg-[var(--table-head)]">
          <tr>
            <th className="px-2 py-1 text-left">#</th>
            <th className="text-left">环节</th>
            <th className="text-left">日期</th>
            <th className="text-left">产品</th>
            <th className="text-left">描述</th>
            <th className="text-left">证据</th>
            <th className="text-left">定稿</th>
          </tr>
        </thead>
        <tbody>
          {data.steps.map((s) => (
            <tr
              key={s.step_no}
              className={`border-t align-top ${s.is_final ? "bg-emerald-950/30" : ""}`}
              style={{ borderColor: "var(--line)" }}
            >
              <td className="px-2 py-1">{s.step_no}</td>
              <td className="py-1">{renderSampleStageTag(s.stage)}</td>
              <td className="py-1">{s.event_date}</td>
              <td className="py-1">{renderSampleProductDesc(s.product_desc, s.round_no)}</td>
              <td className="py-1 text-[var(--text-muted)]">{s.situation_desc}</td>
              <td className="py-1">
                {s.evidence_text || (s.evidence_images && s.evidence_images.length) ? (
                  <div className="space-y-1">
                    {s.evidence_text ? <p>{s.evidence_text}</p> : null}
                    {(s.evidence_images ?? []).map((src, i) => (
                      <img key={i} src={src} alt="完结证据" className="max-h-20 rounded border" style={{ borderColor: "var(--line)" }} />
                    ))}
                  </div>
                ) : (
                  <span className="text-[var(--text-muted)]">—</span>
                )}
              </td>
              <td className="py-1">
                {s.is_final ? (
                  <span className="rounded-md bg-emerald-950 px-2 py-0.5 text-[10px] text-emerald-200 ring-1 ring-emerald-700">
                    最后定稿
                  </span>
                ) : (
                  <span className="text-[var(--text-muted)]">—</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const DEFAULT_STEP_STAGES = ["申请", "打样", "寄样", "客户反馈"] as const;

export function SampleDetailPanel({ sampleCode }: { sampleCode: string }) {
  const auth = useAuth();
  const role = auth.role;
  const [data, setData] = useState<SampleDetail | null>(null);
  const [stage, setStage] = useState<string>("打样");
  const [eventDate, setEventDate] = useState("2026-09-16");
  const [productDesc, setProductDesc] = useState("");
  const [situationDesc, setSituationDesc] = useState("");
  const [text, setText] = useState("");
  const [images, setImages] = useState<string[]>([]);
  const [isFinal, setIsFinal] = useState(false);
  const [isRework, setIsRework] = useState(false);
  const [previewRound, setPreviewRound] = useState<number | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = () => {
    if (!role) return;
    requestWithRole<SampleDetail>(`/api/crm/samples/${encodeURIComponent(sampleCode)}`, role).then((d) => {
      setData(d);
      setProductDesc((prev) => prev || d.item_draft_name);
    });
  };

  useEffect(() => {
    if (!role) return;
    setErr(null);
    load();
  }, [sampleCode, role]);

  useEffect(() => {
    if (!role || isFinal || stage !== "打样") {
      setPreviewRound(null);
      return;
    }
    const q = new URLSearchParams({ stage, is_rework: String(isRework) });
    requestWithRole<{ round_no: number | null }>(
      `/api/crm/samples/${encodeURIComponent(sampleCode)}/steps/preview?${q}`,
      role,
    )
      .then((p) => setPreviewRound(p.round_no ?? null))
      .catch(() => setPreviewRound(null));
  }, [sampleCode, role, stage, isRework, isFinal]);

  const canEdit = role === "GM" || role === "SALES_MGR" || role === "SALES";
  const stageOptions = data?.step_stages?.length ? data.step_stages : [...DEFAULT_STEP_STAGES];

  const onPickFiles = (files: FileList | null) => {
    if (!files) return;
    Array.from(files).forEach((file) => {
      const reader = new FileReader();
      reader.onload = () => {
        if (typeof reader.result === "string") {
          setImages((prev) => [...prev, reader.result as string]);
        }
      };
      reader.readAsDataURL(file);
    });
  };

  const addStep = async () => {
    if (!role) return;
    setBusy(true);
    setErr(null);
    try {
      const next = await requestWithRole<SampleDetail>(
        `/api/crm/samples/${encodeURIComponent(sampleCode)}/steps`,
        role,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            stage: isFinal ? "客户反馈" : stage,
            event_date: eventDate,
            product_desc: productDesc,
            situation_desc: situationDesc,
            evidence_text: text,
            evidence_images: images,
            is_final: isFinal,
            is_rework: isRework,
          }),
        },
      );
      setData(next);
      setSituationDesc("");
      setText("");
      setImages([]);
      setIsFinal(false);
      setIsRework(false);
      setProductDesc(next.item_draft_name);
      if (next.current_stage !== "结案") {
        setStage(next.current_stage === "结案" ? "客户反馈" : next.current_stage);
      }
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  };

  if (!data) return <p className="text-xs text-[var(--text-muted)]">加载打样详情…</p>;

  return (
    <div className="space-y-4">
      <SampleDetailBody data={data} />
      {canEdit && data.current_stage !== "结案" && (
        <section className="space-y-2 border-t pt-3" style={{ borderColor: "var(--line)" }}>
          <div className="flex flex-wrap items-center gap-2">
            <h4 className="text-xs font-semibold">新增打样记录</h4>
            {stage === "打样" && previewRound != null && !isFinal && (
              <span className="text-[10px] text-[var(--text-muted)]">
                保存后产品名将自动带上{" "}
                <span className="font-medium text-amber-300/95">第{previewRound}轮</span>
              </span>
            )}
          </div>
          <p className="text-[10px] text-[var(--text-muted)]">
            持续追加过程行；打样环节自动递增轮次（可勾选本轮复打）；最后定稿须留证据并结案
          </p>
          <div className="grid gap-2 sm:grid-cols-2">
            <label className="grid gap-1 text-[10px] text-[var(--text-muted)]">
              环节
              <select
                className="rounded border px-2 py-1 text-xs"
                style={{ borderColor: "var(--line)", background: "var(--bg-card)" }}
                value={stage}
                disabled={isFinal}
                onChange={(e) => setStage(e.target.value)}
              >
                {stageOptions.map((st) => (
                  <option key={st} value={st}>
                    {st}
                  </option>
                ))}
              </select>
            </label>
            <label className="grid gap-1 text-[10px] text-[var(--text-muted)]">
              日期
              <input
                type="date"
                className="rounded border px-2 py-1 text-xs"
                style={{ borderColor: "var(--line)", background: "var(--bg-card)" }}
                value={eventDate}
                onChange={(e) => setEventDate(e.target.value)}
              />
            </label>
            <label className="grid gap-1 text-[10px] text-[var(--text-muted)] sm:col-span-2">
              产品描述
              <input
                className="rounded border px-2 py-1 text-xs"
                style={{ borderColor: "var(--line)", background: "var(--bg-card)" }}
                value={productDesc}
                onChange={(e) => setProductDesc(e.target.value)}
              />
            </label>
            <label className="grid gap-1 text-[10px] text-[var(--text-muted)] sm:col-span-2">
              过程描述
              <textarea
                className="rounded border px-2 py-1 text-xs"
                style={{ borderColor: "var(--line)", background: "var(--bg-card)" }}
                rows={2}
                placeholder="试模情况、寄样说明等"
                value={situationDesc}
                onChange={(e) => setSituationDesc(e.target.value)}
              />
            </label>
          </div>
          {stage === "打样" && !isFinal && (
            <label className="flex items-center gap-2 text-xs">
              <input type="checkbox" checked={isRework} onChange={(e) => setIsRework(e.target.checked)} />
              本轮复打（沿用当前轮次，不递增）
            </label>
          )}
          <label className="flex items-center gap-2 text-xs">
            <input type="checkbox" checked={isFinal} onChange={(e) => setIsFinal(e.target.checked)} />
            最后定稿（结案证据）
          </label>
          {isFinal && (
            <div className="space-y-2 rounded border p-2" style={{ borderColor: "var(--line)" }}>
              <textarea
                className="w-full rounded border px-2 py-1 text-xs"
                style={{ borderColor: "var(--line)", background: "var(--bg-card)" }}
                rows={2}
                placeholder="客户微信/邮件反馈摘要（定稿必填其一）"
                value={text}
                onChange={(e) => setText(e.target.value)}
              />
              <input type="file" accept="image/*" multiple className="text-xs" onChange={(e) => onPickFiles(e.target.files)} />
              {images.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {images.map((src, i) => (
                    <img key={i} src={src} alt="" className="h-14 rounded border" style={{ borderColor: "var(--line)" }} />
                  ))}
                </div>
              )}
            </div>
          )}
          {err && <p className="text-xs text-rose-400">{err}</p>}
          <button
            type="button"
            className="rounded bg-sky-700 px-3 py-1 text-xs text-white disabled:opacity-50"
            disabled={busy}
            onClick={() => void addStep()}
          >
            {busy ? "保存中…" : isFinal ? "保存定稿并结案" : "追加记录"}
          </button>
        </section>
      )}
    </div>
  );
}

export type OpportunityDetail = {
  id: number;
  name: string;
  stage: string;
  amount: number;
  sales_name: string;
  owner_sales: string;
  expect_close_date: string | null;
  sample_code: string | null;
  customer: { code: string; name: string };
  sample: SampleDetail | null;
};

export function OpportunityDetailPanel({ oppId }: { oppId: number }) {
  const auth = useAuth();
  const role = auth.role;
  const [data, setData] = useState<OpportunityDetail | null>(null);

  useEffect(() => {
    if (!role) return;
    requestWithRole<OpportunityDetail>(`/api/crm/opportunities/${oppId}`, role).then(setData);
  }, [oppId, role]);

  if (!data) return <p className="text-xs text-[var(--text-muted)]">加载商机…</p>;

  return (
    <div className="space-y-4">
      <dl className="grid gap-2 text-sm">
        <div>
          <dt className="text-xs text-[var(--text-muted)]">商机名称</dt>
          <dd className="font-medium">{data.name}</dd>
        </div>
        <div>
          <dt className="text-xs text-[var(--text-muted)]">阶段</dt>
          <dd>{renderOppStageTag(data.stage)}</dd>
        </div>
        <div>
          <dt className="text-xs text-[var(--text-muted)]">金额</dt>
          <dd>{renderMoney(data.amount)}</dd>
        </div>
        <div>
          <dt className="text-xs text-[var(--text-muted)]">客户</dt>
          <dd>
            {data.customer.code} · {data.customer.name}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-[var(--text-muted)]">销售</dt>
          <dd>{data.sales_name || data.owner_sales}</dd>
        </div>
        <div>
          <dt className="text-xs text-[var(--text-muted)]">预计成交</dt>
          <dd>{data.expect_close_date ?? "—"}</dd>
        </div>
      </dl>
      {data.sample ? (
        <section className="border-t pt-4" style={{ borderColor: "var(--line)" }}>
          <h3 className="mb-2 text-sm font-semibold">关联打样单</h3>
          <SampleDetailBody data={data.sample} />
        </section>
      ) : (
        <p className="text-xs text-[var(--text-muted)]">暂无关联打样单</p>
      )}
    </div>
  );
}

export function OrderDetailPanel({ orderNo }: { orderNo: string }) {
  const auth = useAuth();
  const role = auth.role;
  const [data, setData] = useState<{
    order: Record<string, unknown>;
    lines: { line_no: number; item_code: string; item_name: string; qty: number; unit: string }[];
    kitting: { kitting_rate_pct?: number | null };
  } | null>(null);

  useEffect(() => {
    if (!role) return;
    requestWithRole<NonNullable<typeof data>>(
      `/api/mis/orders/${encodeURIComponent(orderNo)}/breakdown`,
      role,
    ).then(setData);
  }, [orderNo, role]);

  if (!data) return <p className="text-xs text-[var(--text-muted)]">加载订单…</p>;

  const o = data.order;
  return (
    <div className="space-y-3 text-xs">
      <p className="font-mono text-base font-semibold">{orderNo}</p>
      <p>{String(o.customer ?? "")}</p>
      <p>
        交期 {renderDate(String(o.due_date ?? ""))} · {renderStatusTag(String(o.order_status ?? ""))}
      </p>
      <p>齐套 {renderProgress(data.kitting.kitting_rate_pct ?? null)}</p>
      <table className="w-full rounded border" style={{ borderColor: "var(--line)" }}>
        <thead className="bg-[var(--table-head)]">
          <tr>
            <th className="px-2 py-1 text-left">行</th>
            <th className="text-left">品项</th>
            <th className="text-right">数量</th>
          </tr>
        </thead>
        <tbody>
          {(data.lines ?? []).map((ln) => (
            <tr key={ln.line_no} className="border-t" style={{ borderColor: "var(--line)" }}>
              <td className="px-2 py-1">{ln.line_no}</td>
              <td className="py-1">
                {ln.item_code} {ln.item_name}
              </td>
              <td className="py-1 text-right">
                {ln.qty} {ln.unit}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
