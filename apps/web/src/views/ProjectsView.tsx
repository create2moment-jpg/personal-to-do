import { useEffect, useState } from "react";
import { api } from "../api";
import { TaskCard } from "../components/TaskCard";
import type { Project, Task } from "../types";
import { isoDay } from "../util";

interface Props {
  revision: number;
  onChanged: () => void;
  onOpenTask: (id: string) => void;
}

export function ProjectsView({ revision, onChanged, onOpenTask }: Props) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [name, setName] = useState("");
  const [area, setArea] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.projects().then(setProjects).catch(() => setProjects([]));
  }, [revision]);

  useEffect(() => {
    if (selected) api.tasks({ project_id: selected, top_level: true }).then(setTasks);
  }, [selected, revision]);

  const areas = [...new Set(projects.map((p) => p.area ?? "No area"))].sort();

  return (
    <div className="view projects">
      <header className="view-head">
        <h1>Projects & Areas</h1>
      </header>
      <form
        className="toolbar"
        onSubmit={async (e) => {
          e.preventDefault();
          try {
            await api.createProject({ name, area: area || undefined });
            setName("");
            setError(null);
            onChanged();
          } catch (err) {
            setError((err as Error).message);
          }
        }}
      >
        <input placeholder="New project name" value={name} onChange={(e) => setName(e.target.value)} required />
        <input placeholder="Area (e.g. Research, Career)" value={area} onChange={(e) => setArea(e.target.value)} />
        <button className="primary" type="submit">
          Add project
        </button>
      </form>
      {error && <p className="error">{error}</p>}
      <div className="projects-grid">
        <div>
          {areas.map((a) => (
            <div key={a} className="area-group">
              <h3>{a}</h3>
              {projects
                .filter((p) => (p.area ?? "No area") === a)
                .map((p) => (
                  <button key={p.id} className={`project-item ${selected === p.id ? "active" : ""}`} onClick={() => setSelected(p.id)}>
                    {p.name}
                  </button>
                ))}
            </div>
          ))}
          {projects.length === 0 && <div className="empty">No projects yet.</div>}
        </div>
        <div>
          {selected ? (
            <>
              <h3>Tasks</h3>
              {tasks.map((t) => (
                <TaskCard key={t.id} task={t} onOpen={onOpenTask} today={isoDay()} />
              ))}
              {tasks.length === 0 && <div className="empty">No tasks in this project.</div>}
            </>
          ) : (
            <div className="empty">Select a project.</div>
          )}
        </div>
      </div>
    </div>
  );
}
