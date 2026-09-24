/** fetch 的 Header 值须为 ISO-8859-1；中文演示名用 b64: 前缀 UTF-8 编码。 */

export function encodeDemoUserHeader(userName: string): string | undefined {
  const t = userName.trim();
  if (!t) return undefined;
  if (/^[\u0020-\u007e]*$/.test(t)) return t;
  const bytes = new TextEncoder().encode(t);
  let binary = "";
  for (const b of bytes) binary += String.fromCharCode(b);
  return `b64:${btoa(binary)}`;
}

export function buildDemoAuthHeaders(role: string, userName?: string): HeadersInit {
  const h: Record<string, string> = { "X-Demo-Role": role };
  const encoded = userName ? encodeDemoUserHeader(userName) : undefined;
  if (encoded) h["X-Demo-User"] = encoded;
  return h;
}
