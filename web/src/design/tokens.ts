/** 全局皮肤：与排程 POC 一致的深色系（Tailwind slate 近似值） */
export type SkinId = "dark";

export const DEFAULT_SKIN: SkinId = "dark";

export const SKINS: Record<SkinId, Record<string, string>> = {
  dark: {
    "--bg-body": "#020617",
    "--bg-card": "#0f172a",
    "--bg-nav": "#0f172a",
    "--text-nav": "#e2e8f0",
    "--text-body": "#e2e8f0",
    "--text-muted": "#94a3b8",
    "--line": "#1e293b",
    "--accent": "#38bdf8",
    "--accent-hover": "#0ea5e9",
    "--nav-active-bg": "rgb(56 189 248 / 0.14)",
    "--table-stripe": "#0b1120",
    "--table-hover": "#1e293b",
    "--table-head": "#1e293b",
  },
};

const LEGACY_SKINS = new Set(["choc", "do1"]);

export function normalizeStoredSkin(raw: string | null): SkinId {
  if (raw === "dark") return "dark";
  if (raw && LEGACY_SKINS.has(raw)) return "dark";
  return DEFAULT_SKIN;
}

export function applySkin(skin: SkinId = DEFAULT_SKIN) {
  const root = document.documentElement;
  const vars = SKINS[skin];
  for (const [k, v] of Object.entries(vars)) {
    root.style.setProperty(k, v);
  }
  root.dataset.skin = skin;
  root.style.colorScheme = "dark";
}
