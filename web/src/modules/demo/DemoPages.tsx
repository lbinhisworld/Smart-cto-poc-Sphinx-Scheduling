import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { DEMO_TODAY } from "../../constants/groups";
import { useAuth } from "../../shell/auth";
import { CUSTOMER_QUESTIONS } from "./customerQuestions";
import { GuidedDemoRunsPanel } from "./GuidedDemoRunsPanel";

const WEEKDAYS = ["日", "一", "二", "三", "四", "五", "六"] as const;

function formatDemoDate(iso: string) {
  const [y, m, d] = iso.split("-").map(Number);
  const weekday = WEEKDAYS[new Date(Date.UTC(y, m - 1, d)).getUTCDay()];
  return {
    ymd: iso,
    cn: `${y}年${m}月${d}日`,
    weekday: `星期${weekday}`,
  };
}

type Scope = {
  offline_ok: boolean;
  disclaimer: string;
  not_delivered: string[];
};

type ScenarioStatus = {
  today: string;
};

type DemoConsoleTab = "runs" | "questions";

export function DemoConsolePage() {
  const auth = useAuth();
  const [tab, setTab] = useState<DemoConsoleTab>("runs");
  const [scope, setScope] = useState<Scope | null>(null);
  const [status, setStatus] = useState<ScenarioStatus | null>(null);

  const loadStatus = useCallback(() => {
    fetch("/api/demo/scenario/status", { headers: auth.headers() })
      .then((r) => r.json())
      .then((j) => setStatus(j.data ?? null))
      .catch(() => undefined);
  }, [auth]);

  useEffect(() => {
    fetch("/api/demo/rehearsal", { headers: auth.headers() })
      .then((r) => r.json())
      .then((j) => setScope(j.data?.scope ?? null))
      .catch(() => undefined);
    loadStatus();
  }, [auth, loadStatus]);

  const demoDate = formatDemoDate(status?.today || DEMO_TODAY);

  return (
    <div className="px-6 py-4">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold">演示控制台</h2>
          <p className="mt-1 text-xs text-slate-400">
            全链路走查用「演示线」；待客户拍板项在「待确认问题」。交期与下单日按右侧演示基准日计算。
          </p>
        </div>
        <div
          className="min-w-[240px] rounded-lg border-2 border-sky-500/70 bg-sky-950/50 px-4 py-3 shadow-[0_0_24px_rgba(14,165,233,0.18)]"
          title="排程、齐套、造数全部锚定此日，不是电脑系统日期"
        >
          <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-sky-300">
            DEMO-TODAY · 演示基准日
          </p>
          <p className="mt-1 font-mono text-3xl font-bold tabular-nums leading-none tracking-tight text-sky-50">
            {demoDate.ymd}
          </p>
          <p className="mt-1.5 text-sm text-sky-100">
            {demoDate.cn} · {demoDate.weekday}
          </p>
          <p className="mt-1 text-[10px] text-sky-300/80">不是电脑今天 · 造数 / 排程 / 齐套都用这一天</p>
        </div>
      </div>

      {scope && (
        <div className="mt-2 rounded border border-amber-800/60 bg-amber-950/30 px-3 py-2 text-xs text-amber-100">
          <p>{scope.disclaimer}</p>
          <p className="mt-1 text-amber-200/80">明确不交付：{scope.not_delivered.join(" · ")}</p>
        </div>
      )}

      <div
        className="mt-4 flex gap-1 border-b border-slate-800"
        role="tablist"
        aria-label="演示控制台分区"
      >
        <button
          type="button"
          role="tab"
          aria-selected={tab === "runs"}
          className={`rounded-t px-4 py-2 text-sm font-medium transition-colors ${
            tab === "runs"
              ? "border border-b-0 border-sky-600/60 bg-sky-950/40 text-sky-100"
              : "text-slate-400 hover:text-slate-200"
          }`}
          onClick={() => setTab("runs")}
        >
          演示线
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === "questions"}
          className={`rounded-t px-4 py-2 text-sm font-medium transition-colors ${
            tab === "questions"
              ? "border border-b-0 border-amber-600/60 bg-amber-950/30 text-amber-100"
              : "text-slate-400 hover:text-slate-200"
          }`}
          onClick={() => setTab("questions")}
        >
          待确认问题
          <span className="ml-1.5 text-[11px] font-normal text-slate-500">{CUSTOMER_QUESTIONS.length}</span>
        </button>
      </div>

      {tab === "runs" && (
        <div role="tabpanel" className="mt-4">
          <GuidedDemoRunsPanel />

          <section className="mt-6 rounded-lg border border-violet-800/50 bg-violet-950/25 p-4">
            <h3 className="text-sm font-semibold text-violet-100">概念讲解（可离线讲）</h3>
            <p className="mt-1 text-[11px] text-violet-200/70">
              与演示线 live 操作互补：先讲逻辑，再进看板 / 生产成本实操。
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              <Link
                to="/demo/story/schedule"
                className="rounded-lg border border-violet-600/60 bg-violet-950/40 px-4 py-2 text-xs text-violet-100 hover:border-violet-500"
              >
                排程算法讲解
                <span className="mt-0.5 block text-[10px] text-violet-300/80">倒排 · 冲突 · 插单 → 再看 /schedule</span>
              </Link>
              <Link
                to="/demo/story/cost"
                className="rounded-lg border border-violet-600/60 bg-violet-950/40 px-4 py-2 text-xs text-violet-100 hover:border-violet-500"
              >
                计划人工成本讲解
                <span className="mt-0.5 block text-[10px] text-violet-300/80">人·时 · 单价 · 打样剔除 → 再看生产成本</span>
              </Link>
            </div>
          </section>
        </div>
      )}

      {tab === "questions" && (
        <section role="tabpanel" className="mt-4">
          <div>
            <h3 className="text-base font-semibold text-amber-100">还要客户确认</h3>
            <p className="mt-1 max-w-3xl text-xs leading-relaxed text-slate-400">
              每一张都还没有拍板。演示按卡片上的「现在」继续跑；确认之前不改排程算法，也不改客户交期。
            </p>
          </div>
          <ol className="mt-4 space-y-4">
            {CUSTOMER_QUESTIONS.map((q) => (
              <li
                key={q.id}
                className="rounded-2xl border border-amber-700/55 bg-gradient-to-br from-amber-950/55 via-slate-950 to-slate-950 px-6 py-6"
              >
                <div className="flex flex-wrap items-center gap-3">
                  <span className="rounded-full bg-amber-400 px-3 py-1 text-sm font-bold tracking-wide text-amber-950">
                    {q.id}
                  </span>
                  <span className="text-sm text-amber-200/90">请{q.ask}确认</span>
                </div>
                <h4 className="mt-4 text-2xl font-semibold leading-snug text-amber-50">{q.question}</h4>
                <div className="mt-5 grid gap-3 md:grid-cols-2">
                  <div className="rounded-xl border border-slate-800 bg-slate-950/80 px-4 py-4">
                    <p className="text-xs font-semibold tracking-wide text-slate-500">现在演示</p>
                    <p className="mt-2 text-sm leading-relaxed text-slate-200">{q.now}</p>
                  </div>
                  <div className="rounded-xl border border-slate-800 bg-slate-950/80 px-4 py-4">
                    <p className="text-xs font-semibold tracking-wide text-slate-500">确认之后才能做</p>
                    <p className="mt-2 text-sm leading-relaxed text-slate-200">{q.after}</p>
                  </div>
                </div>
              </li>
            ))}
          </ol>
        </section>
      )}
    </div>
  );
}

