// Sidebar — 프로젝트 목록 + 추가(단일 프로젝트 스코프 전환, D-DR8).
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FolderPlus, Trash2 } from "lucide-react";
import { api, type Project } from "../api";

const COLORS = ["#10b981", "#0ea5e9", "#6366f1", "#8b5cf6", "#f59e0b", "#f43f5e", "#06b6d4"];

export function Sidebar({
  selected,
  onSelect,
}: {
  selected: number | null;
  onSelect: (id: number | null) => void;
}) {
  const qc = useQueryClient();
  const { data: projects, isLoading, error, refetch } = useQuery({
    queryKey: ["projects"],
    queryFn: api.projects.list,
  });
  const [name, setName] = useState("");

  const create = useMutation({
    mutationFn: (n: string) => api.projects.create(n, COLORS[(projects?.length ?? 0) % COLORS.length]),
    onSuccess: (p: Project) => {
      setName("");
      qc.invalidateQueries({ queryKey: ["projects"] });
      onSelect(p.id);
    },
  });
  const remove = useMutation({
    mutationFn: (id: number) => api.projects.remove(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["projects"] }),
  });

  return (
    <aside className="flex w-60 shrink-0 flex-col border-r border-border2 bg-surface">
      <div className="border-b border-border2 px-4 py-3">
        <h1 className="text-base font-semibold tracking-tight">reins</h1>
        <p className="text-xs text-dim">자율 칸반 커맨드센터</p>
      </div>

      <div className="flex items-center justify-between px-4 pb-1 pt-3">
        <span className="text-xs font-semibold uppercase tracking-wide text-dim">Projects</span>
      </div>

      <nav className="flex-1 overflow-y-auto px-2">
        {isLoading && <p className="px-2 py-2 text-sm text-dim">불러오는 중…</p>}
        {error && <p className="px-2 py-2 text-sm text-danger">프로젝트 로드 실패</p>}
        {projects?.length === 0 && (
          <p className="px-2 py-2 text-sm text-dim">프로젝트 없음</p>
        )}
        {projects?.map((p) => {
          const active = p.id === selected;
          return (
            <div
              key={p.id}
              className={`group flex items-center gap-2 rounded-md px-2 py-1.5 text-sm ${
                active ? "bg-surface2 font-medium" : "hover:bg-surface2"
              }`}
            >
              <button
                className="flex flex-1 items-center gap-2 text-left"
                onClick={() => onSelect(p.id)}
              >
                <span
                  className="h-2 w-2 shrink-0 rounded-full"
                  style={{ background: p.color ?? "#94a3b8" }}
                  aria-hidden
                />
                <span className="truncate">{p.name}</span>
              </button>
              <button
                className="text-dim opacity-0 transition group-hover:opacity-100"
                onClick={() => remove.mutate(p.id)}
                aria-label={`${p.name} 삭제`}
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>
          );
        })}
      </nav>

      <form
        className="flex items-center gap-1 border-t border-border2 p-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (name.trim()) create.mutate(name.trim());
        }}
      >
        <input
          className="flex-1 rounded border border-border3 bg-surface px-2 py-1 text-sm"
          placeholder="새 프로젝트"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <button
          type="submit"
          className="rounded bg-cta p-1.5 text-white disabled:opacity-40"
          disabled={!name.trim() || create.isPending}
          aria-label="프로젝트 추가"
        >
          <FolderPlus className="h-4 w-4" />
        </button>
      </form>
      {error && (
        <button className="px-3 py-1 text-xs text-info" onClick={() => refetch()}>
          재시도
        </button>
      )}
    </aside>
  );
}
