// TicketDrawer — 우측 드로어. Timeline(커서 페이지네이션) / Comments(agent-read ✓) 탭.
import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, CheckCheck, MessageSquare, X } from "lucide-react";
import { api, type TicketStatus } from "../api";
import { ErrorState, Spinner, StatusBadge, type ToastApi } from "./ui";

// 유효 전이 버튼(상태기계 매칭). cancel/reopen 별도.
const NEXT: Partial<Record<TicketStatus, { to: TicketStatus; label: string }[]>> = {
  todo: [{ to: "progressing", label: "진행 시작" }],
  progressing: [{ to: "qa", label: "QA로" }],
  qa: [
    { to: "done", label: "완료" },
    { to: "progressing", label: "반려/재진행" },
  ],
};

export function TicketDrawer({
  ticketId,
  onClose,
  toast,
}: {
  ticketId: number;
  onClose: () => void;
  toast: ToastApi;
}) {
  const qc = useQueryClient();
  const [tab, setTab] = useState<"timeline" | "comments">("timeline");

  const { data: ticket, isLoading, error, refetch } = useQuery({
    queryKey: ["ticket", ticketId],
    queryFn: () => api.tickets.get(ticketId),
  });

  const invalidateAll = () => {
    qc.invalidateQueries({ queryKey: ["ticket", ticketId] });
    qc.invalidateQueries({ queryKey: ["tickets"] });
  };

  const transition = useMutation({
    mutationFn: (vars: { to: TicketStatus; cancel?: boolean; reopen?: boolean }) =>
      vars.cancel
        ? api.tickets.cancel(ticketId)
        : vars.reopen
          ? api.tickets.reopen(ticketId)
          : api.tickets.transition(ticketId, vars.to),
    onSuccess: (_d, vars) => {
      invalidateAll();
      toast.show(vars.cancel ? "취소됨" : vars.reopen ? "재개됨" : "상태 변경됨");
    },
  });

  // 내용(description)은 항상 보이고 인라인 수정 저장(PATCH). 빈 티켓도 편집칸 표시.
  const [desc, setDesc] = useState(ticket?.description ?? "");
  const [focused, setFocused] = useState(false);
  useEffect(() => setDesc(ticket?.description ?? ""), [ticket?.description]);
  const saveDesc = useMutation({
    mutationFn: () => api.tickets.update(ticketId, { description: desc }),
    onSuccess: () => {
      invalidateAll();
      toast.show("내용 저장됨");
    },
  });

  return (
    <div className="fixed inset-y-0 right-0 z-30 flex w-[420px] flex-col border-l border-border2 bg-surface shadow-xl">
      <header className="flex items-center gap-2 border-b border-border2 px-4 py-3">
        {ticket && <StatusBadge status={ticket.status} />}
        <span className="font-mono text-xs text-dim">#{ticketId}</span>
        <button className="ml-auto text-dim hover:text-ink" onClick={onClose} aria-label="닫기">
          <X className="h-4 w-4" />
        </button>
      </header>

      {isLoading && <Spinner label="티켓 로드 중" />}
      {error && <ErrorState message={String((error as Error).message)} onRetry={() => refetch()} />}
      {ticket && (
        <div className="flex-1 overflow-y-auto">
          <div className="border-b border-border2 px-4 py-3">
            <h2 className="text-base font-semibold">{ticket.title}</h2>
            <div className="mt-3">
              <div
                className={`overflow-hidden rounded-lg border bg-surface2 transition-colors ${
                  focused ? "border-info ring-2 ring-info/15" : "border-border2"
                }`}
              >
                <div className="flex items-center justify-between border-b border-border2 bg-surface/60 px-3 py-1.5">
                  <span className="text-[11px] font-semibold uppercase tracking-wider text-dim">
                    내용
                  </span>
                  <span className="font-mono text-[10px] text-dim">
                    {desc.length}자
                    {desc !== (ticket.description ?? "") ? " · 수정됨" : ""}
                  </span>
                </div>
                <textarea
                  id="d-desc"
                  className="block min-h-[140px] w-full resize-y bg-transparent px-3 py-2.5 text-sm leading-relaxed text-ink placeholder:text-dim/50 focus:outline-none"
                  rows={7}
                  value={desc}
                  onChange={(e) => setDesc(e.target.value)}
                  onFocus={() => setFocused(true)}
                  onBlur={() => setFocused(false)}
                  placeholder="이 티켓의 내용, 맥락, 완료 조건 등을 적어주세요…"
                />
                <div className="flex items-center justify-between gap-2 border-t border-border2 bg-surface/60 px-2.5 py-1.5">
                  <span className="text-[10px] text-dim">
                    {focused ? "자동 저장 안 됨 — 저장 버튼을 누르세요" : ""}
                  </span>
                  <button
                    type="button"
                    onClick={() => saveDesc.mutate()}
                    disabled={saveDesc.isPending || desc === (ticket.description ?? "")}
                    className="rounded-md bg-cta px-3 py-1 text-xs font-medium text-white transition hover:bg-ink disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    {saveDesc.isPending ? "저장 중…" : "저장"}
                  </button>
                </div>
              </div>
            </div>
            <div className="mt-3 flex flex-wrap gap-1.5">
              {(NEXT[ticket.status] ?? []).map((n) => (
                <button
                  key={n.to}
                  onClick={() => transition.mutate({ to: n.to })}
                  disabled={transition.isPending}
                  className="rounded bg-cta px-2.5 py-1 text-xs font-medium text-white disabled:opacity-50"
                >
                  {n.label}
                </button>
              ))}
              {ticket.status !== "cancel" && ticket.status !== "done" && (
                <button
                  onClick={() => transition.mutate({ to: "cancel", cancel: true })}
                  disabled={transition.isPending}
                  className="rounded border border-danger px-2.5 py-1 text-xs text-danger disabled:opacity-50"
                >
                  취소
                </button>
              )}
              {(ticket.status === "done" || ticket.status === "cancel") && (
                <button
                  onClick={() => transition.mutate({ to: "todo", reopen: true })}
                  disabled={transition.isPending}
                  className="rounded border border-border3 px-2.5 py-1 text-xs text-muted disabled:opacity-50"
                >
                  재개(reopen)
                </button>
              )}
            </div>
          </div>

          <div className="flex border-b border-border2 px-4 text-sm">
            <TabBtn active={tab === "timeline"} onClick={() => setTab("timeline")}>
              Timeline
            </TabBtn>
            <TabBtn active={tab === "comments"} onClick={() => setTab("comments")}>
              <MessageSquare className="mr-1 inline h-3.5 w-3.5" />
              Comments
            </TabBtn>
          </div>

          {tab === "timeline" ? <Timeline ticketId={ticketId} /> : <Comments ticketId={ticketId} toast={toast} />}
        </div>
      )}
    </div>
  );
}

