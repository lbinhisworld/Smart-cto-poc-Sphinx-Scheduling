/** 排程 POC 同源深色模块（看板 / BOM / 库存），避免半透明叠在门户浅色底上发灰 */
export function isOpsDarkRoute(pathname: string): boolean {
  return (
    pathname.startsWith("/schedule") ||
    pathname.startsWith("/bom") ||
    pathname.startsWith("/stock")
  );
}

export function isScheduleImmersive(pathname: string): boolean {
  return pathname.startsWith("/schedule");
}
