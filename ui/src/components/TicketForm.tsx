// TicketForm — 티켓 생성. type(Task/Epic) + 에픽 셀렉트(parent_id). 필드별 인라인 에러 + aria-live.
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type TicketType } from "../api";
import { ErrorState, Spinner, isCmdEnter, type ToastApi } from "./ui";

export function TicketForm({
  projectId,
  onDone,
  toast,
}: {
  projectId: number;
  onDone: () => void;
  toast: ToastApi;
}) {
  const qc = useQueryClient();
  const { data: epics, isLoading, error } = useQuery({
    queryKey: ["epics", projectId],
    queryFn: () => api.tickets.list({ project_id: projectId, type: "epic" }),
  });

  const [type, setType] = useState<TicketType>("task");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [parentId, setParentId] = useState<number | "">("");
  const [priority, setPriority] = useState(0);
  const [errors, setErrors] = useState<Record<string, string>>({});

  const create = useMutation({
    mutationFn: () =>
      api.tickets.create({
        project_id: projectId,
        title: title.trim(),
        description: description.trim() || undefined,
        type,
        parent_id: type === "task" ? (parentId === "" ? null : parentId) : null,
        priority,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tickets", projectId] });
      qc.invalidateQueries({ queryKey: ["epics", projectId] });
      toast.show("티켓 생성됨");
      onDone();
    },
  });

  if (isLoading) return <Spinner label="에픽 로드 중" />;
  if (error) return <ErrorState message={String((error as Error).message)} />;

  function validate(): boolean {
    const e: Record<string, string> = {};
    if (!title.trim()) e.title = "제목을 입력하세요";
    setErrors(e);
    return Object.keys(e).length === 0;
  }

  return (
    <form
      className="mx-auto max-w-xl space-y-4 p-4"
      onSubmit={(ev) => {
        ev.preventDefault();
        if (validate()) create.mutate();
      }}
      onKeyDown={(ev) => {
        if (isCmdEnter(ev)) {
          ev.preventDefault();
          if (validate()) create.mutate();
        }
      }}
    >
      <h2 className="text-base font-semibold">새 티켓</h2>

      <fieldset className="flex gap-4" aria-label="타입">
        <legend className="sr-only">타입</legend>
        {(["task", "epic"] as TicketType[]).map((t) => (
          <label key={t} className="flex items-center gap-1.5 text-sm">
            <input
              type="radio"
              name="type"
              checked={type === t}
              onChange={() => setType(t)}
            />
            {t === "task" ? "Task" : "Epic"}
          </label>
        ))}
      </fieldset>

      <div>
        <label className="block text-sm font-medium" htmlFor="f-title">
          제목
        </label>
        <input
          id="f-title"
          className="mt-1 w-full rounded border border-border3 bg-surface px-2 py-1.5 text-sm"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          aria-invalid={!!errors.title}
          aria-describedby={errors.title ? "err-title" : undefined}
        />
        {errors.title && (
          <p id="err-title" className="mt-1 text-xs text-danger" aria-live="polite">
            {errors.title}
          </p>
        )}
      </div>

      <div>
        <label className="block text-sm font-medium" htmlFor="f-desc">
          설명
        </label>
        <textarea
          id="f-desc"
          className="mt-1 w-full rounded border border-border3 bg-surface px-2 py-1.5 text-sm"
          rows={4}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
      </div>

      {type === "task" && (
        <div>
          <label className="block text-sm font-medium" htmlFor="f-epic">
            에픽(선택)
          </label>
          <select
            id="f-epic"
            className="mt-1 w-full rounded border border-border3 bg-surface px-2 py-1.5 text-sm"
            value={parentId}
            onChange={(e) => setParentId(e.target.value === "" ? "" : Number(e.target.value))}
          >
            <option value="">없음</option>
            {epics?.map((ep) => (
              <option key={ep.id} value={ep.id}>
                #{ep.id} {ep.title}
              </option>
            ))}
          </select>
        </div>
      )}

      <div>
        <label className="block text-sm font-medium" htmlFor="f-prio">
          우선순위
        </label>
        <input
          id="f-prio"
          type="number"
          min={0}
          className="mt-1 w-24 rounded border border-border3 bg-surface px-2 py-1.5 text-sm"
          value={priority}
          onChange={(e) => setPriority(Number(e.target.value))}
        />
      </div>

      <div className="flex gap-2">
        <button
          type="submit"
          className="rounded bg-cta px-4 py-1.5 text-sm font-medium text-white disabled:opacity-50"
          disabled={create.isPending}
        >
          {create.isPending ? "생성 중…" : "생성"}
        </button>
        <button
          type="button"
          className="rounded border border-border3 px-4 py-1.5 text-sm"
          onClick={onDone}
        >
          취소
        </button>
      </div>
      {create.isError && (
        <p className="text-xs text-danger" aria-live="assertive">
          생성 실패: {String((create.error as Error).message)}
        </p>
      )}
    </form>
  );
}
