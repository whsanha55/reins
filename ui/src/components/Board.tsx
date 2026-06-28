// Board — 단일 프로젝트 스코프(D-DR8). 그룹(에픽 기본)·정렬 드롭다운. 5컬럼(풀 단어).
// 카드: 드래그드롭으로 상태 변경(상태기계). canTransition/canReopen 존중.
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type Group, type Sort, type Ticket, type TicketStatus } from "../api";
import { EmptyState, ErrorState, Spinner, type ToastApi } from "./ui";

const COLUMNS: TicketStatus[] = ["todo", "progressing", "qa", "done", "cancel"];

export function Board({
  projectId,
  projectName,
  toast,
  onOpenTicket,
  onNewTicket,
}: {
  projectId: number;
  projectName: string;
  toast: ToastApi;
  onOpenTicket: (id: number) => void;
  onNewTicket: () => void;
}) {
  const [sort, setSort] = useState<Sort>("created");
  // 에픽별 그룹이 기본값.
  const [group, setGroup] = useState<Group>("epic");

  const { data: tickets, isLoading, error, refetch } = useQuery({
    queryKey: ["tickets", projectId, sort],
    queryFn: () => api.tickets.list({ project_id: projectId, sort }),
  });

  const qc = useQueryClient();
  // workflow 제한 없음 — 어떤 상태든 어디든 transition 1건으로 이동.
  const move = useMutation({
    mutationFn: (v: { id: number; to: TicketStatus }) => api.tickets.transition(v.id, v.to),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tickets"] });
      qc.invalidateQueries({ queryKey: ["ticket"] });
    },
    onError: (e) => toast.show(String((e as Error).message)),
  });

  // DnD/카드 셀렉트 공용. 같은 상태로의 드롭은 no-op(이벤트 노이즈 방지).
  const onMove = (id: number, to: TicketStatus) => {
    const t = tickets?.find((x) => x.id === id);
    if (!t || t.status === to) return;
    move.mutate({ id, to });
  };

  if (isLoading) return <Spinner label="보드 로드 중" />;
  if (error) return <ErrorState message={String((error as Error).message)} onRetry={() => refetch()} />;
  if (!tickets || tickets.length === 0)
    return (
      <EmptyState
        title="티켓 없음"
        hint="첫 티켓을 만들어 보세요."
        action={
          <button onClick={onNewTicket} className="rounded bg-cta px-3 py-1.5 text-sm text-white">
            새 티켓
          </button>
        }
      />
    );

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-3 border-b border-border2 bg-surface px-4 py-2">
        <span className="font-mono text-xs text-dim">project</span>
        <span className="text-sm font-semibold">{projectName}</span>
        <div className="ml-auto flex items-center gap-2 text-xs">
          <label className="flex items-center gap-1">
            <span className="text-dim">그룹</span>
            <select
              className="rounded border border-border3 bg-surface px-1.5 py-1"
              value={group}
              onChange={(e) => setGroup(e.target.value as Group)}
            >
              <option value="none">없음</option>
              <option value="epic">에픽별</option>
            </select>
          </label>
          <label className="flex items-center gap-1">
            <span className="text-dim">정렬</span>
            <select
              className="rounded border border-border3 bg-surface px-1.5 py-1"
              value={sort}
              onChange={(e) => setSort(e.target.value as Sort)}
            >
              <option value="created">등록순</option>
              <option value="updated">최근변경순</option>
              <option value="priority">우선순위</option>
            </select>
          </label>
        </div>
      </div>

      <div className="flex-1 overflow-auto p-3">
        {group === "epic" ? (
          <EpicGrouped tickets={tickets} onOpenTicket={onOpenTicket} onMove={onMove} />
        ) : (
          <Kanban tickets={tickets} onOpenTicket={onOpenTicket} onMove={onMove} />
        )}
      </div>
    </div>
  );
}

// 컬럼 드롭존 래퍼. onDragOver 기본방지 + 드롭 시 onMove(id, col).
function Column({
  status,
  tickets,
  onOpenTicket,
  onMove,
  width = "w-64",
}: {
  status: TicketStatus;
  tickets: Ticket[];
  onOpenTicket: (id: number) => void;
  onMove: (id: number, to: TicketStatus) => void;
  width?: string;
}) {
  const items = tickets.filter((t) => t.status === status);
  return (
    <div className={`${width} shrink-0`}>
      <ColumnHeader status={status} count={items.length} />
      <div
        className="mt-2 flex min-h-16 flex-col gap-2"
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          const id = Number(e.dataTransfer.getData("text/plain"));
          if (id) onMove(id, status);
        }}
      >
        {items.map((t) => (
          <Card key={t.id} ticket={t} onOpen={onOpenTicket} />
        ))}
      </div>
    </div>
  );
}

