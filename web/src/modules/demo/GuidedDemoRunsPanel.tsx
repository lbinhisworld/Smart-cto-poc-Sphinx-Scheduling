import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../../shell/auth";

type RunRow = {
  id: string;
  title: string;
  status: string;
  current_step_id?: string;
  current_step_title?: string;
  current_seq?: number;
  feedback_count: number;
  seed_event_count: number;
  snapshot_count?: number;
  is_active: boolean;
  is_replay?: boolean;
  can_replay?: boolean;
  can_continue?: boolean;
  can_end?: boolean;
};

type Step = { seq: number; step_id: string; title: string; list_path: string };

function statusLabel(status: string): string {
  switch (status) {
    case "DRAFT":
      return "草稿";
    case "ACTIVE":
      return "进行中";
    case "ENDED":
      return "已结束";
    default:
      return status;
  }
}

function statusBadgeClass(status: string): string {
  switch (status) {
    case "ACTIVE":
      return "bg-emerald-900/60 text-emerald-200 ring-emerald-700/50";
    case "ENDED":
      return "bg-slate-800 text-slate-300 ring-slate-600/50";
    default:
      return "bg-slate-900 text-slate-400 ring-slate-700/50";
  }
}

function downloadExport(
  auth: { headers: () => HeadersInit },
  runId: string,
  title: string,
  onError?: (msg: string) => void,
) {
  fetch(`/api/demo/runs/${runId}/export.md`, { headers: auth.headers() })
    .then((res) => {
      if (!res.ok) throw new Error(`导出失败 (${res.status})`);
      return res.text();
    })
    .then((text) => {
      const blob = new Blob([text], { type: "text/markdown" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      const suffix = title.slice(0, 24);
      a.download = `演示过程-${suffix}.md`;
      a.click();
      URL.revokeObjectURL(a.href);
    })
    .catch((e) => onError?.(String(e)));
}

export function GuidedDemoRunsPanel() {
  const auth = useAuth();
  const navigate = useNavigate();
  const isGm = auth.role === "GM";
  const [items, setItems] = useState<RunRow[]>([]);
  const [steps, setSteps] = useState<Step[]>([]);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    fetch("/api/demo/runs", { headers: auth.headers() })
      .then((r) => {
        if (r.status === 404) {
          setErr("演示线 API 未加载，请重启后端（./scripts/start.sh）后刷新本页");
          return null;
        }
        return r.json();
      })
      .then((j) => {
        if (j) setItems(j.data?.items ?? []);
      })
      .catch(() => setErr("无法连接演示线 API"));
    fetch("/api/demo/guided/path", { headers: auth.headers() })
      .then((r) => r.json())
      .then((j) => setSteps(j.data?.steps ?? []))
      .catch(() => undefined);
  }, [auth]);

  useEffect(() => {
    load();
  }, [load]);

  const post = async (url: string, body?: unknown) => {
    setBusy(true);
    setMsg(null);
    setErr(null);
    try {
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...auth.headers() },
        body: body !== undefined ? JSON.stringify(body) : undefined,
      });
      const j = await res.json().catch(() => ({}));
      if (!res.ok) {
        setErr(typeof j.detail === "string" ? j.detail : j.message || "失败");
        return null;
      }
      setMsg(j.message || "完成");
      load();
      return j;
    } finally {
      setBusy(false);
    }
  };

  const onContinue = async (runId: string) => {
    const j = await post(`/api/demo/runs/${runId}/continue`);
    const path = j?.data?.resume_list_path as string | undefined;
    if (path) navigate(path);
  };

  const resetSystem = async () => {
    if (
      !window.confirm(
        "确定重置系统？\n\n将删除全部演示线记录，并清空系统内所有业务数据（含产品/BOM/订单/CRM/人事等）。之后仅能通过演示线「生成数据」或各页手工录入。此操作不可撤销。",
      )
    ) {
      return;
    }
    await post("/api/demo/system/reset");
  };

  const removeRun = async (runId: string, runTitle: string, activeRun?: boolean) => {
    const extra = activeRun
      ? "\n\n该线进行中：删除后将清空系统内全部业务测试数据（订单/CRM/BOM/人事等），仅保留其它已结束的演示线记录。"
      : "";
    if (!window.confirm(`确定删除演示线「${runTitle}」？反馈与归档快照将一并删除，不可恢复。${extra}`)) return;
    setBusy(true);
    setMsg(null);
    setErr(null);
    try {
      const res = await fetch(`/api/demo/runs/${runId}`, {
        method: "DELETE",
        headers: auth.headers(),
      });
      const j = await res.json().catch(() => ({}));
      if (!res.ok) {
        setErr(typeof j.detail === "string" ? j.detail : j.message || "删除失败");
        return;
      }
      setMsg(j.message || "已删除");
      load();
    } finally {
      setBusy(false);
    }
  };

  const live = items.find((x) => x.is_active && x.status === "ACTIVE");
  const replay = items.find((x) => x.is_replay);

  return (
    <section className="rounded-lg border-2 border-sky-600/50 bg-sky-950/20 p-4 shadow-[0_0_20px_rgba(14,165,233,0.12)]">
      <h3 className="text-base font-semibold text-sky-100">演示线管理</h3>
      <p className="mt-1 text-[10px] text-slate-500">
        启动新线前会自动归档当前进行中线并清空业务数据。进行中的线也可删除（会清场）。17 步全部生成数据后才可「结束」。
      </p>
      {!isGm && (
        <p className="mt-2 text-[10px] text-amber-400">新建/启动/结束/重放仅总经理；反馈所有人可追加。</p>
      )}
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <button
          type="button"
          disabled={busy || !isGm}
          className="rounded border border-sky-700 px-3 py-1 text-xs text-sky-200 disabled:opacity-40"
          onClick={() => post("/api/demo/runs", {})}
        >
          新建
        </button>
        <button
          type="button"
          disabled={busy || !isGm}
          className="rounded border border-rose-900 px-3 py-1 text-xs text-rose-200 disabled:opacity-40"
          onClick={() => void resetSystem()}
        >
          重置系统
        </button>
        <span className="text-[10px] text-slate-500">名称自动生成：YYYYMMDD-HHMMSS（北京时间）</span>
      </div>
      {live && (
        <p className="mt-2 text-[11px] text-emerald-300">
          进行中：{live.title} · 第 {live.current_seq}/17 步 {live.current_step_title}
          {steps.find((s) => s.step_id === live.current_step_id)?.list_path && (
            <>
              {" · "}
              <button
                type="button"
                className="underline"
                disabled={busy}
                onClick={() => void onContinue(live.id)}
              >
                继续
              </button>
              {" · "}
              <button
                type="button"
                className="underline text-sky-300"
                disabled={busy}
                onClick={() => downloadExport(auth, live.id, live.title, setErr)}
              >
                导出演示 md
              </button>
            </>
          )}
        </p>
      )}
      {replay && (
        <p className="mt-2 text-[11px] text-violet-300">
          重放中：{replay.title}
          {steps.find((s) => s.step_id === replay.current_step_id)?.list_path && (
            <>
              {" · "}
              <Link
                className="underline"
                to={steps.find((s) => s.step_id === replay.current_step_id)!.list_path}
              >
                继续走链
              </Link>
            </>
          )}
          {isGm && (
            <button
              type="button"
              className="ml-2 underline"
              disabled={busy}
              onClick={() => post(`/api/demo/runs/${replay.id}/replay/end`)}
            >
              退出重放
            </button>
          )}
        </p>
      )}
      {msg && <p className="mt-2 text-[11px] text-emerald-400">{msg}</p>}
      {err && <p className="mt-2 text-[11px] text-rose-400">{err}</p>}
      <ul className="mt-4 space-y-2">
        {items.map((r) => (
          <li
            key={r.id}
            className="flex flex-wrap items-center gap-2 rounded border border-slate-800 px-3 py-2 text-[11px]"
          >
            <span className="min-w-0 flex-1 font-medium text-slate-200">{r.title}</span>
            <span
              className={`rounded-full px-2 py-0.5 text-[10px] font-medium ring-1 ring-inset ${statusBadgeClass(r.status)}`}
            >
              {statusLabel(r.status)}
            </span>
            {r.is_replay && <span className="text-violet-400">重放会话</span>}
            <span className="text-slate-500">
              反馈 {r.feedback_count} · 环节 {r.snapshot_count ?? 0}/{17}
            </span>
            <div className="ml-auto flex flex-wrap items-center gap-2">
              {r.status === "DRAFT" && isGm && (
                <button
                  type="button"
                  disabled={busy}
                  className="rounded border border-emerald-800 px-2 py-0.5 text-emerald-200"
                  onClick={() => post(`/api/demo/runs/${r.id}/start`)}
                >
                  启动
                </button>
              )}
              {r.status === "ACTIVE" && (r.can_continue ?? true) && (
                <button
                  type="button"
                  disabled={busy}
                  className="rounded border border-sky-700 px-2 py-0.5 text-sky-200"
                  onClick={() => void onContinue(r.id)}
                >
                  继续
                </button>
              )}
              {(r.status === "ACTIVE" || r.status === "ENDED") && (
                <button
                  type="button"
                  className="rounded border border-sky-800 px-2 py-0.5 text-sky-200"
                  title={r.status === "ACTIVE" ? "进行中可多次导出，含已反馈与已生成环节" : undefined}
                  onClick={() => downloadExport(auth, r.id, r.title, setErr)}
                >
                  导出演示 md
                </button>
              )}
              {r.status === "ACTIVE" && isGm && r.can_end && (
                <button
                  type="button"
                  disabled={busy}
                  className="rounded border border-amber-800 px-2 py-0.5 text-amber-100"
                  title="17 步均已生成数据后可结束"
                  onClick={() => post(`/api/demo/runs/${r.id}/end`)}
                >
                  结束
                </button>
              )}
              {r.status === "ENDED" && r.can_replay && isGm && !r.is_replay && (
                <button
                  type="button"
                  disabled={busy}
                  className="rounded border border-violet-700 px-2 py-0.5 text-violet-200"
                  onClick={() => post(`/api/demo/runs/${r.id}/replay`)}
                >
                  重放
                </button>
              )}
              {isGm && (
                <button
                  type="button"
                  disabled={busy}
                  className="rounded border border-rose-900/80 px-2 py-0.5 text-rose-300"
                  onClick={() => void removeRun(r.id, r.title, r.status === "ACTIVE")}
                >
                  删除
                </button>
              )}
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
