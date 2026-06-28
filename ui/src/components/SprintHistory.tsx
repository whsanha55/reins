// SprintHistory — #20: 과거 스프린트별 닫힌(done/cancel) 티켓 모아보기 + 제목 검색.
// #14 시간경계 모델: 티켓은 updated_at 이 속한 스프린트 윈도우 [start_i, start_{i-1})에 귀속.
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, type Ticket } from "../api";
import { EmptyState, ErrorState, Spinner, StatusBadge } from "./ui";

export function SprintHistory({
  projectId,
  projectName,
  onOpenTicket,
}: {
  projectId: number;
  projectName: string;
  onOpenTicket: (id: number) => void;
}) {
  const [q, setQ] = useState("");
  const sprintsQ = useQuery({
    queryKey: ["sprints", projectId],
    queryFn: () => api.sprints.list(projectId),
  });
  const ticketsQ = useQuery({
    queryKey: ["tickets", projectId, "all"],
    queryFn: () => api.tickets.list({ project_id: projectId }),
  });

  const { groups, preSprint } = useMemo(() => {
    const sprints = sprintsQ.data ?? [];
    const tickets = ticketsQ.data ?? [];
    const needle = q.trim().toLowerCase();
    const match = (t: Ticket) => !needle || t.title.toLowerCase().includes(needle);
    const closed = tickets.filter((t) => t.status === "done" || t.status === "cancel");
    // sprints desc by started_at. 윈도우 [start_i, start_{i-1}), newest = [start_0, ∞).
    const groups = sprints.map((s, i) => {
      const start = new Date(s.started_at).getTime();
      const end = i === 0 ? Infinity : new Date(sprints[i - 1].started_at).getTime();
      const items = closed.filter((t) => {
        const u = new Date(t.updated_at).getTime();
        return u >= start && u < end && match(t);
      });
      return { sprint: s, items };
    });
    // 가장 오래된 스프린트보다 이전에 닫힌 티켓(미분류).
    const oldest = sprints.length ? new Date(sprints[sprints.length - 1].started_at).getTime() : Infinity;
    const preSprint = closed.filter((t) => new Date(t.updated_at).getTime() < oldest && match(t));
    return { groups, preSprint };
  }, [sprintsQ.data, ticketsQ.data, q]);

  if (sprintsQ.isLoading || ticketsQ.isLoading) return <Spinner label="스프린트 내역 로드 중" />;
  if (sprintsQ.error) return <ErrorState message={String((sprintsQ.error as Error).message)} />;
  const sprints = sprintsQ.data ?? [];

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-3 border-b border-border2 bg-surface px-4 py-2">
        <span className="font-mono text-xs text-dim">sprints</span>
        <span className="text-sm font-semibold">{projectName}</span>
        <input
          className="ml-auto w-56 rounded border border-border3 bg-surface px-2 py-1 text-xs"
          placeholder="티켓 제목 검색…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
      </div>
      <div className="flex-1 overflow-auto p-3">
        {sprints.length === 0 ? (
          <EmptyState title="스프린트 없음" hint="보드에서 '+ 새 스프린트'를 시작하면 내역이 쌓입니다." />
        ) : (
          <div className="flex flex-col gap-4">
            {groups.map(({ sprint, items }) => (
              <SprintSection
                key={sprint.id}
                title={sprint.name}
                subtitle={new Date(sprint.started_at).toLocaleString()}
                items={items}
                onOpenTicket={onOpenTicket}
              />
            ))}
            {preSprint.length > 0 && (
              <SprintSection
                title="스프린트 이전"
                subtitle="가장 오래된 스프린트보다 먼저 닫힘"
                items={preSprint}
                onOpenTicket={onOpenTicket}
              />
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function SprintSection({
  title,
  subtitle,
  items,
  onOpenTicket,
}: {
  title: string;
  subtitle: string;
  items: Ticket[];
  onOpenTicket: (id: number) => void;
}) {
  return (
    <section className="rounded-lg border border-border2">
      <header className="flex items-center gap-2 border-b border-border2 bg-surface2 px-3 py-2">
        <span className="text-sm font-semibold">{title}</span>
        <span className="font-mono text-[11px] text-dim">{subtitle}</span>
        <span className="ml-auto font-mono text-xs text-dim">{items.length}건</span>
      </header>
      {items.length === 0 ? (
        <p className="px-3 py-2 text-xs text-dim">닫힌 티켓 없음</p>
      ) : (
        <ul className="divide-y divide-border2">
          {items.map((t) => (
            <li key={t.id}>
              <button
                onClick={() => onOpenTicket(t.id)}
                className="flex w-full items-center gap-2 px-3 py-1.5 text-left hover:bg-surface2"
              >
                <span className="font-mono text-[11px] text-dim">#{t.id}</span>
                <StatusBadge status={t.status} />
                <span className="truncate text-sm">{t.title}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
