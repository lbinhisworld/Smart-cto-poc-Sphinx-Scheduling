import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { DEMO_TODAY } from "../../constants/groups";

type StoryStep = {
  title: string;
  body: React.ReactNode;
};

function StoryShell({
  title,
  subtitle,
  steps,
  livePath,
  liveLabel,
}: {
  title: string;
  subtitle: string;
  steps: StoryStep[];
  livePath: string;
  liveLabel: string;
}) {
  const [idx, setIdx] = useState(0);
  const step = steps[idx];
  const last = idx === steps.length - 1;

  return (
    <div className="mx-auto max-w-3xl px-4 py-5">
      <nav className="mb-4 flex flex-wrap items-center gap-2 text-xs text-slate-400">
        <Link to="/demo" className="text-sky-400 hover:underline">
          ← 演示控制台
        </Link>
        <span className="text-slate-600">·</span>
        <span className="text-slate-300">{title}</span>
      </nav>
      <header className="mb-6">
        <h1 className="text-xl font-semibold text-slate-100">{title}</h1>
        <p className="mt-1 text-sm text-slate-400">{subtitle}</p>
        <p className="mt-2 text-[10px] text-sky-300/90">
          演示基准日 {DEMO_TODAY} · 概念讲解（可离线讲）· 与 live 系统互补
        </p>
      </header>
      <div className="mb-3 flex gap-1">
        {steps.map((s, i) => (
          <button
            key={s.title}
            type="button"
            title={s.title}
            className={`h-1.5 flex-1 rounded-full transition ${
              i <= idx ? "bg-sky-500" : "bg-slate-800"
            }`}
            onClick={() => setIdx(i)}
          />
        ))}
      </div>
      <article className="min-h-[320px] rounded-lg border border-slate-800 bg-slate-900/80 p-5 text-sm leading-relaxed text-slate-300">
        <h2 className="text-base font-semibold text-slate-100">{step.title}</h2>
        <div className="mt-3 space-y-3">{step.body}</div>
      </article>
      <footer className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <button
          type="button"
          disabled={idx === 0}
          className="rounded border border-slate-700 px-3 py-1.5 text-xs text-slate-300 disabled:opacity-40"
          onClick={() => setIdx((i) => Math.max(0, i - 1))}
        >
          上一步
        </button>
        <span className="text-[10px] text-slate-500">
          {idx + 1} / {steps.length}
        </span>
        {last ? (
          <Link
            to={livePath}
            className="rounded bg-sky-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-sky-500"
          >
            {liveLabel} →
          </Link>
        ) : (
          <button
            type="button"
            className="rounded bg-slate-700 px-3 py-1.5 text-xs text-slate-100 hover:bg-slate-600"
            onClick={() => setIdx((i) => Math.min(steps.length - 1, i + 1))}
          >
            下一步
          </button>
        )}
      </footer>
    </div>
  );
}

function EmbedStory({ src, title }: { src: string; title: string }) {
  return (
    <div className="flex h-[calc(100vh-3.5rem)] flex-col">
      <div className="flex items-center gap-3 border-b border-slate-800 px-4 py-2 text-xs">
        <Link to="/demo" className="text-sky-400 hover:underline">
          ← 演示控制台
        </Link>
        <span className="text-slate-500">{title}</span>
        <span className="text-slate-600">（外部讲解页 {src}）</span>
      </div>
      <iframe title={title} src={src} className="min-h-0 flex-1 border-0 bg-white" />
    </div>
  );
}

function useEmbedSrc(param: string | null): string | null {
  return useMemo(() => {
    if (!param || !param.startsWith("/")) return null;
    if (param.includes("..")) return null;
    return param;
  }, [param]);
}

