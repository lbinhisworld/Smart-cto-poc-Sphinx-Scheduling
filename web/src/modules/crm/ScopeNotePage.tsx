const COPY: Record<string, { title: string; body: string }> = {
  contacts: {
    title: "联系人",
    body: "本轮不做单独联系人档案。「见了谁」仍在拜访完整度与跟进内容里。",
  },
  returns: {
    title: "销售退货",
    body: "本轮不做退货单。签约产品进度详情里的退货数量为 0。",
  },
  ship: {
    title: "销售出库",
    body: "不在本系统过账。发货数量在销售订单详情「发货记录」里只读金蝶同步；没有记录即为未发货。",
  },
  recon: {
    title: "销售对账",
    body: "本轮不做对账。",
  },
};

export function ScopeNotePage({ kind }: { kind: keyof typeof COPY }) {
  const page = COPY[kind];
  if (!page) return null;
  return (
    <div className="p-4">
      <h1 className="text-lg font-semibold">{page.title}</h1>
      <p className="mt-3 max-w-xl text-sm text-[var(--text-muted)]">{page.body}</p>
    </div>
  );
}
