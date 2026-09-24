import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../../shell/auth";
import { FollowAddForm } from "./FollowSection";

type LeadRow = {
  code: string;
  status: string;
  contact_name: string;
  gender?: string;
  phone: string;
  wechat?: string;
  company_name: string;
  follow_situation: string;
  last_follow_date: string | null;
  next_follow_date: string | null;
  owner_sales: string;
  owner_dept?: string;
  detail_text: string;
  customer_level?: string;
  tags?: string;
  pool_name?: string;
  assigned_by?: string;
  assigned_at?: string | null;
  industry?: string;
  source?: string;
  created_by?: string;
  created_at?: string;
};

type LeadDetail = LeadRow & {
  follow_records: {
    id: number;
    follow_date: string;
    content: string;
    next_follow_date: string | null;
    record_type: string;
  }[];
};

function LeadTable({
  pool,
  canAssign,
}: {
  pool: boolean;
  canAssign?: boolean;
}) {
  const auth = useAuth();
  const [rows, setRows] = useState<LeadRow[]>([]);
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [open, setOpen] = useState<LeadDetail | null>(null);
  const [assignTo, setAssignTo] = useState("李业务");

  const load = useCallback(() => {
    const q = pool ? "?pool=true" : "?pool=false";
    fetch(`/api/crm/leads${q}&today=2026-09-15`, { headers: auth.headers() })
      .then((r) => r.json())
      .then((j) => setRows(j.data ?? []));
  }, [auth, pool]);

  useEffect(() => {
    load();
  }, [load]);

  const openDetail = (code: string) => {
    fetch(`/api/crm/leads/${encodeURIComponent(code)}`, { headers: auth.headers() })
      .then((r) => r.json())
      .then((j) => setOpen(j.data));
  };

  const toggle = (code: string) => {
    setPicked((prev) => {
      const next = new Set(prev);
      if (next.has(code)) next.delete(code);
      else next.add(code);
      return next;
    });
  };

  const assign = () => {
    fetch("/api/crm/leads/assign", {
      method: "POST",
      headers: { ...auth.headers(), "Content-Type": "application/json" },
      body: JSON.stringify({ codes: [...picked], owner_sales: assignTo }),
    }).then(() => {
      setPicked(new Set());
      load();
    });
  };

  return (
    <div>
      {canAssign && (
        <div className="mb-3 flex flex-wrap items-center gap-2 text-xs">
          <input
            className="rounded border px-2 py-1"
            style={{ borderColor: "var(--line)" }}
            value={assignTo}
            onChange={(e) => setAssignTo(e.target.value)}
          />
          <button type="button" className="rounded bg-[var(--accent)] px-3 py-1 text-white" onClick={assign} disabled={picked.size === 0}>
            批量分配
          </button>
        </div>
      )}
      <div className="overflow-auto rounded border" style={{ borderColor: "var(--line)" }}>
        <table className="min-w-full text-left text-xs">
          <thead className="text-[var(--text-muted)]">
            <tr>
              {canAssign && <th className="px-2 py-2" />}
              <th className="px-2 py-2">线索状态</th>
              <th className="px-2 py-2">联系人</th>
              <th className="px-2 py-2">联系电话</th>
              <th className="px-2 py-2">跟进情况</th>
              <th className="px-2 py-2">最近跟进</th>
              <th className="px-2 py-2">下次跟进</th>
              <th className="px-2 py-2">负责人</th>
              <th className="px-2 py-2">部门</th>
              <th className="px-2 py-2">公司名称</th>
              <th className="px-2 py-2">线索池</th>
              <th className="px-2 py-2">来源</th>
              <th className="px-2 py-2">创建时间</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.code} className="border-t cursor-pointer hover:bg-black/5" style={{ borderColor: "var(--line)" }} onClick={() => openDetail(row.code)}>
                {canAssign && (
                  <td className="px-2 py-2" onClick={(e) => e.stopPropagation()}>
                    <input type="checkbox" checked={picked.has(row.code)} onChange={() => toggle(row.code)} />
                  </td>
                )}
                <td className="px-2 py-2">{row.status}</td>
                <td className="px-2 py-2">{row.contact_name}</td>
                <td className="px-2 py-2">{row.phone}</td>
                <td className="px-2 py-2">{row.follow_situation}</td>
                <td className="px-2 py-2 tabular-nums">{row.last_follow_date ?? "—"}</td>
                <td className="px-2 py-2 tabular-nums">{row.next_follow_date ?? "—"}</td>
                <td className="px-2 py-2">{row.owner_sales || "—"}</td>
                <td className="px-2 py-2">{row.owner_dept || "—"}</td>
                <td className="px-2 py-2">{row.company_name}</td>
                <td className="px-2 py-2">{row.pool_name || "—"}</td>
                <td className="px-2 py-2">{row.source || "—"}</td>
                <td className="px-2 py-2 tabular-nums">{row.created_at?.slice(0, 10) ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {open && (
        <div className="fixed inset-0 z-40 flex justify-end bg-black/30" onClick={() => setOpen(null)}>
          <aside className="h-full w-full max-w-lg overflow-auto p-4" style={{ background: "var(--bg-card)" }} onClick={(e) => e.stopPropagation()}>
            <div className="flex justify-between">
              <h2 className="font-semibold">线索详情</h2>
              <button type="button" onClick={() => setOpen(null)}>关闭</button>
            </div>
            <p className="mt-1 font-mono text-xs text-[var(--text-muted)]">{open.code}</p>
            <dl className="mt-4 grid grid-cols-2 gap-2 text-sm">
              <div><dt className="text-xs text-[var(--text-muted)]">联系人</dt><dd>{open.contact_name}</dd></div>
              <div><dt className="text-xs text-[var(--text-muted)]">联系电话</dt><dd>{open.phone}</dd></div>
              <div className="col-span-2"><dt className="text-xs text-[var(--text-muted)]">公司名称</dt><dd>{open.company_name}</dd></div>
              <div className="col-span-2"><dt className="text-xs text-[var(--text-muted)]">销售线索详情</dt><dd>{open.detail_text || "-"}</dd></div>
            </dl>
            <h3 className="mt-4 text-sm font-medium">跟进记录</h3>
            <ul className="mt-2 space-y-2 text-xs">
              {open.follow_records.map((f) => (
                <li key={f.id} className="rounded border p-2" style={{ borderColor: "var(--line)" }}>
                  <p className="text-[var(--text-muted)]">{f.follow_date} · {f.record_type}</p>
                  <p>{f.content}</p>
                </li>
              ))}
              {open.follow_records.length === 0 && <li className="text-[var(--text-muted)]">暂无跟进</li>}
            </ul>
            <FollowAddForm
              recordType="线索"
              leadCode={open.code}
              onSaved={() => openDetail(open.code)}
            />
            {open.status !== "已丢失" && open.status !== "已转化" && (
              <div className="mt-4 flex flex-wrap gap-2 text-xs">
                <button
                  type="button"
                  className="rounded border px-2 py-1"
                  style={{ borderColor: "var(--line)" }}
                  onClick={() => {
                    fetch(`/api/crm/leads/${encodeURIComponent(open.code)}/convert-customer`, {
                      method: "POST",
                      headers: { ...auth.headers(), "Content-Type": "application/json" },
                      body: JSON.stringify({ convert_note: "线索转客户" }),
                    }).then(() => openDetail(open.code));
                  }}
                >
                  转为客户
                </button>
                <button
                  type="button"
                  className="rounded bg-[var(--accent)] px-2 py-1 text-slate-950"
                  onClick={() => {
                    fetch(`/api/crm/leads/${encodeURIComponent(open.code)}/convert-opportunity`, {
                      method: "POST",
                      headers: { ...auth.headers(), "Content-Type": "application/json" },
                      body: JSON.stringify({ name: `${open.company_name}·商机`, amount: 50000 }),
                    }).then(() => openDetail(open.code));
                  }}
                >
                  转为商机
                </button>
                <select
                  className="rounded border px-2 py-1"
                  style={{ borderColor: "var(--line)" }}
                  defaultValue=""
                  onChange={(e) => {
                    const reason = e.target.value;
                    if (!reason) return;
                    fetch(`/api/crm/leads/${encodeURIComponent(open.code)}/lose`, {
                      method: "POST",
                      headers: { ...auth.headers(), "Content-Type": "application/json" },
                      body: JSON.stringify({ reason }),
                    }).then(() => {
                      setOpen(null);
                      load();
                    });
                  }}
                >
                  <option value="">标记丢失…</option>
                  {["价格", "交期", "样品未过", "客户取消", "其他"].map((r) => (
                    <option key={r} value={r}>{r}</option>
                  ))}
                </select>
              </div>
            )}
          </aside>
        </div>
      )}
    </div>
  );
}