function Kanban({
  tickets,
  onOpenTicket,
  onMove,
}: {
  tickets: Ticket[];
  onOpenTicket: (id: number) => void;
  onMove: (id: number, to: TicketStatus) => void;
}) {
  return (
    <div className="flex gap-3">
      {COLUMNS.map((col) => (
        <Column key={col} status={col} tickets={tickets} onOpenTicket={onOpenTicket} onMove={onMove} />
      ))}
    </div>
  );
}

function EpicGrouped({
  tickets,
  onOpenTicket,
  onMove,
}: {
  tickets: Ticket[];
  onOpenTicket: (id: number) => void;
  onMove: (id: number, to: TicketStatus) => void;
}) {
  const epics = tickets.filter((t) => t.type === "epic");
  const orphans = tickets.filter((t) => t.type === "task" && t.parent_id == null);

  if (epics.length === 0 && orphans.length === 0) return null;

  return (
    <div className="flex flex-col gap-6">
      {epics.map((epic) => {
        const children = tickets.filter((t) => t.parent_id === epic.id);
        return (
          <section key={epic.id}>
            <EpicHeader epic={epic} children_={children} onOpen={onOpenTicket} />
            <div className="mt-2 flex gap-3">
              {COLUMNS.map((col) => (
                <Column
                  key={col}
                  status={col}
                  tickets={children}
                  onOpenTicket={onOpenTicket}
                  onMove={onMove}
                  width="w-56"
                />
              ))}
            </div>
          </section>
        );
      })}
      {orphans.length > 0 && (
        <section>
          <h3 className="px-1 pb-1 text-xs font-semibold uppercase tracking-wide text-dim">에픽 없음</h3>
          <div className="flex gap-3">
            {COLUMNS.map((col) => (
              <Column
                key={col}
                status={col}
                tickets={orphans}
                onOpenTicket={onOpenTicket}
                onMove={onMove}
                width="w-56"
              />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

function ColumnHeader({ status, count }: { status: TicketStatus; count: number }) {
  return (
    <div className="flex items-center justify-between rounded-md bg-surface2 px-2 py-1">
      <span className="text-xs font-semibold uppercase tracking-wide text-muted">{status}</span>
      <span className="font-mono text-xs text-dim">{count}</span>
    </div>
  );
}

function EpicHeader({
  epic,
  children_,
  onOpen,
}: {
  epic: Ticket;
  children_: Ticket[];
  onOpen: (id: number) => void;
}) {
  const done = children_.filter((c) => c.status === "done").length;
  const total = children_.length;
  const pct = total > 0 ? Math.round((done / total) * 100) : 0;
  return (
    <button
      onClick={() => onOpen(epic.id)}
      className="w-full rounded-md border-2 border-epic bg-surface px-3 py-2 text-left"
    >
      <div className="flex items-center gap-2">
        <span className="rounded bg-epic px-1.5 py-0.5 text-[10px] font-bold uppercase text-white">EPIC</span>
        <span className="truncate text-sm font-semibold">{epic.title}</span>
        <span className="ml-auto font-mono text-xs text-dim">
          {done}/{total}
        </span>
      </div>
      <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-surface2">
        <div className="h-full bg-epic" style={{ width: `${pct}%` }} />
      </div>
    </button>
  );
}

function Card({
  ticket,
  onOpen,
}: {
  ticket: Ticket;
  onOpen: (id: number) => void;
}) {
  const isEpic = ticket.type === "epic";
  return (
    <div
      role="button"
      tabIndex={0}
      draggable
      onDragStart={(e) => {
        e.dataTransfer.setData("text/plain", String(ticket.id));
        e.dataTransfer.effectAllowed = "move";
      }}
      onClick={() => onOpen(ticket.id)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onOpen(ticket.id);
        }
      }}
      className={`group cursor-grab rounded-md border bg-surface px-2.5 py-2 text-left transition hover:border-border3 hover:bg-surface2 active:cursor-grabbing ${
        isEpic ? "border-epic/60" : "border-border2"
      }`}
    >
      <div className="flex items-center gap-1.5">
        <span className="font-mono text-[11px] text-dim">#{ticket.id}</span>
        {isEpic && (
          <span className="rounded bg-epic px-1 text-[10px] font-bold uppercase text-white">EPIC</span>
        )}
      </div>
      <p className="mt-1 line-clamp-2 text-sm">{ticket.title}</p>
      {ticket.priority > 0 && (
        <p className="mt-1 font-mono text-[11px] text-warn">P{ticket.priority}</p>
      )}
    </div>
  );
}

// ponytail: 보드 카드의 코멘트 수 표시는 생략(카드별 카운트 fetch 비용). 드로어 Comments 탭에서 확인.
