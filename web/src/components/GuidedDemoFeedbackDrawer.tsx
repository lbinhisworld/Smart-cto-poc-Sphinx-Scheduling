import { useCallback, useEffect, useRef, useState, type MouseEvent } from "react";

export type FeedbackItem = {
  id: number;
  step_id: string;
  category: string;
  severity: string;
  body: string;
  expectation: string;
  reporter_role: string;
  created_at: string | null;
};

const CATEGORIES = [
  "流程不顺",
  "字段不对",
  "权限",
  "口径疑问",
  "新能力",
  "其他",
] as const;

const SEVERITIES = ["演示阻断", "可绕过", "会后优化"] as const;

type SpeechRecognitionLike = {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  onstart: (() => void) | null;
  onresult: ((ev: unknown) => void) | null;
  onerror: ((ev: { error: string }) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
  abort: () => void;
};

const SPEECH_ERROR_ZH: Record<string, string> = {
  "not-allowed": "麦克风被拒绝：请点击地址栏左侧锁图标，允许麦克风后刷新页面",
  network: "语音识别需要联网（Chrome/Edge 会使用在线识别服务）",
  "service-not-allowed": "当前页面不允许语音服务，请用 http://127.0.0.1:5180 在 Chrome 或 Edge 打开",
  "audio-capture": "未检测到麦克风设备",
  aborted: "已取消",
  "no-speech": "没有听到声音，请靠近麦克风再试",
};

function getSpeechRecognition(): (new () => SpeechRecognitionLike) | null {
  const w = window as unknown as {
    SpeechRecognition?: new () => SpeechRecognitionLike;
    webkitSpeechRecognition?: new () => SpeechRecognitionLike;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

function formatTime(iso: string | null) {
  if (!iso) return "—";
  return iso.replace("T", " ").slice(0, 19);
}

type Props = {
  open: boolean;
  onClose: () => void;
  stepTitle: string;
  stepSeq: number;
  timeline: FeedbackItem[];
  busy: boolean;
  category: string;
  severity: string;
  body: string;
  expectation: string;
  onCategory: (v: string) => void;
  onSeverity: (v: string) => void;
  onBody: (v: string) => void;
  onAppendToBody: (chunk: string) => void;
  onExpectation: (v: string) => void;
  onSubmit: () => void;
  msg: string | null;
};

export function GuidedDemoFeedbackDrawer({
  open,
  onClose,
  stepTitle,
  stepSeq,
  timeline,
  busy,
  category,
  severity,
  body,
  expectation,
  onCategory,
  onSeverity,
  onBody,
  onAppendToBody,
  onExpectation,
  onSubmit,
  msg,
}: Props) {
  const [listening, setListening] = useState(false);
  const [voiceHint, setVoiceHint] = useState<string | null>(null);
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const userFinishRef = useRef(false);
  const bodyRef = useRef<HTMLTextAreaElement>(null);

  const stopListening = useCallback((byUser = false) => {
    if (byUser) userFinishRef.current = true;
    try {
      recognitionRef.current?.stop();
    } catch {
      recognitionRef.current?.abort?.();
    }
    recognitionRef.current = null;
    setListening(false);
  }, []);

  useEffect(() => {
    if (!open) stopListening();
  }, [open, stopListening]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && open) onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const finishSpeaking = (e: MouseEvent<HTMLButtonElement>) => {
    e.preventDefault();
    e.stopPropagation();
    if (!listening) return;
    setVoiceHint("正在结束并解析…");
    stopListening(true);
  };

  const startVoice = (e: MouseEvent<HTMLButtonElement>) => {
    e.preventDefault();
    e.stopPropagation();
    if (listening) return;
    const Ctor = getSpeechRecognition();
    if (!Ctor) {
      setVoiceHint("当前浏览器不支持 Web 语音识别。请用 Chrome 或 Edge 打开 http://127.0.0.1:5180，或改用手动输入");
      return;
    }
    userFinishRef.current = false;
    setVoiceHint("正在请求麦克风…");
    const rec = new Ctor();
    rec.lang = "zh-CN";
    rec.continuous = true;
    rec.interimResults = true;
    rec.onstart = () => {
      setListening(true);
      setVoiceHint("请开始说话，说完后点下方「说完了」（不要只点「语音」结束）");
    };
    rec.onresult = (ev: unknown) => {
      const event = ev as {
        resultIndex: number;
        results: { length: number; [i: number]: { isFinal: boolean; 0: { transcript: string } } };
      };
      let interim = "";
      let finalText = "";
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const row = event.results[i];
        const piece = row?.[0]?.transcript ?? "";
        if (row?.isFinal) finalText += piece;
        else interim += piece;
      }
      if (interim.trim()) setVoiceHint(`识别中：${interim.trim()}`);
      if (finalText.trim()) {
        onAppendToBody(finalText.trim());
        setVoiceHint("已写入，可继续点「语音」说下一段");
      }
    };
    rec.onerror = (ev) => {
      if (ev.error === "no-speech" && userFinishRef.current) {
        setVoiceHint(
          "未识别到文字。请在 Chrome 地址栏 → 网站设置 → 麦克风，选您的耳机；或改用键盘输入",
        );
        stopListening();
        return;
      }
      if (ev.error === "no-speech") {
        setVoiceHint(
          "未听到声音（常见原因：浏览器用了错误麦克风）。请点「开始录音」→ 说话 → 点「说完了」",
        );
        stopListening();
        return;
      }
      const msg = SPEECH_ERROR_ZH[ev.error] ?? `语音识别错误：${ev.error}`;
      setVoiceHint(msg);
      stopListening();
    };
    rec.onend = () => {
      setListening(false);
      recognitionRef.current = null;
      if (userFinishRef.current && !body.trim()) {
        setVoiceHint((h) =>
          h?.includes("未识别") ? h : "已结束。若文本框仍为空，请检查麦克风设备或改用手输",
        );
      }
    };
    recognitionRef.current = rec;
    try {
      rec.start();
      bodyRef.current?.focus();
    } catch (err) {
      setVoiceHint(`无法启动：${String(err)}。若已在录音，请先点「说完了」`);
      stopListening();
    }
  };

  const speechAvailable = typeof window !== "undefined" && getSpeechRecognition() !== null;

  return (
    <>
      <div
        className={`fixed inset-0 z-[60] bg-black/40 transition-opacity duration-300 ${
          open ? "opacity-100" : "pointer-events-none opacity-0"
        }`}
        aria-hidden={!open}
        onClick={onClose}
      />
      <aside
        role="dialog"
        aria-labelledby="guided-feedback-title"
        aria-modal="true"
        className={`fixed right-0 top-0 z-[61] flex h-full w-full max-w-[22rem] flex-col border-l shadow-2xl transition-transform duration-300 ease-out sm:max-w-md ${
          open ? "translate-x-0" : "translate-x-full"
        }`}
        style={{
          borderColor: "var(--line)",
          background: "var(--bg-card)",
          color: "var(--text-body)",
        }}
      >
        <header
          className="flex shrink-0 items-start justify-between gap-2 border-b px-4 py-3"
          style={{ borderColor: "var(--line)" }}
        >
          <div>
            <p className="text-[10px] uppercase tracking-wide text-[var(--text-muted)]">演示反馈</p>
            <h2 id="guided-feedback-title" className="text-sm font-semibold">
              第 {stepSeq} 步 · {stepTitle}
            </h2>
            <p className="mt-0.5 text-[11px] text-[var(--text-muted)]">本环节历次反馈（时间线）</p>
          </div>
          <button
            type="button"
            className="rounded border px-2 py-1 text-[11px]"
            style={{ borderColor: "var(--line)" }}
            onClick={onClose}
          >
            关闭
          </button>
        </header>

        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-3">
          {timeline.length === 0 ? (
            <p className="text-[12px] text-[var(--text-muted)]">还没有反馈，可在下方快速追加。</p>
          ) : (
            <ol className="relative border-l-2 pl-4" style={{ borderColor: "var(--line)" }}>
              {timeline.map((t, i) => (
                <li key={t.id} className="relative pb-6 last:pb-0">
                  <span
                    className="absolute -left-[1.35rem] top-1 h-2.5 w-2.5 rounded-full bg-[var(--accent)]"
                    aria-hidden
                  />
                  <time className="text-[10px] text-[var(--text-muted)]">{formatTime(t.created_at)}</time>
                  <p className="mt-0.5 text-[10px] text-[var(--text-muted)]">
                    {t.category} · {t.severity} · {t.reporter_role}
                  </p>
                  <p className="mt-1 text-[13px] leading-snug">{t.body}</p>
                  {t.expectation ? (
                    <p className="mt-1 text-[11px] text-[var(--text-muted)]">期望：{t.expectation}</p>
                  ) : null}
                  {i < timeline.length - 1 ? null : (
                    <span className="mt-2 inline-block text-[9px] text-[var(--text-muted)]">最新</span>
                  )}
                </li>
              ))}
            </ol>
          )}
        </div>

        <footer
          className="shrink-0 border-t px-4 py-3"
          style={{ borderColor: "var(--line)", background: "var(--bg-body)" }}
        >
          <p className="mb-2 text-[11px] font-medium">快速追加</p>
          <div className="flex flex-col gap-2">
            <div className="flex flex-wrap gap-2">
              <label className="flex flex-1 flex-col gap-0.5 text-[10px]">
                类型
                <select
                  className="rounded border px-2 py-1.5 text-xs"
                  style={{ borderColor: "var(--line)" }}
                  value={category}
                  onChange={(e) => onCategory(e.target.value)}
                >
                  {CATEGORIES.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </label>
              <label className="flex flex-1 flex-col gap-0.5 text-[10px]">
                严重度
                <select
                  className="rounded border px-2 py-1.5 text-xs"
                  style={{ borderColor: "var(--line)" }}
                  value={severity}
                  onChange={(e) => onSeverity(e.target.value)}
                >
                  {SEVERITIES.map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <div className="relative">
              <textarea
                ref={bodyRef}
                className="w-full rounded border px-2 py-2 pr-10 text-xs leading-relaxed"
                style={{ borderColor: "var(--line)" }}
                rows={4}
                placeholder="客户原话或现象（必填）"
                value={body}
                onChange={(e) => onBody(e.target.value)}
              />
              {!listening && (
                <button
                  type="button"
                  disabled={!speechAvailable}
                  title={
                    speechAvailable
                      ? "开始录音（Chrome/Edge）"
                      : "浏览器不支持语音识别，请改用手动输入"
                  }
                  className="absolute bottom-2 right-2 z-10 rounded-full border bg-black/30 px-2 py-1 text-[10px] hover:bg-black/50 disabled:opacity-40"
                  style={{ borderColor: "var(--line)" }}
                  onMouseDown={(ev) => ev.stopPropagation()}
                  onClick={startVoice}
                >
                  开始录音
                </button>
              )}
            </div>
            {listening && (
              <button
                type="button"
                className="w-full rounded py-2 text-xs font-medium text-white"
                style={{ background: "var(--accent)" }}
                onClick={finishSpeaking}
              >
                说完了
              </button>
            )}
            <p className="text-[10px] text-[var(--text-muted)]">
              三步：开始录音 → 对着耳机麦克风说 → 说完了。Chrome 网站设置里请选对外接麦克风。
            </p>
            {voiceHint && <p className="text-[10px] text-amber-400">{voiceHint}</p>}
            <textarea
              className="w-full rounded border px-2 py-1.5 text-xs"
              style={{ borderColor: "var(--line)" }}
              rows={2}
              placeholder="期望（可选）"
              value={expectation}
              onChange={(e) => onExpectation(e.target.value)}
            />
            {msg && <p className="text-[11px] text-[var(--text-muted)]">{msg}</p>}
            <button
              type="button"
              className="w-full rounded py-2 text-xs font-medium text-white"
              style={{ background: "var(--accent)" }}
              disabled={busy}
              onClick={onSubmit}
            >
              追加保存
            </button>
          </div>
        </footer>
      </aside>
    </>
  );
}
