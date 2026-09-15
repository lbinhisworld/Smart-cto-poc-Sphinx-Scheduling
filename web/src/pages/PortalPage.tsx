import { Link } from "react-router-dom";
import { useAuth } from "../shell/auth";

export function PortalPage() {
  const auth = useAuth();

  const cards = [
    { title: "销售订单", desc: "多视图列表 · 字段权限演示", to: "/orders" },
    { title: "生产排程", desc: "倒排看板 · 试排 · 插单", to: "/schedule" },
    { title: "库存中心", desc: "齐套与库存模拟", to: "/stock" },
  ];

  return (
    <div className="px-6 py-4">
      <h2 className="text-lg font-semibold">欢迎，{auth.userName}</h2>
      <p className="mt-1 text-sm text-[var(--text-muted)]">
        演示门户 · 按角色展示常用入口（Phase 0–3）
      </p>
      <div className="mt-6 grid gap-3 md:grid-cols-3">
        {cards.map((c) => (
          <Link
            key={c.to}
            to={c.to}
            className="rounded-lg border p-4 hover:border-[var(--accent)]"
            style={{ background: "var(--bg-card)", borderColor: "var(--line)" }}
          >
            <p className="font-medium">{c.title}</p>
            <p className="mt-1 text-xs text-[var(--text-muted)]">{c.desc}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
