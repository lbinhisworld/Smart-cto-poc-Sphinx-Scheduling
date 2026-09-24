import { useState } from "react";
import {
  scheduleHeadcountAdopt,
  scheduleHeadcountTrial,
} from "../api/client";
import { workCenterLabel, type DeptCode, type GroupCode } from "../constants/groups";
import type { HeadcountGap, HeadcountTrial, Wo } from "../types/schedule";

function hours(value: number | string): string {
  const n = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(n)) return "—";
  return n.toFixed(2);
}

export function HeadcountGapPanel({
  gaps,
  wos,
  orderNos,
  today,
  busy,
}: {
  gaps: HeadcountGap[];
  wos: Wo[];
  orderNos: string[];
  today: string;
  busy: boolean;
}) {
  const [trial, setTrial] = useState<HeadcountTrial | null>(null);
  const [adopted, setAdopted] = useState("");
  const [sphDraft, setSphDraft] = useState<Record<string, string>>({});
  const [localBusy, setLocalBusy] = useState(false);
  const [error, setError] = useState("");

  if (gaps.length === 0) return null;

  async function runTrial(
    gap: HeadcountGap,
    mode: "add_people" | "recalibrate" | "extra_crew",
  ) {
    setError("");
    setLocalBusy(true);
    try {
      const item = wos.find(
        (wo) => wo.dept === gap.dept && wo.group_code === gap.group_code,
      );
      const sphRaw = sphDraft[`${gap.dept}|${gap.group_code}`];
      const data = await scheduleHeadcountTrial({
        orderNos,
        today,
        dept: gap.dept,
        groupCode: gap.group_code,
        mode,
        addPeople: gap.add_people_exact ?? gap.add_people_estimate ?? 0,
        itemCode: item?.item_code,
        sphValue: mode === "recalibrate" ? Number(sphRaw) : undefined,
      });
      setTrial(data.trial);
    } catch (err) {
      setError(err instanceof Error ? err.message : "试排失败");
    } finally {
      setLocalBusy(false);
    }
  }

  async function adopt(gap: HeadcountGap) {
    if (!trial || trial.dept !== gap.dept || trial.group_code !== gap.group_code) return;
    setLocalBusy(true);
    setError("");
    try {
      const data = await scheduleHeadcountAdopt({
        dept: gap.dept,
        groupCode: gap.group_code,
        headcount: trial.headcount,
      });
      setTrial(null);
      setAdopted(
        `已把在编改成 ${data.headcount} 人（${data.days} 天）。交期未改。请再倒排一次。`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "采纳失败");
    } finally {
      setLocalBusy(false);
    }
  }

  return (
    <section className="mb-3 rounded-lg border border-slate-700 bg-slate-900/80 p-3 text-slate-100">
      <h2 className="text-sm font-semibold">这一组要加几个人</h2>
      <ul className="mt-2 space-y-3">
        {gaps.map((gap) => {
          const key = `${gap.dept}|${gap.group_code}`;
          const label = workCenterLabel(gap.dept as DeptCode, gap.group_code as GroupCode);
          const exact =
            gap.add_people_exact == null
              ? null
              : gap.exact_infeasible
                ? "加人仍做不到"
                : `${gap.add_people_exact} 人`;
          const showing = trial && trial.dept === gap.dept && trial.group_code === gap.group_code;
          return (
            <li key={key} className="rounded border border-slate-800 p-2">
              <p className="text-xs text-slate-300">
                {label}
                <span className="ml-2 text-amber-300">{gap.basis_label}</span>
              </p>
              <dl className="mt-1 grid grid-cols-2 gap-x-2 text-[11px] text-slate-400">
                <div>现有人数</div>
                <div className="text-slate-100">{gap.headcount}</div>
                <div>需要人·时</div>
                <div className="text-slate-100">{hours(gap.hours_man_need)}</div>
                <div>现有人·时</div>
                <div className="text-slate-100">{hours(gap.hours_man_have)}</div>
                <div>要加的人数{gap.includes_unplaced ? "（估算）" : ""}</div>
                <div className="text-slate-100">
                  {gap.add_people_estimate == null ? "—" : `${gap.add_people_estimate} 人`}
                  {exact != null ? ` · 准数 ${exact}` : ""}
                </div>
              </dl>
              {gap.note && <p className="mt-1 text-[11px] leading-snug text-slate-400">{gap.note}</p>}
              {gap.basis_code === "SINGLE" && (gap.add_people_exact ?? 0) > 0 && (
                <button
                  type="button"
                  className="mt-2 rounded bg-sky-700 px-2 py-1 text-[11px] disabled:opacity-50"
                  disabled={busy || localBusy || orderNos.length === 0}
                  onClick={() => void runTrial(gap, "add_people")}
                >
                  按 {gap.add_people_exact} 人试排
                </button>
              )}
              {gap.basis_code === "CREW" && (
                <div className="mt-2 flex flex-wrap items-center gap-1">
                  <input
                    className="w-16 rounded border border-slate-600 bg-slate-950 px-1 py-0.5 text-[11px]"
                    inputMode="decimal"
                    placeholder="新产值"
                    value={sphDraft[key] ?? ""}
                    onChange={(e) => setSphDraft((prev) => ({ ...prev, [key]: e.target.value }))}
                  />
                  <button
                    type="button"
                    className="rounded bg-slate-700 px-2 py-1 text-[11px] disabled:opacity-50"
                    disabled={busy || localBusy || !sphDraft[key]}
                    onClick={() => void runTrial(gap, "recalibrate")}
                  >
                    用新产值试排
                  </button>
                  <button
                    type="button"
                    className="rounded bg-slate-700 px-2 py-1 text-[11px] disabled:opacity-50"
                    disabled={busy || localBusy}
                    onClick={() => void runTrial(gap, "extra_crew")}
                  >
                    再开一整组
                  </button>
                </div>
              )}
              {showing && trial && (
                <div className="mt-2 text-[11px] leading-snug text-slate-300">
                  <p>{trial.note}</p>
                  <p>
                    试排在编 {trial.headcount}
                    {trial.added_people != null ? `，增加 ${trial.added_people} 人` : ""}。
                  </p>
                  <p>
                    变得交期内可做：
                    {trial.cleared_wo_nos.length ? trial.cleared_wo_nos.join("、") : "无"}
                  </p>
                  <p>
                    仍然来不及：
                    {trial.still_late.length
                      ? trial.still_late
                          .map((wo) => {
                            const day = trial.earliest_finish[wo];
                            return day ? `${wo}（最快 ${day}）` : wo;
                          })
                          .join("、")
                      : "无"}
                  </p>
                  <div className="mt-1 flex gap-1">
                    <button
                      type="button"
                      className="rounded bg-slate-800 px-2 py-1"
                      onClick={() => setTrial(null)}
                    >
                      丢弃
                    </button>
                    {trial.mode === "add_people" && !trial.infeasible && (
                      <button
                        type="button"
                        className="rounded bg-emerald-800 px-2 py-1 disabled:opacity-50"
                        disabled={localBusy}
                        onClick={() => void adopt(gap)}
                      >
                        采纳在编
                      </button>
                    )}
                  </div>
                </div>
              )}
            </li>
          );
        })}
      </ul>
      {adopted && <p className="mt-2 text-[11px] text-emerald-300">{adopted}</p>}
      {error && <p className="mt-2 text-[11px] text-rose-300">{error}</p>}
    </section>
  );
}
