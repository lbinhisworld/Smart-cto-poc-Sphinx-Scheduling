import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../../shell/auth";

type Act = {
  act: number;
  title: string;
  module: string;
  role: string;
  path: string;
  steps: string[];
  note?: string;
};

type Scope = {
  offline_ok: boolean;
  disclaimer: string;
  not_delivered: string[];
};

export function DemoConsolePage() {
  const auth = useAuth();
  const [acts, setActs] = useState<Act[]>([]);
  const [scope, setScope] = useState<Scope | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/demo/rehearsal", { headers: auth.headers() })
      .then((r) => r.json())
      .then((j) => {
        setActs(j.data?.acts ?? []);
        setScope(j.data?.scope ?? null);
      });
  }, [auth]);

  const triggerS5 = () => {
    setMsg(null);
    fetch("/api/demo/trigger-sample-overdue?sample_code=SP-001", {
      method: "POST",
      headers: auth.headers(),
    })
      .then((r) => r.json())
      .then((j) => setMsg(j.message || "已触发"))
      .catch((e) => setMsg(String(e)));
  };

  return (
    <div className="px-6 py-4">
      <h2 className="text-lg font-semibold">演示控制台 · 十幕剧本</h2>
      {scope && (
        <div className="mt-2 rounded border border-amber-800/60 bg-amber-950/30 px-3 py-2 text-xs text-amber-100">
          <p>{scope.disclaimer}</p>
          <p className="mt-1 text-amber-200/80">明确不交付：{scope.not_delivered.join(" · ")}</p>
        </div>
      )}
      <div className="mt-3 flex flex-wrap gap-2">
        <button
          type="button"
          className="rounded border border-slate-600 px-3 py-1 text-xs"
          onClick={triggerS5}
        >
          联调：触发 S5 打样超期消息
        </button>
        <Link to="/todos" className="rounded border border-sky-700 px-3 py-1 text-xs text-sky-300">
          待办中心 →
        </Link>
        <a
          href="/docs/POC范围说明.md"
          className="rounded border border-slate-600 px-3 py-1 text-xs text-slate-400"
          onClick={(e) => e.preventDefault()}
          title="见仓库 docs/POC范围说明.md"
        >
          POC 范围说明（仓库文档）
        </a>
      </div>
      {msg && <p className="mt-2 text-xs text-emerald-400">{msg}</p>}
      <ol className="mt-6 space-y-4">
        {acts.map((a) => (
          <li
            key={a.act}
            className="rounded-lg border border-slate-800 bg-slate-900 p-4 text-sm"
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="font-semibold text-slate-100">
                第 {a.act} 幕 · {a.title}
              </p>
              <Link to={a.path} className="text-xs text-sky-400 underline">
                {a.path} · 建议 {a.role}
              </Link>
            </div>
            <p className="mt-1 text-[10px] text-slate-500">{a.module}</p>
            <ul className="mt-2 list-decimal pl-5 text-xs text-slate-300">
              {a.steps.map((s) => (
                <li key={s}>{s}</li>
              ))}
            </ul>
            {a.note && <p className="mt-2 text-[10px] text-slate-500">{a.note}</p>}
          </li>
        ))}
      </ol>
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
      <p className="text-xs text-slate-400">按当前角色聚合：变更审批、超期打样、企微模拟、齐套预警</p>
      <ul className="mt-4 space-y-2">
        {items.length === 0 && (
          <li className="text-sm text-slate-500">暂无待办（可去演示控制台触发 S5）</li>
        )}
        {items.map((t) => (
          <li key={t.id}>
            <Link
              to={t.path}
              className="block rounded-lg border border-slate-800 bg-slate-900 px-3 py-2 text-sm hover:border-sky-700"
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
