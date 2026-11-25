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
import { useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { Search } from "lucide-react";
import { type ReactNode, useMemo, useState } from "react";
import { toast } from "sonner";
import { SortableTaskCard, TaskCard } from "../components/TaskCard";
import { StatusDot } from "../components/primitives";
import { api } from "../lib/api";
import { columnCoordinates, inputAwareCollision } from "../lib/dnd";
import { dropOutsideBoard } from "../lib/drop";
import { invalidateTasks, useCreateTask, useProjects, useSettings, useTasks } from "../lib/queries";
import type { Task, TaskStatus } from "../lib/types";
import { useUi } from "../lib/ui-store";
import { cx, formatMinutes, isoDay, positionBetween } from "../lib/util";
import { AddRow } from "./TodayView";

const COLUMNS: { status: TaskStatus; label: string; empty: string }[] = [
  { status: "backlog", label: "Backlog", empty: "Nothing waiting to be planned" },
  { status: "planned", label: "Planned", empty: "Drag work here to plan it" },
  { status: "in_progress", label: "In progress", empty: "Nothing started" },
  { status: "blocked", label: "Blocked", empty: "Nothing waiting. Nice." },
  { status: "done", label: "Completed", empty: "Nothing completed in this period" },
];
const DONE_RANGES: [string, number | null][] = [
  ["7 days", 7],
  ["30 days", 30],
  ["All", null],
];

/** Every task by state — not only today's — with drag and drop between states. */
export function BoardView() {
  const ui = useUi();
  const qc = useQueryClient();
  const create = useCreateTask();
  const { data: projects = [] } = useProjects();
  const { data: settings } = useSettings();
  const lists = {
    backlog: useTasks({ status: "backlog", top_level: true }).data,
    planned: useTasks({ status: "planned", top_level: true }).data,
    in_progress: useTasks({ status: "in_progress", top_level: true }).data,
    blocked: useTasks({ status: "blocked", top_level: true }).data,
    done: useTasks({ status: "done", top_level: true, limit: 1000 }).data,
  } as Record<TaskStatus, Task[] | undefined>;
  const [q, setQ] = useState("");
  const [project, setProject] = useState("");
  const [doneDays, setDoneDays] = useState<number | null>(7);
  const [optimistic, setOptimistic] = useState<Record<string, { status: TaskStatus; position: number }>>({});
  const [active, setActive] = useState<Task | null>(null);
  const [over, setOver] = useState<string | null>(null);
  const [collision] = useState(inputAwareCollision);
  const projectById = useMemo(() => new Map(projects.map((p) => [p.id, p])), [projects]);
  const fallback = settings?.default_task_minutes ?? 30;

  const columns = useMemo(() => {
    const since = doneDays ? Date.now() - doneDays * 86_400_000 : 0;
    const needle = q.trim().toLowerCase();
    const all = Object.values(lists).flatMap((l) => l ?? []);
    const out = Object.fromEntries(COLUMNS.map((c) => [c.status, [] as Task[]])) as Record<TaskStatus, Task[]>;
    for (const raw of all) {
      const o = optimistic[raw.id];
      const t = o ? { ...raw, ...o } : raw;
      if (project && t.project_id !== project) continue;
      if (needle && !`${t.title} ${t.tags.join(" ")}`.toLowerCase().includes(needle)) continue;
      if (t.status === "done" && since && (!t.completed_at || Date.parse(t.completed_at) < since)) continue;
      out[t.status].push(t);
    }
    for (const c of COLUMNS) {
      out[c.status].sort((a, b) =>
        c.status === "done" ? (b.completed_at ?? "").localeCompare(a.completed_at ?? "") : c.status === "backlog" ? a.priority - b.priority || a.position - b.position : (a.scheduled_date ?? "").localeCompare(b.scheduled_date ?? "") || a.position - b.position,
      );
    }
    return out;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lists.backlog, lists.planned, lists.in_progress, lists.blocked, lists.done, q, project, doneDays, optimistic]);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor, { coordinateGetter: columnCoordinates(() => COLUMNS.map((c) => c.status)), keyboardCodes: { start: ["Space"], cancel: ["Escape"], end: ["Space", "Enter"] } }),
  );
  const containerOf = (id: string): TaskStatus | undefined =>
    COLUMNS.some((c) => c.status === id) ? (id as TaskStatus) : COLUMNS.find((c) => columns[c.status].some((t) => t.id === id))?.status;

  const onDragStart = (e: DragStartEvent) => {
    collision.track(e.activatorEvent);
    setActive((e.active.data.current?.task as Task) ?? null);
  };
  const onDragOver = (e: DragOverEvent) => setOver(e.over ? (containerOf(String(e.over.id)) ?? null) : null);
  const onDragEnd = async (e: DragEndEvent) => {
    setActive(null);
    setOver(null);
    if (dropOutsideBoard(e) || !e.over) return;
    const id = String(e.active.id);
    const from = containerOf(id);
    const to = containerOf(String(e.over.id));
    if (!from || !to) return;
    const list = columns[to].filter((t) => t.id !== id);
    let index = list.findIndex((t) => t.id === e.over!.id);
    if (index === -1) index = list.length;
    const position = positionBetween(list[index - 1]?.position, list[index]?.position);
    if (from === to && to !== "backlog") return; // other columns are ordered by day
    setOptimistic((o) => ({ ...o, [id]: { status: to, position } }));
    try {
      const moved = await api.moveTask(id, { status: to, position });
      if (to === "done") toast.success("Completed", { description: moved.title, action: { label: "Undo", onClick: () => void api.moveTask(id, { status: from }).then(() => invalidateTasks(qc)) } });
      else if (from === "backlog" && moved.scheduled_date === isoDay()) toast("Planned for today", { description: "Change the day in the task panel if it belongs elsewhere." });
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      await invalidateTasks(qc);
      setOptimistic((o) => {
        const { [id]: _, ...rest } = o;
        return rest;
      });
    }
  };

  const loading = Object.values(lists).some((l) => l === undefined);
  return (
    <div className="page wide board-page">
      <header className="page-head">
        <div>
          <h1 className="page-title">Task board</h1>
          <div className="page-sub">All your work by state — drag a card to move it. Click a card’s time to change it.</div>
        </div>
        <div className="board-tools">
          <div className="search-input">
            <Search />
            <input className="input" placeholder="Filter tasks" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Filter tasks" />
          </div>
          <select className="select" value={project} onChange={(e) => setProject(e.target.value)} aria-label="Project">
            <option value="">All projects</option>
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </div>
      </header>

      <DndContext sensors={sensors} collisionDetection={collision.detect} onDragStart={onDragStart} onDragOver={onDragOver} onDragEnd={(e) => void onDragEnd(e)} onDragCancel={() => setActive(null)}>
        <div className="all-board">
          {COLUMNS.map(({ status, label, empty }) => {
            const tasks = columns[status];
            const mins = tasks.reduce((s, t) => s + (t.estimate_minutes ?? (status === "done" ? 0 : fallback)), 0);
            return (
              <Column key={status} id={status} label={label} active={over === status && active?.status !== status}>
                <div className="column-head">
                  <StatusDot status={status} /> {label} <span className="count">{tasks.length}</span>
                  {mins > 0 && <span className="mins" title={status === "done" ? "Estimated time of completed work" : "Estimated time (tasks without an estimate use your default)"}>{formatMinutes(mins)}</span>}
                </div>
                {status === "done" && (
                  <div className="segmented done-range" role="group" aria-label="Completed in">
                    {DONE_RANGES.map(([l, d]) => (
                      <button key={l} aria-pressed={doneDays === d} onClick={() => setDoneDays(d)}>
                        {l}
                      </button>
                    ))}
                  </div>
                )}
                <SortableContext id={status} items={tasks.map((t) => t.id)} strategy={verticalListSortingStrategy}>
                  <AnimatePresence initial={false}>
                    {tasks.slice(0, 150).map((t) => (
                      <motion.div key={t.id} layout="position" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, scale: 0.96 }} transition={{ duration: 0.18 }}>
                        <SortableTaskCard containerId={status} task={t} project={t.project_id ? projectById.get(t.project_id) : undefined} onOpen={ui.openTask} showSchedule={status !== "backlog"} />
                      </motion.div>
                    ))}
                  </AnimatePresence>
                </SortableContext>
                {tasks.length > 150 && <div className="column-empty">+{tasks.length - 150} more — narrow with the filter</div>}
                {!loading && tasks.length === 0 && <div className="column-empty">{empty}</div>}
                {status === "backlog" && <AddRow placeholder="Add to backlog — e.g. Draft ADR ~1h" onAdd={(title, est) => create.mutateAsync({ title, estimate_minutes: est, project_id: project || null })} />}
              </Column>
            );
          })}
        </div>
        <DragOverlay dropAnimation={{ duration: 180, easing: "cubic-bezier(0.2, 0.8, 0.2, 1)" }}>
          {active && <TaskCard task={active} overlay onOpen={() => {}} project={active.project_id ? projectById.get(active.project_id) : undefined} />}
        </DragOverlay>
      </DndContext>
    </div>
  );
}

function Column({ id, label, active, children }: { id: string; label: string; active: boolean; children: ReactNode }) {
  const { setNodeRef } = useDroppable({ id, data: { container: id } });
  return (
    <section ref={setNodeRef} className={cx("column", active && "drop-active")} aria-label={label}>
      {children}
    </section>
  );
}
