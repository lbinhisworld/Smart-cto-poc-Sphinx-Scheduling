import { useEffect, useMemo, useState } from "react";
import {
  askKb,
  fetchKbCard,
  fetchKbJournal,
  fetchKbOps,
  fetchKbPending,
  fetchKbProbe,
  fetchKbSuggestions,
  fetchKbThemes,
  fetchKbTree,
  nodKb,
  sealKb,
  type AskResult,
  type JournalEntry,
  type KbCard,
  type KbNode,
  type PendingItem,
  type ProbeItem,
  type ThemeRow,
} from "../../api/kb";
import { useAuth } from "../../shell/auth";

const OPS_LAYERS = ["主张", "权责", "价值流", "环节", "节点", "投影", "结论"] as const;

const LAYER_CODE: Record<string, string> = {
  主张: "L1",
  权责: "L2",
  价值流: "L3",
  环节: "L3.1",
  节点: "L3.2",
  投影: "L4",
  结论: "结论",
  对象: "对象",
  槽: "槽",
  运行结果: "运行",
};

function LayerBadge({ layer }: { layer: string }) {
  const label = LAYER_CODE[layer] ?? layer;
  return (
    <span
      className="mr-1.5 inline-flex shrink-0 items-center rounded px-1 py-px font-mono text-[10px] font-semibold leading-4"
      style={{
        color: "#fb923c",
        background: "color-mix(in srgb, #fb923c 16%, transparent)",
        border: "1px solid color-mix(in srgb, #fb923c 40%, transparent)",
      }}
    >
      {label}
    </span>
  );
}

function statusTone(status: string) {
  return status === "已封印" ? "text-emerald-300" : "text-amber-300";
}

function OpsBranch({
  node,
  selected,
  onSelect,
}: {
  node: KbNode;
  selected: string | null;
  onSelect: (id: string) => void;
}) {
  const active = selected === node.id;
  const caps = node.capabilities ?? [];
  const owners = node.owners ?? [];
  const isClaim = node.layer === "主张";
  return (
    <li>
      <button
        type="button"
        onClick={() => onSelect(node.id)}
        className={`inline-flex w-full items-center rounded px-2 py-1 text-left text-[13px] ${
          active ? "font-medium" : "hover:bg-[var(--table-hover)]"
        }`}
        style={active ? { background: "var(--nav-active-bg)", color: "var(--accent)" } : undefined}
      >
        <LayerBadge layer={node.layer} />
        {node.name}
        <span className={`ml-1 text-[11px] ${statusTone(node.status)}`}>{node.status}</span>
      </button>
      {owners.length > 0 ? (
        <div className="ml-6 flex flex-wrap gap-1 py-0.5">
          {owners.map((owner) => (
            <button
              key={owner.id}
              type="button"
              onClick={() => onSelect(owner.id)}
              className="rounded px-1.5 py-px text-[11px] text-[var(--text-muted)] hover:text-[var(--text-body)]"
              style={{ border: "1px solid var(--line)" }}
            >
              谁有权 {owner.name}
            </button>
          ))}
        </div>
      ) : null}
      {isClaim ? (
        <>
          {caps.length > 0 ? (
            <div className="ml-3 border-l pl-2" style={{ borderColor: "var(--line)" }}>
              <p className="px-2 pt-1 text-[11px] text-[var(--text-muted)]">能力中心</p>
              <ul className="space-y-0.5">
                {caps.map((cap) => (
                  <TreeBranch key={cap.id} node={cap} selected={selected} onSelect={onSelect} />
                ))}
              </ul>
            </div>
          ) : null}
          {node.children.length > 0 ? (
            <div className="ml-3 border-l pl-2" style={{ borderColor: "var(--line)" }}>
              <p className="px-2 pt-1 text-[11px] text-[var(--text-muted)]">价值流</p>
              <ul className="space-y-0.5">
                {node.children.map((child) => (
                  <OpsBranch key={child.id} node={child} selected={selected} onSelect={onSelect} />
                ))}
              </ul>
            </div>
          ) : null}
        </>
      ) : node.layer === "价值流" && node.children.length > 0 ? (
        <div className="ml-3 border-l pl-2" style={{ borderColor: "var(--line)" }}>
          <p className="px-2 pt-1 text-[11px] text-[var(--text-muted)]">价值流阶段</p>
          <ul className="space-y-0.5">
            {node.children.map((child) => (
              <OpsBranch key={child.id} node={child} selected={selected} onSelect={onSelect} />
            ))}
          </ul>
        </div>
      ) : node.children.length > 0 ? (
        <ul className="ml-3 border-l pl-2" style={{ borderColor: "var(--line)" }}>
          {node.children.map((child) => (
            <OpsBranch key={child.id} node={child} selected={selected} onSelect={onSelect} />
          ))}
        </ul>
      ) : null}
    </li>
  );
}

