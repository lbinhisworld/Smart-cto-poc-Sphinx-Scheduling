import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { isScheduleImmersive } from "../design/opsRoutes";
import { useAuth, type RoleCode } from "./auth";

type MenuItem = { key: string; label: string; path: string; module: string };

export function ShellLayout() {
  const auth = useAuth();
  const location = useLocation();
  const [menu, setMenu] = useState<MenuItem[]>([]);

  useEffect(() => {
    fetch("/api/portal/menu", { headers: auth.headers() })
      .then((r) => r.json())
      .then((j) => setMenu(j.data?.items ?? []))
      .catch(() => setMenu([]));
  }, [auth.role, auth.headers]);

  const isSchedule = isScheduleImmersive(location.pathname);

  return (
    <div
      className="flex min-h-screen flex-col"
      style={{ background: "var(--bg-body)", color: "var(--text-body)" }}
    >
      {!isSchedule && (
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
        </header>
      )}
      <div className="flex min-h-0 flex-1">
        {!isSchedule && (
          <nav
            className="w-48 shrink-0 border-r p-2 text-sm"
            style={{
              borderColor: "var(--line)",
              background: "var(--bg-nav)",
              color: "var(--text-nav)",
            }}
          >
            {menu.map((m) => (
              <NavLink
                key={m.key}
                to={m.path}
                className={({ isActive }) =>
                  `mb-1 block rounded px-2 py-2 ${
                    isActive ? "font-medium" : "opacity-80 hover:opacity-100"
                  }`
                }
                style={({ isActive }) =>
                  isActive
                    ? {
                        background: "var(--nav-active-bg)",
                        color: "var(--accent)",
                      }
                    : undefined
                }
              >
                {m.label}
              </NavLink>
            ))}
          </nav>
        )}
        <main className="min-w-0 flex-1 overflow-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
