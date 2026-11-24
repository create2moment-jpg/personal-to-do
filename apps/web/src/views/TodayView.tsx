import {
  DndContext,
  type DragEndEvent,
  type DragOverEvent,
  DragOverlay,
  type DragStartEvent,
  KeyboardSensor,
  PointerSensor,
  useDroppable,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import { SortableContext, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { AnimatePresence, motion } from "framer-motion";
import {
  AlertTriangle,
  ArrowRight,
  BookOpen,
  CalendarClock,
  CalendarCheck2,
  ChevronLeft,
  ChevronRight,
  CircleCheckBig,
  Gauge,
  Inbox,
  MoonStar,
  Phone,
  Plus,
  Sparkles,
  Wand2,
} from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "sonner";
import { MeetingRow } from "../components/meetings";
import { ProgressRing, StatusDot } from "../components/primitives";
import { SortableTaskCard, TaskCard } from "../components/TaskCard";
import { api } from "../lib/api";
import { celebrate } from "../lib/celebrate";
import { columnCoordinates, inputAwareCollision } from "../lib/dnd";
import { invalidateTasks, queryClient, useCreateTask, useMoveTask, useProjects, useTasks, useToday } from "../lib/queries";
import { STATUS_LABEL, type DailyReview, type Meeting, type Task, type TaskStatus } from "../lib/types";
import { useUi } from "../lib/ui-store";
import { addDays, cx, formatMinutes, greeting, greetingEmoji, isoDay, positionBetween, prettyDay } from "../lib/util";

const COLUMNS: TaskStatus[] = ["planned", "in_progress", "blocked", "done"];
const COLUMN_LABEL: Record<string, string> = { planned: "Planned", in_progress: "In progress", blocked: "Blocked", done: "Done" };
const COLUMN_EMPTY: Record<string, string> = {
  planned: "Drag work here from the backlog",
  in_progress: "Start something — drag it here",
  blocked: "Nothing waiting. Nice.",
  done: "Finished work lands here",
};

const boardCoordinates = columnCoordinates(() => ["backlog", ...COLUMNS]);

export function TodayView() {
  const ui = useUi();
  const [day, setDay] = useState(isoDay());
  const isToday = day === isoDay();
  const { data, isLoading } = useToday(day);
  const { data: backlog = [] } = useTasks({ status: "backlog", top_level: true });
  const { data: projects = [] } = useProjects();
  const move = useMoveTask(day);
  const create = useCreateTask();
  const [activeTask, setActiveTask] = useState<Task | null>(null);
  const [collision] = useState(inputAwareCollision);
  const [overContainer, setOverContainer] = useState<string | null>(null);
  const [showReview, setShowReview] = useState(false);

  const projectById = useMemo(() => new Map(projects.map((p) => [p.id, p])), [projects]);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor, { coordinateGetter: boardCoordinates, keyboardCodes: { start: ["Space"], cancel: ["Escape"], end: ["Space", "Enter"] } }),
  );

  const columns = useMemo(() => {
    const surfaced = new Set((data?.due_today_unscheduled ?? []).map((t) => t.id));
    const result: Record<string, Task[]> = { backlog: backlog.filter((t) => !surfaced.has(t.id)).sort((a, b) => a.priority - b.priority || a.position - b.position) };
    for (const s of COLUMNS) result[s] = (data?.tasks ?? []).filter((t) => t.parent_id === null && t.status === s).sort((a, b) => a.position - b.position);
    return result;
  }, [data, backlog]);

  const subtaskCounts = useMemo(() => {
    const m = new Map<string, { done: number; total: number }>();
    for (const t of data?.tasks ?? []) {
      if (!t.parent_id) continue;
      const c = m.get(t.parent_id) ?? { done: 0, total: 0 };
      c.total++;
      if (t.status === "done") c.done++;
      m.set(t.parent_id, c);
    }
    return m;
  }, [data]);

  if (isLoading || !data) return <div className="page faint">Loading…</div>;

  const plan = data.plan;
  const cap = data.capacity;
  const topLevel = data.tasks.filter((t) => t.parent_id === null);
  const doneCount = topLevel.filter((t) => t.status === "done").length;
  const progress = topLevel.length ? doneCount / topLevel.length : 0;
  const loadPct = cap.capacity_minutes ? Math.min(1, cap.planned_minutes / cap.capacity_minutes) : 1;

  const containerOf = (id: string): string | undefined => {
    if (id in columns) return id;
    return Object.keys(columns).find((k) => columns[k]!.some((t) => t.id === id));
  };

  const setStar = (t: Task) => {
    const ids = plan.top_priority_ids;
    const next = ids.includes(t.id) ? ids.filter((i) => i !== t.id) : [...ids, t.id];
    if (next.length > 3) {
      toast("Three top priorities max", { description: "Unstar one first — focus is the point." });
      return;
    }
    api.updateDay(day, { top_priority_ids: next }).then(() => invalidateTasks());
  };

  const toggleDone = (t: Task) => {
    const prev = t.status;
    const next: TaskStatus = prev === "done" ? "planned" : "done";
    move.mutate(
      { id: t.id, status: next, scheduled_date: t.scheduled_date ?? day },
      {
        onSuccess: () => {
          if (next !== "done") return;
          const remainingTop = plan.top_priority_ids.filter((id) => id !== t.id && topLevel.find((x) => x.id === id)?.status !== "done");
          const allTop = remainingTop.length === 0 && plan.top_priority_ids.includes(t.id);
          if (allTop) celebrate("top3");
          toast.success(allTop ? "🎉 All top priorities done" : "Completed", {
            description: t.title,
            action: { label: "Undo", onClick: () => move.mutate({ id: t.id, status: prev }) },
          });
        },
      },
    );
  };

  const onDragStart = (e: DragStartEvent) => {
    collision.track(e.activatorEvent);
    setActiveTask((e.active.data.current?.task as Task) ?? null);
  };
  const onDragOver = (e: DragOverEvent) => setOverContainer(e.over ? (containerOf(String(e.over.id)) ?? null) : null);
  const onDragEnd = (e: DragEndEvent) => {
    setActiveTask(null);
    setOverContainer(null);
    const { active, over } = e;
    if (!over) return;
    const from = containerOf(String(active.id));
    const to = containerOf(String(over.id));
    if (!to || !from) return;
    const list = columns[to]!.filter((t) => t.id !== active.id);
    let index = list.findIndex((t) => t.id === over.id);
    if (index === -1) index = list.length;
    else if (from === to) {
      const oldIndex = columns[to]!.findIndex((t) => t.id === active.id);
      const overIndex = columns[to]!.findIndex((t) => t.id === over.id);
      if (oldIndex < overIndex) index += 1;
    }
    const position = positionBetween(list[index - 1]?.position, list[index]?.position);
    if (to === "backlog") {
      if (from !== "backlog") move.mutate({ id: String(active.id), status: "backlog", position });
      return;
    }
    if (from === to && position === columns[to]!.find((t) => t.id === active.id)?.position) return;
    move.mutate({ id: String(active.id), status: to as TaskStatus, scheduled_date: day, position });
  };

  const card = (t: Task, containerId: string) => (
    <SortableTaskCard
      key={t.id}
      containerId={containerId}
      task={t}
      project={t.project_id ? projectById.get(t.project_id) : undefined}
      subtasks={subtaskCounts.get(t.id)}
      starred={plan.top_priority_ids.includes(t.id)}
      onOpen={ui.openTask}
      onToggleDone={containerId === "backlog" ? undefined : toggleDone}
      onToggleStar={containerId === "backlog" ? undefined : setStar}
      showSchedule={containerId === "backlog"}
    />
  );

  return (
    <div className="page wide">
      <header className="hero">
        <div>
          <div className="hero-greeting">
            {isToday ? `${greetingEmoji()} ${greeting()}` : "Planning"}
            <span className="faint">·</span>
            <div style={{ display: "inline-flex", gap: 2 }}>
              <button className="btn icon sm ghost" aria-label="Previous day" onClick={() => setDay(addDays(day, -1))}>
                <ChevronLeft />
              </button>
              {!isToday && (
                <button className="btn sm ghost" onClick={() => setDay(isoDay())}>
                  Back to today
                </button>
              )}
              <button className="btn icon sm ghost" aria-label="Next day" onClick={() => setDay(addDays(day, 1))}>
                <ChevronRight />
              </button>
            </div>
          </div>
          <h1 className="hero-title">{prettyDay(day)}</h1>
          <ObjectiveInput key={`${day}-${plan.objective}`} day={day} value={plan.objective} />
        </div>
        <div className="hero-stats">
          <ProgressRing value={progress} label={`${doneCount} of ${topLevel.length} tasks done`} />
          <div className={cx("stat", cap.overcommitted && "warn")}>
            <div className="stat-label">
              <Gauge /> Planned focus
              {plan.capacity_mode === "manual" ? (
                <button
                  className="chip"
                  style={{ cursor: "pointer", marginLeft: "auto" }}
                  title="Capacity was set by hand — click to compute it from working hours and meetings again"
                  onClick={() => api.updateDay(day, { capacity_mode: "auto" }).then(() => invalidateTasks())}
                >
                  manual · reset
                </button>
              ) : (
                <span
                  className="chip accent"
                  style={{ marginLeft: "auto" }}
                  title={data.time ? `Working hours ${formatMinutes(data.time.work_minutes)} − meetings ${formatMinutes(data.time.meeting_minutes)} − buffer` : "Working hours − meetings − buffer"}
                >
                  auto
                </span>
              )}
            </div>
            <div className="stat-value">
              {formatMinutes(cap.planned_minutes)}
              <small>
                {" / "}
                <CapacityInput day={day} value={plan.capacity_minutes} />h
              </small>
            </div>
            <div className="capacity-track">
              <motion.i
                initial={false}
                animate={{ width: `${loadPct * 100}%` }}
                style={{ background: cap.overcommitted ? "var(--red)" : loadPct > 0.85 ? "var(--orange)" : "var(--green)" }}
              />
            </div>
          </div>
          <div className="stat">
            <div className="stat-label">
              <CircleCheckBig /> Done
            </div>
            <div className="stat-value">
              {doneCount}
              <small> tasks · {formatMinutes(cap.done_minutes)}</small>
            </div>
          </div>
        </div>
      </header>

      <AnimatePresence>
        {cap.overcommitted && (
          <motion.div className="alert-strip" style={{ marginBottom: 16 }} initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }}>
            <AlertTriangle /> You’ve planned {formatMinutes(-cap.remaining_capacity)} more than your capacity. Move something back to the backlog or tomorrow.
            {cap.unestimated_count > 0 && <span className="faint"> ({cap.unestimated_count} unestimated task(s) counted as 30m)</span>}
          </motion.div>
        )}
      </AnimatePresence>

      {(data.meetings.length > 0 || isToday) && <TodayMeetings meetings={data.meetings} minutes={data.time?.meeting_minutes_total ?? 0} />}

      <DndContext sensors={sensors} collisionDetection={collision.detect} onDragStart={onDragStart} onDragOver={onDragOver} onDragEnd={onDragEnd} onDragCancel={() => setActiveTask(null)}>
        <div className="today-layout">
          <aside className="tray">
            {data.overdue.length > 0 && (
              <div className="tray-panel" style={{ borderColor: "color-mix(in srgb, var(--red) 30%, var(--border))" }}>
                <div className="tray-head">
                  <span className="section-label" style={{ color: "var(--red)" }}>
                    Overdue · {data.overdue.length}
                  </span>
                  <button
                    className="btn sm ghost"
                    onClick={() => Promise.all(data.overdue.map((t) => api.moveTask(t.id, { scheduled_date: day }))).then(() => invalidateTasks())}
                  >
                    Move all to today <ArrowRight />
                  </button>
                </div>
                {data.overdue.map((t) => (
                  <TaskCard key={t.id} task={t} onOpen={ui.openTask} showSchedule project={t.project_id ? projectById.get(t.project_id) : undefined} />
                ))}
              </div>
            )}
            {data.due_today_unscheduled.length > 0 && (
              <div className="tray-panel">
                <div className="tray-head">
                  <span className="section-label">Due, not planned</span>
                </div>
                {data.due_today_unscheduled.map((t) => (
                  <TaskCard key={t.id} task={t} onOpen={ui.openTask} project={t.project_id ? projectById.get(t.project_id) : undefined} />
                ))}
              </div>
            )}
            <DroppablePanel id="backlog" active={overContainer === "backlog" && activeTask?.status !== "backlog"}>
              <div className="tray-head">
                <span className="section-label" style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <Inbox size={13} /> Backlog · {columns.backlog!.length}
                </span>
                <button className="btn sm ghost" onClick={() => ui.navigate("backlog")}>
                  All <ArrowRight />
                </button>
              </div>
              <SortableContext id="backlog" items={columns.backlog!.map((t) => t.id)} strategy={verticalListSortingStrategy}>
                {columns.backlog!.slice(0, 40).map((t) => card(t, "backlog"))}
              </SortableContext>
              {columns.backlog!.length === 0 && <div className="column-empty">Backlog is clear</div>}
            </DroppablePanel>
          </aside>

          <div className="board">
            {COLUMNS.map((status) => {
              const tasks = columns[status]!;
              const mins = tasks.reduce((s, t) => s + (t.estimate_minutes ?? 0), 0);
              return (
                <DroppableColumn key={status} id={status} active={overContainer === status && activeTask?.status !== status}>
                  <div className="column-head">
                    <StatusDot status={status} /> {COLUMN_LABEL[status]} <span className="count">{tasks.length}</span>
                    {mins > 0 && <span className="mins">{formatMinutes(mins)}</span>}
                  </div>
                  <SortableContext id={status} items={tasks.map((t) => t.id)} strategy={verticalListSortingStrategy}>
                    <AnimatePresence initial={false}>
                      {tasks.map((t) => (
                        <motion.div key={t.id} layout="position" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, scale: 0.96 }} transition={{ duration: 0.18 }}>
                          {card(t, status)}
                        </motion.div>
                      ))}
                    </AnimatePresence>
                  </SortableContext>
                  {tasks.length === 0 && <div className="column-empty">{COLUMN_EMPTY[status]}</div>}
                  {status === "planned" && <AddRow onAdd={(title) => create.mutateAsync({ title, scheduled_date: day })} />}
                </DroppableColumn>
              );
            })}
          </div>
        </div>

        <DragOverlay dropAnimation={{ duration: 180, easing: "cubic-bezier(0.2, 0.8, 0.2, 1)" }}>
          {activeTask && <TaskCard task={activeTask} overlay onOpen={() => {}} project={activeTask.project_id ? projectById.get(activeTask.project_id) : undefined} />}
        </DragOverlay>
      </DndContext>

      <div className="day-actions">
        <button
          className="btn"
          onClick={async () => {
            const j = await api.journal(day);
            ui.navigate("notes", j.id);
          }}
        >
          <BookOpen /> {data.journal ? "Open journal" : "Start today’s journal"}
        </button>
        <button className={cx("btn", showReview && "primary")} onClick={() => setShowReview((s) => !s)}>
          <MoonStar /> {plan.review.completed_at ? "Review complete" : "End-of-day review"}
        </button>
        <button
          className="btn ghost"
          title="Move unfinished tasks to the next day"
          onClick={async () => {
            const moved = await api.rollOver(day);
            invalidateTasks();
            toast.success(moved.length ? `Moved ${moved.length} task(s) to ${prettyDay(addDays(day, 1))}` : "Nothing to roll over");
          }}
        >
          <CalendarCheck2 /> Roll unfinished to tomorrow
        </button>
      </div>

      <AnimatePresence>
        {showReview && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 8 }}>
            <ReviewCard day={day} review={plan.review} tasks={topLevel} />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function DroppableColumn({ id, active, children }: { id: string; active: boolean; children: React.ReactNode }) {
  const { setNodeRef } = useDroppable({ id, data: { container: id } });
  return (
    <section ref={setNodeRef} className={cx("column", active && "drop-active")} aria-label={STATUS_LABEL[id as TaskStatus]}>
      {children}
    </section>
  );
}