function TreeBranch({
  node,
  selected,
  onSelect,
}: {
  node: KbNode;
  selected: string | null;
  onSelect: (id: string) => void;
}) {
  const active = selected === node.id;
  return (
    <li>
      <button
        type="button"
        onClick={() => onSelect(node.id)}
        className={`inline-flex w-full items-center rounded px-2 py-1 text-left text-[13px] ${
          active ? "font-medium" : "hover:bg-[var(--table-hover)]"
        }`}
        style={active ? { background: "var(--nav-active-bg)", color: "var(--accent)" } : undefined}
      >
        <LayerBadge layer={node.layer} />
        {node.name}
        <span className={`ml-1 text-[11px] ${statusTone(node.status)}`}>{node.status}</span>
      </button>
      {node.children.length > 0 ? (
        <ul className="ml-3 border-l pl-2" style={{ borderColor: "var(--line)" }}>
          {node.children.map((child) => (
            <TreeBranch key={child.id} node={child} selected={selected} onSelect={onSelect} />
          ))}
        </ul>
      ) : null}
    </li>
  );
}

function RefLine({
  label,
  refs,
  names,
  onSelect,
}: {
  label: string;
  refs?: string[] | null;
  names: Record<string, string>;
  onSelect?: (id: string) => void;
}) {
  const items = refs ?? [];
  if (items.length === 0) return null;
  return (
    <p className="text-[12px] text-[var(--text-muted)]">
      {label}{" "}
      {items.map((item, index) => {
        const linked = Boolean(onSelect && (names[item] || item.includes(".")));
        return (
          <span key={item}>
            {index > 0 ? "、" : null}
            {linked ? (
              <button type="button" className="underline" onClick={() => onSelect?.(item)}>
                {names[item] ?? item}
              </button>
            ) : (
              item
            )}
          </span>
        );
      })}
    </p>
  );
}

