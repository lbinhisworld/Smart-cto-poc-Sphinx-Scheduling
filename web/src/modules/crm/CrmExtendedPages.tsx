import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { requestWithRole } from "../../api/client";
import { useGuidedDemoSeedReload } from "../../hooks/guidedDemoSeed";
import { useAuth } from "../../shell/auth";
import { Customer360Drawer } from "./Customer360Drawer";
import { FollowAddForm } from "./FollowSection";
import { OpportunityDetailDrawer } from "./OpportunityDetailDrawer";

type OppFunnelStep = { stage: string; count: number; to_next_pct: number | null };
type OppFunnelData = {
  steps: OppFunnelStep[];
  lost: number;
  overall_pct: number | null;
  scope: "all" | "my";
  note: string;
};

const OPP_FUNNEL_COLORS: Record<string, { bg: string; fg: string }> = {
  尚未打样: { bg: "#475569", fg: "#f1f5f9" },
  打样中: { bg: "#0284c7", fg: "#e0f2fe" },
  方案报价: { bg: "#d97706", fg: "#fffbeb" },
  已签单: { bg: "#059669", fg: "#ecfdf5" },
};

function OpportunityFunnelBar({ data }: { data: OppFunnelData | null }) {
  if (!data || data.steps.length === 0) return null;
  const top = data.steps[0]?.count ?? 0;
  const maxCount = top > 0 ? top : 1;

  return (
    <div className="mt-4 rounded-xl border p-4" style={{ borderColor: "var(--line)", background: "var(--bg-card)" }}>
      <div className="flex flex-wrap items-baseline justify-between gap-2 text-xs">
        <span className="font-medium text-[var(--text)]">
          {data.scope === "my" ? "我的商机转化漏斗" : "全体商机转化漏斗"}
        </span>
        <span className="text-[var(--text-muted)]">
          {data.overall_pct != null && <span className="mr-3 tabular-nums">签单率 {data.overall_pct}%</span>}
          {data.lost > 0 && <span className="tabular-nums">丢单 {data.lost}</span>}
        </span>
      </div>
      <div className="mt-3 flex w-full items-center gap-0.5">
        {data.steps.map((step, index) => {
          const colors = OPP_FUNNEL_COLORS[step.stage] ?? OPP_FUNNEL_COLORS["尚未打样"];
          const widthPct = Math.max(14, Math.round((step.count / maxCount) * 100));
          const prev = index > 0 ? data.steps[index - 1] : null;
          return (
            <div key={step.stage} className="flex min-w-0 items-center" style={{ flex: `${widthPct} 1 0` }}>
              {prev && prev.to_next_pct != null && (
                <div
                  className="flex shrink-0 flex-col items-center px-1 text-[10px] leading-tight text-[var(--text-muted)]"
                  title={`${prev.stage} → ${step.stage}`}
                >
                  <span className="text-sky-400">▶</span>
                  <span className="tabular-nums font-medium text-sky-300">{prev.to_next_pct}%</span>
                </div>
              )}
              <div
                className="flex h-16 flex-1 flex-col items-center justify-center rounded-lg px-1 shadow-inner"
                style={{ background: colors.bg, color: colors.fg }}
              >
                <span className="text-[11px] font-medium leading-tight">{step.stage}</span>
                <span className="mt-0.5 text-lg font-semibold tabular-nums">{step.count}</span>
              </div>
            </div>
          );
        })}
      </div>
      <p className="mt-2 text-[10px] leading-relaxed text-[var(--text-muted)]">{data.note}</p>
    </div>
  );
}

function SideDrawer({
  open,
  onClose,
  title,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
}) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-black/40">
      <div
        className="flex h-full w-full max-w-lg flex-col border-l shadow-xl"
        style={{ background: "var(--bg-body)", borderColor: "var(--line)" }}
      >
        <div className="flex items-center justify-between border-b px-4 py-3" style={{ borderColor: "var(--line)" }}>
          <p className="text-sm font-semibold">{title}</p>
          <button type="button" className="text-xs text-[var(--text-muted)]" onClick={onClose}>
            关闭
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-4 text-sm">{children}</div>
      </div>
    </div>
  );
}