export function MyLeadsPage() {
  return (
    <div className="p-4">
      <h1 className="text-lg font-semibold">我的线索</h1>
      <p className="mt-1 text-xs text-[var(--text-muted)]">打开列表时会按线索池规则回收未有效跟进的线索。</p>
      <div className="mt-4">
        <LeadTable pool={false} />
      </div>
    </div>
  );
}

export function LeadPoolPage() {
  return (
    <div className="p-4">
      <h1 className="text-lg font-semibold">线索池</h1>
      <div className="mt-4">
        <LeadTable pool canAssign />
      </div>
    </div>
  );
}

export function LeadPoolRulesPage() {
  const auth = useAuth();
  const [rules, setRules] = useState<{ id: number; pool_name: string; admin_name: string; members: string[]; recycle_days: number | null }[]>([]);
  const [open, setOpen] = useState<(typeof rules)[0] | null>(null);

  useEffect(() => {
    fetch("/api/crm/lead-pool-rules", { headers: auth.headers() })
      .then((r) => r.json())
      .then((j) => setRules(j.data ?? []));
  }, [auth]);

  return (
    <div className="p-4">
      <h1 className="text-lg font-semibold">线索池规则</h1>
      <p className="mt-1 text-xs text-[var(--text-muted)]">有效跟进 = 已确认且满 15 分钟的客户拜访，并挂在这条线索上。</p>
      <table className="mt-4 min-w-full text-left text-xs">
        <thead>
          <tr className="text-[var(--text-muted)]">
            <th className="py-2">线索池名称</th>
            <th className="py-2">管理员</th>
            <th className="py-2">成员</th>
            <th className="py-2">未跟进回收天数</th>
          </tr>
        </thead>
        <tbody>
          {rules.map((r) => (
            <tr key={r.id} className="border-t cursor-pointer" style={{ borderColor: "var(--line)" }} onClick={() => setOpen(r)}>
              <td className="py-2">{r.pool_name}</td>
              <td className="py-2">{r.admin_name}</td>
              <td className="py-2">{r.members.join("、")}</td>
              <td className="py-2">{r.recycle_days ?? "-"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {open && (
        <div className="fixed inset-0 z-40 flex justify-end bg-black/30" onClick={() => setOpen(null)}>
          <aside className="h-full w-full max-w-md p-4" style={{ background: "var(--bg-card)" }} onClick={(e) => e.stopPropagation()}>
            <h2 className="font-semibold">规则详情</h2>
            <p className="mt-3 text-sm">线索池名称：{open.pool_name}</p>
            <p className="mt-2 text-sm">管理员：{open.admin_name}</p>
            <p className="mt-2 text-sm">线索池成员：{open.members.join("、")}</p>
            <p className="mt-2 text-sm">未跟进回收天数：{open.recycle_days ?? "不自动回收"}</p>
          </aside>
        </div>
      )}
    </div>
  );
}
