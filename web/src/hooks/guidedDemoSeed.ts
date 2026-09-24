import { useEffect, useState } from "react";

/** 与 GuidedDemoToolbar 派发的事件名一致 */
export const GUIDED_DEMO_SEED_EVENT = "guided-demo-seeded";

export type GuidedDemoSeededDetail = {
  stepId: string;
  runId: string;
  apply?: Record<string, unknown>;
};

/**
 * 演示线顶栏「生成数据」成功后递增 token，供列表页 useEffect 依赖以重新拉数。
 * @param stepIds 本页关心的环节 id；传 `"*"` 表示任意环节都刷新；不传则不监听。
 */
export function useGuidedDemoSeedReload(stepIds?: string | readonly string[] | "*"): number {
  const [token, setToken] = useState(0);
  const key =
    stepIds === "*"
      ? "*"
      : stepIds === undefined
        ? ""
        : Array.isArray(stepIds)
          ? stepIds.join("|")
          : stepIds;

  useEffect(() => {
    if (!stepIds) return;
    const allowed =
      stepIds === "*"
        ? null
        : new Set(Array.isArray(stepIds) ? stepIds : [stepIds]);
    const onSeeded = (ev: Event) => {
      const detail = (ev as CustomEvent<GuidedDemoSeededDetail>).detail;
      if (!detail?.stepId) return;
      if (allowed && !allowed.has(detail.stepId)) return;
      setToken((t) => t + 1);
    };
    window.addEventListener(GUIDED_DEMO_SEED_EVENT, onSeeded);
    return () => window.removeEventListener(GUIDED_DEMO_SEED_EVENT, onSeeded);
  }, [key]);

  return token;
}