function DroppablePanel({ id, active, children }: { id: string; active: boolean; children: React.ReactNode }) {
  const { setNodeRef } = useDroppable({ id, data: { container: id } });
  return (
    <section ref={setNodeRef} className={cx("tray-panel", active && "drop-active")} aria-label="Backlog">
      {children}
    </section>
  );
}

function ObjectiveInput({ day, value }: { day: string; value: string }) {
  const [v, setV] = useState(value);
  return (
    <input
      className="objective-input"
      value={v}
      placeholder="Set today’s objective — what would make today a win?"
      aria-label="Daily objective"
      onChange={(e) => setV(e.target.value)}
      onBlur={() => v !== value && api.updateDay(day, { objective: v }).then(() => queryClient.invalidateQueries({ queryKey: ["today"] }))}
      onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
    />
  );
}

function CapacityInput({ day, value }: { day: string; value: number }) {
  return (
    <input
      key={`${day}-${value}`}
      className="capacity-input tnum"
      type="number"
      min={0}
      max={24}
      step={0.5}
      defaultValue={Math.round(value / 6) / 10}
      aria-label="Capacity in hours"
      title="Focus capacity (hours)"
      onBlur={(e) => {
        const mins = Math.round(Number(e.target.value) * 60);
        if (mins !== value && mins >= 0 && mins <= 1440) api.updateDay(day, { capacity_minutes: mins }).then(() => invalidateTasks());
      }}
      onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
    />
  );
}

