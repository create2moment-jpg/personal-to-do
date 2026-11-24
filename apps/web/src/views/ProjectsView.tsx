import { useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { FolderKanban, Plus } from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "sonner";
import { EmptyState } from "../components/primitives";
import { TaskCard } from "../components/TaskCard";
import { api } from "../lib/api";
import { keys, useProjects, useTasks } from "../lib/queries";
import { useUi } from "../lib/ui-store";

const COLORS = ["#6366f1", "#0ea5e9", "#10b981", "#f59e0b", "#ef4444", "#d946ef", "#64748b"];

export function ProjectsView() {
  const ui = useUi();
  const qc = useQueryClient();
  const { data: projects = [] } = useProjects();
  const { data: allTasks = [] } = useTasks({ top_level: true });
  const [selected, setSelected] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [area, setArea] = useState("");
  const [color, setColor] = useState(COLORS[0]!);

  const stats = useMemo(() => {
    const m = new Map<string, { open: number; done: number }>();
    for (const t of allTasks) {
      if (!t.project_id) continue;
      const s = m.get(t.project_id) ?? { open: 0, done: 0 };
      if (t.status === "done") s.done++;
      else s.open++;
      m.set(t.project_id, s);
    }
    return m;
  }, [allTasks]);

  const areas = [...new Set(projects.map((p) => p.area ?? "Unsorted"))].sort();
  const selectedTasks = allTasks.filter((t) => t.project_id === selected).sort((a, b) => Number(a.status === "done") - Number(b.status === "done") || a.priority - b.priority);
  const selectedProject = projects.find((p) => p.id === selected);

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <h1 className="page-title">Projects</h1>
          <div className="page-sub">Outcomes you’re driving, grouped by area of responsibility.</div>
        </div>
        <button className="btn primary" onClick={() => setCreating((c) => !c)}>
          <Plus /> New project
        </button>
      </header>

      {creating && (
        <motion.form
          className="card"
          style={{ padding: 16, marginBottom: 18, display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}
          initial={{ opacity: 0, y: -6 }}
          animate={{ opacity: 1, y: 0 }}
          onSubmit={async (e) => {
            e.preventDefault();
            try {
              await api.createProject({ name, area: area || undefined, color });
              void qc.invalidateQueries({ queryKey: keys.projects });
              toast.success(`Project “${name}” created`);
              setName("");
              setCreating(false);
            } catch (err) {
              toast.error((err as Error).message);
            }
          }}
        >
          <input className="input" style={{ flex: 2, minWidth: 200 }} placeholder="Project name" value={name} onChange={(e) => setName(e.target.value)} autoFocus required />
          <input className="input" style={{ flex: 1, minWidth: 140 }} placeholder="Area (e.g. Engineering)" value={area} onChange={(e) => setArea(e.target.value)} list="areas" />
          <datalist id="areas">
            {areas.map((a) => (
              <option key={a} value={a} />
            ))}
          </datalist>
          <div className="swatches" role="group" aria-label="Color">
            {COLORS.map((c) => (
              <button type="button" key={c} className="swatch" style={{ background: c }} aria-pressed={c === color} aria-label={c} onClick={() => setColor(c)} />
            ))}
          </div>
          <button className="btn primary" type="submit">
            Create
          </button>
        </motion.form>
      )}

      {projects.length === 0 ? (
        <EmptyState icon={FolderKanban} title="No projects yet">
          Projects group related tasks and notes. Create one, then use <code>+project-name</code> in quick capture.
        </EmptyState>
      ) : (
        areas.map((a) => (
          <section key={a}>
            <div className="group-head">
              <h3>{a}</h3>
            </div>
            <div className="projects-grid">
              {projects
                .filter((p) => (p.area ?? "Unsorted") === a)
                .map((p) => {
                  const s = stats.get(p.id) ?? { open: 0, done: 0 };
                  const total = s.open + s.done;
                  const color = p.color ?? "#64748b";
                  return (
                    <button key={p.id} className={`card project-card ${selected === p.id ? "active" : ""}`} onClick={() => setSelected(selected === p.id ? null : p.id)}>
                      <div className="project-icon" style={{ background: color }}>
                        {p.name[0]}
                      </div>
                      <h4>{p.name}</h4>
                      <div className="faint" style={{ fontSize: "0.8929rem" }}>
                        {s.open} open · {s.done} done
                      </div>
                      <div className="project-bar">
                        <motion.i initial={{ width: 0 }} animate={{ width: `${total ? (s.done / total) * 100 : 0}%` }} style={{ background: color }} />
                      </div>
                    </button>
                  );
                })}
            </div>
          </section>
        ))
      )}

      {selectedProject && (
        <motion.section initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} style={{ marginTop: 26 }}>
          <div className="group-head">
            <h3>{selectedProject.name}</h3>
            <span className="faint">{selectedTasks.length} tasks</span>
          </div>
          <div className="list">
            {selectedTasks.map((t) => (
              <TaskCard key={t.id} task={t} onOpen={ui.openTask} showSchedule />
            ))}
            {selectedTasks.length === 0 && <div className="faint">No tasks yet.</div>}
          </div>
        </motion.section>
      )}
    </div>
  );
}
