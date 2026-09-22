import { request, requestWithRole } from "./client";

export type KbNode = {
  id: string;
  name: string;
  layer: string;
  status: string;
  pack: string;
  children: KbNode[];
  capabilities?: KbNode[];
  owners?: KbNode[];
};

export type KbCard = {
  编号: string;
  名称: string;
  套: string;
  层: string;
  状态: string;
  命题?: string | null;
  定义?: string | null;
  属于?: string | null;
  关联?: string[];
  是一种?: string[];
  别名?: string[];
  其下?: string[];
  撑住谁?: string[];
  谁有权?: string[];
  谁兑现?: string[];
  角色?: string | null;
  持有?: string | null;
  可以?: string[];
  阶段产出?: string | null;
  绑哪个对象?: string[];
  对外怎么说?: Record<string, string>;
  说明?: string | null;
  出处?: string[] | string | null;
  类型?: string | null;
  必须有?: string | boolean | null;
  禁止?: string[] | null;
};

export type AskResult = {
  verdict: string;
  question: string;
  intent: string | null;
  mode: string;
  slots: string[];
  missing: string[];
  claim: string | null;
  chain: string[];
  text: string;
  suggestions: string[];
  workbench_kind?: string;
  workbench_theme?: string;
  workbench_id?: string;
  readonly: boolean;
};

export type PendingItem = {
  shallow_id: string;
  name: string;
  status: string;
  layer: string;
  track: string;
  chain: string[];
  captured: string[];
  permits: string[];
  speech: string;
};

export type ProbeItem = {
  anchor: string;
  name: string;
  field: string;
  question: string;
  status: string;
  layer: string;
};

export type JournalEntry = {
  编号?: string;
  小白问?: string;
  状态?: string;
  锚点?: string;
  探针栏?: string;
  增量?: { 新卡?: string[]; 改栏?: { 编号?: string; 栏?: string; 到?: string[] }[]; 新边?: unknown[] };
};

export type ThemeRow = {
  主题: string;
  轨: string;
  默认打开: boolean;
  说明: string;
};

export function fetchKbTree(): Promise<{ roots: KbNode[]; runtime?: KbNode[]; readonly: boolean }> {
  return request("/api/kb/tree");
}

export function fetchKbOps(): Promise<{
  roots: KbNode[];
  unattached?: KbNode[];
  projections: KbCard[];
  cards: KbCard[];
  readonly: boolean;
}> {
  return request("/api/kb/ops");
}

export function fetchKbCard(id: string): Promise<KbCard> {
  return request(`/api/kb/card/${encodeURIComponent(id)}`);
}

export function fetchKbSuggestions(): Promise<{ questions: string[] }> {
  return request("/api/kb/suggestions");
}

export function askKb(question: string, role?: string): Promise<AskResult> {
  return request("/api/kb/ask", {
    method: "POST",
    body: JSON.stringify({ question, role }),
  });
}

export function fetchKbThemes(): Promise<{ themes: ThemeRow[]; default: string; readonly: boolean }> {
  return request("/api/kb/themes");
}

export function fetchKbPending(theme: string): Promise<{ theme: string; readonly: boolean; items: PendingItem[] }> {
  return request(`/api/kb/pending?theme=${encodeURIComponent(theme)}`);
}

export function fetchKbProbe(theme: string): Promise<{ theme: string; readonly: boolean; items: ProbeItem[] }> {
  return request(`/api/kb/probe?theme=${encodeURIComponent(theme)}`);
}

export function fetchKbJournal(): Promise<{ entries: JournalEntry[]; readonly: boolean }> {
  return request("/api/kb/journal");
}

export function nodKb(
  role: string,
  body: { 叶子: string; 主题: string; 结果: string; 断在?: string; 栏?: string; 探针?: string[] },
): Promise<{ row: Record<string, unknown>; sealed: boolean }> {
  return requestWithRole("/api/kb/nod", role, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function sealKb(role: string, body: { 叶子: string; 主题: string }): Promise<{ changed: string[] }> {
  return requestWithRole("/api/kb/seal", role, {
    method: "POST",
    body: JSON.stringify(body),
  });
}