export function SeaCustomersPage() {
  const auth = useAuth();
  const role = auth.role!;
  const canAssign = role === "GM" || role === "SALES_MGR";
  const [rows, setRows] = useState<
    { code: string; company_name: string; contact_name: string; customer_type: string; sea_pool_name: string }[]
  >([]);
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [owners, setOwners] = useState<string[]>([]);
  const [assignTo, setAssignTo] = useState("李业务");

  const load = useCallback(() => {
    requestWithRole<typeof rows>("/api/crm/sea", role).then(setRows);
  }, [role]);

  useEffect(() => {
    load();
    if (canAssign) {
      requestWithRole<string[]>("/api/crm/goals/owners", role).then((o) => {
        setOwners(o);
        if (o[0]) setAssignTo(o[0]);
      });
    }
  }, [load, canAssign, role]);

  const claim = (ownerSales?: string) => {
    fetch("/api/crm/sea/claim", {
      method: "POST",
      headers: { ...auth.headers(), "Content-Type": "application/json" },
      body: JSON.stringify({
        codes: [...picked],
        owner_sales: ownerSales ?? (canAssign ? assignTo : auth.userName),
      }),
    }).then(() => {
      setPicked(new Set());
      load();
    });
  };

  return (
    <div className="px-6 py-4">
      <h2 className="text-lg font-semibold">公海池</h2>
      <p className="text-xs text-[var(--text-muted)]">无负责人客户 · 领取后进入「我的客户」</p>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        {!canAssign && (
          <button type="button" className="rounded bg-[var(--accent)] px-3 py-1 text-xs text-white" onClick={() => claim()}>
            领取选中
          </button>
        )}
        {canAssign && (
          <>
            <select className="rounded border px-2 py-1 text-xs" style={{ borderColor: "var(--line)" }} value={assignTo} onChange={(e) => setAssignTo(e.target.value)}>
              {(owners.length ? owners : ["李业务"]).map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
            <button type="button" className="rounded bg-[var(--accent)] px-3 py-1 text-xs text-white" onClick={() => claim(assignTo)}>
              批量分配给销售
            </button>
          </>
        )}
      </div>
      <table className="mt-4 w-full text-xs">
        <thead>
          <tr className="text-[var(--text-muted)]">
            <th className="py-2 text-left" />
            <th>公海池</th>
            <th>联系人</th>
            <th>公司</th>
            <th>客户类型</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.code} className="border-t" style={{ borderColor: "var(--line)" }}>
              <td className="py-2">
                <input
                  type="checkbox"
                  checked={picked.has(r.code)}
                  onChange={() =>
                    setPicked((p) => {
                      const n = new Set(p);
                      if (n.has(r.code)) n.delete(r.code);
                      else n.add(r.code);
                      return n;
                    })
                  }
                />
              </td>
              <td>{r.sea_pool_name}</td>
              <td>{r.contact_name}</td>
              <td>{r.company_name}</td>
              <td>{r.customer_type}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function MyCustomersPage() {
  const auth = useAuth();
  const role = auth.role!;
  const demoSeedReload = useGuidedDemoSeedReload("customer");
  const [industry, setIndustry] = useState("全部");
  const [statusTab, setStatusTab] = useState("全部");
  const [data, setData] = useState<{
    items: {
      code: string;
      company_name: string;
      contact_name: string;
      crm_status: string;
      last_follow_date: string | null;
      days_without_follow: number | null;
      is_new_customer: boolean;
    }[];
    status_counts: Record<string, number>;
    industry_tree: string[];
  } | null>(null);
  const [detail, setDetail] = useState<string | null>(null);
  const [followCode, setFollowCode] = useState<string | null>(null);
  const [collabCode, setCollabCode] = useState<string | null>(null);
  const [collabText, setCollabText] = useState("");
  const [oppFor, setOppFor] = useState<{ code: string; name: string } | null>(null);
  const [oppName, setOppName] = useState("");
  const [oppAmount, setOppAmount] = useState("10000");

  const load = useCallback(() => {
    const q = new URLSearchParams({ today: "2026-09-15" });
    if (industry !== "全部") q.set("industry", industry);
    if (statusTab !== "全部") q.set("status_tab", statusTab);
    requestWithRole<NonNullable<typeof data>>(
      `/api/crm/customers/mine?${q}`,
      role,
      undefined,
      auth.userName,
    )
      .then(setData)
      .catch(() => setData(null));
  }, [role, industry, statusTab, auth.userName]);

  useEffect(() => {
    load();
  }, [load, demoSeedReload]);

  return (
    <div className="flex min-h-0 flex-1">
      <aside className="w-40 shrink-0 border-r p-3 text-xs" style={{ borderColor: "var(--line)" }}>
        <p className="mb-2 font-medium">行业类型</p>
        {(data?.industry_tree ?? ["全部"]).map((n) => (
          <button
            key={n}
            type="button"
            className={`mb-1 block w-full rounded px-2 py-1 text-left ${industry === n ? "bg-[var(--nav-active-bg)] text-[var(--accent)]" : ""}`}
            onClick={() => setIndustry(n)}
          >
            {n}
          </button>
        ))}
      </aside>
      <div className="min-w-0 flex-1 px-4 py-4">
        <h2 className="text-lg font-semibold">我的客户</h2>
        <div className="mt-2 flex flex-wrap gap-2 text-xs">
          {Object.entries(data?.status_counts ?? {}).map(([k, n]) => (
            <button
              key={k}
              type="button"
              className={`rounded-full border px-2 py-0.5 ${statusTab === k ? "border-[var(--accent)] text-[var(--accent)]" : ""}`}
              style={{ borderColor: "var(--line)" }}
              onClick={() => setStatusTab(k)}
            >
              {k} ({n})
            </button>
          ))}
        </div>
        <table className="mt-4 w-full text-xs">
          <thead className="text-[var(--text-muted)]">
            <tr>
              <th className="text-left py-2">公司</th>
              <th>联系人</th>
              <th>状态</th>
              <th>最近跟进</th>
              <th>未跟进天</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {data && data.items.length === 0 && (
              <tr>
                <td colSpan={6} className="py-6 text-center text-[var(--text-muted)]">
                  暂无可见客户。若刚点「生成数据」，请刷新页面；演示线客户对销售角色已放开可见，仍为空请确认后端已重启。
                </td>
              </tr>
            )}
            {(data?.items ?? []).map((r) => (
              <tr key={r.code} className="border-t" style={{ borderColor: "var(--line)" }}>
                <td className="py-2">
                  <button type="button" className="text-[var(--accent)] underline" onClick={() => setDetail(r.code)}>
                    {r.company_name}
                    {r.is_new_customer && <span className="ml-1 text-emerald-400">新增</span>}
                  </button>
                </td>
                <td>{r.contact_name}</td>
                <td>{r.crm_status}</td>
                <td>{r.last_follow_date ?? "—"}</td>
                <td>{r.days_without_follow ?? "—"}</td>
                <td className="space-x-1 whitespace-nowrap py-2">
                  <button type="button" className="text-[var(--accent)]" onClick={() => setFollowCode(r.code)}>
                    跟进
                  </button>
                  <button
                    type="button"
                    className="text-[var(--accent)]"
                    onClick={() => {
                      setOppFor({ code: r.code, name: r.company_name });
                      setOppName(`${r.company_name}·商机`);
                    }}
                  >
                    商机
                  </button>
                  <button
                    type="button"
                    className="text-[var(--accent)]"
                    onClick={() => {
                      setCollabCode(r.code);
                      setCollabText("");
                    }}
                  >
                    协作
                  </button>
                  <button
                    type="button"
                    className="text-rose-400"
                    onClick={() => {
                      if (!window.confirm(`关闭客户 ${r.company_name}？`)) return;
                      fetch(`/api/crm/customers/${encodeURIComponent(r.code)}/close`, {
                        method: "POST",
                        headers: auth.headers(),
                      }).then(() => load());
                    }}
                  >
                    关单
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <Customer360Drawer customerCode={detail} onClose={() => setDetail(null)} />
        <SideDrawer open={!!followCode} onClose={() => setFollowCode(null)} title="客户跟进">
          {followCode && (
            <FollowAddForm
              recordType="客户"
              customerCode={followCode}
              onSaved={() => {
                setFollowCode(null);
                load();
              }}
            />
          )}
        </SideDrawer>
        <SideDrawer open={!!collabCode} onClose={() => setCollabCode(null)} title="协作人">
          {collabCode && (
            <div className="space-y-2 text-xs">
              <p className="text-[var(--text-muted)]">多人逗号分隔，如：王助理,李业务</p>
              <input
                className="w-full rounded border px-2 py-1"
                style={{ borderColor: "var(--line)" }}
                value={collabText}
                onChange={(e) => setCollabText(e.target.value)}
              />
              <button
                type="button"
                className="rounded bg-[var(--accent)] px-3 py-1 text-slate-950"
                onClick={() => {
                  const names = collabText.split(/[,，]/).map((s) => s.trim()).filter(Boolean);
                  fetch(`/api/crm/customers/${encodeURIComponent(collabCode)}/collaborators`, {
                    method: "POST",
                    headers: { ...auth.headers(), "Content-Type": "application/json" },
                    body: JSON.stringify({ names }),
                  }).then(() => {
                    setCollabCode(null);
                    load();
                  });
                }}
              >
                保存
              </button>
            </div>
          )}
        </SideDrawer>
        <SideDrawer open={!!oppFor} onClose={() => setOppFor(null)} title="新增商机">
          {oppFor && (
            <div className="space-y-2 text-xs">
              <p>{oppFor.name}</p>
              <input className="w-full rounded border px-2 py-1" style={{ borderColor: "var(--line)" }} value={oppName} onChange={(e) => setOppName(e.target.value)} placeholder="商机名称" />
              <input className="w-full rounded border px-2 py-1" style={{ borderColor: "var(--line)" }} value={oppAmount} onChange={(e) => setOppAmount(e.target.value)} placeholder="预计金额" />
              <button
                type="button"
                className="rounded bg-[var(--accent)] px-3 py-1 text-slate-950"
                onClick={() => {
                  fetch("/api/crm/opportunities", {
                    method: "POST",
                    headers: { ...auth.headers(), "Content-Type": "application/json" },
                    body: JSON.stringify({
                      customer_code: oppFor.code,
                      name: oppName,
                      amount: Number(oppAmount) || 0,
                    }),
                  }).then(() => {
                    setOppFor(null);
                    load();
                  });
                }}
              >
                创建
              </button>
            </div>
          )}
        </SideDrawer>
      </div>
    </div>
  );
}

export function FollowsPage() {
  const auth = useAuth();
  const role = auth.role!;
  const demoSeedReload = useGuidedDemoSeedReload("follow_up");
  const [rows, setRows] = useState<
    { id: number; record_type: string; customer_name: string; follow_date: string; content: string; owner_sales: string }[]
  >([]);
  const [showNew, setShowNew] = useState(false);

  const load = useCallback(() => {
    requestWithRole<typeof rows>("/api/crm/follows", role).then(setRows);
  }, [role]);

  useEffect(() => {
    load();
  }, [load, demoSeedReload]);

  return (
    <div className="px-6 py-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">跟进记录</h2>
        <button type="button" className="rounded bg-[var(--accent)] px-3 py-1 text-xs text-slate-950" onClick={() => setShowNew((v) => !v)}>
          {showNew ? "收起" : "新建跟进"}
        </button>
      </div>
      {showNew && (
        <FollowAddForm
          recordType="客户"
          onSaved={() => {
            setShowNew(false);
            load();
          }}
        />
      )}
      <table className="mt-4 w-full text-xs">
        <thead className="text-[var(--text-muted)]">
          <tr>
            <th className="text-left">日期</th>
            <th>类型</th>
            <th>客户</th>
            <th>内容</th>
            <th>负责人</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id} className="border-t" style={{ borderColor: "var(--line)" }}>
              <td className="py-2">{r.follow_date}</td>
              <td>{r.record_type}</td>
              <td>{r.customer_name || "—"}</td>
              <td className="max-w-md truncate">{r.content}</td>
              <td>{r.owner_sales}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

type FieldVisit = {
  code: string;
  title: string;
  owner_sales: string;
  customer_name: string;
  status: string;
  started_at?: string | null;
  elapsed_minutes?: number | null;
  visit_minutes: number | null;
  minutes_until_checkout_ok: number | null;
  situation_note: string;
  progress_tags?: string[];
  meets_standard?: boolean | null;
};

type FieldVisitDetail = FieldVisit & {
  before_note?: string;
  visit_kind?: string;
  customer_code?: string | null;
  summary?: string;
  standard_reason?: string;
  eval_source?: string;
  timeline?: { id: number; recorded_at: string; body: string; created_by: string }[];
};

type CheckinStats = { not_meeting: number; by_tag: Record<string, number>; total: number };

const CHECKIN_TODAY = "2026-09-15";

export function CheckinPage() {
  const auth = useAuth();
  const role = auth.role!;
  const demoSeedReload = useGuidedDemoSeedReload("visit_stranger");
  const [rows, setRows] = useState<FieldVisit[]>([]);
  const [stats, setStats] = useState<CheckinStats | null>(null);
  const [filterTag, setFilterTag] = useState<string | null>(null);
  const [filterNotMeeting, setFilterNotMeeting] = useState(false);
  const [open, setOpen] = useState<FieldVisitDetail | null>(null);
  const [draft, setDraft] = useState("");
  const [logDraft, setLogDraft] = useState("");
  const [newOpen, setNewOpen] = useState(false);
  const [newTitle, setNewTitle] = useState("外勤拜访");
  const [newCustomer, setNewCustomer] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [matchInfo, setMatchInfo] = useState<{
    customers: { code: string; name: string }[];
    leads: { code: string; company_name: string }[];
    visit_kind: string;
    opp_draft: { name: string; amount: number; hint: string } | null;
  } | null>(null);
  const [pickCustomer, setPickCustomer] = useState("");
  const [pickLead, setPickLead] = useState("");
  const [createCustomer, setCreateCustomer] = useState(false);
  const [confirmOpp, setConfirmOpp] = useState(false);

  const load = useCallback(() => {
    const q = new URLSearchParams({ today: CHECKIN_TODAY });
    if (filterTag) q.set("tag", filterTag);
    if (filterNotMeeting) q.set("not_meeting_only", "true");
    requestWithRole<FieldVisit[]>(`/api/crm/checkin?${q}`, role)
      .then(setRows)
      .catch(() => setRows([]));
    requestWithRole<CheckinStats>(`/api/crm/checkin/stats?today=${CHECKIN_TODAY}`, role)
      .then(setStats)
      .catch(() => setStats(null));
  }, [role, filterTag, filterNotMeeting]);

  useEffect(() => {
    load();
  }, [load, demoSeedReload]);

  const openDetail = (code: string) => {
    requestWithRole<FieldVisitDetail>(
      `/api/crm/checkin/${encodeURIComponent(code)}`,
      role,
    ).then((d) => {
      setOpen(d);
      setDraft(d.situation_note || d.summary || "");
      setLogDraft("");
    });
  };

  const act = (code: string, path: "sign-in" | "sign-out") => {
    setErr(null);
    fetch(`/api/crm/checkin/${encodeURIComponent(code)}/${path}`, {
      method: "POST",
      headers: auth.headers(),
    })
      .then(async (r) => {
        const j = await r.json();
        if (!r.ok || j.code !== 0) throw new Error(j.detail || j.message);
        return j.data as FieldVisit;
      })
      .then((d) => {
        setOpen(d);
        load();
      })
      .catch((e) => setErr(String(e)));
  };

  const saveDetail = () => {
    if (!open) return;
    fetch(`/api/crm/checkin/${encodeURIComponent(open.code)}`, {
      method: "PATCH",
      headers: { ...auth.headers(), "Content-Type": "application/json" },
      body: JSON.stringify({ situation_note: draft }),
    })
      .then((r) => r.json())
      .then((j) => {
        if (j.data) setOpen(j.data as FieldVisitDetail);
        load();
      });
  };

  const aiParse = () => {
    if (!open) return;
    fetch(`/api/crm/checkin/${encodeURIComponent(open.code)}/parse`, {
      method: "POST",
      headers: { ...auth.headers(), "Content-Type": "application/json" },
      body: JSON.stringify({ raw_text: draft }),
    })
      .then((r) => r.json())
      .then((j) => {
        if (j.data?.parsed) setDraft(j.data.parsed);
        setMatchInfo(j.data);
        if (j.data?.visit_kind) setCreateCustomer(j.data.visit_kind === "陌生客户拜访");
      });
  };

  const confirmFollow = () => {
    if (!open) return;
    fetch(`/api/crm/checkin/${encodeURIComponent(open.code)}/confirm-follow?today=2026-09-15`, {
      method: "POST",
      headers: { ...auth.headers(), "Content-Type": "application/json" },
      body: JSON.stringify({
        create_customer: createCustomer,
        customer_code: pickCustomer || open.customer_code || null,
        lead_code: pickLead || null,
        confirm_opportunity: confirmOpp,
        opp_name: matchInfo?.opp_draft?.name,
        opp_amount: matchInfo?.opp_draft?.amount,
      }),
    })
      .then(async (r) => {
        const j = await r.json();
        if (!r.ok || j.code !== 0) throw new Error(j.detail || j.message);
        return j.data;
      })
      .then((d) => {
        setOpen(d.visit as FieldVisitDetail);
        load();
      })
      .catch((e) => setErr(String(e)));
  };

  const createVisit = () => {
    fetch(`/api/crm/checkin?today=${CHECKIN_TODAY}`, {
      method: "POST",
      headers: { ...auth.headers(), "Content-Type": "application/json" },
      body: JSON.stringify({
        title: newTitle,
        customer_name: newCustomer,
        visit_kind: newCustomer ? "老客户拜访" : "陌生客户拜访",
      }),
    })
      .then((r) => r.json())
      .then(() => {
        setNewOpen(false);
        load();
      });
  };

  const addLog = () => {
    if (!open || !logDraft.trim()) return;
    fetch(`/api/crm/checkin/${encodeURIComponent(open.code)}/logs?today=${CHECKIN_TODAY}`, {
      method: "POST",
      headers: { ...auth.headers(), "Content-Type": "application/json" },
      body: JSON.stringify({ body: logDraft }),
    })
      .then((r) => r.json())
      .then((j) => {
        if (j.data) setOpen(j.data as FieldVisitDetail);
        setLogDraft("");
        load();
      });
  };

  const finalizeVisit = () => {
    if (!open) return;
    fetch(`/api/crm/checkin/${encodeURIComponent(open.code)}/finalize?today=${CHECKIN_TODAY}`, {
      method: "POST",
      headers: { ...auth.headers(), "Content-Type": "application/json" },
      body: JSON.stringify({ prefer_llm: true }),
    })
      .then((r) => r.json())
      .then((j) => {
        if (j.data) {
          setOpen(j.data as FieldVisitDetail);
          setDraft(j.data.summary || j.data.situation_note || "");
        }
        load();
      })
      .catch((e) => setErr(String(e)));
  };

  const fmtStart = (iso: string | null | undefined) =>
    iso ? iso.replace("T", " ").slice(0, 16) : "—";

  return (
    <div className="px-6 py-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">拜访签到</h2>
          <p className="text-xs text-[var(--text-muted)]">新建即开始 · 签退须满 15 分钟</p>
        </div>
        <button type="button" className="rounded bg-[var(--accent)] px-3 py-1 text-xs text-slate-950" onClick={() => setNewOpen(true)}>
          新建外勤
        </button>
      </div>
      {stats && (
        <div className="mt-3 flex flex-wrap gap-2 text-[11px]">
          <button
            type="button"
            className={`rounded-full border px-2 py-0.5 ${filterNotMeeting ? "border-amber-400 text-amber-300" : ""}`}
            style={{ borderColor: "var(--line)" }}
            onClick={() => {
              setFilterNotMeeting((v) => !v);
              setFilterTag(null);
            }}
          >
            不达标 {stats.not_meeting}
          </button>
          {Object.entries(stats.by_tag).map(([tag, n]) => (
            <button
              key={tag}
              type="button"
              className={`rounded-full border px-2 py-0.5 ${filterTag === tag ? "border-[var(--accent)] text-[var(--accent)]" : ""}`}
              style={{ borderColor: "var(--line)" }}
              onClick={() => {
                setFilterTag((t) => (t === tag ? null : tag));
                setFilterNotMeeting(false);
              }}
            >
              {tag} {n}
            </button>
          ))}
        </div>
      )}
      {err && <p className="mt-2 text-xs text-rose-400">{err}</p>}
      <table className="mt-4 w-full text-xs">
        <thead className="text-[var(--text-muted)]">
          <tr>
            <th className="text-left">编码</th>
            <th>标题</th>
            <th>客户</th>
            <th>开始</th>
            <th>持续(分)</th>
            <th>进展</th>
            <th>达标</th>
            <th>状态</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.code} className="border-t" style={{ borderColor: "var(--line)" }}>
              <td className="py-2 font-mono">{r.code}</td>
              <td>
                <button type="button" className="underline" onClick={() => openDetail(r.code)}>
                  {r.title}
                </button>
              </td>
              <td>{r.customer_name || "—"}</td>
              <td>{fmtStart(r.started_at)}</td>
              <td>{r.elapsed_minutes ?? r.visit_minutes ?? "—"}</td>
              <td>{(r.progress_tags ?? []).slice(0, 2).join("、") || "—"}</td>
              <td>{r.meets_standard === true ? "是" : r.meets_standard === false ? "否" : "—"}</td>
              <td>{r.status}</td>
              <td className="space-x-2">
                {r.status === "待签到" && (
                  <button type="button" className="text-[var(--accent)]" onClick={() => act(r.code, "sign-in")}>
                    签到
                  </button>
                )}
                {(r.status === "已签到" || r.status === "进行中") && (
                  <button type="button" className="text-[var(--accent)]" onClick={() => act(r.code, "sign-out")}>
                    签退
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <SideDrawer open={!!open} onClose={() => setOpen(null)} title={open?.title ?? "外勤详情"}>
        {open && (
          <div className="space-y-2 text-xs">
            <div
              className={`rounded-lg border p-3 text-center text-sm font-semibold ${
                open.meets_standard === true
                  ? "border-emerald-600 text-emerald-300"
                  : open.meets_standard === false
                    ? "border-amber-600 text-amber-200"
                    : "border-[var(--line)] text-[var(--text-muted)]"
              }`}
            >
              {open.meets_standard === true
                ? "拜访达标"
                : open.meets_standard === false
                  ? "尚未达标"
                  : "待归纳评估"}
              {open.standard_reason && open.meets_standard === false && (
                <p className="mt-1 text-[10px] font-normal">{open.standard_reason}</p>
              )}
            </div>
            <p>状态：{open.status}</p>
            <p>
              时长：{open.elapsed_minutes ?? open.visit_minutes ?? "—"} 分钟
              {open.eval_source && <span className="text-[var(--text-muted)]"> · {open.eval_source}</span>}
            </p>
            {open.minutes_until_checkout_ok != null && (
              <p className="text-amber-300">签退还差 {open.minutes_until_checkout_ok} 分钟</p>
            )}
            {(open.timeline ?? []).length > 0 && (
              <ul className="space-y-1 rounded border p-2" style={{ borderColor: "var(--line)" }}>
                {(open.timeline ?? []).map((t) => (
                  <li key={t.id}>
                    <span className="text-[var(--text-muted)]">{fmtStart(t.recorded_at)}</span> · {t.body}
                  </li>
                ))}
              </ul>
            )}
            {open.status !== "已确认" && (
              <div className="flex gap-2">
                <input
                  className="min-w-0 flex-1 rounded border px-2 py-1"
                  style={{ borderColor: "var(--line)" }}
                  value={logDraft}
                  onChange={(e) => setLogDraft(e.target.value)}
                  placeholder="追加一条拜访记录…"
                />
                <button type="button" className="shrink-0 rounded border px-2 py-1" style={{ borderColor: "var(--line)" }} onClick={addLog}>
                  追加
                </button>
              </div>
            )}
            <label className="block">
              拜访情况 / 归纳
              <textarea
                className="mt-1 w-full rounded border p-2"
                style={{ borderColor: "var(--line)", background: "var(--bg-body)" }}
                rows={6}
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                disabled={open.status === "已确认"}
              />
            </label>
            {matchInfo && (
              <div className="rounded border p-2 text-[10px]" style={{ borderColor: "var(--line)" }}>
                <p>匹配客户：{(matchInfo.customers ?? []).map((c) => c.name).join("、") || "无"}</p>
                <p>匹配线索：{(matchInfo.leads ?? []).map((l) => l.code).join("、") || "无"}</p>
                {matchInfo.opp_draft && <p className="text-amber-200">{matchInfo.opp_draft.hint}</p>}
                {(matchInfo.customers ?? []).length > 0 && (
                  <select className="mt-1 w-full rounded border px-1 py-0.5" value={pickCustomer} onChange={(e) => setPickCustomer(e.target.value)}>
                    <option value="">选择关联客户</option>
                    {matchInfo.customers.map((c) => (
                      <option key={c.code} value={c.code}>{c.name}</option>
                    ))}
                  </select>
                )}
                {(matchInfo.leads ?? []).length > 0 && (
                  <select className="mt-1 w-full rounded border px-1 py-0.5" value={pickLead} onChange={(e) => setPickLead(e.target.value)}>
                    <option value="">选择关联线索</option>
                    {matchInfo.leads.map((l) => (
                      <option key={l.code} value={l.code}>{l.company_name}</option>
                    ))}
                  </select>
                )}
                <label className="mt-1 flex items-center gap-1">
                  <input type="checkbox" checked={createCustomer} onChange={(e) => setCreateCustomer(e.target.checked)} />
                  陌生拜访 · 确认时新建客户
                </label>
                {matchInfo.opp_draft && (
                  <label className="mt-1 flex items-center gap-1">
                    <input type="checkbox" checked={confirmOpp} onChange={(e) => setConfirmOpp(e.target.checked)} />
                    确认建立商机
                  </label>
                )}
              </div>
            )}
            {open.status !== "已确认" && (
              <div className="flex flex-wrap gap-2">
                <button type="button" className="rounded border px-2 py-1" style={{ borderColor: "var(--line)" }} onClick={saveDetail}>
                  保存
                </button>
                <button type="button" className="rounded border px-2 py-1 text-sky-300" style={{ borderColor: "var(--line)" }} onClick={aiParse}>
                  AI 整理
                </button>
                <button type="button" className="rounded border px-2 py-1 text-violet-300" style={{ borderColor: "var(--line)" }} onClick={finalizeVisit}>
                  归纳成果
                </button>
                {open.status === "已完成" && (
                  <button type="button" className="rounded bg-emerald-700 px-2 py-1 text-white" onClick={confirmFollow}>
                    确认写入跟进
                  </button>
                )}
              </div>
            )}
          </div>
        )}
      </SideDrawer>
      <SideDrawer open={newOpen} onClose={() => setNewOpen(false)} title="新建外勤">
        <div className="space-y-2 text-xs">
          <input className="w-full rounded border px-2 py-1" style={{ borderColor: "var(--line)" }} value={newTitle} onChange={(e) => setNewTitle(e.target.value)} placeholder="标题" />
          <input className="w-full rounded border px-2 py-1" style={{ borderColor: "var(--line)" }} value={newCustomer} onChange={(e) => setNewCustomer(e.target.value)} placeholder="客户名称（可空）" />
          <button type="button" className="rounded bg-[var(--accent)] px-3 py-1 text-slate-950" onClick={createVisit}>
            创建
          </button>
        </div>
      </SideDrawer>
    </div>
  );
}

export function OpportunitiesListPage() {
  const auth = useAuth();
  const role = auth.role!;
  const demoSeedReload = useGuidedDemoSeedReload("opportunity");
  const [rows, setRows] = useState<
    {
      id: number;
      name: string;
      customer_name: string;
      stage: string;
      stage_label?: string;
      source?: string;
      amount: number;
      owner_sales: string;
      expect_close_date: string | null;
    }[]
  >([]);
  const [openId, setOpenId] = useState<number | null>(null);
  const [funnel, setFunnel] = useState<OppFunnelData | null>(null);

  useEffect(() => {
    requestWithRole<typeof rows>("/api/crm/opportunities", role).then(setRows);
    requestWithRole<OppFunnelData>("/api/crm/opportunities/funnel", role).then(setFunnel);
  }, [role, demoSeedReload]);

  return (
    <div className="px-6 py-4">
      <h2 className="text-lg font-semibold">商机</h2>
      <p className="text-xs text-[var(--text-muted)]">
        商机单据列表 · 大盘漏斗见 <Link to="/crm/opportunities">商机大盘</Link>
      </p>
      <OpportunityFunnelBar data={funnel} />
      <table className="mt-4 w-full text-xs">
        <thead className="text-[var(--text-muted)]">
          <tr>
            <th className="text-left">商机标题</th>
            <th>客户</th>
            <th>来源</th>
            <th>阶段</th>
            <th>金额</th>
            <th>负责人</th>
            <th>预计成交</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id} className="border-t" style={{ borderColor: "var(--line)" }}>
              <td className="py-2">
                <button type="button" className="text-[var(--accent)] underline" onClick={() => setOpenId(r.id)}>
                  {r.name}
                </button>
              </td>
              <td>{r.customer_name}</td>
              <td>{r.source ?? "—"}</td>
              <td>{r.stage_label ?? r.stage}</td>
              <td className="tabular-nums">{r.amount}</td>
              <td>{r.owner_sales}</td>
              <td>{r.expect_close_date ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <OpportunityDetailDrawer oppId={openId} onClose={() => setOpenId(null)} />
    </div>
  );
}
