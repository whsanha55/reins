// App — path 라우트 기반. /project/:pid (board) · /project/:pid/new · /project/:pid/t/:tid (drawer) · /decisions.
// URL이 각 기능을 구분(router.ts). 좌측 사이드바 + 헤더 탭 + 결정 배지 + 우측 드로어.
import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { Sidebar } from "./components/Sidebar";
import { Board } from "./components/Board";
import { DecisionQueue } from "./components/DecisionQueue";
import { TicketForm } from "./components/TicketForm";
import { TicketDrawer } from "./components/TicketDrawer";
import { useToast } from "./components/ui";
import { api, getToken, setToken } from "./api";
import { useRoute, type Route } from "./router";

type Tab = "board" | "decisions" | "new";

export default function App() {
  // ponytail: 게이트/본체 분리 — React hooks 순서 위반 방지(gate 시 미호출 hook 방지).
  const [authed, setAuthed] = useState(() => !!getToken());
  useEffect(() => {
    const h = () => setAuthed(false);
    window.addEventListener("reins:unauth", h);
    return () => window.removeEventListener("reins:unauth", h);
  }, []);
  if (!authed) return <TokenGate onAuthed={() => setAuthed(true)} />;
  return <Main />;
}

function Main() {
  const toast = useToast();
  const [route, navigate] = useRoute();
  const [lastPid, setLastPid] = useState<number | null>(null);

  const { data: pending } = useQuery({
    queryKey: ["decisions", "pending"],
    queryFn: () => api.decisions.list("pending"),
  });
  const { data: projects } = useQuery({ queryKey: ["projects"], queryFn: api.projects.list });

  const pid = routePid(route);
  const project = projects?.find((p) => p.id === pid) ?? null;

  // 마지막으로 본 프로젝트 기억(뉴/보드 탭 복귀용).
  useEffect(() => {
    if (pid != null) setLastPid(pid);
  }, [pid]);

  // home 진입 시 첫 프로젝트 보드로(콜드스타트).
  useEffect(() => {
    if (route.view === "home" && projects && projects.length > 0) {
      navigate(`/project/${projects[0].id}`);
    }
  }, [route, projects, navigate]);

  const tab: Tab =
    route.view === "decisions" ? "decisions" : route.view === "new" ? "new" : "board";
  const openTicketId = route.view === "ticket" ? route.tid : null;

  const goProject = (id: number | null) => navigate(id == null ? "/" : `/project/${id}`);

  return (
    <div className="flex h-screen w-screen overflow-hidden">
      <Sidebar selected={pid} onSelect={goProject} />

      <main className="flex flex-1 flex-col">
        <header className="z-20 flex items-center gap-1 border-b border-border2 bg-surface px-3 py-2">
          <TabBtn
            active={tab === "board"}
            onClick={() => navigate(lastPid ? `/project/${lastPid}` : "/")}
          >
            Board
          </TabBtn>
          <TabBtn active={tab === "decisions"} onClick={() => navigate("/decisions")}>
            <span className="flex items-center gap-1.5">
              Decision Queue
              {(pending?.length ?? 0) > 0 && (
                <span className="inline-flex items-center gap-1 rounded-full bg-warnsoft px-1.5 text-[11px] font-medium text-warn">
                  <span className="h-1.5 w-1.5 rounded-full bg-warn" />
                  {pending!.length}
                </span>
              )}
            </span>
          </TabBtn>
          <TabBtn
            active={tab === "new"}
            onClick={() => navigate(lastPid ? `/project/${lastPid}/new` : "/")}
          >
            New Ticket
          </TabBtn>
        </header>

        <section className="flex-1 overflow-hidden bg-bg">
          {tab === "board" && project && (
            <Board
              projectId={project.id}
              projectName={project.name}
              toast={toast}
              onOpenTicket={(id) => navigate(`/project/${project.id}/t/${id}`)}
              onNewTicket={() => navigate(`/project/${project.id}/new`)}
            />
          )}
          {tab === "board" && !project && (
            <div className="flex h-full items-center justify-center text-sm text-dim">
              왼쪽에서 프로젝트를 선택하거나 만드세요.
            </div>
          )}
          {tab === "decisions" && <DecisionQueue toast={toast} />}
          {tab === "new" && project && (
            <TicketForm projectId={project.id} toast={toast} onDone={() => navigate(`/project/${project.id}`)} />
          )}
          {tab === "new" && !project && (
            <div className="flex h-full items-center justify-center text-sm text-dim">
              먼저 프로젝트를 만드세요.
            </div>
          )}
        </section>
      </main>

      {openTicketId !== null && (
        <TicketDrawer
          ticketId={openTicketId}
          onClose={() => navigate(pid ? `/project/${pid}` : "/")}
          toast={toast}
        />
      )}
      {toast.node}
    </div>
  );
}

function routePid(route: Route): number | null {
  return route.view === "board" || route.view === "new" || route.view === "ticket" ? route.pid : null;
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
      className={`rounded px-3 py-1.5 text-sm ${
        active ? "bg-cta text-white" : "text-muted hover:bg-surface2"
      }`}
    >
      {children}
    </button>
  );
}

function TokenGate({ onAuthed }: { onAuthed: () => void }) {
  const [v, setV] = useState("");
  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const t = v.trim();
    if (!t) return;
    setToken(t);
    onAuthed();
  };
  return (
    <div className="flex h-screen w-screen items-center justify-center bg-bg">
      <form onSubmit={submit} className="w-80 rounded-lg border border-border2 bg-surface p-5 shadow-lg">
        <div className="mb-1 text-sm font-semibold text-text">reins</div>
        <div className="mb-3 text-xs text-dim">API 토큰을 입력하세요.</div>
        <input
          type="password"
          value={v}
          onChange={(e) => setV(e.target.value)}
          placeholder="token"
          autoFocus
          className="w-full rounded border border-border2 bg-bg px-2 py-1.5 text-sm text-text outline-none focus:border-cta"
        />
        <button
          type="submit"
          className="mt-3 w-full rounded bg-cta px-3 py-1.5 text-sm font-medium text-white hover:opacity-90"
        >
          저장
        </button>
      </form>
    </div>
  );
}