function TabBtn({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`-mb-px border-b-2 px-3 py-2 ${
        active ? "border-cta font-medium text-ink" : "border-transparent text-dim hover:text-muted"
      }`}
    >
      {children}
    </button>
  );
}

function Timeline({ ticketId }: { ticketId: number }) {
  const [cursor, setCursor] = useState<number | undefined>();
  const { data, isLoading, error } = useQuery({
    queryKey: ["events", ticketId, cursor],
    queryFn: () => api.tickets.events(ticketId, cursor),
  });

  if (isLoading) return <Spinner label="이벤트 로드 중" />;
  if (error) return <ErrorState message={String((error as Error).message)} />;
  if (!data || data.items.length === 0)
    return <p className="px-4 py-6 text-sm text-dim">이벤트 없음</p>;

  return (
    <div className="px-4 py-3">
      <ul className="space-y-1.5 font-mono text-xs">
        {data.items.map((ev) => (
          <li key={ev.id} className="border-l-2 border-border2 pl-2">
            <span className="text-dim">{new Date(ev.created_at).toLocaleString()}</span>{" "}
            <span className="font-medium text-info">{ev.kind}</span>
            <pre className="mt-0.5 whitespace-pre-wrap break-all text-muted">
              {typeof ev.payload === "string" ? ev.payload : JSON.stringify(ev.payload)}
            </pre>
          </li>
        ))}
      </ul>
      {data.next_cursor && (
        <button
          className="mt-3 text-xs text-info"
          onClick={() => setCursor(data.next_cursor!)}
        >
          더보기 ▾
        </button>
      )}
    </div>
  );
}

