import {
  DndContext,
  type DragEndEvent,
  DragOverlay,
  KeyboardSensor,
  PointerSensor,
  useDroppable,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import { SortableContext, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { useQuery } from "@tanstack/react-query";
import { CalendarPlus, ArrowRight, CalendarCheck2, CalendarRange, ChevronLeft, ChevronRight, ClipboardCheck, Rocket, Sparkles, Target } from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "sonner";
import { DayTimeChart } from "../components/charts";
import { EmojiPicker } from "../components/EmojiPicker";
import { EmptyState } from "../components/primitives";
import { SortableTaskCard, TaskCard } from "../components/TaskCard";
import { api } from "../lib/api";
import { celebrate } from "../lib/celebrate";
import { columnCoordinates, inputAwareCollision } from "../lib/dnd";
import { dropOutsideBoard } from "../lib/drop";
import { invalidateTasks, queryClient, useMoveTask, useProjects, useWeek } from "../lib/queries";
import type { Task, Week, WeeklyObjective } from "../lib/types";
import { useUi } from "../lib/ui-store";
import { addDays, clockTime, cx, formatMinutes, isoDay, mondayOf } from "../lib/util";
import { AddRow } from "./TodayView";
import { appendBullets, GroundedDraft } from "../components/GroundedDraft";

type Tab = "plan" | "review";

export function WeekView({ initialTab = "plan" }: { initialTab?: Tab }) {
  const [anchor, setAnchor] = useState(isoDay());
  const [tab, setTab] = useState<Tab>(initialTab);
  const monday = mondayOf(anchor);
  const { data: week } = useWeek(monday);
  const thisWeek = monday === mondayOf(isoDay());
  const range = `${fmt(monday)} – ${fmt(addDays(monday, 6))}`;

  return (
    <div className="page wide">
      <header className="page-head">
        <div>
          <div className="hero-greeting">
            {thisWeek ? "This week" : monday > mondayOf(isoDay()) ? "Upcoming week" : "Past week"}
            <span className="faint">·</span>
            <div style={{ display: "inline-flex", gap: 2 }}>
              <button className="btn icon sm ghost" aria-label="Previous week" onClick={() => setAnchor(addDays(monday, -7))}>
                <ChevronLeft />
              </button>
              {!thisWeek && (
                <button className="btn sm ghost" onClick={() => setAnchor(isoDay())}>
                  This week
                </button>
              )}
              <button className="btn icon sm ghost" aria-label="Next week" onClick={() => setAnchor(addDays(monday, 7))}>
                <ChevronRight />
              </button>
            </div>
          </div>
          <h1 className="page-title">{range}</h1>
          {week?.sprint && (
            <div className="page-sub" style={{ display: "flex", gap: 6, alignItems: "center" }}>
              <Rocket size={14} /> {week.sprint.name}
              {week.sprint.goal && <span className="faint">— {week.sprint.goal}</span>}
            </div>
          )}
        </div>
      </header>
      <div className="tabs" role="tablist">
        <button role="tab" aria-selected={tab === "plan"} onClick={() => setTab("plan")}>
          <CalendarRange /> Plan
        </button>
        <button role="tab" aria-selected={tab === "review"} onClick={() => setTab("review")}>
          <ClipboardCheck /> Weekly review
        </button>
      </div>
      {!week ? <div className="faint">Loading…</div> : tab === "plan" ? <WeekPlan week={week} /> : <WeekReviewPanel week={week} onPlanNext={() => { setAnchor(addDays(monday, 7)); setTab("plan"); }} />}
    </div>
  );
}

const fmt = (iso: string) => new Date(`${iso}T12:00:00Z`).toLocaleDateString(undefined, { month: "short", day: "numeric", timeZone: "UTC" });

function Objectives({ week }: { week: Week }) {
  const [items, setItems] = useState<WeeklyObjective[]>(() => {
    const o = [...week.plan.objectives];
    while (o.length < 3) o.push({ text: "", done: false });
    return o;
  });
  const save = (next: WeeklyObjective[]) =>
    api.updateWeek(week.week_start, { objectives: next.filter((o) => o.text.trim()) }).then(() => queryClient.invalidateQueries({ queryKey: ["week"] }));
  return (
    <section className="card panel" style={{ marginBottom: 14 }}>
      <h3>
        <Target size={16} /> Weekly objectives <span className="faint" style={{ fontWeight: 400, fontSize: "0.8929rem" }}>three outcomes that make this week a success</span>
      </h3>
      <div className="objectives">
        {items.map((o, i) => (
          <div key={i} className="objective-row">
            <input
              type="checkbox"
              className="check"
              checked={o.done}
              disabled={!o.text.trim()}
              aria-label={`Objective ${i + 1} done`}
              onChange={() => {
                const next = items.map((x, j) => (j === i ? { ...x, done: !x.done } : x));
                setItems(next);
                void save(next);
              }}
            />
            <EmojiPicker
              value={o.emoji}
              label={`Objective ${i + 1} emoji`}
              onChange={(e) => {
                const next = items.map((x, j) => (j === i ? { ...x, emoji: e } : x));
                setItems(next);
                void save(next);
              }}
            />
            <input
              className="input"
              value={o.text}
              placeholder={["e.g. Retrieval ADR approved", "e.g. Eval harness covers 4-bit model", "e.g. Mid-year self-review drafted"][i]}
              aria-label={`Objective ${i + 1}`}
              onChange={(e) => setItems(items.map((x, j) => (j === i ? { ...x, text: e.target.value } : x)))}
              onBlur={() => void save(items)}
              onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
            />
          </div>
        ))}
      </div>
    </section>
  );
}

function WeekPlan({ week }: { week: Week }) {
  const ui = useUi();
  const move = useMoveTask();
  const { data: projects = [] } = useProjects();
  const projectById = useMemo(() => new Map(projects.map((p) => [p.id, p])), [projects]);
  const [active, setActive] = useState<Task | null>(null);
  const [collision] = useState(inputAwareCollision);
  const [over, setOver] = useState<string | null>(null);
  const today = isoDay();
  const columnIds = useMemo(() => [...week.days.map((d) => d.day), "sprint-backlog"], [week]);
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor, { coordinateGetter: columnCoordinates(() => columnIds), keyboardCodes: { start: ["Space"], cancel: ["Escape"], end: ["Space", "Enter"] } }),
  );
  const containerOf = (id: string) => (columnIds.includes(id) ? id : (week.days.find((d) => d.tasks.some((t) => t.id === id))?.day ?? (week.sprint_backlog.some((t) => t.id === id) ? "sprint-backlog" : undefined)));

  const onDragEnd = (e: DragEndEvent) => {
    setActive(null);
    setOver(null);
    if (dropOutsideBoard(e)) return;
    if (!e.over) return;
    const to = containerOf(String(e.over.id));
    const from = containerOf(String(e.active.id));
    if (!to || to === from) return;
    const id = String(e.active.id);
    if (to === "sprint-backlog") move.mutate({ id, unschedule: true });
    else move.mutate({ id, scheduled_date: to }, { onSuccess: () => toast.success(`Planned for ${fmt(to)}`) });
  };

  return (
    <>
      <Objectives key={week.week_start} week={week} />
      <DndContext
        sensors={sensors}
        collisionDetection={collision.detect}
        onDragStart={(e) => {
          collision.track(e.activatorEvent);
          setActive((e.active.data.current?.task as Task) ?? null);
        }}
        onDragOver={(e) => setOver(e.over ? (containerOf(String(e.over.id)) ?? null) : null)}
        onDragEnd={onDragEnd}
        onDragCancel={() => setActive(null)}
      >
        <div className="week-layout">
          <div className="week-grid">
            {week.days.map((d) => {
              const off = d.time.work_minutes === 0;
              const meetShare = d.time.work_minutes ? Math.min(1, d.time.meeting_minutes / d.time.work_minutes) : 0;
              const planShare = d.time.work_minutes ? Math.min(1 - meetShare, d.planned_minutes / d.time.work_minutes) : 0;
              const over_ = d.planned_minutes > d.capacity_minutes;
              return (
                <DayColumn key={d.day} id={d.day} className={cx(d.day === today && "today", off && "off", over === d.day && active && "drop-active")}>
                  <div className="wd-head">
                    <span className="wd-name">{new Date(`${d.day}T12:00:00Z`).toLocaleDateString(undefined, { weekday: "short", timeZone: "UTC" })}</span>
                    <span className="wd-date">{Number(d.day.slice(8))}</span>
                    <button
                      className="btn icon sm ghost wd-add-meeting"
                      aria-label={`Add meeting on ${d.day}`}
                      title="Add a meeting on this day"
                      onClick={() => ui.openScheduleMeeting({ day: d.day })}
                    >
                      <CalendarPlus />
                    </button>
                  </div>
                  {!off && (
                    <>
                      <div className="wd-load" title={`Meetings ${formatMinutes(d.time.meeting_minutes)} · planned ${formatMinutes(d.planned_minutes)} · capacity ${formatMinutes(d.capacity_minutes)}`}>
                        <i style={{ width: `${meetShare * 100}%`, background: "var(--series-2)" }} />
                        <i style={{ width: `${planShare * 100}%`, background: over_ ? "var(--red)" : "var(--series-1)", marginLeft: meetShare && planShare ? 2 : 0 }} />
                      </div>
                      <div className="wd-stats" title="Planned work / capacity after meetings and buffer">
                        <span style={over_ ? { color: "var(--red)", fontWeight: 600 } : undefined}>
                          {formatMinutes(d.planned_minutes)} / {formatMinutes(d.capacity_minutes)}
                        </span>
                        {d.time.meeting_minutes > 0 && <span>{formatMinutes(d.time.meeting_minutes)} mtg</span>}
                      </div>
                    </>
                  )}
                  {d.meetings.length > 0 && (
                    <div className="wd-meetings">
                      {d.meetings.slice(0, 5).map((m) => (
                        <div key={m.id} className={cx("wd-meeting", m.effective_status === "skipped" && "skipped")} title={`${m.title} · ${formatMinutes(m.duration_minutes)}`}>
                          {m.all_day ? "All day" : clockTime(m.start_at)} {m.title}
                        </div>
                      ))}
                      {d.meetings.length > 5 && <div className="faint" style={{ fontSize: "0.7857rem" }}>+{d.meetings.length - 5} more</div>}
                    </div>
                  )}
                  <SortableContext id={d.day} items={d.tasks.map((t) => t.id)} strategy={verticalListSortingStrategy}>
                    {d.tasks.map((t) => (
                      <SortableTaskCard key={t.id} containerId={d.day} task={t} onOpen={ui.openTask} project={t.project_id ? projectById.get(t.project_id) : undefined} />
                    ))}
                  </SortableContext>
                  <AddRow placeholder="Add" onAdd={(title, est) => api.createTask({ title, scheduled_date: d.day, estimate_minutes: est }).then(() => invalidateTasks())} />
                </DayColumn>
              );
            })}
          </div>
          <DayColumn id="sprint-backlog" className={cx("lane", over === "sprint-backlog" && active && "drop-active")}>
            <div className="tray-head">
              <span className="section-label" style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <Rocket size={13} /> Sprint backlog · {week.sprint_backlog.length}
              </span>
              <button className="btn sm ghost" onClick={() => ui.navigate("sprint")}>
                Sprint <ArrowRight />
              </button>
            </div>
            {week.sprint ? (
              <>
                <div className="faint" style={{ fontSize: "0.8571rem", padding: "0 4px" }}>
                  Unscheduled sprint work — drag onto a day.
                </div>
                <SortableContext id="sprint-backlog" items={week.sprint_backlog.map((t) => t.id)} strategy={verticalListSortingStrategy}>
                  {week.sprint_backlog.map((t) => (
                    <SortableTaskCard key={t.id} containerId="sprint-backlog" task={t} onOpen={ui.openTask} project={t.project_id ? projectById.get(t.project_id) : undefined} />
                  ))}
                </SortableContext>
                {week.sprint_backlog.length === 0 && <div className="column-empty">Everything in the sprint is scheduled</div>}
              </>
            ) : (
              <EmptyState icon={Rocket} title="No sprint this week">
                <button className="btn sm" onClick={() => ui.navigate("sprint")}>
                  Plan a sprint
                </button>
              </EmptyState>
            )}
          </DayColumn>
        </div>
        <DragOverlay dropAnimation={{ duration: 160 }}>{active && <TaskCard task={active} overlay onOpen={() => {}} />}</DragOverlay>
      </DndContext>
      <div className="day-actions">
        <button
          className="btn ghost"
          onClick={async () => {
            const r = await api.rollOverWeek(week.week_start);
            invalidateTasks();
            toast.success(r.moved ? `Moved ${r.moved} unfinished task(s) to next Monday` : "Nothing to roll over");
          }}
        >
          <CalendarCheck2 /> Roll unfinished to next week
        </button>
      </div>
    </>
  );
}

