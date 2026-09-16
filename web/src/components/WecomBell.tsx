import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../shell/auth";

type Msg = { id: number; title: string; body: string; deep_link: string; is_read: boolean };

export function WecomBell() {
  const auth = useAuth();
  const [open, setOpen] = useState(false);
  const [msgs, setMsgs] = useState<Msg[]>([]);

  useEffect(() => {
    fetch("/api/wecom/messages", { headers: auth.headers() })
      .then((r) => r.json())
      .then((j) => setMsgs(j.data ?? []));
  }, [auth.role, auth.headers]);

  const unread = msgs.filter((m) => !m.is_read).length;

  return (
    <div className="relative">
      <button
        type="button"
        className="rounded border px-2 py-1 text-[11px]"
        style={{ borderColor: "var(--line)" }}
        onClick={() => setOpen((o) => !o)}
      >
        企微模拟 {unread > 0 ? `(${unread})` : ""}
      </button>
      {open && (
        <div
          className="absolute right-0 top-9 z-50 w-72 rounded border p-2 text-xs shadow-lg"
          style={{ borderColor: "var(--line)", background: "var(--bg-card)" }}
        >
          {msgs.length === 0 && <p className="text-[var(--text-muted)]">暂无消息</p>}
          {msgs.slice(0, 8).map((m) => (
            <Link
              key={m.id}
              to={m.deep_link}
              className="mb-2 block rounded border p-2 hover:opacity-90"
              style={{ borderColor: "var(--line)" }}
              onClick={() => setOpen(false)}
            >
              <p className="font-medium">{m.title}</p>
              <p className="text-[var(--text-muted)]">{m.body}</p>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