export function ScheduleStoryPage() {
  const [params] = useSearchParams();
  const embed = useEmbedSrc(params.get("embed"));
  if (embed) return <EmbedStory src={embed} title="排程算法讲解" />;

  const steps: StoryStep[] = [
    {
      title: "从交期往回推",
      body: (
        <>
          <p>
            斯芬克斯 POC 排程是 <strong className="text-slate-100">JIT 倒排</strong>
            ：交期是锚，系统从交期往今天填任务，看能不能装下；装不下就亮灯并算
            <strong className="text-emerald-300/90"> 最快可完成日</strong>，由人决定是否找销售改交期。
          </p>
          <p className="text-xs text-slate-500">
            不是 APS 全局最优；不会自动写回订单交期。
          </p>
        </>
      ),
    },
    {
      title: "七步流水线",
      body: (
        <ol className="list-decimal space-y-1 pl-5 text-xs">
          <li>订单展开 → 成品工单（数量归一到「版」）</li>
          <li>组日产能（日历 × SPH，扣预留）</li>
          <li>倒排落位：从 due_date 往前填</li>
          <li>展开半成品（库存抵扣后开二部工单）</li>
          <li>再倒排半成品</li>
          <li>冲突体检 E1–E10（软约束，只提示）</li>
          <li>人：试排、拖拽、沙箱 diff 后发布</li>
        </ol>
      ),
    },
    {
      title: "三条红线",
      body: (
        <ul className="list-disc space-y-2 pl-5 text-xs">
          <li>
            <strong className="text-slate-200">交期是锚</strong> — 系统不改 so_order.due_date
          </li>
          <li>
            <strong className="text-slate-200">先成品后半成品</strong> — 成品一动，半成品工单重建
          </li>
          <li>
            <strong className="text-slate-200">默认交期晚的先占格</strong>（DUE_DESC）；插单时变更单先占位（PIN_FIRST）。倒排下挤占常表现为他人
            <strong className="text-amber-200/90"> 开工提前</strong>，不是一律延后。
          </li>
        </ul>
      ),
    },
    {
      title: "算例 · 手工单 SO-001 / P1",
      body: (
        <>
          <p>520 盒 P1，仅手工组，交期 10/8：从 10/8 往前填工作日，产能条未满则绿灯，计划员确认发布。</p>
          <p className="rounded border border-slate-800 bg-slate-950/60 px-3 py-2 font-mono text-xs text-slate-400">
            内部只算「版」· 休息日跳过 · 未安置 → E1 红
          </p>
        </>
      ),
    },
    {
      title: "算例 · 模具 + 半成品 SO-002 / P2",
      body: (
        <>
          <p>
            200 盒 P2：模具组成品约 1236 版多日分摊；S2 库存 130 版后净需求约 282 版进二部，须在成品开工前 4 天就绪。
          </p>
          <p>
            交期改早到 9/23 时常见 <strong className="text-rose-300">E2 半成品来不及</strong>
            ：红灯表示倒排窗口不够，若物理最快仍不晚于客户交期，则提示「交期本身够，勿误导改交期」。
          </p>
        </>
      ),
    },
    {
      title: "算例 · 插单与多半成品",
      body: (
        <>
          <p>SO-004 插单：PIN_FIRST 让紧急单先占位，diff 里看其他单开工日变化与超交期单数。</p>
          <p>
            P9 / SO-303：一条订单三条半成品工单，冲突面板会合并同质 E1，仍可按 S2/S5/S6 分别定位。
          </p>
        </>
      ),
    },
    {
      title: "进入 live 排程看板",
      body: (
        <p>
          下一步请在真实看板操作：订单池加入排程 → 一键倒排 → 右侧冲突面板 → 拖拽 / 试排。本页仅讲逻辑，数据以试排结果为准。
        </p>
      ),
    },
  ];

  return (
    <StoryShell
      title="排程算法 · 概念讲解"
      subtitle="倒排 · 半成品联动 · 冲突预警 · 人确认发布"
      steps={steps}
      livePath="/schedule"
      liveLabel="打开排程看板"
    />
  );
}

