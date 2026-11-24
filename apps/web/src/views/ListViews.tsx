import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight, CalendarDays, Inbox, Search, SunMedium } from "lucide-react";
import { useMemo, useState } from "react";
import { useQueries } from "@tanstack/react-query";
import { EmptyState } from "../components/primitives";
import { TaskCard } from "../components/TaskCard";
import { api } from "../lib/api";
import { keys, useCreateTask, useMoveTask, useProjects, useTasks } from "../lib/queries";
import type { Task } from "../lib/types";
import { useUi } from "../lib/ui-store";
import { addDays, formatMinutes, isoDay, relativeDay } from "../lib/util";
import { AddRow } from "./TodayView";

type Sort = "priority" | "due" | "newest";

export function BacklogView() {
  const ui = useUi();
  const [filter, setFilter] = useState("");
  const [project, setProject] = useState("");
  const [sort, setSort] = useState<Sort>("priority");
  const { data: tasks = [], isLoading } = useTasks({ status: "backlog", top_level: true, project_id: project || undefined });
  const { data: projects = [] } = useProjects();
  const create = useCreateTask();
  const move = useMoveTask(isoDay());
  const projectById = useMemo(() => new Map(projects.map((p) => [p.id, p])), [projects]);

  const needle = filter.toLowerCase();
  const shown = tasks
    .filter((t) => !needle || t.title.toLowerCase().includes(needle) || t.tags.some((g) => g.includes(needle)))
    .sort((a, b) => {
      if (sort === "priority") return a.priority - b.priority || a.position - b.position;
      if (sort === "due") return (a.due_date ?? "9999").localeCompare(b.due_date ?? "9999");
      return b.created_at.localeCompare(a.created_at);
    });
  const totalMins = shown.reduce((s, t) => s + (t.estimate_minutes ?? 0), 0);

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <h1 className="page-title">Backlog</h1>
          <div className="page-sub">
            {tasks.length} uncommitted {tasks.length === 1 ? "task" : "tasks"}
            {totalMins > 0 && ` · ${formatMinutes(totalMins)} estimated`} — commit work to a day when you’re ready to do it.
          </div>
        </div>
      </header>

      <div className="toolbar">
        <div className="search-input">
          <Search />
          <input className="input" placeholder="Filter by title or #tag" value={filter} onChange={(e) => setFilter(e.target.value)} />
        </div>
        <select className="select" style={{ width: "auto" }} value={project} onChange={(e) => setProject(e.target.value)} aria-label="Project">
          <option value="">All projects</option>
          {projects.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
        <div className="segmented" role="group" aria-label="Sort">
          {(["priority", "due", "newest"] as Sort[]).map((s) => (
            <button key={s} aria-pressed={sort === s} onClick={() => setSort(s)}>
              {s[0]!.toUpperCase() + s.slice(1)}
            </button>
          ))}
        </div>
      </div>

      <div style={{ marginBottom: 10 }}>
        <AddRow placeholder="Add to backlog — press Enter" onAdd={(title) => create.mutateAsync({ title, project_id: project || null })} />
      </div>

      {!isLoading && shown.length === 0 ? (
        <EmptyState icon={Inbox} title={filter ? "No matches" : "Inbox zero"}>
          {filter ? "Try a different filter." : "Nothing waiting. Capture something with C."}
        </EmptyState>
      ) : (
        <div className="list">
          <AnimatePresence initial={false}>
            {shown.map((t) => (
              <motion.div key={t.id} className="list-row" layout initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0, x: 20 }} transition={{ duration: 0.16 }}>
                <TaskCard task={t} project={t.project_id ? projectById.get(t.project_id) : undefined} onOpen={ui.openTask} />
                <div className="row-actions">
                  <button className="btn sm" onClick={() => move.mutate({ id: t.id, scheduled_date: isoDay() })}>
                    <SunMedium /> Today
                  </button>
                  <button className="btn sm ghost" onClick={() => move.mutate({ id: t.id, scheduled_date: addDays(isoDay(), 1) })}>
                    Tomorrow <ArrowRight />
                  </button>
                </div>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      )}
    </div>
  );
}

export function UpcomingView() {
  const ui = useUi();
  const today = isoDay();
  const days = Array.from({ length: 7 }, (_, i) => addDays(today, i + 1));
  const results = useQueries({ queries: days.map((d) => ({ queryKey: keys.today(d), queryFn: () => api.today(d) })) });
  const { data: projects = [] } = useProjects();
  const projectById = useMemo(() => new Map(projects.map((p) => [p.id, p])), [projects]);
  const create = useCreateTask();

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <h1 className="page-title">Upcoming</h1>
          <div className="page-sub">The next seven days at a glance. Add directly to any day.</div>
        </div>
      </header>
      {days.map((d, i) => {
        const data = results[i]?.data;
        const tasks: Task[] = (data?.tasks ?? []).filter((t) => t.parent_id === null);
        const mins = data?.capacity.planned_minutes ?? 0;
        return (
          <section key={d} className="upcoming-day">
            <div className="group-head">
              <h3>{relativeDay(d, today)}</h3>
              <span className="faint">{new Date(`${d}T12:00:00`).toLocaleDateString(undefined, { month: "long", day: "numeric" })}</span>
              {mins > 0 && (
                <span className={data?.capacity.overcommitted ? "chip red" : "chip"} style={{ marginLeft: "auto" }}>
                  {formatMinutes(mins)} planned
                </span>
              )}
            </div>
            <div className="list" style={{ marginBottom: 8 }}>
              {tasks.map((t) => (
                <TaskCard key={t.id} task={t} project={t.project_id ? projectById.get(t.project_id) : undefined} onOpen={ui.openTask} />
              ))}
              <AddRow placeholder={`Add to ${relativeDay(d, today)}`} onAdd={(title) => create.mutateAsync({ title, scheduled_date: d })} />
            </div>
          </section>
        );
      })}
      {results.every((r) => r.data && r.data.tasks.length === 0) && (
        <EmptyState icon={CalendarDays} title="A clear week ahead">
          Schedule work with <code>@tomorrow</code> or <code>@fri</code> in quick capture.
        </EmptyState>
      )}
    </div>
  );
}
