import { useEffect, useState } from "react";
import { useAuth } from "../../shell/auth";

async function api<T>(path: string, role: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", "X-Demo-Role": role, ...init?.headers },
  });
  const body = await res.json();
  if (!res.ok || body.code !== 0) {
    throw new Error(body.detail || body.message || "请求失败");
  }
  return body.data as T;
}

export function SettingsPage() {
  const auth = useAuth();
  const role = auth.role;
  const [baseUrl, setBaseUrl] = useState("https://api.deepseek.com/v1");
  const [model, setModel] = useState("deepseek-chat");
  const [apiKey, setApiKey] = useState("");
  const [hasKey, setHasKey] = useState(false);
  const [msg, setMsg] = useState("");

  useEffect(() => {
    if (!role) return;
    api<{ base_url: string; model: string; has_key: boolean }>("/api/crm/llm-config", role)
      .then((cfg) => {
        setBaseUrl(cfg.base_url);
        setModel(cfg.model);
        setHasKey(cfg.has_key);
      })
      .catch((err) => setMsg(String(err)));
  }, [role]);

  if (role !== "GM") {
    return (
      <div className="px-6 py-4">
        <h2 className="text-lg font-semibold">系统配置</h2>
        <p className="mt-2 text-sm text-[var(--text-muted)]">只有总经理能改模型配置。</p>
      </div>
    );
  }

  return (
    <div className="px-6 py-4">
      <h2 className="text-lg font-semibold">系统配置</h2>
      <p className="mt-1 text-xs text-[var(--text-muted)]">
        销售移动端、排程讲解共用这一处模型。密钥只写不读，不进仓库。
      </p>
      <form
        className="mt-6 max-w-lg space-y-4 text-sm"
        onSubmit={(e) => {
          e.preventDefault();
          if (!role) return;
          api("/api/crm/llm-config", role, {
            method: "PUT",
            body: JSON.stringify({ base_url: baseUrl, model, api_key: apiKey }),
          })
            .then(() => {
              setHasKey(true);
              setApiKey("");
              setMsg("已保存。密钥不回显。");
            })
            .catch((err) => setMsg(String(err)));
        }}
      >
        <label className="block">
          <span className="text-xs text-[var(--text-muted)]">接口地址</span>
          <input
            className="mt-1 w-full rounded-lg border px-3 py-2"
            style={{ borderColor: "var(--line)", background: "var(--bg-card)" }}
            value={baseUrl}
            onChange={(e) => setBaseUrl(e.target.value)}
          />
        </label>
        <label className="block">
          <span className="text-xs text-[var(--text-muted)]">模型名</span>
          <input
            className="mt-1 w-full rounded-lg border px-3 py-2"
            style={{ borderColor: "var(--line)", background: "var(--bg-card)" }}
            value={model}
            onChange={(e) => setModel(e.target.value)}
          />
        </label>
        <label className="block">
          <span className="text-xs text-[var(--text-muted)]">密钥 {hasKey ? "· 已有密钥" : "· 未配置时走关键词"}</span>
          <input
            type="password"
            className="mt-1 w-full rounded-lg border px-3 py-2"
            style={{ borderColor: "var(--line)", background: "var(--bg-card)" }}
            placeholder="留空则不改"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            autoComplete="off"
          />
        </label>
        <button type="submit" className="rounded-lg bg-[var(--accent)] px-4 py-2 text-white">
          保存
        </button>
        {msg && <p className="text-xs text-[var(--text-muted)]">{msg}</p>}
      </form>
    </div>
  );
}
