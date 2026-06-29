// Board — 단일 프로젝트 스코프(D-DR8). 그룹(에픽 기본)·정렬 드롭다운. 5컬럼(풀 단어).
// 카드: 드래그드롭으로 상태 변경(상태기계). canTransition/canReopen 존중.
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type Group, type Sort, type Ticket, type TicketStatus } from "../api";
import { EmptyState, ErrorState, Spinner, type ToastApi } from "./ui";

const COLUMNS: TicketStatus[] = ["todo", "progressing", "qa", "done", "cancel"];

// 에픽별 구분 색 — 보드 섹션 전체 테두리에 사용. 에픽 순서 index로 안정 매핑.
const EPIC_PALETTE = ["#4F46E5", "#0891B2", "#DB2777", "#16A34A", "#D97706", "#7C3AED", "#DC2626", "#0D9488"];
const epicColor = (idx: number) => EPIC_PALETTE[idx % EPIC_PALETTE.length];

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

  // 스프린트(#14): 최신 = 활성. 시작 시점 기준으로 이전에 닫힌 done/cancel 을 기본 숨김.
  const { data: sprints } = useQuery({
    queryKey: ["sprints", projectId],
    queryFn: () => api.sprints.list(projectId),
  });
  const [showClosed, setShowClosed] = useState(false);
  // #25: 새 스프린트 시작 전 인라인 컨펌(이전 완료/취소가 숨겨지므로).
  const [confirmSprint, setConfirmSprint] = useState(false);
  const newSprint = useMutation({
    mutationFn: () => api.sprints.create(projectId, `스프린트 ${(sprints?.length ?? 0) + 1}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["sprints", projectId] });
      toast.show("새 스프린트 시작 — 이전 완료/취소 숨김");
    },
    onError: (e) => toast.show(String((e as Error).message)),
  });

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

  const currentSprint = sprints?.[0] ?? null;
  const sprintStart = currentSprint ? new Date(currentSprint.started_at).getTime() : null;
  // 활성 스프린트 시작 이전에 닫힌(done/cancel) 티켓은 숨김. showClosed 또는 스프린트 없으면 전부 노출.
  const visible = tickets.filter((t) => {
    if (showClosed || sprintStart == null) return true;
    if (t.status !== "done" && t.status !== "cancel") return true;
    return new Date(t.updated_at).getTime() >= sprintStart;
  });

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-3 border-b border-border2 bg-surface px-4 py-2">
        <span className="font-mono text-xs text-dim">project</span>
        <span className="text-sm font-semibold">{projectName}</span>
        <span className="ml-2 flex items-center gap-1.5 text-xs">
          <span className="rounded bg-surface2 px-1.5 py-0.5 text-dim">
            {currentSprint ? currentSprint.name : "스프린트 없음"}
          </span>
          {confirmSprint ? (
            <span className="flex items-center gap-1">
              <span className="text-dim">이전 완료/취소 숨김 — 시작?</span>
              <button
                onClick={() => {
                  newSprint.mutate();
                  setConfirmSprint(false);
                }}
                disabled={newSprint.isPending}
                className="rounded bg-cta px-1.5 py-0.5 font-medium text-white disabled:opacity-50"
              >
                시작
              </button>
              <button
                onClick={() => setConfirmSprint(false)}
                className="rounded border border-border3 px-1.5 py-0.5 text-dim hover:bg-surface2"
              >
                취소
              </button>
            </span>
          ) : (
            <button
              onClick={() => setConfirmSprint(true)}
              className="rounded border border-border3 px-1.5 py-0.5 text-dim hover:bg-surface2"
              title="새 스프린트를 시작하면 이전에 완료/취소된 티켓이 보드에서 숨겨집니다"
            >
              + 새 스프린트
            </button>
          )}
        </span>
        <div className="ml-auto flex items-center gap-2 text-xs">
          <button
            onClick={onNewTicket}
            className="rounded bg-cta px-2 py-1 font-medium text-white hover:bg-ink"
          >
            + 새 티켓
          </button>
          <label className="flex items-center gap-1">
            <input
              type="checkbox"
              checked={showClosed}
              onChange={(e) => setShowClosed(e.target.checked)}
            />
            <span className="text-dim">지난 완료/취소</span>
          </label>
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
          <EpicGrouped tickets={visible} onOpenTicket={onOpenTicket} onMove={onMove} />
        ) : (
          <Kanban tickets={visible} onOpenTicket={onOpenTicket} onMove={onMove} />
        )}
      </div>
    </div>
  );
}

// 컬럼 드롭존 래퍼. flex-1 로 화면 채우되 min-w 로 좁아지면 가로 스크롤.
// 드래그 오버 시 점선 테두리 + "여기에 놓기 → {status}" 가이드 표시.
function Column({
  status,
  tickets,
  onOpenTicket,
  onMove,
}: {
  status: TicketStatus;
  tickets: Ticket[];
  onOpenTicket: (id: number) => void;
  onMove: (id: number, to: TicketStatus) => void;
}) {
  const items = tickets.filter((t) => t.status === status);
  const [over, setOver] = useState(false);
  return (
    <div className="flex min-w-[180px] flex-1 flex-col">
      <ColumnHeader status={status} count={items.length} />
      <div
        className={`mt-2 flex min-h-16 flex-1 flex-col gap-2 rounded-md border-2 border-dashed p-1 transition-colors ${
          over ? "border-info bg-info/5" : "border-transparent"
        }`}
        onDragOver={(e) => e.preventDefault()}
        onDragEnter={() => setOver(true)}
        onDragLeave={(e) => {
          // 자식 요소로의 이동은 leave 아님 — 컨테이너 밖으로 나갈 때만 해제.
          if (!e.currentTarget.contains(e.relatedTarget as Node)) setOver(false);
        }}
        onDrop={(e) => {
          e.preventDefault();
          setOver(false);
          const id = Number(e.dataTransfer.getData("text/plain"));
          if (id) onMove(id, status);
        }}
      >
        {over && (
          <div className="pointer-events-none rounded border border-dashed border-info bg-surface px-2 py-1 text-center text-[11px] font-medium text-info">
            여기에 놓기 → {status}
          </div>
        )}
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
      {epics.map((epic, i) => {
        const children = tickets.filter((t) => t.parent_id === epic.id);
        const color = epicColor(i);
        return (
          <section key={epic.id} className="rounded-lg border-2 p-2" style={{ borderColor: color }}>
            <EpicHeader epic={epic} children_={children} onOpen={onOpenTicket} color={color} />
            <div className="mt-2 flex gap-3">
              {COLUMNS.map((col) => (
                <Column
                  key={col}
                  status={col}
                  tickets={children}
                  onOpenTicket={onOpenTicket}
                  onMove={onMove}
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
  color,
}: {
  epic: Ticket;
  children_: Ticket[];
  onOpen: (id: number) => void;
  color: string;
}) {
  const done = children_.filter((c) => c.status === "done").length;
  const total = children_.length;
  const pct = total > 0 ? Math.round((done / total) * 100) : 0;
  return (
    <button
      onClick={() => onOpen(epic.id)}
      className="w-full rounded-md border-2 bg-surface px-3 py-2 text-left"
      style={{ borderColor: color }}
    >
      <div className="flex items-center gap-2">
        <span
          className="rounded px-1.5 py-0.5 text-[10px] font-bold uppercase text-white"
          style={{ backgroundColor: color }}
        >
          EPIC
        </span>
        <span className="truncate text-sm font-semibold">{epic.title}</span>
        <span className="ml-auto font-mono text-xs text-dim">
          {done}/{total}
        </span>
      </div>
      <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-surface2">
        <div className="h-full" style={{ width: `${pct}%`, backgroundColor: color }} />
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
