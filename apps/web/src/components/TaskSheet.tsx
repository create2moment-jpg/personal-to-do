import { useQueryClient } from "@tanstack/react-query";
import {
  AlarmClock,
  CalendarClock,
  ChevronUp,
  Clock,
  Flag,
  FolderKanban,
  Hash,
  Hourglass,
  MapPin,
  Plus,
  Repeat,
  Rocket,
  Trash2,
  X,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { api } from "../lib/api";
import { invalidateTasks, keys, useMoveTask, useProjects, useSprints, useTask, useTasks, useUpdateTask } from "../lib/queries";
import { STATUS_LABEL, type Task, type TaskStatus } from "../lib/types";
import { relativeTime } from "../lib/util";
import { Sheet, StatusDot } from "./primitives";

const STATUSES = Object.keys(STATUS_LABEL) as TaskStatus[];

export function TaskSheet({ taskId, onClose, onOpenTask }: { taskId: string | null; onClose: () => void; onOpenTask: (id: string) => void }) {
  return (
    <Sheet open={taskId !== null} onClose={onClose} label="Task details">
      {taskId && <TaskSheetBody key={taskId} taskId={taskId} onClose={onClose} onOpenTask={onOpenTask} />}
    </Sheet>
  );
}

function TaskSheetBody({ taskId, onClose, onOpenTask }: { taskId: string; onClose: () => void; onOpenTask: (id: string) => void }) {
  const qc = useQueryClient();
  const { data: task } = useTask(taskId);
  const { data: subtasks = [] } = useTasks({ parent_id: taskId });
  const { data: projects = [] } = useProjects();
  const { data: sprints = [] } = useSprints();
  const update = useUpdateTask();
  const move = useMoveTask();
  const [title, setTitle] = useState("");
  const [newSub, setNewSub] = useState("");
  const titleRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (task) setTitle(task.title);
  }, [task?.title]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!task) return <div className="sheet-body faint">Loading…</div>;

  const save = (changes: Partial<Task>) => update.mutate({ id: task.id, changes });
  const field = <K extends keyof Task>(k: K) => ({
    defaultValue: (task[k] ?? "") as string | number,
    key: `${k}-${String(task[k])}`,
  });

  return (
    <>
      <div className="sheet-head">
        {task.parent_id && (
          <button className="btn sm ghost" onClick={() => onOpenTask(task.parent_id!)}>
            <ChevronUp /> Parent
          </button>
        )}
        <span className="faint" style={{ fontSize: "0.8571rem" }}>
          Updated {relativeTime(task.updated_at)}
        </span>
        <div style={{ marginLeft: "auto", display: "flex", gap: 4 }}>
          <button
            className="btn icon ghost danger"
            aria-label="Delete task"
            title="Delete task"
            onClick={async () => {
              if (!confirm(`Delete “${task.title}”${subtasks.length ? " and its subtasks" : ""}?`)) return;
              await api.deleteTask(task.id);
              invalidateTasks(qc);
              toast(`Deleted “${task.title}”`);
              onClose();
            }}
          >
            <Trash2 />
          </button>
          <button className="btn icon ghost" aria-label="Close" onClick={onClose}>
            <X />
          </button>
        </div>
      </div>

      <div className="sheet-body">
        <textarea
          ref={titleRef}
          className="sheet-title"
          rows={Math.min(4, Math.ceil(title.length / 38) || 1)}
          value={title}
          aria-label="Title"
          onChange={(e) => setTitle(e.target.value.replace(/\n/g, ""))}
          onBlur={() => title.trim() && title !== task.title && save({ title })}
          onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), titleRef.current?.blur())}
        />

        <div className="status-picker" style={{ marginTop: 14 }}>
          {STATUSES.map((s) => (
            <button
              key={s}
              aria-pressed={task.status === s}
              onClick={() =>
                move.mutate({ id: task.id, status: s }, { onSuccess: (t) => qc.setQueryData<Task>(keys.task(t.id), t) })
              }
            >
              <StatusDot status={s} /> {STATUS_LABEL[s]}
            </button>
          ))}
        </div>

        <div className="props">
          <Label icon={Flag} text="Priority" />
          <select className="select" value={task.priority} onChange={(e) => save({ priority: Number(e.target.value) })}>
            <option value={1}>P1 · Urgent</option>
            <option value={2}>P2 · High</option>
            <option value={3}>P3 · Medium</option>
            <option value={4}>P4 · None</option>
          </select>

          <Label icon={CalendarClock} text="Scheduled" />
          <input
            type="date"
            className="input"
            {...field("scheduled_date")}
            onChange={(e) =>
              move.mutate(
                e.target.value ? { id: task.id, scheduled_date: e.target.value } : { id: task.id, unschedule: true },
                { onSuccess: (t) => qc.setQueryData<Task>(keys.task(t.id), t) },
              )
            }
          />

          <Label icon={AlarmClock} text="Due" />
          <input type="date" className="input" {...field("due_date")} onChange={(e) => save({ due_date: e.target.value || null })} />

          <Label icon={Clock} text="Estimate" />
          <input
            type="number"
            min={0}
            step={5}
            className="input"
            placeholder="minutes"
            {...field("estimate_minutes")}
            onBlur={(e) => save({ estimate_minutes: e.target.value === "" ? null : Number(e.target.value) })}
          />

          <Label icon={Hourglass} text="Time spent" />
          <input type="number" min={0} step={5} className="input" placeholder="minutes" {...field("actual_minutes")} onBlur={(e) => save({ actual_minutes: Number(e.target.value || 0) })} />

          <Label icon={FolderKanban} text="Project" />
          <select className="select" value={task.project_id ?? ""} onChange={(e) => save({ project_id: e.target.value || null })}>
            <option value="">No project</option>
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>

          <Label icon={Rocket} text="Sprint" />
          <select
            className="select"
            value={task.sprint_id ? `${task.sprint_id}|${task.commitment ?? "committed"}` : ""}
            aria-label="Sprint"
            onChange={async (e) => {
              const v = e.target.value;
              if (!v) await api.removeFromSprint(task.id);
              else {
                const [sid, c] = v.split("|") as [string, "committed" | "stretch"];
                await api.addToSprint(sid, [task.id], c);
              }
              invalidateTasks(qc);
            }}
          >
            <option value="">Not in a sprint</option>
            {sprints
              .filter((s) => s.status !== "completed" || s.id === task.sprint_id)
              .flatMap((s) => [
                <option key={`${s.id}c`} value={`${s.id}|committed`}>
                  {s.name} · committed
                </option>,
                <option key={`${s.id}s`} value={`${s.id}|stretch`}>
                  {s.name} · stretch
                </option>,
              ])}
          </select>

          <Label icon={MapPin} text="Area" />
          <input className="input" placeholder="e.g. Engineering" {...field("area")} onBlur={(e) => save({ area: e.target.value || null })} />

          <Label icon={Hash} text="Tags" />
          <input
            className="input"
            placeholder="space separated"
            defaultValue={task.tags.join(" ")}
            key={task.tags.join(" ")}
            onBlur={(e) => save({ tags: e.target.value.split(/[\s,]+/).filter(Boolean) })}
          />

          <Label icon={Repeat} text="Repeats" />
          <input className="input" placeholder="RRULE, e.g. FREQ=WEEKLY;BYDAY=MO" {...field("recurrence")} onBlur={(e) => save({ recurrence: e.target.value || null })} />
        </div>

        <div className="section-label" style={{ margin: "18px 0 8px" }}>
          Description
        </div>
        <textarea className="textarea" rows={4} placeholder="Context, acceptance criteria, links…" {...field("description")} onBlur={(e) => save({ description: e.target.value })} />

        <div className="section-label" style={{ margin: "18px 0 8px" }}>
          Notes & evidence
        </div>
        <textarea className="textarea" rows={3} placeholder="What happened, outcomes, links to evidence…" {...field("notes")} onBlur={(e) => save({ notes: e.target.value })} />

        <div className="section-label" style={{ margin: "22px 0 4px", display: "flex", justifyContent: "space-between" }}>
          <span>Subtasks</span>
          <span>
            {subtasks.filter((s) => s.status === "done").length}/{subtasks.length}
          </span>
        </div>
        <div className="subtasks">
          {subtasks.map((s) => (
            <div key={s.id} className={s.status === "done" ? "subtask done" : "subtask"}>
              <input
                type="checkbox"
                className="check"
                checked={s.status === "done"}
                aria-label={`Toggle ${s.title}`}
                onChange={() => move.mutate({ id: s.id, status: s.status === "done" ? "planned" : "done" })}
              />
              <span onClick={() => onOpenTask(s.id)}>{s.title}</span>
            </div>
          ))}
          <div className="add-row">
            <Plus />
            <input
              value={newSub}
              placeholder="Add subtask"
              onChange={(e) => setNewSub(e.target.value)}
              onKeyDown={async (e) => {
                if (e.key === "Enter" && newSub.trim()) {
                  await api.createTask({ title: newSub.trim(), parent_id: task.id });
                  setNewSub("");
                  invalidateTasks(qc);
                }
              }}
            />
          </div>
        </div>
      </div>
      <div className="sheet-foot">
        <span>Created {new Date(task.created_at).toLocaleDateString(undefined, { dateStyle: "medium" })}</span>
        {task.completed_at && <span>Completed {relativeTime(task.completed_at)}</span>}
      </div>
    </>
  );
}

function Label({ icon: Icon, text }: { icon: typeof Flag; text: string }) {
  return (
    <div className="p-label">
      <Icon /> {text}
    </div>
  );
}
