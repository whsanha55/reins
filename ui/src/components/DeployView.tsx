// DeployView — 보드에서 배포(deploy 액션). 프로젝트별 트리거 + 이력(log tail 펼침).
// pending/running 동안 자동 폴링(2s). host_path 세팅된 프로젝트만 트리거 가능.
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, ChevronRight, Rocket } from "lucide-react";
import { api, type DeployJob, type DeployStatus } from "../api";
import { EmptyState, ErrorState, Spinner, type ToastApi } from "./ui";

const STATUS_STYLE: Record<DeployStatus, string> = {
  pending: "bg-amber-50 text-warn border-amber-200",
  running: "bg-blue-50 text-info border-blue-200",
  success: "bg-emerald-50 text-ok border-emerald-200",
  failed: "bg-rose-50 text-danger border-rose-200",
};

function relTime(iso: string): string {
  const s = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 1000));
  if (s < 60) return `${s}s 전`;
  if (s < 3600) return `${Math.floor(s / 60)}m 전`;
  if (s < 86400) return `${Math.floor(s / 3600)}h 전`;
  return `${Math.floor(s / 86400)}d 전`;
}

export function DeployView({ toast }: { toast: ToastApi }) {
  const qc = useQueryClient();
  const [pid, setPid] = useState<number | "">("");
  const [ref, setRef] = useState("main");
  const [openId, setOpenId] = useState<number | null>(null);

  const { data: projects } = useQuery({ queryKey: ["projects"], queryFn: api.projects.list });
  const deployable = (projects ?? []).filter((p) => p.host_path);

  const { data: jobs, isLoading, error, refetch } = useQuery({
    queryKey: ["deploy"],
    queryFn: () => api.deploy.list(),
    // 진행 중(pending/running) job 이 있으면 2s 폴링, 아니면 정지.
    refetchInterval: (q) =>
      (q.state.data ?? []).some((j) => j.status === "pending" || j.status === "running")
        ? 2000
        : false,
  });

  const trigger = useMutation({
    mutationFn: () => api.deploy.trigger(pid as number, ref.trim() || "main"),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["deploy"] });
      toast.show("배포 트리거됨");
    },
    onError: (e) => toast.show(String((e as Error).message)),
  });

  if (isLoading) return <Spinner label="배포 이력 로드 중" />;
  if (error) return <ErrorState message={String((error as Error).message)} onRetry={() => refetch()} />;

  return (
    <div className="mx-auto max-w-3xl p-4">
      <h2 className="mb-3 text-sm font-semibold text-muted">보드에서 배포</h2>

      {/* 트리거 */}
      <form
        className="mb-4 flex flex-wrap items-center gap-2 rounded-lg border border-border2 bg-surface p-3"
        onSubmit={(e) => {
          e.preventDefault();
          if (pid !== "") trigger.mutate();
        }}
      >
        <select
          className="rounded border border-border3 bg-bg px-2 py-1.5 text-sm"
          value={pid}
          onChange={(e) => setPid(e.target.value === "" ? "" : Number(e.target.value))}
        >
          <option value="">프로젝트 선택…</option>
          {deployable.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
        <input
          className="w-28 rounded border border-border3 bg-bg px-2 py-1.5 font-mono text-sm"
          value={ref}
          onChange={(e) => setRef(e.target.value)}
          placeholder="branch"
        />
        <button
          type="submit"
          className="flex items-center gap-1.5 rounded bg-cta px-3 py-1.5 text-sm font-medium text-white disabled:opacity-40"
          disabled={pid === "" || trigger.isPending}
        >
          <Rocket className="h-4 w-4" />
          {trigger.isPending ? "트리거 중…" : "Deploy"}
        </button>
        {projects && deployable.length === 0 && (
          <span className="text-xs text-dim">host_path 세팅된 프로젝트 없음</span>
        )}
      </form>

      {/* 이력 */}
      {!jobs || jobs.length === 0 ? (
        <EmptyState title="배포 이력 없음" hint="첫 배포를 트리거해 보세요." />
      ) : (
        <ul className="flex flex-col gap-1.5">
          {jobs.map((j) => (
            <JobRow
              key={j.id}
              job={j}
              open={openId === j.id}
              onToggle={() => setOpenId(openId === j.id ? null : j.id)}
            />
          ))}
        </ul>
      )}
    </div>
  );
}

function JobRow({ job, open, onToggle }: { job: DeployJob; open: boolean; onToggle: () => void }) {
  return (
    <li className="rounded-lg border border-border2 bg-surface">
      <button className="flex w-full items-center gap-2 px-3 py-2 text-left" onClick={onToggle}>
        {open ? (
          <ChevronDown className="h-3.5 w-3.5 shrink-0 text-dim" />
        ) : (
          <ChevronRight className="h-3.5 w-3.5 shrink-0 text-dim" />
        )}
        <span className={`rounded border px-1.5 py-0.5 text-[11px] font-medium ${STATUS_STYLE[job.status]}`}>
          {job.status === "running" ? "running…" : job.status}
        </span>
        <span className="text-sm font-medium">{job.project_name ?? `#${job.project_id}`}</span>
        <span className="font-mono text-xs text-dim">@ {job.ref}</span>
        {job.exit_code !== null && (
          <span className="font-mono text-[11px] text-dim">exit {job.exit_code}</span>
        )}
        <span className="ml-auto text-[11px] text-dim">{relTime(job.created_at)}</span>
      </button>
      {open && (
        <pre className="max-h-80 overflow-auto whitespace-pre-wrap border-t border-border2 bg-bg px-3 py-2 font-mono text-[11px] text-muted">
          {job.log_tail?.trim() ||
            (job.status === "pending" ? "대기 중(agent 클레임 대기)…" : "로그 없음")}
        </pre>
      )}
    </li>
  );
}