function DayColumn({ id, className, children }: { id: string; className?: string; children: React.ReactNode }) {
  const { setNodeRef } = useDroppable({ id });
  return (
    <section ref={setNodeRef} className={cx("week-day", className)} aria-label={id === "sprint-backlog" ? "Sprint backlog" : `Day ${id}`}>
      {children}
    </section>
  );
}

function WeekReviewPanel({ week, onPlanNext }: { week: Week; onPlanNext: () => void }) {
  const { data: r } = useQuery({ queryKey: ["week", week.week_start, "review"], queryFn: () => api.weekReview(week.week_start) });
  const [form, setForm] = useState({
    review_wins: week.plan.review_wins,
    review_lessons: week.plan.review_lessons,
    review_risks: week.plan.review_risks,
    review_next_focus: week.plan.review_next_focus,
  });
  if (!r) return <div className="faint">Loading…</div>;
  const accuracy = r.estimate_minutes ? Math.round((r.actual_minutes / r.estimate_minutes) * 100) : null;
  const meetingShare = r.work_minutes ? Math.round((r.meeting_minutes / r.work_minutes) * 100) : 0;

  return (
    <div>
      <div className="kpis">
        <Kpi label="Completed" value={`${r.done}/${r.planned}`} sub={r.planned ? `${Math.round((r.done / r.planned) * 100)}% of planned` : "nothing planned"} />
        <Kpi label="Unfinished" value={String(r.open)} sub="roll over or drop" />
        <Kpi label="Meetings" value={formatMinutes(r.meeting_minutes)} sub={`${meetingShare}% of working hours`} />
        <Kpi label="Free for focus" value={formatMinutes(r.available_minutes)} sub={`of ${formatMinutes(r.work_minutes)} working`} />
        <Kpi label="Estimate accuracy" value={accuracy === null ? "—" : `${accuracy}%`} sub={accuracy === null ? "log actual time on tasks" : accuracy > 115 ? "took longer than estimated" : accuracy < 85 ? "faster than estimated" : "on target"} />
      </div>
      <div className="grid-2">
        <section className="card panel">
          <h3>Meetings vs. focus</h3>
          <DayTimeChart days={week.days.map((d) => d.time)} />
        </section>
        <section className="card panel">
          <h3>
            <Target size={16} /> Objectives
          </h3>
          {r.objectives.length === 0 && <div className="faint">No objectives were set for this week.</div>}
          <ul className="priority-list">
            {r.objectives.map((o, i) => (
              <li key={i} className={cx(o.done && "done")}>
                <span className="p-num">{o.done ? "✓" : i + 1}</span>
                <span className="p-title">
                  {o.emoji && <span aria-hidden>{o.emoji} </span>}
                  {o.text}
                </span>
              </li>
            ))}
          </ul>
          <div className="divider" />
          <div className="faint" style={{ fontSize: "0.8929rem" }}>
            <strong style={{ color: "var(--text-2)" }}>Done:</strong> {r.done_titles.slice(0, 6).join(" · ") || "—"}
          </div>
          <div className="faint" style={{ fontSize: "0.8929rem", marginTop: 6 }}>
            <strong style={{ color: "var(--text-2)" }}>Open:</strong> {r.open_titles.slice(0, 6).join(" · ") || "—"}
          </div>
        </section>
      </div>
      <section className="card review-card">
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <h3 style={{ fontSize: "1.2143rem", fontWeight: 650 }}>Reflect</h3>
        </div>
        <GroundedDraft
          fetchDraft={() => api.draftWeekReview(week.week_start)}
          fields={[
            { key: "review_wins", label: "Wins", from: ["highlights"] },
            { key: "review_lessons", label: "Lessons", from: ["learnings"] },
            { key: "review_risks", label: "Risks & blockers", from: ["challenges"] },
            { key: "review_next_focus", label: "Next week's focus", from: ["next_focus"] },
          ]}
          onUse={(k, bullets) => setForm((f) => ({ ...f, [k]: appendBullets(f[k], bullets) }))}
        />
        <div className="review-grid">
          {(
            [
              ["review_wins", "Wins", "What moved the needle?"],
              ["review_lessons", "Lessons", "What would you do differently?"],
              ["review_risks", "Risks & blockers", "What could derail next week?"],
              ["review_next_focus", "Next week's focus", "The one thing that matters most"],
            ] as const
          ).map(([k, label, ph]) => (
            <label key={k}>
              {label}
              <textarea className="textarea" rows={3} placeholder={ph} value={form[k]} onChange={(e) => setForm({ ...form, [k]: e.target.value })} />
            </label>
          ))}
        </div>
        <div style={{ display: "flex", gap: 8, marginTop: 16, alignItems: "center" }}>
          <button
            className="btn primary"
            onClick={async () => {
              await api.updateWeek(week.week_start, { ...form, complete_review: true });
              void queryClient.invalidateQueries({ queryKey: ["week"] });
              celebrate("week");
              toast.success("✨ Week reviewed", { description: "Now set next week's objectives." });
              onPlanNext();
            }}
          >
            <Sparkles /> Complete review & plan next week
          </button>
          <button
            className="btn ghost"
            onClick={async () => {
              await api.updateWeek(week.week_start, form);
              toast("Saved");
            }}
          >
            Save draft
          </button>
          {week.plan.review_completed_at && <span className="chip green">Reviewed</span>}
        </div>
      </section>
    </div>
  );
}

export function Kpi({ label, value, sub, warn }: { label: string; value: string; sub?: string; warn?: boolean }) {
  return (
    <div className={cx("stat", warn && "warn")}>
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      {sub && <div className="faint" style={{ fontSize: "0.8571rem", marginTop: 2 }}>{sub}</div>}
    </div>
  );
}
