import type { ReactNode } from "react";

export type StatCard = { label: string; value: string | number; hint?: string };

export type ColumnDef<T> = {
  key: string;
  label: string;
  width?: number;
  align?: "left" | "right" | "center";
  render: (row: T) => ReactNode;
};

export type ViewTab = { id: string; label: string; count?: number };

type Props<T> = {
  title: string;
  views: ViewTab[];
  activeView: string;
  onViewChange: (id: string) => void;
  stats: StatCard[];
  search: string;
  onSearchChange: (v: string) => void;
  columns: ColumnDef<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  toolbar?: ReactNode;
};

export function ObjectTable<T>({
  title,
  views,
  activeView,
  onViewChange,
  stats,
  search,
  onSearchChange,
  columns,
  rows,
  rowKey,
  toolbar,
}: Props<T>) {
  return (
    <div className="px-6 py-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-[18px] font-semibold">{title}</h2>
        <div className="flex gap-2">{toolbar}</div>
      </div>

      <div
        className="mt-3 flex flex-wrap gap-4 border-b text-[13px]"
        style={{ borderColor: "var(--line)" }}
      >
        {views.map((v) => {
          const active = v.id === activeView;
          return (
            <button
              key={v.id}
              type="button"
              onClick={() => onViewChange(v.id)}
              className={`relative pb-2 ${active ? "font-medium" : "text-[var(--text-muted)]"}`}
            >
              {v.label}
              {v.count != null && (
                <span className="ml-1 text-xs text-[var(--text-muted)]">
                  ({v.count})
                </span>
              )}
              {active && (
                <span
                  className="absolute bottom-0 left-0 h-0.5 w-full"
                  style={{ background: "var(--accent)" }}
                />
              )}
            </button>
          );
        })}
      </div>

      <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((s) => (
          <div
            key={s.label}
            className="rounded-md border px-4 py-3"
            style={{ borderColor: "var(--line)", background: "var(--bg-card)" }}
          >
            <p className="text-xs text-[var(--text-muted)]">{s.label}</p>
            <p className="mt-1 text-xl font-semibold tabular-nums">{s.value}</p>
            {s.hint && (
              <p className="mt-0.5 text-[10px] text-[var(--text-muted)]">{s.hint}</p>
            )}
          </div>
        ))}
      </div>

      <div
        className="mt-3 flex h-11 items-center justify-between gap-2 border-b text-[13px]"
        style={{ borderColor: "var(--line)" }}
      >
        <span className="text-[var(--text-muted)]">筛选</span>
        <input
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder="客户名 / 订单号 / 品名"
          className="h-8 w-60 rounded border px-2 text-sm text-[var(--text-body)]"
          style={{
            borderColor: "var(--line)",
            background: "var(--bg-body)",
          }}
        />
      </div>

      <div
        className="mt-0 overflow-x-auto rounded-md border"
        style={{ borderColor: "var(--line)", background: "var(--bg-card)" }}
      >
        <table className="w-full min-w-[720px] border-collapse text-[13px]">
          <thead style={{ background: "var(--table-head)" }}>
            <tr>
              {columns.map((c) => (
                <th
                  key={c.key}
                  className="border-b px-3 py-2 text-left text-xs font-medium text-[var(--text-muted)]"
                  style={{
                    borderColor: "var(--line)",
                    width: c.width,
                    textAlign: c.align ?? "left",
                  }}
                >
                  {c.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td
                  colSpan={columns.length}
                  className="px-3 py-8 text-center text-[var(--text-muted)]"
                >
                  暂无数据
                </td>
              </tr>
            ) : (
              rows.map((row, i) => (
                <tr
                  key={rowKey(row)}
                  style={{
                    background: i % 2 === 1 ? "var(--table-stripe)" : undefined,
                  }}
                  className="border-b hover:bg-[var(--table-hover)]"
                >
                  {columns.map((c) => (
                    <td
                      key={c.key}
                      className="px-3 py-2"
                      style={{ textAlign: c.align ?? "left" }}
                    >
                      {c.render(row)}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-right text-xs text-[var(--text-muted)]">
        共 {rows.length} 条
      </p>
    </div>
  );
}
