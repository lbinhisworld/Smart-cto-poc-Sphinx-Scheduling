import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { requestWithRole } from "../../api/client";
import { useAuth } from "../../shell/auth";

type Cell = { done: boolean; completed_on: string | null };
type BoardProject = {
  code: string;
  name: string;
  customer_name: string;
  order_no: string | null;
  status: string;
  cells: Record<string, Cell>;
};
type Board = {
  stages: { code: string; name: string }[];
  projects: BoardProject[];
  active_projects: number;
  launched_projects: number;
  note: string;
};
type Step = { step_no: number; name: string; event_date: string | null; note: string };
type StageDetail = {
  project_code: string;
  project_name: string;
  customer_name: string;
  stage_code: string;
  stage_name: string;
  done: boolean;
  completed_on: string | null;
  order_no: string | null;
  handoff: string | null;
  steps: Step[];
};

export function ProjectBoardPage() {
  const auth = useAuth();
  const role = auth.role;
  const [board, setBoard] = useState<Board | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState<{ project: string; stage: string } | null>(null);
  const [detail, setDetail] = useState<StageDetail | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<Record<number, string>>({});
  const [saving, setSaving] = useState<number | null>(null);

  const loadBoard = useCallback(() => {
    if (!role) return;
    requestWithRole<Board>("/api/modules/project/board", role)
      .then(setBoard)
      .catch((e) => setError(String(e)));
  }, [role]);

  useEffect(() => {
    loadBoard();
  }, [loadBoard]);

  const loadDetail = useCallback(
    (project: string, stage: string) => {
      if (!role) return;
      setDetail(null);
      setDetailError(null);
      requestWithRole<StageDetail>(`/api/modules/project/${project}/stages/${stage}`, role)
        .then((d) => {
          setDetail(d);
          const next: Record<number, string> = {};
          for (const step of d.steps) {
            if (step.event_date) next[step.step_no] = step.event_date;
          }
          setDrafts(next);
        })
        .catch((e) => setDetailError(String(e)));
    },
    [role],
  );

  useEffect(() => {
    if (!open) {
      setDetail(null);
      return;
    }
    loadDetail(open.project, open.stage);
  }, [open, loadDetail]);

  async function saveStep(stepNo: number) {
    if (!role || !open) return;
    const eventDate = drafts[stepNo];
    if (!eventDate) return;
    setSaving(stepNo);
    setDetailError(null);
    try {
      await requestWithRole<StageDetail>(`/api/modules/project/${open.project}/steps`, role, {
        method: "POST",
        body: JSON.stringify({
          stage_code: open.stage,
          step_no: stepNo,
          event_date: eventDate,
        }),
      });
      loadDetail(open.project, open.stage);
      loadBoard();
    } catch (e) {
      setDetailError(String(e));
    } finally {
      setSaving(null);
    }
  }

  return (
    <div className="px-6 py-4">
      <h2 className="text-lg font-semibold">大客户项目大盘</h2>
      <p className="mt-1 text-xs text-[var(--text-muted)]">
        一行一个专项。绿色格子是该环节完成日；点格子看里面的时间线。
      </p>
      {board && (
        <div className="mt-3 flex gap-6 text-sm">
          <span>
            进行中 <strong className="tabular-nums">{board.active_projects}</strong>
          </span>
          <span>
            已投产 <strong className="tabular-nums">{board.launched_projects}</strong>
          </span>
        </div>
      )}
      {error && <p className="mt-3 text-sm text-rose-400">{error}</p>}
      {board === null && !error && <p className="mt-3 text-sm text-[var(--text-muted)]">加载中…</p>}
      {board && (
        <div className="mt-4 overflow-x-auto rounded-lg border" style={{ borderColor: "var(--line)" }}>
          <table className="w-full min-w-[720px] border-collapse text-sm">
            <thead>
              <tr className="text-left text-xs text-[var(--text-muted)]">
                <th className="px-3 py-2 font-medium">客户 / 项目</th>
                {board.stages.map((s) => (
                  <th key={s.code} className="px-3 py-2 font-medium">
                    {s.name}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {board.projects.map((p) => (
                <tr key={p.code} className="border-t" style={{ borderColor: "var(--line)" }}>
                  <td className="px-3 py-3 align-top">
                    <p className="font-medium">{p.customer_name}</p>
                    <p className="text-xs text-[var(--text-muted)]">
                      {p.name}
                      <span className="ml-2">{p.status}</span>
                    </p>
                  </td>
                  {board.stages.map((s) => {
                    const cell = p.cells[s.code];
                    const selected = open?.project === p.code && open?.stage === s.code;
                    return (
                      <td key={s.code} className="px-2 py-2">
                        <button
                          type="button"
                          className={`w-full rounded-md border px-2 py-3 text-center tabular-nums ${
                            cell?.done
                              ? "border-emerald-600 bg-emerald-700 font-medium text-white"
                              : "text-[var(--text-muted)]"
                          } ${selected ? "ring-2 ring-[var(--accent)]" : ""}`}
                          style={
                            cell?.done
                              ? undefined
                              : { background: "var(--bg-card)", borderColor: "var(--line)" }
                          }
                          onClick={() => setOpen({ project: p.code, stage: s.code })}
                        >
                          {cell?.done ? cell.completed_on : "待完成"}
                        </button>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {board?.note && <p className="mt-3 text-xs text-[var(--text-muted)]">{board.note}</p>}

      {open && (
        <div
          className="fixed inset-0 z-50 flex justify-end bg-black/45"
          role="dialog"
          onClick={() => setOpen(null)}
        >
          <div
            className="flex h-full w-full max-w-md flex-col overflow-hidden shadow-xl"
            style={{ background: "var(--bg-card)" }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b px-4 py-3" style={{ borderColor: "var(--line)" }}>
              <div>
                <p className="font-semibold">
                  {detail ? `${detail.customer_name} · ${detail.stage_name}` : "环节时间线"}
                </p>
                {detail && (
                  <p className="text-xs text-[var(--text-muted)]">
                    {detail.project_name}
                    {detail.done ? ` · 完成于 ${detail.completed_on}` : " · 待完成"}
                  </p>
                )}
              </div>
              <button type="button" className="text-sm text-[var(--text-muted)]" onClick={() => setOpen(null)}>
                关闭
              </button>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto p-4">
              {detailError && <p className="mb-3 text-sm text-rose-400">{detailError}</p>}
              {detail === null && !detailError && (
                <p className="text-sm text-[var(--text-muted)]">加载中…</p>
              )}
              {detail?.handoff && (
                <p className="mb-4 text-sm">
                  {detail.handoff}
                  {detail.order_no && (
                    <>
                      {" "}
                      <Link className="text-[var(--accent)] underline" to={`/orders?order=${detail.order_no}`}>
                        {detail.order_no}
                      </Link>
                    </>
                  )}
                </p>
              )}
              <ol className="space-y-4 border-l pl-4" style={{ borderColor: "var(--line)" }}>
                {detail?.steps.map((step) => (
                  <li key={step.step_no}>
                    <p className="text-sm font-medium">{step.name}</p>
                    <p className="text-xs text-[var(--text-muted)]">
                      {step.event_date ? step.event_date : "未发生"}
                      {step.note ? ` · ${step.note}` : ""}
                    </p>
                    <div className="mt-2 flex items-center gap-2">
                      <input
                        type="date"
                        className="rounded border bg-transparent px-2 py-1 text-sm"
                        style={{ borderColor: "var(--line)" }}
                        value={drafts[step.step_no] ?? ""}
                        onChange={(e) =>
                          setDrafts((prev) => ({ ...prev, [step.step_no]: e.target.value }))
                        }
                      />
                      <button
                        type="button"
                        className="rounded bg-emerald-800 px-2 py-1 text-xs text-white disabled:opacity-50"
                        disabled={!drafts[step.step_no] || saving === step.step_no}
                        onClick={() => void saveStep(step.step_no)}
                      >
                        {saving === step.step_no ? "保存中…" : "登记"}
                      </button>
                    </div>
                  </li>
                ))}
              </ol>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
