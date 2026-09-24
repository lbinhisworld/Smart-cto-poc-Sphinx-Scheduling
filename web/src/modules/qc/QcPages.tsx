import { Link, NavLink, useSearchParams } from "react-router-dom";
import { useCallback, useEffect, useState } from "react";
import { requestWithRole } from "../../api/client";
import { useGuidedDemoSeedReload } from "../../hooks/guidedDemoSeed";
import { useAuth } from "../../shell/auth";

const linkClass = ({ isActive }: { isActive: boolean }) =>
  `text-sm ${isActive ? "font-semibold text-[var(--accent)]" : "text-[var(--text-muted)] hover:text-[var(--accent)]"}`;

async function downloadQcExport(path: string, role: string, filename: string) {
  const res = await fetch(path, { headers: { "X-Demo-Role": role } });
  if (!res.ok) throw new Error("导出失败");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function QcNav() {
  return (
    <nav className="mb-4 flex flex-wrap gap-3 border-b pb-2" style={{ borderColor: "var(--line)" }}>
      <NavLink to="/qc/receipts" className={linkClass}>
        来料
      </NavLink>
      <NavLink to="/qc/exceptions" className={linkClass}>
        异常
      </NavLink>
      <NavLink to="/qc/daily-defects" className={linkClass}>
        每日异常
      </NavLink>
      <NavLink to="/qc/complaints" className={linkClass}>
        客诉
      </NavLink>
      <NavLink to="/qc/audits" className={linkClass}>
        审核
      </NavLink>
      <NavLink to="/qc/lab-external" className={linkClass}>
        外来测试
      </NavLink>
      <NavLink to="/qc/swab-tests" className={linkClass}>
        涂抹检测
      </NavLink>
      <NavLink to="/qc/product-tests" className={linkClass}>
        产品检测
      </NavLink>
      <NavLink to="/qc/master" className={linkClass}>
        主数据
      </NavLink>
    </nav>
  );
}

function LedgerShell({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="px-6 py-4">
      <h2 className="text-lg font-semibold">{title}</h2>
      <p className="mt-1 text-xs text-[var(--text-muted)]">M9 品控台账 · Excel 对齐</p>
      <QcNav />
      {children}
    </div>
  );
}

function SimpleTable({ columns, rows }: { columns: string[]; rows: (string | number)[][] }) {
  return (
    <div
      className="mt-4 overflow-x-auto rounded-lg border"
      style={{ borderColor: "var(--line)", background: "var(--bg-card)" }}
    >
      <table className="w-full min-w-[640px] border-collapse text-xs">
        <thead className="bg-[var(--table-head)] text-[var(--text-muted)]">
          <tr>
            {columns.map((c) => (
              <th
                key={c}
                className="border-b px-3 py-2 text-left text-xs font-medium"
                style={{ borderColor: "var(--line)" }}
              >
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className="px-3 py-8 text-center text-[var(--text-muted)]">
                暂无数据
              </td>
            </tr>
          ) : (
            rows.map((row, i) => (
              <tr
                key={i}
                className="border-t hover:bg-[var(--table-row-hover)]"
                style={{
                  borderColor: "var(--line)",
                  background: i % 2 === 1 ? "var(--table-stripe)" : undefined,
                }}
              >
                {row.map((cell, j) => (
                  <td key={j} className="whitespace-nowrap px-3 py-2">
                    {cell}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

export function QcReceiptsPage() {
  const { role } = useAuth();
  const [rows, setRows] = useState<Record<string, unknown>[]>([]);
  const load = useCallback(() => {
    if (!role) return;
    requestWithRole<Record<string, unknown>[]>("/api/qc/receipts", role).then(setRows);
  }, [role]);
  useEffect(() => {
    load();
  }, [load]);
  return (
    <LedgerShell title="原辅料来料台账">
      <button
        type="button"
        className="mt-2 rounded border px-2 py-1 text-xs hover:bg-[var(--table-row-hover)]"
        style={{ borderColor: "var(--line)" }}
        onClick={() => {
          if (!role) return;
          void downloadQcExport("/api/qc/export/receipts", role, "qc_receipts.csv");
        }}
      >
        导出 CSV
      </button>
      <SimpleTable
        columns={["单号", "日期", "供应商", "物料", "批次", "数量"]}
        rows={rows.map((r) => [
          String(r.receipt_no),
          String(r.incoming_date),
          String(r.supplier_name),
          String(r.material_name),
          String(r.batch_no),
          `${r.qty} ${r.uom}`,
        ])}
      />
    </LedgerShell>
  );
}

export function QcExceptionsPage() {
  const { role } = useAuth();
  const [rows, setRows] = useState<Record<string, unknown>[]>([]);
  useEffect(() => {
    if (!role) return;
    requestWithRole<Record<string, unknown>[]>("/api/qc/exceptions", role).then(setRows);
  }, [role]);
  return (
    <LedgerShell title="原辅料异常台账">
      <SimpleTable
        columns={["异常单号", "状态", "现象", "来料单"]}
        rows={rows.map((r) => {
          const rcpt = r.receipt as Record<string, unknown> | undefined;
          return [
            String(r.exception_no),
            String(r.status),
            String(r.phenomenon).slice(0, 40),
            String(rcpt?.receipt_no ?? r.receipt_id),
          ];
        })}
      />
    </LedgerShell>
  );
}

export function QcDailyDefectsPage() {
  const { role } = useAuth();
  const [rows, setRows] = useState<Record<string, unknown>[]>([]);
  useEffect(() => {
    if (!role) return;
    requestWithRole<Record<string, unknown>[]>("/api/qc/daily-defects", role).then(setRows);
  }, [role]);
  return (
    <LedgerShell title="每日异常记录">
      <SimpleTable
        columns={["日期", "部门", "品名", "不良数", "案号"]}
        rows={rows.map((r) => [
          String(r.record_date),
          String(r.dept_found),
          String(r.product_name),
          String(r.defect_qty),
          String(r.case_no),
        ])}
      />
    </LedgerShell>
  );
}

export function QcComplaintsPage() {
  const { role } = useAuth();
  const [searchParams] = useSearchParams();
  const customerCode = searchParams.get("customer_code");
  const highlightId = searchParams.get("id");
  const [rows, setRows] = useState<Record<string, unknown>[]>([]);
  useEffect(() => {
    if (!role) return;
    requestWithRole<Record<string, unknown>[]>("/api/qc/complaints", role).then(setRows);
  }, [role]);
  const visible = customerCode
    ? rows.filter((r) => String(r.customer_code ?? "") === customerCode)
    : rows;
  return (
    <LedgerShell title="客诉登记台账">
      {customerCode && (
        <p className="mb-2 text-xs text-[var(--text-muted)]">
          已筛选客户编码：<span className="font-mono text-[var(--text)]">{customerCode}</span>
          {highlightId ? ` · 记录 #${highlightId}` : ""}
          <Link to="/qc/complaints" className="ml-2 text-[var(--accent)] hover:underline">
            清除筛选
          </Link>
        </p>
      )}
      <SimpleTable
        columns={["日期", "客户", "产品编码", "状态", "内容"]}
        rows={visible.map((r) => [
          String(r.record_date),
          String(r.customer_name),
          String(r.item_code),
          String(r.status),
          String(r.content).slice(0, 30),
        ])}
      />
    </LedgerShell>
  );
}

export function QcAuditsPage() {
  const { role } = useAuth();
  const [rows, setRows] = useState<Record<string, unknown>[]>([]);
  useEffect(() => {
    if (!role) return;
    requestWithRole<Record<string, unknown>[]>("/api/qc/audits", role).then(setRows);
  }, [role]);
  return (
    <LedgerShell title="第二方/第三方审核">
      <SimpleTable
        columns={["审核日期", "类型", "不符合项", "结果"]}
        rows={rows.map((r) => [
          String(r.audit_date),
          String(r.audit_type),
          String(r.nc_count),
          String(r.audit_result),
        ])}
      />
    </LedgerShell>
  );
}

export function QcLabExternalPage() {
  const { role } = useAuth();
  const [rows, setRows] = useState<Record<string, unknown>[]>([]);
  useEffect(() => {
    if (!role) return;
    requestWithRole<Record<string, unknown>[]>("/api/qc/lab-external", role).then(setRows);
  }, [role]);
  return (
    <LedgerShell title="实验室外来测试">
      <SimpleTable
        columns={["接受日期", "客户", "产品", "测试项目"]}
        rows={rows.map((r) => [
          String(r.accepted_date),
          String(r.customer_name),
          String(r.product_name),
          String(r.test_items).slice(0, 30),
        ])}
      />
    </LedgerShell>
  );
}

export function QcSwabTestsPage() {
  const { role } = useAuth();
  const [rows, setRows] = useState<Record<string, unknown>[]>([]);
  useEffect(() => {
    if (!role) return;
    requestWithRole<Record<string, unknown>[]>("/api/qc/swab-tests", role).then(setRows);
  }, [role]);
  return (
    <LedgerShell title="涂抹检测台账">
      <SimpleTable
        columns={["采样日", "菌落", "大肠菌群", "系统判定", "有效判定"]}
        rows={rows.map((r) => [
          String(r.sampling_date),
          String(r.tpc_cfu_ml),
          String(r.coliform_cfu_ml),
          String(r.verdict_computed),
          String(r.verdict_effective),
        ])}
      />
    </LedgerShell>
  );
}

export function QcProductTestsPage() {
  const { role } = useAuth();
  const demoSeedReload = useGuidedDemoSeedReload("qc");
  const [rows, setRows] = useState<Record<string, unknown>[]>([]);
  useEffect(() => {
    if (!role) return;
    requestWithRole<Record<string, unknown>[]>("/api/qc/product-tests", role).then(setRows);
  }, [role, demoSeedReload]);
  return (
    <LedgerShell title="产品检测台账">
      <SimpleTable
        columns={["采样日", "产品", "水分", "判定"]}
        rows={rows.map((r) => [
          String(r.sampling_date),
          String(r.product_name),
          String(r.moisture_pct),
          String(r.verdict_effective),
        ])}
      />
    </LedgerShell>
  );
}

export function QcMasterPage() {
  const { role } = useAuth();
  const [suppliers, setSuppliers] = useState<Record<string, unknown>[]>([]);
  const [materials, setMaterials] = useState<Record<string, unknown>[]>([]);
  const load = useCallback(() => {
    if (!role) return;
    requestWithRole<Record<string, unknown>[]>("/api/qc/master/suppliers", role).then(setSuppliers);
    requestWithRole<Record<string, unknown>[]>("/api/qc/master/raw-materials", role).then(setMaterials);
  }, [role]);
  useEffect(() => {
    load();
  }, [load]);
  const sync = async (path: string) => {
    if (!role) return;
    await requestWithRole(path, role, { method: "POST" });
    load();
  };
  return (
    <LedgerShell title="品控主数据（金蝶 1:1）">
      <div className="mt-2 flex flex-wrap gap-2">
        <button
          type="button"
          className="rounded border px-2 py-1 text-xs"
          onClick={() => sync("/api/kingdee/sync-suppliers")}
        >
          同步供应商
        </button>
        <button
          type="button"
          className="rounded border px-2 py-1 text-xs"
          onClick={() => sync("/api/kingdee/sync-raw-materials")}
        >
          同步原辅料
        </button>
        <Link to="/kingdee" className="text-xs text-[var(--accent)] underline">
          金蝶工作台
        </Link>
      </div>
      <h3 className="mt-4 text-sm font-medium">供应商</h3>
      <SimpleTable
        columns={["编码", "名称"]}
        rows={suppliers.map((s) => [String(s.supplier_code), String(s.name)])}
      />
      <h3 className="mt-4 text-sm font-medium">原辅料</h3>
      <SimpleTable
        columns={["编码", "名称", "规格"]}
        rows={materials.map((m) => [String(m.material_code), String(m.name), String(m.spec)])}
      />
    </LedgerShell>
  );
}
