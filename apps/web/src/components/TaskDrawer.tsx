import { useEffect, useState } from "react";
import { api } from "../api";
import type { Project, Task, TaskStatus } from "../types";
import { STATUS_LABEL } from "../types";
import { InlineAdd } from "../views/TodayView";

interface Props {
  taskId: string;
  onClose: () => void;
  onChanged: () => void;
  onOpenTask: (id: string) => void;
}

type Draft = Pick<
  Task,
  "title" | "description" | "notes" | "priority" | "estimate_minutes" | "actual_minutes" | "project_id" | "area" | "due_date" | "recurrence"
> & { tags: string };

function toDraft(t: Task): Draft {
  return {
    title: t.title,
    description: t.description,
    notes: t.notes,
    priority: t.priority,
    estimate_minutes: t.estimate_minutes,
    actual_minutes: t.actual_minutes,
    project_id: t.project_id,
    area: t.area,
    due_date: t.due_date,
    recurrence: t.recurrence,
    tags: t.tags.join(" "),
  };
}

export function TaskDrawer({ taskId, onClose, onChanged, onOpenTask }: Props) {
  const [task, setTask] = useState<Task | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [subtasks, setSubtasks] = useState<Task[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    Promise.all([api.task(taskId), api.tasks({ parent_id: taskId }), api.projects()])
      .then(([t, subs, ps]) => {
        if (!alive) return;
        setTask(t);
        setDraft(toDraft(t));
        setSubtasks(subs);
        setProjects(ps);
      })
      .catch((e: Error) => setError(e.message));
    return () => {
      alive = false;
    };
  }, [taskId]);

  if (!task || !draft) {
    return (
      <div className="drawer" role="dialog" aria-label="Task">
        {error ? <p className="error">{error}</p> : "Loading…"}
      </div>
    );
  }

  const save = async () => {
    try {
      const updated = await api.updateTask(task.id, {
        ...draft,
        area: draft.area || null,
        due_date: draft.due_date || null,
        recurrence: draft.recurrence || null,
        tags: draft.tags.split(/[\s,]+/).filter(Boolean),
      } as Partial<Task>);
      setTask(updated);
      setDraft(toDraft(updated));
      setError(null);
      onChanged();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const move = async (status: TaskStatus) => {
    try {
      setTask(await api.moveTask(task.id, { status }));
      onChanged();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const reloadSubs = async () => setSubtasks(await api.tasks({ parent_id: task.id }));
  const set = <K extends keyof Draft>(k: K, v: Draft[K]) => setDraft({ ...draft, [k]: v });
  const numOrNull = (v: string) => (v === "" ? null : Math.max(0, Number(v)));

  return (
    <>
      <div className="scrim" onClick={onClose} />
      <aside className="drawer" role="dialog" aria-label={`Task: ${task.title}`}>
        <div className="drawer-head">
          <input className="title-input" value={draft.title} onChange={(e) => set("title", e.target.value)} onBlur={save} />
          <button className="ghost" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </div>
        {error && <p className="error">{error}</p>}

        <div className="status-row">
          {(Object.keys(STATUS_LABEL) as TaskStatus[]).map((s) => (
            <button key={s} className={task.status === s ? "primary" : ""} onClick={() => move(s)}>
              {STATUS_LABEL[s]}
            </button>
          ))}
        </div>
        <div className="hint">
          {task.scheduled_date ? `Scheduled ${task.scheduled_date}` : "Not scheduled"}
          {task.completed_at && ` · completed ${new Date(task.completed_at).toLocaleString()}`}
        </div>

        <div className="field-grid">
          <label>
            Priority
            <select value={draft.priority} onChange={(e) => set("priority", Number(e.target.value))} onBlur={save}>
              {[1, 2, 3, 4].map((p) => (
                <option key={p} value={p}>
                  P{p}
                </option>
              ))}
            </select>
          </label>
          <label>
            Estimate (min)
            <input type="number" min={0} value={draft.estimate_minutes ?? ""} onChange={(e) => set("estimate_minutes", numOrNull(e.target.value))} onBlur={save} />
          </label>
          <label>
            Actual (min)
            <input type="number" min={0} value={draft.actual_minutes} onChange={(e) => set("actual_minutes", numOrNull(e.target.value) ?? 0)} onBlur={save} />
          </label>
          <label>
            Due
            <input type="date" value={draft.due_date ?? ""} onChange={(e) => set("due_date", e.target.value || null)} onBlur={save} />
          </label>
          <label>
            Project
            <select value={draft.project_id ?? ""} onChange={(e) => set("project_id", e.target.value || null)} onBlur={save}>
              <option value="">—</option>
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Area
            <input value={draft.area ?? ""} onChange={(e) => set("area", e.target.value)} onBlur={save} />
          </label>
          <label className="wide">
            Tags
            <input value={draft.tags} placeholder="space separated" onChange={(e) => set("tags", e.target.value)} onBlur={save} />
          </label>
          <label className="wide">
            Recurrence (RRULE, expansion arrives in Phase 3)
            <input value={draft.recurrence ?? ""} placeholder="FREQ=WEEKLY;BYDAY=MO" onChange={(e) => set("recurrence", e.target.value)} onBlur={save} />
          </label>
        </div>

        <label className="block">
          Description
          <textarea rows={4} value={draft.description} onChange={(e) => set("description", e.target.value)} onBlur={save} />
        </label>
        <label className="block">
          Notes / evidence
          <textarea rows={4} value={draft.notes} onChange={(e) => set("notes", e.target.value)} onBlur={save} />
        </label>

        <h3>Subtasks</h3>
        {subtasks.map((s) => (
          <div key={s.id} className="subtask">
            <input
              type="checkbox"
              checked={s.status === "done"}
              onChange={async () => {
                await api.moveTask(s.id, { status: s.status === "done" ? "planned" : "done" });
                await reloadSubs();
              }}
              aria-label={`Toggle ${s.title}`}
            />
            <button className="link" onClick={() => onOpenTask(s.id)}>
              {s.title}
            </button>
          </div>
        ))}
        <InlineAdd
          placeholder="+ Add subtask"
          onAdd={async (title) => {
            await api.createTask({ title, parent_id: task.id });
            await reloadSubs();
          }}
        />

        <div className="drawer-foot">
          {task.parent_id && (
            <button className="link" onClick={() => onOpenTask(task.parent_id!)}>
              ↑ Parent task
            </button>
          )}
          <button
            className="danger"
            onClick={async () => {
              if (!confirm(`Delete "${task.title}" and its subtasks?`)) return;
              await api.deleteTask(task.id);
              onChanged();
              onClose();
            }}
          >
            Delete
          </button>
        </div>
      </aside>
    </>
  );
}