export function AddRow({ onAdd, placeholder = "Add task" }: { onAdd: (title: string) => Promise<unknown>; placeholder?: string }) {
  const [value, setValue] = useState("");
  return (
    <label className="add-row">
      <Plus />
      <input
        value={value}
        placeholder={placeholder}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={async (e) => {
          if (e.key === "Enter" && value.trim()) {
            const v = value.trim();
            setValue("");
            await onAdd(v);
          }
        }}
      />
    </label>
  );
}

const REVIEW_FIELDS: { key: keyof Omit<DailyReview, "completed_at">; label: string; placeholder: string; full?: boolean }[] = [
  { key: "wins", label: "Wins", placeholder: "What went well? What are you proud of?" },
  { key: "learning", label: "What I learned", placeholder: "Insights, techniques, surprises…" },
  { key: "unfinished", label: "Unfinished", placeholder: "What didn’t get done, and why?" },
  { key: "blockers", label: "Blockers", placeholder: "What slowed you down?" },
  { key: "tomorrow_first_task", label: "Tomorrow’s first task", placeholder: "The one thing to start with", full: true },
];

function ReviewCard({ day, review, tasks }: { day: string; review: DailyReview; tasks: Task[] }) {
  const [form, setForm] = useState<Omit<DailyReview, "completed_at">>(review);
  const completed = tasks.filter((t) => t.status === "done");

  const save = async (complete: boolean) => {
    await api.saveReview(day, { ...form, complete });
    void queryClient.invalidateQueries({ queryKey: ["today"] });
    toast.success(complete ? "🌙 Day closed. See you tomorrow." : "Review saved");
  };

  return (
    <section className="card review-card">
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
        <div>
          <h3 style={{ fontSize: "1.2143rem", fontWeight: 650 }}>End-of-day review</h3>
          <div className="muted" style={{ fontSize: "0.9286rem", marginTop: 2 }}>
            {completed.length} completed ·{" "}
            {completed
              .slice(0, 4)
              .map((t) => t.title)
              .join(" · ") || "nothing completed yet"}
          </div>
        </div>
        <button
          className="btn"
          onClick={async () => {
            const d = await api.reviewDraft(day);
            setForm((f) => ({
              ...f,
              unfinished: f.unfinished || d.unfinished,
              blockers: f.blockers || d.blockers,
              tomorrow_first_task: f.tomorrow_first_task || d.tomorrow_first_task,
            }));
            toast("Pre-filled from today’s board");
          }}
        >
          <Wand2 /> Pre-fill from today
        </button>
      </div>
      <div className="review-grid">
        {REVIEW_FIELDS.map(({ key, label, placeholder, full }) => (
          <label key={key} className={full ? "full" : undefined}>
            {label}
            {full ? (
              <input className="input" value={form[key]} placeholder={placeholder} onChange={(e) => setForm({ ...form, [key]: e.target.value })} />
            ) : (
              <textarea className="textarea" rows={3} value={form[key]} placeholder={placeholder} onChange={(e) => setForm({ ...form, [key]: e.target.value })} />
            )}
          </label>
        ))}
      </div>
      <div style={{ display: "flex", gap: 8, marginTop: 16, alignItems: "center" }}>
        <button className="btn primary" onClick={() => save(true)}>
          <Sparkles /> Complete review
        </button>
        <button className="btn ghost" onClick={() => save(false)}>
          Save draft
        </button>
        {review.completed_at && <span className="faint" style={{ fontSize: "0.8571rem" }}>Completed {new Date(review.completed_at).toLocaleTimeString()}</span>}
      </div>
    </section>
  );
}

