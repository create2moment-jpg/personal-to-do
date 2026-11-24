import { useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Flag, History, Play, Plus, Rocket, Search, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { BurndownChart } from "../components/charts";
import { Dialog, EmptyState } from "../components/primitives";
import { TaskCard } from "../components/TaskCard";
import { api } from "../lib/api";
import { invalidateTasks, useProjects, useSettings, useSprints, useSprintSummary, useTasks } from "../lib/queries";
import type { Sprint, Task } from "../lib/types";
import { useUi } from "../lib/ui-store";
import { formatMinutes } from "../lib/util";
import { Kpi } from "./WeekView";

const fmt = (iso: string) => new Date(`${iso}T12:00:00Z`).toLocaleDateString(undefined, { month: "short", day: "numeric", timeZone: "UTC" });

export function SprintView() {
  const { data: sprints, isLoading } = useSprints();
  const [selected, setSelected] = useState<string | null>(null);
  const current = useMemo(() => {
    if (!sprints) return undefined;
    return sprints.find((s) => s.status === "active") ?? [...sprints].filter((s) => s.status === "planned").sort((a, b) => a.start_date.localeCompare(b.start_date))[0];
  }, [sprints]);
  const sprint = sprints?.find((s) => s.id === selected) ?? current;

  if (isLoading) return <div className="page faint">Loading…</div>;
  return (
    <div className="page wide">
      {sprint ? <SprintDetail key={sprint.id} sprint={sprint} sprints={sprints ?? []} onSelect={setSelected} /> : <NoSprint />}
    </div>
  );
}

function NoSprint() {
  const { data: settings } = useSettings();
  const qc = useQueryClient();
  const [goal, setGoal] = useState("");
  return (
    <div style={{ maxWidth: 640, margin: "6vh auto" }}>
      <div className="soon-hero">
        <div className="project-icon" style={{ background: "var(--accent)", width: 36, height: 36, borderRadius: 10 }}>
          <Rocket size={18} />
        </div>
        <h2>Plan your first sprint</h2>
        <p>
          A {settings?.sprint_length_days ?? 14}-day container for the work you commit to. Set one goal, pull committed and stretch work from the backlog, and review honestly at the end.
        </p>
        <form
          style={{ display: "flex", gap: 8, marginTop: 18 }}
          onSubmit={async (e) => {
            e.preventDefault();
            await api.createSprint({ goal });
            void qc.invalidateQueries({ queryKey: ["sprints"] });
            toast.success("Sprint created — add work from the backlog");
          }}
        >
          <input className="input" placeholder="Sprint goal — the one outcome that matters" value={goal} onChange={(e) => setGoal(e.target.value)} autoFocus />
          <button className="btn primary" type="submit">
            <Plus /> Create sprint
          </button>
        </form>
      </div>
    </div>
  );
}

function SprintDetail({ sprint, sprints, onSelect }: { sprint: Sprint; sprints: Sprint[]; onSelect: (id: string) => void }) {
  const ui = useUi();
  const qc = useQueryClient();
  const { data: s } = useSprintSummary(sprint.id);
  const { data: projects = [] } = useProjects();
  const projectById = useMemo(() => new Map(projects.map((p) => [p.id, p])), [projects]);
  const [goal, setGoal] = useState(sprint.goal);
  const [completing, setCompleting] = useState(false);
  const [picking, setPicking] = useState(false);
  useEffect(() => setGoal(sprint.goal), [sprint.goal]);

  const refresh = () => {
    invalidateTasks(qc);
    void qc.invalidateQueries({ queryKey: ["sprints"] });
  };
  if (!s) return <div className="faint">Loading…</div>;

  const daysLeft = Math.max(0, s.days_total - s.days_elapsed);
  const committed = s.tasks.filter((t) => t.commitment !== "stretch");
  const stretch = s.tasks.filter((t) => t.commitment === "stretch");
  const sortTasks = (ts: Task[]) => [...ts].sort((a, b) => Number(a.status === "done") - Number(b.status === "done") || a.priority - b.priority);
  const onTrack = (() => {
    const today = s.burndown.filter((p) => p.remaining_minutes >= 0).at(-1);
    if (!today || sprint.status !== "active") return null;
    return today.remaining_minutes <= today.ideal_minutes * 1.1;
  })();
  const others = sprints.filter((x) => x.id !== sprint.id);

  const lane = (title: string, tasks: Task[], kind: "committed" | "stretch") => (
    <section className="lane" aria-label={`${title} work`}>
      <div className="tray-head">
        <span className="section-label">
          {title} · {tasks.filter((t) => t.status === "done").length}/{tasks.length}
        </span>
      </div>
      {sortTasks(tasks).map((t) => (
        <div key={t.id} className="list-row">
          <TaskCard task={t} onOpen={ui.openTask} showSchedule project={t.project_id ? projectById.get(t.project_id) : undefined} />
          {sprint.status !== "completed" && (
            <div className="row-actions">
              <button
                className="btn sm ghost"
                title={kind === "committed" ? "Make stretch" : "Commit"}
                onClick={() => api.addToSprint(sprint.id, [t.id], kind === "committed" ? "stretch" : "committed").then(refresh)}
              >
                {kind === "committed" ? "Stretch" : "Commit"}
              </button>
              <button className="btn icon sm ghost" aria-label="Remove from sprint" onClick={() => api.removeFromSprint(t.id).then(refresh)}>
                <X />
              </button>
            </div>
          )}
        </div>
      ))}
      {tasks.length === 0 && <div className="column-empty">{kind === "committed" ? "Commit to work you're confident you'll finish" : "Nice-to-haves if time allows"}</div>}
    </section>
  );

  return (
    <>
      <header className="sprint-head" style={{ marginBottom: 18 }}>
        <div style={{ flex: 1 }}>
          <div className="hero-greeting">
            <Rocket size={14} /> {sprint.name}
            <span className={sprint.status === "active" ? "chip accent" : sprint.status === "completed" ? "chip green" : "chip"}>{sprint.status}</span>
            <span className="faint">
              {fmt(sprint.start_date)} – {fmt(sprint.end_date)}
            </span>
            {onTrack !== null && <span className={onTrack ? "chip green" : "chip orange"}>{onTrack ? "On track" : "Behind ideal"}</span>}
          </div>
          <input
            className="objective-input"
            style={{ fontSize: "1.7143rem", fontWeight: 680, color: "var(--text)", letterSpacing: "-0.03em", marginTop: 4 }}
            value={goal}
            placeholder="Set a sprint goal…"
            aria-label="Sprint goal"
            onChange={(e) => setGoal(e.target.value)}
            onBlur={() => goal !== sprint.goal && api.updateSprint(sprint.id, { goal }).then(refresh)}
            onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
          />
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          {others.length > 0 && (
            <select className="select" style={{ width: "auto" }} value={sprint.id} aria-label="Switch sprint" onChange={(e) => onSelect(e.target.value)}>
              {sprints.map((x) => (
                <option key={x.id} value={x.id}>
                  {x.name} ({x.status})
                </option>
              ))}
            </select>
          )}
          {sprint.status === "planned" && (
            <button
              className="btn primary"
              onClick={() =>
                api
                  .startSprint(sprint.id)
                  .then(() => {
                    refresh();
                    toast.success("Sprint started", { description: "Scope added from now on is tracked as a scope change." });
                  })
                  .catch((e: Error) => toast.error(e.message))
              }
            >
              <Play /> Start sprint
            </button>
          )}
          {sprint.status === "active" && (
            <button className="btn primary" onClick={() => setCompleting(true)}>
              <Flag /> Complete sprint
            </button>
          )}
          {sprint.status === "completed" && (
            <button
              className="btn"
              onClick={() => api.createSprint({}).then((n) => { refresh(); onSelect(n.id); })}
            >
              <Plus /> Next sprint
            </button>
          )}
        </div>
      </header>

      <div className="kpis">
        <Kpi label="Committed done" value={`${s.committed_done}/${s.committed_total}`} sub={`${Math.round(s.completion_rate * 100)}% complete`} />
        <Kpi label="Stretch done" value={`${s.stretch_done}/${s.stretch_total}`} />
        <Kpi label="Work remaining" value={formatMinutes(s.remaining_minutes)} sub={`committed + stretch · ${formatMinutes(s.committed_minutes)} committed`} />
        <Kpi label={sprint.status === "completed" ? "Length" : "Days left"} value={sprint.status === "completed" ? `${s.days_total}d` : String(daysLeft)} sub={`day ${Math.min(s.days_elapsed, s.days_total)} of ${s.days_total}`} />
        <Kpi label="Scope changes" value={`+${s.added_after_start.length} / −${s.removed_after_start.length}`} sub="added / removed after start" warn={s.added_after_start.length > 2} />
      </div>

      <div className="grid-2" style={{ marginBottom: 14 }}>
        <section className="card panel">
          <h3>Burndown</h3>
          <BurndownChart points={s.burndown} />
        </section>
        <section className="card panel">
          <h3>
            <History size={16} /> {sprint.status === "completed" ? "Sprint review" : "Notes for the review"}
          </h3>
          {sprint.status === "completed" ? (
            <>
              <p style={{ margin: "0 0 8px", color: "var(--text-2)" }}>
                Completed {s.committed_done} of {s.committed_total} committed ({Math.round(s.completion_rate * 100)}%), {s.stretch_done} stretch, {s.added_after_start.length} added mid-sprint.
              </p>
              {sprint.review_summary && <p style={{ margin: "0 0 8px" }}>{sprint.review_summary}</p>}
              {sprint.review_lessons && (
                <p style={{ margin: 0 }}>
                  <strong>Lessons:</strong> {sprint.review_lessons}
                </p>
              )}
            </>
          ) : (
            <ReviewNotes sprint={sprint} />
          )}
        </section>
      </div>

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", margin: "6px 0 10px" }}>
        <h3 style={{ fontSize: "1.0714rem", fontWeight: 620 }}>Sprint work</h3>
        {sprint.status !== "completed" && (
          <button className="btn" onClick={() => setPicking(true)}>
            <Plus /> Add from backlog
          </button>
        )}
      </div>
      <div className="lanes">
        {lane("Committed", committed, "committed")}
        {lane("Stretch", stretch, "stretch")}
      </div>

      <BacklogPicker open={picking} sprint={sprint} onClose={() => setPicking(false)} onAdded={refresh} />
      <CompleteDialog open={completing} sprint={sprint} openCount={s.tasks.filter((t) => t.status !== "done").length} onClose={() => setCompleting(false)} onDone={(next) => { refresh(); if (next) onSelect(next); }} />
    </>
  );
}

function ReviewNotes({ sprint }: { sprint: Sprint }) {
  const [v, setV] = useState(sprint.review_lessons);
  return (
    <textarea
      className="textarea"
      rows={6}
      value={v}
      placeholder="Jot down what's working, what isn't, surprises… These become the sprint's lessons."
      onChange={(e) => setV(e.target.value)}
      onBlur={() => v !== sprint.review_lessons && api.updateSprint(sprint.id, { review_lessons: v })}
    />
  );
}

function BacklogPicker({ open, sprint, onClose, onAdded }: { open: boolean; sprint: Sprint; onClose: () => void; onAdded: () => void }) {
  const { data: backlog = [] } = useTasks({ top_level: true });
  const [q, setQ] = useState("");
  const candidates = backlog.filter((t) => t.status !== "done" && t.sprint_id !== sprint.id && (!q || t.title.toLowerCase().includes(q.toLowerCase())));
  return (
    <Dialog open={open} onClose={onClose} label="Add work to sprint" width={680}>
      <div style={{ padding: "16px 18px", display: "flex", flexDirection: "column", gap: 10, maxHeight: "70vh" }}>
        <h3 style={{ fontSize: "1.2143rem", fontWeight: 650 }}>Add work to {sprint.name}</h3>
        <div className="search-input" style={{ maxWidth: "none" }}>
          <Search />
          <input className="input" autoFocus placeholder="Filter open tasks" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <div className="list" style={{ overflowY: "auto" }}>
          {candidates.map((t) => (
            <div key={t.id} className="list-row">
              <TaskCard task={t} onOpen={() => {}} showSchedule />
              <div style={{ display: "flex", gap: 4 }}>
                <button className="btn sm primary" onClick={() => api.addToSprint(sprint.id, [t.id], "committed").then(() => { onAdded(); toast.success("Committed"); })}>
                  Commit
                </button>
                <button className="btn sm" onClick={() => api.addToSprint(sprint.id, [t.id], "stretch").then(() => { onAdded(); toast("Added as stretch"); })}>
                  Stretch
                </button>
              </div>
            </div>
          ))}
          {candidates.length === 0 && <EmptyState icon={CheckCircle2} title="Nothing left to add" />}
        </div>
      </div>
    </Dialog>
  );
}

function CompleteDialog({ open, sprint, openCount, onClose, onDone }: { open: boolean; sprint: Sprint; openCount: number; onClose: () => void; onDone: (nextId?: string) => void }) {
  const [rollover, setRollover] = useState<"next" | "backlog">("next");
  const [summary, setSummary] = useState("");
  const [lessons, setLessons] = useState(sprint.review_lessons);
  return (
    <Dialog open={open} onClose={onClose} label="Complete sprint" width={600}>
      <form
        style={{ padding: "18px 20px", display: "flex", flexDirection: "column", gap: 12 }}
        onSubmit={async (e) => {
          e.preventDefault();
          const r = await api.completeSprint(sprint.id, { rollover, summary, lessons });
          toast.success(`${sprint.name} completed`, { description: r.rolled_over ? `${r.rolled_over} open task(s) moved to ${r.next_sprint ? r.next_sprint.name : "the backlog"}` : "Everything was finished. Impressive." });
          onClose();
          onDone(r.next_sprint?.id);
        }}
      >
        <h3 style={{ fontSize: "1.2143rem", fontWeight: 650 }}>Complete {sprint.name}</h3>
        <p className="muted" style={{ margin: 0 }}>
          {openCount} unfinished task(s). Where should they go?
        </p>
        <div className="segmented" style={{ alignSelf: "flex-start" }}>
          <button type="button" aria-pressed={rollover === "next"} onClick={() => setRollover("next")}>
            Next sprint
          </button>
          <button type="button" aria-pressed={rollover === "backlog"} onClick={() => setRollover("backlog")}>
            Back to backlog
          </button>
        </div>
        <label className="lc-field">
          <span>Summary — what did this sprint deliver?</span>
          <textarea className="textarea" rows={3} value={summary} onChange={(e) => setSummary(e.target.value)} />
        </label>
        <label className="lc-field">
          <span>Lessons — what will you change next sprint?</span>
          <textarea className="textarea" rows={3} value={lessons} onChange={(e) => setLessons(e.target.value)} />
        </label>
        <div className="lc-foot">
          <span />
          <button type="button" className="btn ghost" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="btn primary">
            <Flag /> Complete sprint
          </button>
        </div>
      </form>
    </Dialog>
  );
}