type TodoItem = {
  id: string;
  kind: string;
  title: string;
  detail: string;
  path: string;
  priority: string;
  pulse?: boolean;
};

export function TodoCenterPage() {
  const auth = useAuth();
  const [items, setItems] = useState<TodoItem[]>([]);

  useEffect(() => {
    fetch("/api/demo/todos", { headers: auth.headers() })
      .then((r) => r.json())
      .then((j) => setItems(j.data?.items ?? []));
  }, [auth.role, auth.headers]);

  return (
    <div className="px-6 py-4">
      <h2 className="text-lg font-semibold">待办中心</h2>
      <p className="text-xs text-slate-400">按当前角色聚合：变更审批、未完尾数、超期打样、企微模拟、齐套预警</p>
      <ul className="mt-4 space-y-2">
        {items.length === 0 && (
          <li className="text-sm text-slate-500">暂无待办（可去演示控制台触发 S5）</li>
        )}
        {items.map((t) => (
          <li key={t.id}>
            <Link
              to={t.path}
              className={`block rounded-lg border px-3 py-2 text-sm hover:border-sky-700 ${
                t.pulse
                  ? "animate-pulse border-amber-500 bg-amber-950/40"
                  : "border-slate-800 bg-slate-900"
              }`}
            >
              <span className="text-[10px] uppercase text-slate-500">{t.kind}</span>
              <p className="font-medium text-slate-100">{t.title}</p>
              <p className="text-xs text-slate-400">{t.detail}</p>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
