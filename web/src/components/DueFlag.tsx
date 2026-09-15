/** 交期锚点标记（销售交期，非最后生产日） */
export function DueFlag({ dueDate }: { dueDate: string }) {
  return (
    <span
      className="pointer-events-none absolute right-1 top-1 text-sm leading-none"
      title={`交期 ${dueDate}`}
      aria-label={`交期 ${dueDate}`}
    >
      🚩
    </span>
  );
}