function Comments({ ticketId, toast }: { ticketId: number; toast: ToastApi }) {
  const qc = useQueryClient();
  const [author, setAuthor] = useState("me");
  const [body, setBody] = useState("");

  const { data: comments, isLoading, error } = useQuery({
    queryKey: ["comments", ticketId],
    queryFn: () => api.comments.list(ticketId),
  });

  // ponytail: 진입 시 미읽음 코멘트를 agent 관점에서 읽음 처리(데모). 실제 agent-read 는 에이전트 poll.
  const markAllRead = useMutation({
    mutationFn: async (ids: number[]) =>
      Promise.all(ids.map((cid) => api.comments.markRead(ticketId, cid))),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["comments", ticketId] }),
  });

  useEffect(() => {
    if (comments) {
      const unread = comments.filter((c) => !c.read_at).map((c) => c.id);
      if (unread.length) markAllRead.mutate(unread);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [comments?.length]);

  const create = useMutation({
    mutationFn: () => api.comments.create(ticketId, author.trim() || "me", body.trim()),
    onSuccess: () => {
      setBody("");
      qc.invalidateQueries({ queryKey: ["comments", ticketId] });
      toast.show("코멘트 작성됨");
    },
  });

  if (isLoading) return <Spinner label="코멘트 로드 중" />;
  if (error) return <ErrorState message={String((error as Error).message)} />;

  return (
    <div className="flex flex-col px-4 py-3">
      {comments && comments.length === 0 && (
        <p className="py-4 text-sm text-dim">첫 코멘트를 남겨주세요</p>
      )}
      <ul className="space-y-2">
        {comments?.map((c) => (
          <li key={c.id} className="rounded-md bg-surface2 p-2">
            <div className="flex items-center gap-1.5">
              <span className="text-xs font-medium">{c.author}</span>
              {c.read_at && (
                <span className="inline-flex items-center text-ok" title={`읽음 ${c.read_at}`}>
                  <CheckCheck className="h-3.5 w-3.5" />
                </span>
              )}
              <span className="ml-auto font-mono text-[11px] text-dim">
                {new Date(c.created_at).toLocaleString()}
              </span>
            </div>
            <p className="mt-1 whitespace-pre-wrap text-sm">{c.body}</p>
          </li>
        ))}
      </ul>

      <form
        className="mt-3 space-y-1.5"
        onSubmit={(e) => {
          e.preventDefault();
          if (body.trim()) create.mutate();
        }}
      >
        <input
          className="w-full rounded border border-border3 bg-surface px-2 py-1 text-xs"
          value={author}
          onChange={(e) => setAuthor(e.target.value)}
          placeholder="작성자"
        />
        <textarea
          className="w-full rounded border border-border3 bg-surface px-2 py-1 text-sm"
          rows={2}
          value={body}
          onChange={(e) => setBody(e.target.value)}
          placeholder="코멘트"
        />
        <button
          type="submit"
          className="flex items-center gap-1 rounded bg-cta px-2.5 py-1 text-xs text-white disabled:opacity-50"
          disabled={!body.trim() || create.isPending}
        >
          <Check className="h-3.5 w-3.5" />
          작성
        </button>
      </form>
    </div>
  );
}
