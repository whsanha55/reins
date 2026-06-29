// Sidebar — 프로젝트 목록 + 추가(단일 프로젝트 스코프 전환, D-DR8).
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FolderPlus, PanelLeftClose, PanelLeftOpen, Pencil, Trash2 } from "lucide-react";
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
  const [editing, setEditing] = useState<Project | null>(null);
  // #24: 사이드바 접기/펴기(localStorage 유지).
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem("reins_sidebar_collapsed") === "1");
  const toggleCollapsed = () =>
    setCollapsed((v) => {
      const n = !v;
      localStorage.setItem("reins_sidebar_collapsed", n ? "1" : "0");
      return n;
    });

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
    <aside
      className={`flex shrink-0 flex-col border-r border-border2 bg-surface transition-[width] ${
        collapsed ? "w-14" : "w-60"
      }`}
    >
      <div className="flex items-center justify-between gap-1 border-b border-border2 px-3 py-3">
        {!collapsed && (
          <div className="min-w-0">
            <h1 className="text-base font-semibold tracking-tight">reins</h1>
            <p className="truncate text-xs text-dim">자율 칸반 커맨드센터</p>
          </div>
        )}
        <button
          onClick={toggleCollapsed}
          className="shrink-0 text-dim hover:text-ink"
          aria-label={collapsed ? "사이드바 펼치기" : "사이드바 접기"}
          title={collapsed ? "펼치기" : "접기"}
        >
          {collapsed ? <PanelLeftOpen className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
        </button>
      </div>

      {!collapsed && (
        <div className="flex items-center justify-between px-4 pb-1 pt-3">
          <span className="text-xs font-semibold uppercase tracking-wide text-dim">Projects</span>
        </div>
      )}

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
                collapsed ? "justify-center" : ""
              } ${active ? "bg-surface2 font-medium" : "hover:bg-surface2"}`}
            >
              <button
                className={`flex items-center gap-2 text-left ${collapsed ? "" : "flex-1"}`}
                onClick={() => onSelect(p.id)}
                title={collapsed ? p.name : undefined}
              >
                <span
                  className="h-2 w-2 shrink-0 rounded-full"
                  style={{ background: p.color ?? "#94a3b8" }}
                  aria-hidden
                />
                {!collapsed && (
                  <span className="truncate" title={p.description ?? p.name}>
                    {p.name}
                  </span>
                )}
              </button>
              {!collapsed && (
                <>
                  <button
                    className="text-dim opacity-0 transition group-hover:opacity-100"
                    onClick={() => setEditing(p)}
                    aria-label={`${p.name} 편집`}
                  >
                    <Pencil className="h-3.5 w-3.5" />
                  </button>
                  <button
                    className="text-dim opacity-0 transition group-hover:opacity-100"
                    onClick={() => remove.mutate(p.id)}
                    aria-label={`${p.name} 삭제`}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </>
              )}
            </div>
          );
        })}
      </nav>

      {!collapsed && (
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
      )}
      {error && (
        <button className="px-3 py-1 text-xs text-info" onClick={() => refetch()}>
          재시도
        </button>
      )}
      {editing && <ProjectEditModal project={editing} onClose={() => setEditing(null)} />}
    </aside>
  );
}

// 프로젝트 편집 모달 — 이름 + 설명/Git 주소 + host_path(deploy 경로). 저장 시 projects 쿼리 갱신.
function ProjectEditModal({ project, onClose }: { project: Project; onClose: () => void }) {
  const qc = useQueryClient();
  const [name, setName] = useState(project.name);
  const [description, setDescription] = useState(project.description ?? "");
  const [hostPath, setHostPath] = useState(project.host_path ?? "");

  const update = useMutation({
    mutationFn: () =>
      api.projects.update(project.id, {
        name: name.trim(),
        description: description.trim(),
        host_path: hostPath.trim(),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["projects"] });
      onClose();
    },
  });

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={onClose}
    >
      <form
        className="w-[28rem] max-w-[90vw] rounded-lg border border-border2 bg-surface p-4 shadow-xl"
        onClick={(e) => e.stopPropagation()}
        onSubmit={(e) => {
          e.preventDefault();
          if (name.trim()) update.mutate();
        }}
      >
        <h2 className="mb-3 text-sm font-semibold">프로젝트 편집</h2>

        <label className="block text-xs font-medium text-dim" htmlFor="pj-name">
          이름
        </label>
        <input
          id="pj-name"
          className="mt-1 w-full rounded border border-border3 bg-bg px-2 py-1.5 text-sm"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />

        <label className="mt-3 block text-xs font-medium text-dim" htmlFor="pj-desc">
          설명 / Git 주소
        </label>
        <textarea
          id="pj-desc"
          className="mt-1 w-full rounded border border-border3 bg-bg px-2 py-1.5 text-sm"
          rows={5}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="이 프로젝트의 작업 내용과 git 주소"
        />

        <label className="mt-3 block text-xs font-medium text-dim" htmlFor="pj-hostpath">
          Host 경로 (deploy)
        </label>
        <input
          id="pj-hostpath"
          className="mt-1 w-full rounded border border-border3 bg-bg px-2 py-1.5 font-mono text-sm"
          value={hostPath}
          onChange={(e) => setHostPath(e.target.value)}
          placeholder="/home/ubuntu/reins (비우면 deploy 비활성)"
        />

        <div className="mt-3 flex justify-end gap-2">
          <button
            type="button"
            className="rounded border border-border3 px-3 py-1.5 text-sm"
            onClick={onClose}
          >
            취소
          </button>
          <button
            type="submit"
            className="rounded bg-cta px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
            disabled={!name.trim() || update.isPending}
          >
            {update.isPending ? "저장 중…" : "저장"}
          </button>
        </div>
        {update.isError && (
          <p className="mt-2 text-xs text-danger" aria-live="assertive">
            수정 실패: {String((update.error as Error).message)}
          </p>
        )}
      </form>
    </div>
  );
}
