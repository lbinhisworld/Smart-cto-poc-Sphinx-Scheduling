import { useEffect, useState } from "react";
import { requestWithRole } from "../../api/client";
import { useAuth } from "../../shell/auth";
import { ContractDetailPanel, CreateContractPanel } from "./ContractPanels";
import {
  Customer360Data,
  Customer360Panel,
  OpportunityDetailPanel,
  OrderDetailPanel,
  SampleDetailPanel,
} from "./crm360Panels";

export type Crm360StackEntry =
  | { kind: "customer"; code: string }
  | { kind: "sample"; code: string }
  | { kind: "opportunity"; id: number }
  | { kind: "order"; orderNo: string }
  | { kind: "contract"; contractNo: string }
  | { kind: "contract-new"; customerCode: string };

type Props = {
  customerCode: string | null;
  onClose: () => void;
};

function stackTitle(top: Crm360StackEntry | undefined): string {
  if (!top) return "客户 360";
  switch (top.kind) {
    case "customer":
      return `客户 360 · ${top.code}`;
    case "sample":
      return `打样 · ${top.code}`;
    case "opportunity":
      return `商机 #${top.id}`;
    case "order":
      return `订单 · ${top.orderNo}`;
    case "contract":
      return `合同 · ${top.contractNo}`;
    case "contract-new":
      return "新建合同";
    default:
      return "详情";
  }
}

export function Customer360Drawer({ customerCode, onClose }: Props) {
  const auth = useAuth();
  const role = auth.role;
  const [stack, setStack] = useState<Crm360StackEntry[]>([]);
  const [customerData, setCustomerData] = useState<Customer360Data | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!customerCode || !role) {
      setStack([]);
      setCustomerData(null);
      return;
    }
    setStack([{ kind: "customer", code: customerCode }]);
    setErr(null);
    requestWithRole<Customer360Data>(`/api/crm/customers/${encodeURIComponent(customerCode)}`, role)
      .then(setCustomerData)
      .catch((e) => setErr(String(e)));
  }, [customerCode, role]);

  if (!customerCode) return null;

  const top = stack[stack.length - 1];
  const canBack = stack.length > 1;

  const goBack = () => setStack((s) => (s.length > 1 ? s.slice(0, -1) : s));

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/45" role="dialog" onClick={onClose}>
      <div
        className="flex h-full w-full max-w-xl flex-col overflow-hidden shadow-xl"
        style={{ background: "var(--bg-card)" }}
        onClick={(e) => e.stopPropagation()}
      >
        <div
          className="flex shrink-0 items-center gap-2 border-b px-3 py-3"
          style={{ borderColor: "var(--line)" }}
        >
          {canBack ? (
            <button type="button" className="text-sm text-[var(--accent)]" onClick={goBack}>
              ← 返回
            </button>
          ) : (
            <span className="w-12" />
          )}
          <p className="min-w-0 flex-1 truncate text-sm font-semibold">{stackTitle(top)}</p>
          <button type="button" className="text-sm text-[var(--text-muted)]" onClick={onClose}>
            关闭
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto p-4">
          {err && <p className="text-xs text-rose-400">{err}</p>}
          {top?.kind === "customer" && customerData && (
            <Customer360Panel
              data={customerData}
              onOpenSample={(code) => setStack((s) => [...s, { kind: "sample", code }])}
              onOpenOpportunity={(id) => setStack((s) => [...s, { kind: "opportunity", id }])}
              onOpenOrder={(orderNo) => setStack((s) => [...s, { kind: "order", orderNo }])}
              onOpenContract={(contractNo) => setStack((s) => [...s, { kind: "contract", contractNo }])}
              onNewContract={() =>
                setStack((s) => [...s, { kind: "contract-new", customerCode: customerCode! }])
              }
            />
          )}
          {top?.kind === "customer" && !customerData && !err && (
            <p className="text-xs text-[var(--text-muted)]">加载客户 360…</p>
          )}
          {top?.kind === "sample" && <SampleDetailPanel sampleCode={top.code} />}
          {top?.kind === "opportunity" && <OpportunityDetailPanel oppId={top.id} />}
          {top?.kind === "order" && <OrderDetailPanel orderNo={top.orderNo} />}
          {top?.kind === "contract" && (
            <ContractDetailPanel
              contractNo={top.contractNo}
              onOpenOrder={(orderNo) => setStack((s) => [...s, { kind: "order", orderNo }])}
            />
          )}
          {top?.kind === "contract-new" && (
            <CreateContractPanel
              customerCode={top.customerCode}
              onCancel={goBack}
              onCreated={(contractNo) => {
                requestWithRole<Customer360Data>(
                  `/api/crm/customers/${encodeURIComponent(top.customerCode)}`,
                  role!,
                ).then(setCustomerData);
                setStack((s) => [...s.slice(0, -1), { kind: "contract", contractNo }]);
              }}
            />
          )}
        </div>
      </div>
    </div>
  );
}