function TodayMeetings({ meetings, minutes }: { meetings: Meeting[]; minutes: number }) {
  const ui = useUi();
  const [open, setOpen] = useState(true);
  return (
    <section className="card" style={{ padding: "10px 12px", marginBottom: 16 }}>
      <div className="tray-head" style={{ padding: "0 2px 6px" }}>
        <button className="btn sm ghost" style={{ paddingLeft: 2 }} onClick={() => setOpen((o) => !o)} aria-expanded={open}>
          <CalendarClock /> <strong>Meetings today</strong>
          <span className="faint">
            {meetings.length} · {formatMinutes(minutes)}
          </span>
        </button>
        <div style={{ display: "flex", gap: 4 }}>
          <button className="btn sm ghost" onClick={() => ui.navigate("meetings")}>
            Insights
          </button>
          <button className="btn sm" onClick={() => ui.openLogCall()}>
            <Phone /> Log call
          </button>
        </div>
      </div>
      {open &&
        (meetings.length === 0 ? (
          <div className="faint" style={{ fontSize: "0.8929rem", padding: "2px 4px 4px" }}>
            No meetings today — a full day for focus. Import your calendar on the Meetings page to see recurring meetings here.
          </div>
        ) : (
          <div className="meeting-list">
            {meetings.map((m) => (
              <MeetingRow key={m.id} m={m} />
            ))}
          </div>
        ))}
    </section>
  );
}
