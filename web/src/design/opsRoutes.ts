/** 排程 POC 同源深色模块（看板 / BOM / 库存），避免半透明叠在门户浅色底上发灰 */
export function isOpsDarkRoute(pathname: string): boolean {
  return (
    pathname.startsWith("/schedule") ||
    pathname.startsWith("/bom") ||
    pathname.startsWith("/stock")
  );
}

/** 排程已嵌入一体化 Shell（保留左侧导航），不再全屏沉浸 */
export function isScheduleImmersive(_pathname: string): boolean {
  return false;
}
