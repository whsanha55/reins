// TicketDrawer — 우측 드로어. Comments(기본·agent-read ✓) / Timeline(커서 페이지네이션) 탭.
// 상태 전이는 보드 드래그앤드롭으로 — 드로어엔 전이 버튼 없음.
import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, CheckCheck, Maximize2, MessageSquare, Minimize2, Pencil, X } from "lucide-react";
import { api } from "../api";
import { ErrorState, Spinner, StatusBadge, isCmdEnter, type ToastApi } from "./ui";
import { Markdown } from "./Markdown";

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
  const [tab, setTab] = useState<"timeline" | "comments">("comments");
  const [wide, setWide] = useState(false);

  const { data: ticket, isLoading, error, refetch } = useQuery({
    queryKey: ["ticket", ticketId],
    queryFn: () => api.tickets.get(ticketId),
  });

  const invalidateAll = () => {
    qc.invalidateQueries({ queryKey: ["ticket", ticketId] });
    qc.invalidateQueries({ queryKey: ["tickets"] });
  };

  // 내용(description) — 기본은 마크다운 렌더, "수정"으로 인라인 편집(PATCH). 빈 티켓은 바로 편집칸.
  const [desc, setDesc] = useState(ticket?.description ?? "");
  const [editing, setEditing] = useState(false);
  const [focused, setFocused] = useState(false);
  useEffect(() => setDesc(ticket?.description ?? ""), [ticket?.description]);
  const saveDesc = useMutation({
    mutationFn: () => api.tickets.update(ticketId, { description: desc }),
    onSuccess: () => {
      invalidateAll();
      setEditing(false);
      toast.show("내용 저장됨");
    },
  });

  return (
    <div
      className={`fixed inset-y-0 right-0 z-30 flex flex-col border-l border-border2 bg-surface shadow-xl transition-[width] ${
        wide ? "w-[min(960px,92vw)]" : "w-[420px]"
      }`}
    >
      <header className="flex items-center gap-2 border-b border-border2 px-4 py-3">
        {ticket && <StatusBadge status={ticket.status} />}
        <span className="font-mono text-xs text-dim">#{ticketId}</span>
        <button
          className="ml-auto text-dim hover:text-ink"
          onClick={() => setWide((w) => !w)}
          aria-label={wide ? "좁게 보기" : "넓게 보기"}
          title={wide ? "좁게" : "넓게"}
        >
          {wide ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
        </button>
        <button className="text-dim hover:text-ink" onClick={onClose} aria-label="닫기">
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
              {!editing && (ticket.description ?? "").trim() ? (
                <div className="rounded-lg border border-border2 bg-surface2 px-3 py-2.5">
                  <div className="mb-1.5 flex items-center justify-between">
                    <span className="text-[11px] font-semibold uppercase tracking-wider text-dim">내용</span>
                    <button
                      type="button"
                      onClick={() => setEditing(true)}
                      className="flex items-center gap-1 text-[11px] text-dim hover:text-ink"
                    >
                      <Pencil className="h-3 w-3" /> 수정
                    </button>
                  </div>
                  <Markdown>{ticket.description ?? ""}</Markdown>
                </div>
              ) : (
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
                    onKeyDown={(e) => {
                      if (isCmdEnter(e) && desc !== (ticket.description ?? "")) {
                        e.preventDefault();
                        saveDesc.mutate();
                      }
                    }}
                    placeholder="이 티켓의 내용, 맥락, 완료 조건 등을 적어주세요… (마크다운 지원, ⌘/Ctrl+Enter 저장)"
                  />
                  <div className="flex items-center justify-between gap-2 border-t border-border2 bg-surface/60 px-2.5 py-1.5">
                    <span className="text-[10px] text-dim">
                      {focused ? "⌘/Ctrl+Enter 로 저장" : ""}
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
              )}
            </div>
          </div>

          <div className="flex border-b border-border2 px-4 text-sm">
            <TabBtn active={tab === "comments"} onClick={() => setTab("comments")}>
              <MessageSquare className="mr-1 inline h-3.5 w-3.5" />
              Comments
            </TabBtn>
            <TabBtn active={tab === "timeline"} onClick={() => setTab("timeline")}>
              Timeline
            </TabBtn>
          </div>

          {tab === "comments" ? <Comments ticketId={ticketId} toast={toast} /> : <Timeline ticketId={ticketId} />}
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
            <div className="mt-1">
              <Markdown>{c.body}</Markdown>
            </div>
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
          onKeyDown={(e) => {
            if (isCmdEnter(e) && body.trim()) {
              e.preventDefault();
              create.mutate();
            }
          }}
          placeholder="코멘트 (마크다운 지원, ⌘/Ctrl+Enter 작성)"
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