function CardPanel({
  card,
  names,
  onSelect,
}: {
  card: KbCard | null;
  names: Record<string, string>;
  onSelect?: (id: string) => void;
}) {
  if (!card) {
    return <p className="text-sm text-[var(--text-muted)]">点左侧对象或运营卡看定义 / 命题。</p>;
  }
  const body = card.套 === "行业" ? card.定义 : card.命题;
  const say = card.对外怎么说 ?? {};
  const canDo = card.可以 ?? [];
  const banned = card.禁止 ?? [];
  return (
    <article className="space-y-3 text-sm">
      <header>
        <p className="flex flex-wrap items-center gap-1 text-[11px] text-[var(--text-muted)]">
          <LayerBadge layer={card.层} />
          {card.编号} · {card.套} · {card.层}
        </p>
        <h3 className="mt-1 text-base font-semibold">{card.名称}</h3>
        <p className={`text-[12px] ${statusTone(card.状态)}`}>{card.状态}</p>
      </header>
      {body ? <p className="leading-relaxed">{body}</p> : null}
      {card.阶段产出 ? <p className="text-[12px] text-[var(--text-muted)]">阶段产出 {card.阶段产出}</p> : null}
      {card.角色 ? <p className="text-[12px] text-[var(--text-muted)]">角色 {card.角色}</p> : null}
      {card.持有 ? <p className="text-[12px] text-[var(--text-muted)]">持有 {card.持有}</p> : null}
      {canDo.length > 0 ? <p className="text-[12px] text-[var(--text-muted)]">可以 {canDo.join("、")}</p> : null}
      {banned.length > 0 ? <p className="text-[12px] text-[var(--text-muted)]">禁止 {banned.join("、")}</p> : null}
      <RefLine label="谁兑现" refs={card.谁兑现} names={names} onSelect={onSelect} />
      <RefLine label="撑住谁" refs={card.撑住谁} names={names} onSelect={onSelect} />
      <RefLine label="谁有权" refs={card.谁有权} names={names} onSelect={onSelect} />
      {card.别名 && card.别名.length > 0 ? (
        <p className="text-[12px] text-[var(--text-muted)]">别名 {card.别名.join("、")}</p>
      ) : null}
      {card.属于 ? (
        <p className="text-[12px] text-[var(--text-muted)]">属于 {card.属于}</p>
      ) : null}
      {card.关联 && card.关联.length > 0 ? (
        <p className="text-[12px] text-[var(--text-muted)]">关联 {card.关联.join("、")}</p>
      ) : null}
      {card.是一种 && card.是一种.length > 0 ? (
        <p className="text-[12px] text-[var(--text-muted)]">是一种 {card.是一种.join("、")}</p>
      ) : null}
      {card.其下 && card.其下.length > 0 ? (
        <p className="text-[12px] text-[var(--text-muted)]">其下 {card.其下.join("、")}</p>
      ) : null}
      {Object.keys(say).length > 0 ? (
        <ul className="space-y-1 text-[13px]">
          {Object.entries(say).map(([who, line]) => (
            <li key={who}>
              <span className="text-[var(--text-muted)]">{who}：</span>
              {line}
            </li>
          ))}
        </ul>
      ) : null}
      {card.出处 ? (
        <p className="text-[12px] text-[var(--text-muted)]">
          出处 {Array.isArray(card.出处) ? card.出处.join("、") : card.出处}
        </p>
      ) : null}
      {String(Array.isArray(card.出处) ? card.出处.join(" ") : card.出处 || "").includes("probe_journal.yaml#") ? (
        <p className="text-[12px] text-amber-200">由探针补过栏，见出处里的 P 号。</p>
      ) : null}
      {card.说明 ? (
        <p className="whitespace-pre-wrap text-[12px] leading-relaxed text-[var(--text-muted)]">{card.说明}</p>
      ) : null}
    </article>
  );
}

const NOD_ROLES = new Set(["PMC", "SALES", "SALES_MGR", "GM"]);
const TENSION_LAYERS = ["主张", "权责", "价值流", "环节", "许可", "对象"];

