import { useCallback, useEffect, useState, type DragEvent } from "react";
import { api } from "../api";
import { TaskCard, draggedTaskId } from "../components/TaskCard";
import type { DailyReview, Task, TaskStatus, Today } from "../types";
import { STATUS_LABEL } from "../types";
import { addDays, formatMinutes, isoDay, prettyDay } from "../util";

const COLUMNS: TaskStatus[] = ["planned", "in_progress", "blocked", "done"];

interface Props {
  revision: number;
  onChanged: () => void;
  onOpenTask: (id: string) => void;
}

export function TodayView({ revision, onChanged, onOpenTask }: Props) {
  const [day, setDay] = useState(isoDay());
  const [data, setData] = useState<Today | null>(null);
  const [backlog, setBacklog] = useState<Task[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [objective, setObjective] = useState("");
  const [showReview, setShowReview] = useState(false);

  const load = useCallback(async () => {
    try {
      const [t, b] = await Promise.all([api.today(day), api.tasks({ status: "backlog", top_level: true })]);
      setData(t);
      setObjective(t.plan.objective);
      setBacklog(b);
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }, [day]);

  useEffect(() => {
    void load();
  }, [load, revision]);

  const act = async (fn: () => Promise<unknown>) => {
    try {
      await fn();
      onChanged();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const onDrop = (status: TaskStatus) => (e: DragEvent) => {
    e.preventDefault();
    const id = draggedTaskId(e);
    if (id) void act(() => api.moveTask(id, { status, scheduled_date: day }));
  };

  const toggleDone = (t: Task) =>
    act(() => api.moveTask(t.id, { status: t.status === "done" ? "planned" : "done" }));

  const toggleStar = (t: Task) => {
    if (!data) return;
    const ids = data.plan.top_priority_ids;
    const next = ids.includes(t.id) ? ids.filter((i) => i !== t.id) : [...ids, t.id];
    if (next.length > 3) {
      setError("Pick at most three top priorities — that's the point.");
      return;
    }
    void act(() => api.updateDay(day, { top_priority_ids: next }));
  };

  if (!data) return <div className="view">{error ? <p className="error">{error}</p> : "Loading…"}</div>;

  const cap = data.capacity;
  const pct = cap.capacity_minutes ? Math.min(100, Math.round((cap.planned_minutes / cap.capacity_minutes) * 100)) : 100;
  const topLevel = data.tasks.filter((t) => t.parent_id === null);
  const isToday = day === isoDay();

  return (
    <div className="view today">
      <header className="view-head">
        <div>
          <h1>{isToday ? "Today" : prettyDay(day)}</h1>
          <div className="sub">{isToday ? prettyDay(day) : day}</div>
        </div>
        <div className="day-nav">
          <button onClick={() => setDay(addDays(day, -1))} aria-label="Previous day">
            ←
          </button>
          <button onClick={() => setDay(isoDay())} disabled={isToday}>
            Today
          </button>
          <button onClick={() => setDay(addDays(day, 1))} aria-label="Next day">
            →
          </button>
        </div>
      </header>

      {error && (
        <p className="error" role="alert" onClick={() => setError(null)}>
          {error}
        </p>
      )}

      <section className="plan-row">
        <label className="objective">
          <span>Daily objective</span>
          <input
            value={objective}
            placeholder="What would make today a success?"
            onChange={(e) => setObjective(e.target.value)}
            onBlur={() => objective !== data.plan.objective && void act(() => api.updateDay(day, { objective }))}
            onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
          />
        </label>
        <div className={`capacity ${cap.overcommitted ? "over" : ""}`}>
          <div className="capacity-label">
            <span>
              Planned {formatMinutes(cap.planned_minutes)} of{" "}
              <input
                className="cap-input"
                type="number"
                min={0}
                max={1440}
                step={30}
                defaultValue={data.plan.capacity_minutes}
                key={`${day}-${data.plan.capacity_minutes}`}
                aria-label="Capacity in minutes"
                onBlur={(e) => {
                  const v = Number(e.target.value);
                  if (v !== data.plan.capacity_minutes) void act(() => api.updateDay(day, { capacity_minutes: v }));
                }}
              />{" "}
              min
            </span>
            {cap.overcommitted && <strong>Overcommitted by {formatMinutes(-cap.remaining_capacity)}</strong>}
          </div>
          <div className="meter" role="meter" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
            <div style={{ width: `${pct}%` }} />
          </div>
          {cap.unestimated_count > 0 && (
            <div className="hint">{cap.unestimated_count} unestimated task(s) counted as 30m each</div>
          )}
        </div>
      </section>

      <div className="today-grid">
        <aside className="pull-panel">
          {data.overdue.length > 0 && (
            <TaskList title="Overdue — reschedule or drop" tasks={data.overdue} onOpen={onOpenTask} today={day} />
          )}
          {data.due_today_unscheduled.length > 0 && (
            <TaskList title="Due, not scheduled" tasks={data.due_today_unscheduled} onOpen={onOpenTask} today={day} />
          )}
          <TaskList
            title={`Backlog (${backlog.length}) — drag onto the board`}
            tasks={backlog.slice(0, 50)}
            onOpen={onOpenTask}
            today={day}
            onDrop={(e) => {
              e.preventDefault();
              const id = draggedTaskId(e);
              if (id) void act(() => api.moveTask(id, { status: "backlog" }));
            }}
          />
        </aside>

        <div className="board">
          {COLUMNS.map((status) => {
            const tasks = topLevel.filter((t) => t.status === status);
            return (
              <div key={status} className={`column col-${status}`} onDragOver={(e) => e.preventDefault()} onDrop={onDrop(status)}>
                <div className="column-head">
                  <span>{STATUS_LABEL[status]}</span>
                  <span className="count">{tasks.length}</span>
                </div>
                {tasks.map((t) => (
                  <div key={t.id} className="card-wrap">
                    <TaskCard
                      task={t}
                      onOpen={onOpenTask}
                      onToggleDone={toggleDone}
                      highlight={data.plan.top_priority_ids.includes(t.id)}
                      today={day}
                    />
                    {status !== "done" && (
                      <button
                        className="star-btn"
                        title="Toggle top priority"
                        aria-label="Toggle top priority"
                        onClick={() => toggleStar(t)}
                      >
                        {data.plan.top_priority_ids.includes(t.id) ? "★" : "☆"}
                      </button>
                    )}
                  </div>
                ))}
                {status === "planned" && <InlineAdd onAdd={(title) => act(() => api.createTask({ title, scheduled_date: day }))} />}
              </div>
            );
          })}
        </div>
      </div>

      <section className="day-foot">
        <button
          onClick={async () => {
            const j = await api.journal(day);
            window.location.hash = `/notes/${j.id}`;
          }}
        >
          {data.journal ? "Open journal" : "Start journal"}
        </button>
        <button onClick={() => setShowReview((s) => !s)}>
          {data.plan.review.completed_at ? "✓ Review done — edit" : "End-of-day review"}
        </button>
        <button
          onClick={() => void act(() => api.rollOver(day))}
          title="Move unfinished tasks to the next day"
        >
          Roll over unfinished →
        </button>
      </section>

      {showReview && <ReviewPanel day={day} review={data.plan.review} tasks={topLevel} onSaved={onChanged} />}
    </div>
  );
}

function TaskList(props: {
  title: string;
  tasks: Task[];
  onOpen: (id: string) => void;
  today: string;
  onDrop?: (e: DragEvent) => void;
}) {
  return (
    <div className="task-list" onDragOver={props.onDrop ? (e) => e.preventDefault() : undefined} onDrop={props.onDrop}>
      <h3>{props.title}</h3>
      {props.tasks.length === 0 && <div className="empty">Nothing here.</div>}
      {props.tasks.map((t) => (
        <TaskCard key={t.id} task={t} onOpen={props.onOpen} today={props.today} />
      ))}
    </div>
  );
}

export function InlineAdd({ onAdd, placeholder = "+ Add task" }: { onAdd: (title: string) => Promise<unknown>; placeholder?: string }) {
  const [value, setValue] = useState("");
  return (
    <input
      className="inline-add"
      value={value}
      placeholder={placeholder}
      onChange={(e) => setValue(e.target.value)}
      onKeyDown={async (e) => {
        if (e.key === "Enter" && value.trim()) {
          await onAdd(value.trim());
          setValue("");
        }
      }}
    />
  );
}

const REVIEW_FIELDS: { key: keyof Omit<DailyReview, "completed_at">; label: string }[] = [
  { key: "wins", label: "Wins" },
  { key: "unfinished", label: "Unfinished work" },
  { key: "blockers", label: "Blockers" },
  { key: "learning", label: "What I learned" },
  { key: "tomorrow_first_task", label: "Tomorrow's first task" },
];

function ReviewPanel({ day, review, tasks, onSaved }: { day: string; review: DailyReview; tasks: Task[]; onSaved: () => void }) {
  const [form, setForm] = useState<Omit<DailyReview, "completed_at">>(review);
  const [status, setStatus] = useState("");
  const completed = tasks.filter((t) => t.status === "done");

  const prefill = async () => {
    const d = await api.reviewDraft(day);
    setForm((f) => ({
      ...f,
      unfinished: f.unfinished || d.unfinished,
      blockers: f.blockers || d.blockers,
      tomorrow_first_task: f.tomorrow_first_task || d.tomorrow_first_task,
    }));
  };

  const save = async (complete: boolean) => {
    await api.saveReview(day, { ...form, complete });
    setStatus(complete ? "Review completed." : "Saved.");
    onSaved();
  };

  return (
    <section className="review-panel">
      <h2>End-of-day review</h2>
      <div className="completed-list">
        <strong>Completed ({completed.length}):</strong> {completed.map((t) => t.title).join(" · ") || "nothing yet"}
      </div>
      {REVIEW_FIELDS.map(({ key, label }) => (
        <label key={key}>
          <span>{label}</span>
          <textarea rows={key === "tomorrow_first_task" ? 1 : 3} value={form[key]} onChange={(e) => setForm({ ...form, [key]: e.target.value })} />
        </label>
      ))}
      <div className="actions">
        <button onClick={prefill}>Pre-fill from today's tasks</button>
        <button onClick={() => save(false)}>Save draft</button>
        <button className="primary" onClick={() => save(true)}>
          Complete review
        </button>
        <span className="hint">{status}</span>
      </div>
    </section>
  );
}
