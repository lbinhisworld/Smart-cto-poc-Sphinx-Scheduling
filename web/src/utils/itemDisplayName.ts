/** 演示/种子展示用：去掉历史占位后缀，统一列表可读性 */
export function cleanItemDisplayName(name: string): string {
  return name.replace(/（拟真）|\(拟真\)/g, "").trim() || name;
}
