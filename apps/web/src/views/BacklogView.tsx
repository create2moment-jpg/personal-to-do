import { useEffect, useState } from "react";
import { api } from "../api";
import { TaskCard } from "../components/TaskCard";
import type { Project, Task } from "../types";
import { isoDay } from "../util";
import { InlineAdd } from "./TodayView";

interface Props {
  revision: number;
  onChanged: () => void;
  onOpenTask: (id: string) => void;
}

type Sort = "priority" | "due" | "created";

export function BacklogView({ revision, onChanged, onOpenTask }: Props) {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [filter, setFilter] = useState("");
  const [project, setProject] = useState("");
  const [sort, setSort] = useState<Sort>("priority");

  useEffect(() => {
    Promise.all([api.tasks({ status: "backlog", top_level: true, project_id: project || undefined }), api.projects()])
      .then(([t, p]) => {
        setTasks(t);
        setProjects(p);
      })
      .catch(() => setTasks([]));
  }, [revision, project]);

  const needle = filter.toLowerCase();
  const shown = tasks
    .filter((t) => !needle || t.title.toLowerCase().includes(needle) || t.tags.some((g) => g.includes(needle)))
    .sort((a, b) => {
      if (sort === "priority") return a.priority - b.priority || a.position - b.position;
      if (sort === "due") return (a.due_date ?? "9999").localeCompare(b.due_date ?? "9999");
      return b.created_at.localeCompare(a.created_at);
    });

  const today = isoDay();
  return (
    <div className="view backlog">
      <header className="view-head">
        <div>
          <h1>Backlog</h1>
          <div className="sub">{tasks.length} uncommitted tasks — pull work onto a day when you commit to it.</div>
        </div>
      </header>
      <div className="toolbar">
        <input placeholder="Filter by text or tag" value={filter} onChange={(e) => setFilter(e.target.value)} />
        <select value={project} onChange={(e) => setProject(e.target.value)} aria-label="Project">
          <option value="">All projects</option>
          {projects.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
        <select value={sort} onChange={(e) => setSort(e.target.value as Sort)} aria-label="Sort">
          <option value="priority">Priority</option>
          <option value="due">Due date</option>
          <option value="created">Newest</option>
        </select>
      </div>
      <InlineAdd
        placeholder="+ Add to backlog (Enter)"
        onAdd={async (title) => {
          await api.createTask({ title, project_id: project || null });
          onChanged();
        }}
      />
      <div className="backlog-list">
        {shown.map((t) => (
          <div key={t.id} className="backlog-row">
            <TaskCard task={t} onOpen={onOpenTask} today={today} />
            <button
              onClick={async () => {
                await api.moveTask(t.id, { scheduled_date: today });
                onChanged();
              }}
            >
              → Today
            </button>
          </div>
        ))}
        {shown.length === 0 && <div className="empty">Backlog is empty.</div>}
      </div>
    </div>
  );
}
