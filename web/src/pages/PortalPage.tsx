import { Link } from "react-router-dom";
import {
  groupedNavForRole,
  MENU_SHORT_DESC,
  type MenuItem,
} from "../shell/menuConfig";
import { useAuth, type RoleCode } from "../shell/auth";

function NavCard({ item }: { item: MenuItem }) {
  return (
    <Link
      to={item.path}
      className="rounded-lg border p-3 transition hover:border-[var(--accent)]"
      style={{ background: "var(--bg-card)", borderColor: "var(--line)" }}
    >
      <p className="text-sm font-medium">{item.label}</p>
      <p className="mt-1 text-[11px] leading-snug text-[var(--text-muted)]">
        {MENU_SHORT_DESC[item.key] ?? item.module}
      </p>
    </Link>
  );
}

export function PortalPage() {
  const auth = useAuth();
  const role = auth.role as RoleCode | null;
  const grouped = role ? groupedNavForRole(role) : null;

  return (
    <div className="px-6 py-4">
      <h2 className="text-lg font-semibold">欢迎，{auth.userName}</h2>
      <p className="mt-1 text-sm text-[var(--text-muted)]">
        演示门户 · 待办与演示控制台直达 · 业务入口按管理 / 销售 / 人事 / 生产 / 财务分类
      </p>

      {grouped && grouped.topLevel.length > 0 && (
        <section className="mt-6">
          <div className="grid gap-3 sm:grid-cols-2 lg:max-w-2xl">
            {grouped.topLevel.map((item) => (
              <NavCard key={item.key} item={item} />
            ))}
          </div>
        </section>
      )}

      {grouped?.categories.map((cat) => (
        <section key={cat.label} className="mt-8">
          <h3 className="text-sm font-semibold text-[var(--accent)]">{cat.label}</h3>
          <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {cat.items.map((item) => (
              <NavCard key={item.key} item={item} />
            ))}
          </div>
        </section>
      ))}

      {grouped && grouped.categories.length === 0 && grouped.topLevel.length === 0 && (
        <p className="mt-6 text-sm text-[var(--text-muted)]">当前角色暂无业务入口，请从侧栏或联系管理员。</p>
      )}
    </div>
  );
}
