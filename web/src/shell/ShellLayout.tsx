import { useCallback, useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { GuidedDemoToolbar } from "../components/GuidedDemoToolbar";
import { WecomBell } from "../components/WecomBell";
import { useAuth, type RoleCode } from "./auth";
import { checkApiHealth, requestWithRole } from "../api/client";
import { fallbackMenuForRole, groupedNavForRole, type MenuItem } from "./menuConfig";

export function ShellLayout() {
  const auth = useAuth();
  const location = useLocation();
  const role = auth.role;
  const [menu, setMenu] = useState<MenuItem[]>(() =>
    role ? fallbackMenuForRole(role) : [],
  );
  const [menuError, setMenuError] = useState<string | null>(null);
  const [apiDown, setApiDown] = useState(false);

  const loadMenu = useCallback(() => {
    if (!role) return;
    setMenuError(null);
    requestWithRole<{ items?: MenuItem[] }>("/api/portal/menu", role)
      .then((data) => {
        const items = data.items;
        if (items?.length) setMenu(items);
        else setMenu(fallbackMenuForRole(role));
        setApiDown(false);
      })
      .catch((e) => {
        setMenu(fallbackMenuForRole(role));
        setMenuError(String(e));
      });
  }, [role]);

  useEffect(() => {
    loadMenu();
  }, [loadMenu]);

  useEffect(() => {
    void checkApiHealth().then((ok) => setApiDown(!ok));
  }, [location.pathname]);

  const grouped = role ? groupedNavForRole(role as RoleCode, menu) : null;
  const phoneVisit = location.pathname.startsWith("/crm/visit");

  const navLinkClass = ({ isActive }: { isActive: boolean }) =>
    `mb-0.5 block rounded px-2 py-1.5 text-[var(--text-nav)] ${
      isActive ? "font-medium" : "opacity-90 hover:opacity-100"
    }`;

  const navLinkStyle = ({ isActive }: { isActive: boolean }) =>
    isActive ? { background: "var(--nav-active-bg)", color: "var(--accent)" } : undefined;

  return (
    <div
      className="flex h-screen flex-col overflow-hidden"
      style={{ background: "var(--bg-body)", color: "var(--text-body)" }}
    >
      {apiDown && (
        <div className="shrink-0 border-b border-rose-900/60 bg-rose-950/50 px-4 py-2 text-xs text-rose-100">
          未检测到 API（127.0.0.1:8000）。请另开终端在项目根执行{" "}
          <code className="rounded bg-black/30 px-1">./scripts/start.sh</code>
          ，本页仅 5180 前端无法单独工作。
        </div>
      )}
      <header
        className="flex shrink-0 items-center justify-between border-b px-4 py-2"
        style={{ borderColor: "var(--line)", background: "var(--bg-card)" }}
      >
        <div>
          <p className="text-sm font-semibold">斯芬克斯一体化管理系统</p>
          <p className="text-[11px] text-[var(--text-muted)]">
            {auth.userName} · {auth.role as RoleCode}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <WecomBell />
          <button
            type="button"
            className="rounded border px-2 py-1 text-[11px] text-[var(--text-muted)] hover:text-[var(--text-body)]"
            style={{ borderColor: "var(--line)" }}
            onClick={() => {
              auth.logout();
              window.location.href = "/login";
            }}
          >
            退出
          </button>
        </div>
      </header>
      <div className="flex min-h-0 flex-1 overflow-hidden">
        <nav
          className={`h-full w-52 shrink-0 overflow-y-auto overscroll-contain border-r p-2 text-sm text-[var(--text-nav)] ${phoneVisit ? "hidden" : ""}`}
          style={{
            borderColor: "var(--line)",
            background: "var(--bg-nav)",
          }}
        >
          {menuError && (
            <p className="mb-2 px-1 text-[10px] leading-snug text-amber-400/90">
              菜单 API 不可用，已用本地兜底。
              <button type="button" className="ml-1 underline" onClick={() => loadMenu()}>
                重试
              </button>
            </p>
          )}
          {grouped?.home && (
            <NavLink to={grouped.home.path} className={navLinkClass} style={navLinkStyle}>
              {grouped.home.label}
            </NavLink>
          )}
          {grouped && grouped.topLevel.length > 0 && (
            <div className="my-2 border-t pt-2" style={{ borderColor: "var(--line)" }}>
              {grouped.topLevel.map((m) => (
                <NavLink key={m.key} to={m.path} className={navLinkClass} style={navLinkStyle}>
                  {m.label}
                </NavLink>
              ))}
            </div>
          )}
          {grouped?.categories.map((cat) => (
            <div key={cat.label} className="mb-3 mt-1">
              <p className="mb-1.5 px-2 text-[15px] font-semibold leading-snug text-[var(--text-body)]">
                {cat.label}
              </p>
              <div
                className="ml-1 space-y-0.5 border-l-2 py-0.5 pl-4"
                style={{ borderColor: "var(--line)" }}
              >
                {cat.items.map((m) => (
                  <NavLink
                    key={m.key}
                    to={m.path}
                    className={({ isActive }) => `${navLinkClass({ isActive })} text-[13px]`}
                    style={navLinkStyle}
                  >
                    {m.label}
                  </NavLink>
                ))}
              </div>
            </div>
          ))}
        </nav>
        <main className="flex h-full min-h-0 min-w-0 flex-1 flex-col overflow-y-auto overscroll-contain">
          {!phoneVisit && <GuidedDemoToolbar />}
          <Outlet />
        </main>
      </div>
    </div>
  );
}
