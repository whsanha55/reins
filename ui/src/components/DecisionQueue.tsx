// DecisionQueue — 4게이트 결정 카드. 노화 UI(1h amber/24h red, D-DR5). 더블클릭 idempotent.
import type { ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, X, RotateCcw } from "lucide-react";
import { api, type Decision, type Gate, type Resolution } from "../api";
import { agingClass, EmptyState, ErrorState, Spinner, type ToastApi } from "./ui";

const GATE_LABEL: Record<Gate, string> = {
  pr_open: "PR 오픈",
  merge: "머지",
  deploy: "배포",
  spec_ambiguous: "스펙 애매",
};

export function DecisionQueue({ toast }: { toast: ToastApi }) {
  const qc = useQueryClient();
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["decisions", "pending"],
    queryFn: () => api.decisions.list("pending"),
  });

  const resolve = useMutation({
    mutationFn: (vars: { id: number; resolution: Resolution }) =>
      api.decisions.resolve(vars.id, vars.resolution),
    // idempotent: 서버가 applied 여부와 무관하게 200. 중복 클릭 → 카드 fade-out 유지.
    onMutate: async (vars) => {
      await qc.cancelQueries({ queryKey: ["decisions", "pending"] });
      const prev = qc.getQueryData<Decision[]>(["decisions", "pending"]);
      qc.setQueryData<Decision[]>(["decisions", "pending"], (old) =>
        (old ?? []).filter((d) => d.id !== vars.id),
      );
      return { prev };
    },
    onError: (_e, _v, ctx) => {
      if (ctx?.prev) qc.setQueryData(["decisions", "pending"], ctx.prev);
    },
    onSettled: () => qc.invalidateQueries({ queryKey: ["decisions", "pending"] }),
    onSuccess: (_d, vars) => {
      toast.show(`결정 ${vars.resolution} 처리됨`);
    },
  });

  if (isLoading) return <Spinner label="결정 큐 로드 중" />;
  if (error) return <ErrorState message={String((error as Error).message)} onRetry={() => refetch()} />;
  if (!data || data.length === 0)
    return <EmptyState title="대기 결정 없음 ✓" hint="모든 결정을 처리했습니다." />;

  return (
    <div className="mx-auto max-w-2xl p-4">
      <h2 className="mb-3 text-sm font-semibold text-muted">결정 큐 · {data.length}건</h2>
      <ul className="flex flex-col gap-2">
        {data.map((d) => {
          const age = agingClass(d.created_at);
          return (
            <li key={d.id} className={`rounded-lg border bg-warnsoft/40 p-3 ${age.border}`}>
              <div className="flex items-center gap-2">
                <span className="rounded border border-warn bg-warnsoft px-1.5 py-0.5 text-[11px] font-medium text-warn">
                  결정필요
                </span>
                <span className="rounded bg-surface2 px-1.5 py-0.5 text-[11px] text-muted">
                  {GATE_LABEL[d.gate]}
                </span>
                <a className="ml-auto font-mono text-[11px] text-dim" href={`#ticket-${d.ticket_id}`}>
                  #{d.ticket_id}
                </a>
              </div>
              <p className="mt-2 whitespace-pre-wrap text-sm">{d.summary}</p>
              <p className={`mt-1 font-mono text-[11px] ${age.text}`}>{age.label}</p>
              <div className="mt-2 flex gap-1.5">
                <ResolveBtn
                  label="Approve"
                  icon={<Check className="h-3.5 w-3.5" />}
                  cls="bg-cta text-white"
                  pending={resolve.isPending}
                  onClick={() => resolve.mutate({ id: d.id, resolution: "approved" })}
                />
                <ResolveBtn
                  label="Reject"
                  icon={<X className="h-3.5 w-3.5" />}
                  cls="border border-danger text-danger"
                  pending={resolve.isPending}
                  onClick={() => resolve.mutate({ id: d.id, resolution: "rejected" })}
                />
                <ResolveBtn
                  label="Changes"
                  icon={<RotateCcw className="h-3.5 w-3.5" />}
                  cls="border border-border3 text-muted"
                  pending={resolve.isPending}
                  onClick={() => resolve.mutate({ id: d.id, resolution: "changes" })}
                />
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function ResolveBtn({
  label,
  icon,
  cls,
  pending,
  onClick,
}: {
  label: string;
  icon: ReactNode;
  cls: string;
  pending: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      disabled={pending}
      className={`flex items-center gap-1 rounded px-2.5 py-1 text-xs font-medium disabled:opacity-50 ${cls}`}
    >
      {icon}
      {label}
    </button>
  );
}
