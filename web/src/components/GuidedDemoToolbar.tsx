import { useCallback, useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../shell/auth";
import { GUIDED_DEMO_SEED_EVENT, type GuidedDemoSeededDetail } from "../hooks/guidedDemoSeed";
import {
  GuidedDemoFeedbackDrawer,
  type FeedbackItem,
} from "./GuidedDemoFeedbackDrawer";

type GuidedContext = {
  run: { id: string; title: string; current_step_id?: string };
  session_mode: "live" | "replay";
  step: { step_id: string; title: string; seq: number; seed_kind: string };
  next: { step_id: string; title: string; list_path: string } | null;
  readiness: { ready: boolean; missing_steps: string[]; replay?: boolean };
  saved_step: { summary: string; refs: { display?: string; story_index?: number }[] } | null;
  seed_allowed: boolean;
  step_has_seed?: boolean;
  needs_business_sync?: boolean;
  step_count: number;
};

export function GuidedDemoToolbar() {
  const auth = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [ctx, setCtx] = useState<GuidedContext | null>(null);
  const [timeline, setTimeline] = useState<FeedbackItem[]>([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [fbOpen, setFbOpen] = useState(false);
  const [category, setCategory] = useState("流程不顺");
  const [severity, setSeverity] = useState("会后优化");
  const [body, setBody] = useState("");
  const [expectation, setExpectation] = useState("");

  const load = useCallback(() => {
    const path = location.pathname;
    fetch(`/api/demo/guided/context?path=${encodeURIComponent(path)}`, { headers: auth.headers() })
      .then((r) => r.json())
      .then((j) => setCtx(j.data ?? null))
      .catch(() => setCtx(null));
  }, [auth, location.pathname]);

  const loadTimeline = useCallback(
    (runId: string, stepId: string) => {
      fetch(
        `/api/demo/runs/${encodeURIComponent(runId)}/feedback?step_id=${encodeURIComponent(stepId)}`,
        { headers: auth.headers() },
      )
        .then((r) => r.json())
        .then((j) => setTimeline(j.data?.items ?? []))
        .catch(() => setTimeline([]));
    },
    [auth],
  );

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (fbOpen && ctx?.run?.id && ctx?.step?.step_id) {
      loadTimeline(ctx.run.id, ctx.step.step_id);
    }
  }, [fbOpen, ctx, loadTimeline]);

  const post = async (url: string, init?: RequestInit) => {
    setBusy(true);
    setMsg(null);
    try {
      const res = await fetch(url, {
        ...init,
        headers: { ...auth.headers(), ...(init?.headers as Record<string, string>) },
      });
      const j = await res.json().catch(() => ({}));
      if (!res.ok) {
        const detail = typeof j.detail === "string" ? j.detail : j.message || "操作失败";
        setMsg(detail);
        return null;
      }
      return j;
    } finally {
      setBusy(false);
    }
  };

  if (!ctx?.run || !ctx.step) return null;

  const runId = ctx.run.id;
  const stepId = ctx.step.step_id;
  const isReplay = ctx.session_mode === "replay";
  const canSeed = ctx.seed_allowed && !isReplay;

  const onSeed = async () => {
    const j = await post(`/api/demo/guided/step/${encodeURIComponent(stepId)}/seed?run_id=${encodeURIComponent(runId)}`, {
      method: "POST",
    });
    if (j?.message) setMsg(String(j.message));
    if (j?.data) {
      const detail: GuidedDemoSeededDetail = {
        stepId,
        runId,
        apply: j.data.apply,
      };
      window.dispatchEvent(new CustomEvent(GUIDED_DEMO_SEED_EVENT, { detail }));
    }
    load();
  };

  const onNext = async () => {
    if (!ctx.next) return;
    await post(`/api/demo/runs/${encodeURIComponent(runId)}/advance`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    navigate(ctx.next.list_path);
  };

  const onFeedback = async () => {
    if (!body.trim()) {
      setMsg("请填写现象描述");
      return;
    }
    const j = await post(`/api/demo/runs/${encodeURIComponent(runId)}/feedback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        step_id: stepId,
        category,
        severity,
        body: body.trim(),
        expectation: expectation.trim(),
      }),
    });
    if (j) {
      setBody("");
      setExpectation("");
      setMsg("反馈已追加");
      loadTimeline(runId, stepId);
      load();
    }
  };

  const shortId = runId.slice(0, 8);

  return (
    <>
      <div
        className="shrink-0 border-b px-4 py-2 text-xs"
        style={{ borderColor: "var(--line)", background: "var(--bg-card)" }}
      >
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-medium text-[var(--accent)]">
            {isReplay ? "重放 · " : "演示线 · "}
            {ctx.run.title}
          </span>
          <span className="text-[var(--text-muted)]">
            批次 {shortId} · 第 {ctx.step.seq}/{ctx.step_count} 步 · {ctx.step.title}
          </span>
          <div className="ml-auto flex flex-wrap gap-2">
            <button
              type="button"
              disabled={busy || !canSeed}
              title={
                isReplay
                  ? "重放模式不可生成数据"
                  : ctx.needs_business_sync
                    ? "谱系已记录但未写入业务表，请再点一次「生成数据」"
                    : ctx.step_has_seed
                      ? "本环节已有数据，请点「下一步」继续"
                    : canSeed
                      ? "本环节将清空旧谱系并重新生成 5 条"
                      : `缺少：${ctx.readiness.missing_steps.join("、")}`
              }
              className="rounded border border-sky-600/70 px-2 py-1 font-medium text-sky-400 disabled:opacity-40"
              onClick={() => void onSeed()}
            >
              生成数据
            </button>
            {ctx.next ? (
              <button
                type="button"
                disabled={busy}
                className="rounded border border-emerald-800/60 px-2 py-1 text-emerald-200"
                onClick={() => void onNext()}
              >
                下一步：{ctx.next.title}
              </button>
            ) : null}
            <button
              type="button"
              disabled={busy}
              className={`rounded border px-2 py-1 ${
                fbOpen ? "border-amber-500 bg-amber-950/40 text-amber-100" : "border-amber-800/60 text-amber-100"
              }`}
              onClick={() => setFbOpen(true)}
            >
              反馈
            </button>
          </div>
        </div>
        {msg && !fbOpen && (
          <p className="mt-1 text-[11px] text-sky-300/90">{msg}</p>
        )}
      </div>

      <GuidedDemoFeedbackDrawer
        open={fbOpen}
        onClose={() => setFbOpen(false)}
        stepTitle={ctx.step.title}
        stepSeq={ctx.step.seq}
        timeline={timeline}
        busy={busy}
        category={category}
        severity={severity}
        body={body}
        expectation={expectation}
        onCategory={setCategory}
        onSeverity={setSeverity}
        onBody={setBody}
        onAppendToBody={(chunk) =>
          setBody((b) => (b.trim() ? `${b.trimEnd()} ${chunk}` : chunk))
        }
        onExpectation={setExpectation}
        onSubmit={() => void onFeedback()}
        msg={fbOpen ? msg : null}
      />
    </>
  );
}