export function CostStoryPage() {
  const [params] = useSearchParams();
  const embed = useEmbedSrc(params.get("embed"));
  if (embed) return <EmbedStory src={embed} title="计划人工成本讲解" />;

  const steps: StoryStep[] = [
    {
      title: "排程算出来的计划人工成本",
      body: (
        <>
          <p>
            POC 一期成本主线是 <strong className="text-slate-100">计划人工成本</strong>：排程任务上的
            <strong className="text-sky-200"> 人·时</strong> × 人事维护的
            <strong className="text-sky-200"> 组标准单价</strong>。班组长组×日报工确认后，同一单价看计划 vs 实际差异。
          </p>
          <p className="text-xs text-slate-500">非薪酬发薪；不含料费、制造费用分摊、金蝶凭证结转。</p>
        </>
      ),
    },
    {
      title: "墙钟 vs 人·时（不可混用）",
      body: (
        <ul className="space-y-2 text-xs">
          <li>
            <strong className="text-slate-200">hours_wall</strong> = 版数 ÷ 版/时 → 排日程、看 E4 组日产能
          </li>
          <li>
            <strong className="text-slate-200">hours_man</strong> = hours_wall × crew_plan →{" "}
            <strong className="text-emerald-300/90">算成本只用这个</strong>
          </li>
          <li className="font-mono text-slate-400">cost = hours_man × rate_per_man_hour</li>
        </ul>
      ),
    },
    {
      title: "组标准单价（演示数据）",
      body: (
        <table className="w-full text-left text-[11px]">
          <thead className="text-slate-500">
            <tr>
              <th className="pb-1">组</th>
              <th className="pb-1 text-right">元/人·时</th>
            </tr>
          </thead>
          <tbody className="text-slate-300">
            <tr>
              <td>一部·手工</td>
              <td className="text-right font-mono">48</td>
            </tr>
            <tr>
              <td>一部·模具</td>
              <td className="text-right font-mono">62</td>
            </tr>
            <tr>
              <td>一部·浇注</td>
              <td className="text-right font-mono">55</td>
            </tr>
            <tr>
              <td>二部·模具</td>
              <td className="text-right font-mono">58</td>
            </tr>
          </tbody>
        </table>
      ),
    },
    {
      title: "手算算例 · ¥1,152",
      body: (
        <>
          <p>量产 SO-MASS-1 · P1 · 一部手工组 · 某日 10 版：</p>
          <pre className="overflow-x-auto rounded border border-slate-800 bg-slate-950/70 p-3 font-mono text-xs text-emerald-200/90">
            {`hours_wall = 8 h\ncrew_plan = 3\nhours_man = 8 × 3 = 24\nrate = 48 元/人·时\ncost_planned = 24 × 48 = ¥1,152.00`}
          </pre>
        </>
      ),
    },
    {
      title: "计划 vs 实际 · 打样剔除",
      body: (
        <>
          <p>
            组×日：计划人·时来自已发布排程 Σ；实际来自报工确认，且
            <strong className="text-amber-200/90"> 不得超过当日考勤上限</strong>。
          </p>
          <p className="mt-2">
            打样 SO-SMP-1 的 10 人·时不进入量产品项 P1；接口字段{" "}
            <code className="text-sky-300">sample_excluded</code> 单独展示。量产 P1 仍只计 24 人·时。
          </p>
        </>
      ),
    },
    {
      title: "一期边界",
      body: (
        <ul className="list-disc space-y-1 pl-5 text-xs text-slate-400">
          <li className="text-slate-300">已做：任务→人·时→计划成本；组×日/品项汇总；报工差异率</li>
          <li>未做：原料金额、backflush、工序×中心报工、OEE/水电/折旧</li>
        </ul>
      ),
    },
    {
      title: "进入 live 生产成本",
      body: (
        <p>
          建议路径：排程发布 → 班组长组×日报工 → 人事「生产成本」看部门-组计划 vs 实际。BOM 页可看单品的计划人工成本。
        </p>
      ),
    },
  ];

  return (
    <StoryShell
      title="计划人工成本 · 概念讲解"
      subtitle="人·时 × 组单价 · 报工对比 · 打样不进量产"
      steps={steps}
      livePath="/modules/hr/labor-cost"
      liveLabel="打开生产成本页"
    />
  );
}
