// 공용 UI 조각 — 로딩/빈/에러 상태 + 배지 + 토스트(a11y aria-live).
import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { CheckCircle2, Inbox, AlertTriangle } from "lucide-react";

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 p-4 text-muted" role="status" aria-live="polite">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-border3 border-t-info" />
      {label && <span>{label}</span>}
    </div>
  );
}

export function EmptyState({ title, hint, action }: { title: string; hint?: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 p-10 text-center text-muted">
      <Inbox className="h-8 w-8 text-dim" />
      <p className="font-medium text-ink">{title}</p>
      {hint && <p className="text-sm">{hint}</p>}
      {action}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div
      className="flex flex-col items-center gap-2 p-6 text-center text-danger"
      role="alert"
      aria-live="assertive"
    >
      <AlertTriangle className="h-8 w-8" />
      <p className="font-medium">로드 실패</p>
      <p className="font-mono text-xs break-all">{message}</p>
      {onRetry && (
        <button onClick={onRetry} className="mt-1 rounded bg-cta px-3 py-1 text-xs text-white">
          재시도
        </button>
      )}
    </div>
  );
}

// 상태별 색 매핑(green/amber/red/blue/indigo — 상태 식별 전용, 본문 아님).
export function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    todo: "bg-surface2 text-muted border-border2",
    progressing: "bg-blue-50 text-info border-blue-200",
    qa: "bg-amber-50 text-warn border-amber-200",
    done: "bg-emerald-50 text-ok border-emerald-200",
    cancel: "bg-rose-50 text-danger border-rose-200",
  };
  const label: Record<string, string> = {
    todo: "todo",
    progressing: "progressing",
    qa: "qa",
    done: "done",
    cancel: "cancel",
  };
  return (
    <span className={`rounded border px-1.5 py-0.5 text-[11px] font-medium ${map[status] ?? ""}`}>
      {label[status] ?? status}
    </span>
  );
}

// 토스트 — idempotent resolve 등. aria-live 로 스크린리더 전달.
export function useToast() {
  const [msg, setMsg] = useState<string | null>(null);
  useEffect(() => {
    if (!msg) return;
    const t = setTimeout(() => setMsg(null), 2200);
    return () => clearTimeout(t);
  }, [msg]);
  return {
    show: (m: string) => setMsg(m),
    node: msg ? (
      <div
        className="fixed bottom-4 right-4 z-50 flex items-center gap-2 rounded-lg bg-cta px-4 py-2 text-sm text-white shadow-lg"
        role="status"
        aria-live="polite"
      >
        <CheckCircle2 className="h-4 w-4" />
        {msg}
      </div>
    ) : null,
  };
}

// 결정 노화 — 1h+ amber, 24h+ red (D-DR5).
export function agingClass(iso: string): { border: string; text: string; label: string } {
  const ms = Date.now() - new Date(iso).getTime();
  const h = ms / 3.6e6;
  if (h >= 24) return { border: "border-danger", text: "text-danger", label: `${Math.floor(h)}h 경과` };
  if (h >= 1) return { border: "border-warn", text: "text-warn", label: `${Math.floor(h)}h 경과` };
  return {
    border: "border-border2",
    text: "text-dim",
    label: `${Math.max(0, Math.floor(ms / 60000))}m 경과`,
  };
}

export interface ToastApi {
  show: (m: string) => void;
  node: ReactNode;
}