export function KbPage() {
  const { role } = useAuth();
  const [pack, setPack] = useState<"行业" | "运营">("行业");
  const [roots, setRoots] = useState<KbNode[]>([]);
  const [runtime, setRuntime] = useState<KbNode[]>([]);
  const [showRuntime, setShowRuntime] = useState(false);
  const [ops, setOps] = useState<KbCard[]>([]);
  const [opsRoots, setOpsRoots] = useState<KbNode[]>([]);
  const [unattached, setUnattached] = useState<KbNode[]>([]);
  const [showUnattached, setShowUnattached] = useState(false);
  const [showProjections, setShowProjections] = useState(false);
  const [selected, setSelected] = useState<string | null>("D.order.due_date");
  const [card, setCard] = useState<KbCard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [question, setQuestion] = useState("E2 了能不能改订单交期");
  const [hints, setHints] = useState<string[]>([]);
  const [answer, setAnswer] = useState<AskResult | null>(null);
  const [asking, setAsking] = useState(false);
  const [themes, setThemes] = useState<ThemeRow[]>([]);
  const [theme, setTheme] = useState("履约四环节");
  const [pending, setPending] = useState<PendingItem[]>([]);
  const [probes, setProbes] = useState<ProbeItem[]>([]);
  const [journal, setJournal] = useState<JournalEntry[]>([]);
  const [tensionLayer, setTensionLayer] = useState("");
  const [busyLeaf, setBusyLeaf] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    Promise.all([fetchKbTree(), fetchKbOps(), fetchKbSuggestions(), fetchKbThemes()])
      .then(([tree, opsBody, sug, themeBody]) => {
        if (!alive) return;
        setRoots(tree.roots);
        setRuntime(tree.runtime ?? []);
        setOpsRoots(opsBody.roots ?? []);
        setUnattached(opsBody.unattached ?? []);
        setOps(opsBody.cards);
        setHints(sug.questions);
        setThemes(themeBody.themes);
        if (themeBody.default) setTheme(themeBody.default);
      })
      .catch((e: Error) => {
        if (alive) setError(e.message);
      });
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    if (!selected) return;
    let alive = true;
    fetchKbCard(selected)
      .then((data) => {
        if (alive) setCard(data);
      })
      .catch((e: Error) => {
        if (alive) setError(e.message);
      });
    return () => {
      alive = false;
    };
  }, [selected]);

  const reloadWorkbench = () => {
    Promise.all([fetchKbPending(theme), fetchKbProbe(theme), fetchKbJournal()])
      .then(([pendingBody, probeBody, journalBody]) => {
        setPending(pendingBody.items);
        setProbes(probeBody.items);
        setJournal(journalBody.entries);
      })
      .catch((e: Error) => setError(e.message));
  };

  useEffect(() => {
    reloadWorkbench();
    // theme is the only trigger; reloadWorkbench closes over it
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [theme]);

  const opsByLayer = useMemo(() => {
    return OPS_LAYERS.map((layer) => ({
      layer,
      cards: ops.filter((c) => c.层 === layer),
    })).filter((row) => row.cards.length > 0);
  }, [ops]);

  const nameById = useMemo(() => {
    const map: Record<string, string> = {};
    for (const item of ops) map[item.编号] = item.名称;
    return map;
  }, [ops]);

  const onAsk = async (text: string) => {
    setAsking(true);
    setError(null);
    try {
      const result = await askKb(text);
      setAnswer(result);
      if (result.slots[0]) setSelected(result.slots[0]);
      if (result.workbench_theme) setTheme(result.workbench_theme);
      if (result.workbench_id) setSelected(result.workbench_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setAsking(false);
    }
  };

  return (
    <div className="px-6 py-4">
      <h2 className="text-lg font-semibold">封印本体</h2>
      <p className="mt-1 text-sm text-[var(--text-muted)]">
        只读。行业主林是格子与量纲；五幕、计划版本在运行结果林。运营主张下并列能力中心与价值流。询问走顾问，对词看别名。槽未封印或对不上就停，本页不能改库。
      </p>

      {error ? (
        <p className="mt-3 rounded border border-rose-800 bg-rose-950/40 px-3 py-2 text-sm text-rose-100">{error}</p>
      ) : null}

      <div className="mt-3 flex gap-2">
        {(["行业", "运营"] as const).map((name) => (
          <button
            key={name}
            type="button"
            onClick={() => setPack(name)}
            className="rounded border px-3 py-1 text-sm"
            style={{
              borderColor: pack === name ? "var(--accent)" : "var(--line)",
              background: pack === name ? "var(--nav-active-bg)" : "var(--bg-card)",
            }}
          >
            {name}包
          </button>
        ))}
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(260px,1fr)_minmax(280px,1.1fr)_minmax(280px,1fr)]">
        <section className="rounded-lg border p-3" style={{ borderColor: "var(--line)", background: "var(--bg-card)" }}>
          <h3 className="mb-2 text-sm font-semibold text-[var(--accent)]">
            {pack === "行业" ? "对象构成" : "主张 · 能力 · 价值流"}
          </h3>
          {pack === "行业" ? (
            <div className="max-h-[70vh] space-y-3 overflow-auto">
              <ul className="space-y-0.5">
                {roots.map((node) => (
                  <TreeBranch key={node.id} node={node} selected={selected} onSelect={setSelected} />
                ))}
              </ul>
              {runtime.length > 0 ? (
                <div>
                  <button
                    type="button"
                    className="text-[11px] text-[var(--text-muted)]"
                    onClick={() => setShowRuntime((v) => !v)}
                  >
                    {showRuntime ? "收起运行结果林" : "查看运行结果林（本趟倒排切片）"}
                  </button>
                  {showRuntime ? (
                    <ul className="mt-1 space-y-0.5">
                      {runtime.map((node) => (
                        <TreeBranch key={node.id} node={node} selected={selected} onSelect={setSelected} />
                      ))}
                    </ul>
                  ) : null}
                </div>
              ) : null}
            </div>
          ) : (
            <div className="max-h-[70vh] space-y-3 overflow-auto">
              <ul className="space-y-0.5">
                {opsRoots.map((node) => (
                  <OpsBranch key={node.id} node={node} selected={selected} onSelect={setSelected} />
                ))}
              </ul>
              {unattached.length > 0 ? (
                <div>
                  <button
                    type="button"
                    className="text-[11px] text-[var(--text-muted)]"
                    onClick={() => setShowUnattached((v) => !v)}
                  >
                    {showUnattached ? "收起未挂主张的能力" : "未挂主张的能力"}
                  </button>
                  {showUnattached ? (
                    <ul className="mt-1 space-y-0.5">
                      {unattached.map((node) => (
                        <TreeBranch key={node.id} node={node} selected={selected} onSelect={setSelected} />
                      ))}
                    </ul>
                  ) : null}
                </div>
              ) : null}
              <button
                type="button"
                className="text-[11px] text-[var(--text-muted)]"
                onClick={() => setShowProjections((v) => !v)}
              >
                {showProjections ? "收起演示投影" : "查看演示菜单 / 角色投影"}
              </button>
              {showProjections
                ? opsByLayer
                    .filter((row) => row.layer === "投影")
                    .map((row) => (
                      <div key={row.layer}>
                        <p className="mb-1 text-[11px] text-[var(--text-muted)]">投影</p>
                        <ul>
                          {row.cards.map((item) => (
                            <li key={item.编号}>
                              <button
                                type="button"
                                onClick={() => setSelected(item.编号)}
                                className={`inline-flex w-full items-center rounded px-2 py-1 text-left text-[13px] ${
                                  selected === item.编号 ? "font-medium" : "hover:bg-[var(--table-hover)]"
                                }`}
                                style={
                                  selected === item.编号
                                    ? { background: "var(--nav-active-bg)", color: "var(--accent)" }
                                    : undefined
                                }
                              >
                                <LayerBadge layer={item.层} />
                                {item.名称}
                                <span className={`ml-1 text-[11px] ${statusTone(item.状态)}`}>{item.状态}</span>
                              </button>
                            </li>
                          ))}
                        </ul>
                      </div>
                    ))
                : null}
            </div>
          )}
        </section>

        <section className="rounded-lg border p-3" style={{ borderColor: "var(--line)", background: "var(--bg-card)" }}>
          <h3 className="mb-2 text-sm font-semibold text-[var(--accent)]">卡片</h3>
          <CardPanel card={card} names={nameById} onSelect={setSelected} />
        </section>

        <section className="rounded-lg border p-3" style={{ borderColor: "var(--line)", background: "var(--bg-card)" }}>
          <h3 className="mb-2 text-sm font-semibold text-[var(--accent)]">顾问询问</h3>
          <div className="mb-2 flex flex-wrap gap-1">
            {hints.map((hint) => (
              <button
                key={hint}
                type="button"
                className="rounded border px-2 py-0.5 text-[11px] text-[var(--text-muted)] hover:text-[var(--text-body)]"
                style={{ borderColor: "var(--line)" }}
                onClick={() => {
                  setQuestion(hint);
                  void onAsk(hint);
                }}
              >
                {hint}
              </button>
            ))}
          </div>
          <form
            className="flex gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              void onAsk(question);
            }}
          >
            <input
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              className="min-w-0 flex-1 rounded border bg-transparent px-2 py-1 text-sm"
              style={{ borderColor: "var(--line)" }}
              placeholder="先问交期、版、CREW"
            />
            <button
              type="submit"
              disabled={asking}
              className="rounded px-3 py-1 text-sm"
              style={{ background: "var(--nav-active-bg)", color: "var(--accent)" }}
            >
              {asking ? "…" : "问"}
            </button>
          </form>
          {answer ? (
            <div className="mt-3 space-y-2 text-sm">
              <p className={answer.verdict === "成立" ? "text-emerald-300" : "text-amber-300"}>
                {answer.verdict}
                {answer.mode ? <span className="ml-2 text-[12px] text-[var(--text-muted)]">{answer.mode}</span> : null}
              </p>
              <p className="whitespace-pre-wrap leading-relaxed">{answer.text}</p>
              {answer.chain.length > 0 ? (
                <p className="text-[12px] text-[var(--text-muted)]">链 {answer.chain.join(" → ")}</p>
              ) : null}
              {answer.missing.length > 0 ? (
                <p className="text-[12px] text-[var(--text-muted)]">缺口：{answer.missing.join("、")}</p>
              ) : null}
              {answer.slots.length > 0 ? (
                <p className="text-[12px] text-[var(--text-muted)]">绑到 {answer.slots.join("、")}</p>
              ) : null}
              {answer.workbench_kind === "pending" ? (
                <button
                  type="button"
                  className="text-[12px] underline"
                  onClick={() => {
                    if (answer.workbench_id) setSelected(answer.workbench_id);
                  }}
                >
                  去待确认认这条链
                </button>
              ) : null}
              {answer.workbench_kind === "probe" ? (
                <button
                  type="button"
                  className="text-[12px] underline"
                  onClick={() => {
                    if (answer.workbench_id) setSelected(answer.workbench_id);
                  }}
                >
                  去探针问这句
                </button>
              ) : null}
            </div>
          ) : (
            <p className="mt-3 text-[12px] text-[var(--text-muted)]">
              对不上库的问题会停住，不会现场发明机台或冷链。
            </p>
          )}
        </section>
      </div>

      <section className="mt-4 rounded-lg border p-3" style={{ borderColor: "var(--line)", background: "var(--bg-card)" }}>
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <h3 className="text-sm font-semibold text-[var(--accent)]">主题工作台</h3>
          <select
            value={theme}
            onChange={(e) => setTheme(e.target.value)}
            className="rounded border bg-transparent px-2 py-1 text-sm"
            style={{ borderColor: "var(--line)" }}
          >
            {themes.map((row) => (
              <option key={row.主题} value={row.主题}>
                {row.主题}
                {row.默认打开 ? "（默认）" : ""}
              </option>
            ))}
          </select>
          <button type="button" className="text-[11px] text-[var(--text-muted)]" onClick={() => void onAsk("小白有没有要补充的")}>
            小白有没有要补充的
          </button>
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          <div>
            <h4 className="mb-2 text-[13px] font-semibold">待确认 · 认链</h4>
            {pending.length === 0 ? (
              <p className="text-[12px] text-[var(--text-muted)]">这个主题没有未封浅卡。</p>
            ) : (
              <ul className="space-y-3">
                {pending.map((item) => (
                  <li key={item.shallow_id} className="rounded border p-2 text-sm" style={{ borderColor: "var(--line)" }}>
                    <button type="button" className="text-left font-medium" onClick={() => setSelected(item.shallow_id)}>
                      {item.name}
                      <span className={`ml-2 text-[11px] ${statusTone(item.status)}`}>{item.status}</span>
                    </button>
                    <p className="mt-1 text-[11px] text-[var(--text-muted)]">{item.chain.join(" → ")}</p>
                    <p className="mt-1 whitespace-pre-wrap text-[12px] leading-relaxed">{item.speech}</p>
                    {NOD_ROLES.has(role ?? "") ? (
                      <div className="mt-2 flex flex-wrap items-center gap-2">
                        <button
                          type="button"
                          disabled={busyLeaf === item.shallow_id}
                          className="rounded border px-2 py-0.5 text-[11px]"
                          style={{ borderColor: "var(--line)" }}
                          onClick={() => {
                            if (!role) return;
                            setBusyLeaf(item.shallow_id);
                            nodKb(role, { 叶子: item.shallow_id, 主题: theme, 结果: "认" })
                              .then(() => reloadWorkbench())
                              .catch((e: Error) => setError(e.message))
                              .finally(() => setBusyLeaf(null));
                          }}
                        >
                          认
                        </button>
                        <select
                          value={tensionLayer}
                          onChange={(e) => setTensionLayer(e.target.value)}
                          className="rounded border bg-transparent px-1 py-0.5 text-[11px]"
                          style={{ borderColor: "var(--line)" }}
                        >
                          <option value="">断在哪一层</option>
                          {TENSION_LAYERS.map((layer) => (
                            <option key={layer} value={layer}>
                              {layer}
                            </option>
                          ))}
                        </select>
                        <button
                          type="button"
                          disabled={!tensionLayer || busyLeaf === item.shallow_id}
                          className="rounded border px-2 py-0.5 text-[11px]"
                          style={{ borderColor: "var(--line)" }}
                          onClick={() => {
                            if (!role || !tensionLayer) return;
                            setBusyLeaf(item.shallow_id);
                            nodKb(role, { 叶子: item.shallow_id, 主题: theme, 结果: "张力", 断在: tensionLayer })
                              .then(() => reloadWorkbench())
                              .catch((e: Error) => setError(e.message))
                              .finally(() => setBusyLeaf(null));
                          }}
                        >
                          有张力
                        </button>
                        {role === "GM" ? (
                          <button
                            type="button"
                            disabled={busyLeaf === item.shallow_id}
                            className="rounded border px-2 py-0.5 text-[11px]"
                            style={{ borderColor: "var(--line)" }}
                            onClick={() => {
                              if (!role) return;
                              setBusyLeaf(item.shallow_id);
                              sealKb(role, { 叶子: item.shallow_id, 主题: theme })
                                .then(() => reloadWorkbench())
                                .catch((e: Error) => setError(e.message))
                                .finally(() => setBusyLeaf(null));
                            }}
                          >
                            封印本条
                          </button>
                        ) : null}
                      </div>
                    ) : (
                      <p className="mt-2 text-[11px] text-[var(--text-muted)]">计划 / 销售演示角色可点头；封印仅总经理。</p>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div>
            <h4 className="mb-2 text-[13px] font-semibold">探针 · 问栏</h4>
            {probes.length === 0 ? (
              <p className="text-[12px] text-[var(--text-muted)]">这次没有可补的栏。</p>
            ) : (
              <ul className="space-y-2">
                {probes.map((item) => (
                  <li key={`${item.anchor}-${item.field}`} className="text-sm">
                    <button type="button" className="text-left" onClick={() => setSelected(item.anchor)}>
                      <span className="text-[11px] text-[var(--text-muted)]">
                        {item.anchor} · {item.field}
                      </span>
                      <span className="mt-0.5 block">{item.question}</span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
            <h4 className="mb-2 mt-4 text-[13px] font-semibold">探针时间线</h4>
            {journal.length === 0 ? (
              <p className="text-[12px] text-[var(--text-muted)]">尚无问句入库记录。已问不等于更新了库。</p>
            ) : (
              <ul className="space-y-2 text-[12px]">
                {journal.map((row) => {
                  const patches = row.增量?.改栏 ?? [];
                  const pendingIn = row.状态 === "已问" || row.状态 === "已答";
                  return (
                    <li key={row.编号}>
                      <span className="font-mono">{row.编号}</span> {row.小白问}
                      <span className="ml-1 text-[var(--text-muted)]">
                        {patches.length ? patches.map((p) => `${p.编号} ${p.栏}`).join("、") : "无改栏"} · {row.状态}
                      </span>
                      {pendingIn ? <span className="ml-1 text-amber-200">尚未入库</span> : null}
                      {row.状态 === "拒收" ? <span className="ml-1 text-rose-200">拒收，增量应空</span> : null}
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}
