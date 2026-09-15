import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth, type RoleCode } from "./auth";

type RoleCard = {
  code: RoleCode;
  label: string;
  name: string;
  home_path: string;
};

export function LoginPage() {
  const navigate = useNavigate();
  const { setSession, isAuthenticated } = useAuth();
  const [roles, setRoles] = useState<RoleCard[]>([]);

  useEffect(() => {
    if (isAuthenticated) {
      navigate("/portal", { replace: true });
      return;
    }
    fetch("/api/portal/roles")
      .then((r) => r.json())
      .then((j) => setRoles(j.data ?? []))
      .catch(() => setRoles([]));
  }, [isAuthenticated, navigate]);

  const enter = (card: RoleCard) => {
    setSession(card.code, card.name);
    navigate(card.home_path || "/portal");
  };

  return (
    <div
      className="min-h-screen px-6 py-10"
      style={{ background: "var(--bg-body)", color: "var(--text-body)" }}
    >
      <div className="mx-auto max-w-4xl">
        <h1 className="text-2xl font-semibold">斯芬克斯 · 一体化演示</h1>
        <p className="mt-1 text-sm" style={{ color: "var(--text-muted)" }}>
          选择角色进入（演示用，无需密码）
        </p>
        <div className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {roles.map((r) => (
            <button
              key={r.code}
              type="button"
              onClick={() => enter(r)}
              className="rounded-lg border px-4 py-4 text-left transition hover:shadow-sm"
              style={{
                borderColor: "var(--line)",
                background: "var(--bg-card)",
              }}
            >
              <p className="text-xs font-medium uppercase tracking-wide text-[var(--accent)]">
                {r.code}
              </p>
              <p className="mt-1 text-base font-semibold">{r.label}</p>
              <p className="text-sm text-[var(--text-muted)]">{r.name}</p>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
