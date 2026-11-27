import { useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { CheckCircle2, ChevronDown, ChevronLeft, ChevronRight, CornerDownRight, FolderKanban, Pencil, Plus, Sprout, Target, Trash2, TrendingUp } from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "sonner";
import { TaskCard } from "../components/TaskCard";
import { Dialog, EmptyState } from "../components/primitives";
import { api } from "../lib/api";
import { celebrate } from "../lib/celebrate";
import { dropProps } from "../lib/drop";
import { invalidateTasks, useProjects } from "../lib/queries";
import type { CareerMatrix, Goal, GoalHorizon, GoalMode, GoalNode, GoalPace } from "../lib/types";
import { useUi } from "../lib/ui-store";
import { cx } from "../lib/util";
import { AddRow } from "./TodayView";
import { Kpi } from "./WeekView";

const HORIZON_LABEL: Record<GoalHorizon, string> = { year: "Year", quarter: "Quarter", month: "Month" };
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const PACE_TONE: Partial<Record<GoalPace, string>> = { ahead: "green", "on track": "accent", behind: "orange", achieved: "green", dropped: "red" };

export function periodLabel(period: string): string {
  const q = /^(\d{4})-Q(\d)$/.exec(period);
  if (q) return `Q${q[2]} ${q[1]}`;
  const m = /^(\d{4})-(\d{2})$/.exec(period);
  if (m) return `${MONTHS[Number(m[2]) - 1]} ${m[1]}`;
  return period;
}

function currentPeriod(h: GoalHorizon, year: number): string {
  const now = new Date();
  const month = now.getFullYear() === year ? now.getMonth() : 0;
  if (h === "year") return String(year);
  if (h === "quarter") return `${year}-Q${Math.floor(month / 3) + 1}`;
  return `${year}-${String(month + 1).padStart(2, "0")}`;
}

function periodOptions(h: GoalHorizon, year: number): [string, string][] {
  if (h === "year") return [year - 1, year, year + 1].map((y) => [String(y), String(y)]);
  if (h === "quarter") return [1, 2, 3, 4].map((q) => [`${year}-Q${q}`, `Q${q} ${year}`]);
  return MONTHS.map((m, i) => [`${year}-${String(i + 1).padStart(2, "0")}`, `${m} ${year}`]);
}

const invalidate = (qc: ReturnType<typeof useQueryClient>) => {
  void qc.invalidateQueries({ queryKey: ["goals"] });
  void qc.invalidateQueries({ queryKey: ["career"] });
  invalidateTasks(qc);
};

export function GoalsView() {
  const [year, setYear] = useState(new Date().getFullYear());
  const { data, isLoading } = useQuery({ queryKey: ["goals", year], queryFn: () => api.goals(year) });
  const { data: career } = useQuery({ queryKey: ["career"], queryFn: api.career });
  const [editing, setEditing] = useState<{ goal?: Goal; parent?: Goal; horizon?: GoalHorizon } | null>(null);
  const roots = data?.roots ?? [];
  const flat = useMemo(() => {
    const out: GoalNode[] = [];
    const walk = (n: GoalNode) => (out.push(n), n.children.forEach(walk));
    roots.forEach(walk);
    return out;
  }, [roots]);
  const active = flat.filter((n) => n.goal.status === "active");
  const achieved = flat.filter((n) => n.goal.status === "achieved").length;
  const behind = active.filter((n) => n.pace === "behind").length;
  const unmeasured = active.filter((n) => n.progress.value === null).length;

  return (
    <div className="page goals-page">
      <header className="page-head">
        <div>
          <h1 className="page-title">Goals</h1>
          <div className="page-sub">Year → quarter → month. Progress comes from linked tasks, a number you track, or your own estimate.</div>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <div className="year-switch">
            <button className="btn icon sm ghost" aria-label="Previous year" onClick={() => setYear(year - 1)}>
              <ChevronLeft />
            </button>
            <strong className="tnum">{year}</strong>
            <button className="btn icon sm ghost" aria-label="Next year" onClick={() => setYear(year + 1)}>
              <ChevronRight />
            </button>
          </div>
          <button className="btn primary" onClick={() => setEditing({ horizon: "quarter" })}>
            <Plus /> Add goal
          </button>
        </div>
      </header>

      {flat.length > 0 && (
        <div className="kpis">
          <Kpi label="Active goals" value={String(active.length)} />
          <Kpi label="Achieved" value={String(achieved)} />
          <Kpi label="Behind pace" value={String(behind)} sub="progress below the share of time passed" warn={behind > 0} />
          <Kpi label="Not measurable yet" value={String(unmeasured)} sub="add tasks, a number or sub-goals" />
        </div>
      )}

      {roots.map((n) => (
        <GoalItem key={n.goal.id} node={n} depth={0} career={career} onEdit={(g) => setEditing({ goal: g })} onAddChild={(g) => setEditing({ parent: g, horizon: g.horizon === "year" ? "quarter" : "month" })} />
      ))}

      {!isLoading && roots.length === 0 && (
        <EmptyState icon={Target} title={`No goals for ${year} yet`}>
          Start with one or two goals for the year, break them into quarter goals, and link the tasks that move them forward. Goals can also support a level expectation from your Career view.
          <div style={{ display: "flex", gap: 8, justifyContent: "center", marginTop: 12 }}>
            <button className="btn primary" onClick={() => setEditing({ horizon: "year" })}>
              <Plus /> Year goal
            </button>
            <button className="btn" onClick={() => setEditing({ horizon: "quarter" })}>
              <Plus /> Quarter goal
            </button>
          </div>
        </EmptyState>
      )}

      <GoalDialog key={editing ? JSON.stringify([editing.goal?.id, editing.parent?.id, editing.horizon]) : "closed"} state={editing} year={year} all={flat.map((n) => n.goal)} onClose={() => setEditing(null)} />
    </div>
  );
}

function GoalItem({ node, depth, career, onEdit, onAddChild }: { node: GoalNode; depth: number; career?: CareerMatrix; onEdit: (g: Goal) => void; onAddChild: (g: Goal) => void }) {
  const qc = useQueryClient();
  const g = node.goal;
  const [open, setOpen] = useState(depth === 0);
  const [over, setOver] = useState(false);
  const pct = node.progress.value === null ? null : Math.round(node.progress.value * 100);
  const expectations = useMemo(() => {
    const all = career?.levels.flatMap((l) => l.rows.map((r) => r.expectation)) ?? [];
    return node.expectation_ids.map((id) => all.find((e) => e.id === id)).filter((e): e is NonNullable<typeof e> => !!e);
  }, [career, node.expectation_ids]);

  const setStatus = async (status: Goal["status"]) => {
    await api.updateGoal(g.id, { status });
    if (status === "achieved") {
      celebrate("goal");
      toast.success("Goal achieved 🎯", { description: g.title });
    }
    invalidate(qc);
  };

  return (
    <div className={cx("goal", `h-${g.horizon}`, g.status !== "active" && `is-${g.status}`)} style={{ marginLeft: depth ? `${depth * 1.6}rem` : 0 }}>
      <article className={cx("card goal-card", over && "drop-over-zone")} {...dropProps(`goal:${g.id}`, setOver, () => invalidate(qc))} aria-label={`Goal: ${g.title}`}>
        <div className="goal-top">
          <button className="btn icon sm ghost" aria-label={open ? "Collapse" : "Expand"} aria-expanded={open} onClick={() => setOpen(!open)}>
            <ChevronDown style={{ transform: open ? undefined : "rotate(-90deg)", transition: "transform .15s" }} />
          </button>
          {depth > 0 && <CornerDownRight className="faint" size={14} />}
          <div className="goal-title">
            {g.emoji && <span className="goal-emoji">{g.emoji}</span>}
            <button className="goal-name" onClick={() => setOpen(!open)}>
              {g.title}
            </button>
            <span className="chip">{HORIZON_LABEL[g.horizon]} · {periodLabel(g.period)}</span>
            <span className={cx("chip", PACE_TONE[node.pace])} title="Compares progress with the share of the period that has passed — a hint, not a judgement">
              {node.pace}
            </span>
          </div>
          <div className="goal-actions">
            {g.status === "active" ? (
              <button className="btn sm ghost" onClick={() => void setStatus("achieved")} title="Mark achieved">
                <CheckCircle2 /> Achieved
              </button>
            ) : (
              <button className="btn sm ghost" onClick={() => void setStatus("active")}>
                Reopen
              </button>
            )}
            {g.horizon !== "month" && (
              <button className="btn icon sm ghost" aria-label={`Add sub-goal to ${g.title}`} title="Add sub-goal" onClick={() => onAddChild(g)}>
                <Plus />
              </button>
            )}
            <button className="btn icon sm ghost" aria-label={`Edit ${g.title}`} onClick={() => onEdit(g)}>
              <Pencil />
            </button>
          </div>
        </div>
        <div className="goal-progress">
          <div className="capacity-track" role="meter" aria-label={`Progress of ${g.title}`} aria-valuenow={pct ?? 0} aria-valuemin={0} aria-valuemax={100}>
            <motion.i initial={false} animate={{ width: `${pct ?? 0}%` }} style={{ background: g.status === "achieved" ? "var(--green)" : "var(--series-1)" }} />
          </div>
          <span className="goal-pct tnum">{pct === null ? "—" : `${pct}%`}</span>
          <span className="faint goal-basis">{node.progress.basis}</span>
        </div>
        {(expectations.length > 0 || node.project_ids.length > 0 || node.skill_ids.length > 0) && (
          <div className="goal-links">
            {expectations.map((e) => (
              <span key={e.id} className="chip accent" title={e.text}>
                <TrendingUp /> {e.level} · {e.text.length > 48 ? `${e.text.slice(0, 47)}…` : e.text}
              </span>
            ))}
            <ProjectChips ids={node.project_ids} />
            <SkillChips ids={node.skill_ids} />
          </div>
        )}
        {open && <GoalDetails node={node} career={career} />}
      </article>
      {node.children.map((c) => (
        <GoalItem key={c.goal.id} node={c} depth={depth + 1} career={career} onEdit={onEdit} onAddChild={onAddChild} />
      ))}
    </div>
  );
}

function SkillChips({ ids }: { ids: string[] }) {
  const ui = useUi();
  const { data } = useQuery({ queryKey: ["skills"], queryFn: api.skills, enabled: ids.length > 0 });
  const all = data?.categories.flatMap((c) => c.rows.map((r) => r.skill)) ?? [];
  return (
    <>
      {ids.map((id) => {
        const s = all.find((x) => x.id === id);
        return s ? (
          <button key={id} className="chip green" onClick={() => ui.navigate("skills")}>
            <Sprout /> {s.name}
          </button>
        ) : null;
      })}
    </>
  );
}

function ProjectChips({ ids }: { ids: string[] }) {
  const { data: projects = [] } = useProjects();
  return (
    <>
      {ids.map((id) => {
        const p = projects.find((x) => x.id === id);
        return p ? (
          <span key={id} className="chip">
            <FolderKanban /> {p.name}
          </span>
        ) : null;
      })}
    </>
  );
}

function GoalDetails({ node, career }: { node: GoalNode; career?: CareerMatrix }) {
  const ui = useUi();
  const qc = useQueryClient();
  const g = node.goal;
  const { data: tasks = [] } = useQuery({ queryKey: ["goals", "tasks", g.id, node.progress.total, node.progress.done], queryFn: () => api.goalTasks(g.id) });
  const { data: projects = [] } = useProjects();
  const [metric, setMetric] = useState(String(g.metric_current ?? g.metric_start ?? 0));
  const expectations = career?.levels.flatMap((l) => l.rows.map((r) => r.expectation)) ?? [];
  const link = async (kind: "expectation" | "project", id: string, on = true) => {
    try {
      await api.linkGoal(g.id, kind, id, on);
      invalidate(qc);
    } catch (e) {
      toast.error((e as Error).message);
    }
  };
  const open = tasks.filter((t) => t.status !== "done");
  const done = tasks.filter((t) => t.status === "done");

  return (
    <div className="goal-details">
      {g.description && <p className="goal-desc">{g.description}</p>}
      {g.progress_mode === "metric" && (
        <form
          className="inline-field"
          onSubmit={async (e) => {
            e.preventDefault();
            await api.updateGoal(g.id, { metric_current: Number(metric) });
            invalidate(qc);
          }}
        >
          Current value
          <input className="input" type="number" step="any" value={metric} onChange={(e) => setMetric(e.target.value)} aria-label={`Current value for ${g.title}`} />
          of {g.metric_target} {g.metric_unit}
          <button className="btn sm" type="submit">
            Update
          </button>
        </form>
      )}
      {g.progress_mode === "manual" && (
        <label className="inline-field">
          Your estimate
          <input
            type="range"
            min={0}
            max={100}
            step={5}
            defaultValue={g.manual_progress ?? 0}
            aria-label={`Progress estimate for ${g.title}`}
            onMouseUp={(e) => void api.updateGoal(g.id, { manual_progress: Number((e.target as HTMLInputElement).value) }).then(() => invalidate(qc))}
            onKeyUp={(e) => void api.updateGoal(g.id, { manual_progress: Number((e.target as HTMLInputElement).value) }).then(() => invalidate(qc))}
          />
        </label>
      )}

      <div className="section-label" style={{ marginTop: "0.6rem" }}>
        Tasks {tasks.length > 0 && `· ${done.length}/${tasks.length} done`}
      </div>
      <div className="goal-tasks">
        {open.map((t) => (
          <TaskCard key={t.id} task={t} onOpen={ui.openTask} showSchedule />
        ))}
        {done.slice(0, 5).map((t) => (
          <TaskCard key={t.id} task={t} onOpen={ui.openTask} />
        ))}
        {done.length > 5 && <div className="faint" style={{ fontSize: "0.85rem" }}>+{done.length - 5} more done</div>}
        <AddRow
          placeholder={g.progress_mode === "auto" ? "Add a task that moves this goal — e.g. Draft the plan ~1h" : "Add a task for this goal"}
          onAdd={async (title, est) => {
            await api.addGoalTask(g.id, title, est);
            invalidate(qc);
          }}
        />
        {tasks.length === 0 && <div className="faint goal-hint">Tip: drag any task card onto this goal to link it.</div>}
      </div>

      <div className="goal-linkers">
        <select
          className="select"
          value=""
          aria-label={`Support a level expectation with ${g.title}`}
          onChange={(e) => e.target.value && void link("expectation", e.target.value)}
        >
          <option value="">Supports a career expectation…</option>
          {expectations
            .filter((e) => !node.expectation_ids.includes(e.id))
            .map((e) => (
              <option key={e.id} value={e.id}>
                {e.level} · {e.text}
              </option>
            ))}
        </select>
        <select className="select" value="" aria-label={`Count a project's tasks toward ${g.title}`} onChange={(e) => e.target.value && void link("project", e.target.value)}>
          <option value="">Count a project’s tasks…</option>
          {projects
            .filter((p) => !node.project_ids.includes(p.id))
            .map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
        </select>
        {node.expectation_ids.map((id) => {
          const e = expectations.find((x) => x.id === id);
          return e ? (
            <button key={id} className="chip removable" onClick={() => void link("expectation", id, false)} title="Remove link">
              {e.level} · {e.text.slice(0, 30)} ×
            </button>
          ) : null;
        })}
        {node.project_ids.map((id) => {
          const p = projects.find((x) => x.id === id);
          return p ? (
            <button key={id} className="chip removable" onClick={() => void link("project", id, false)} title="Remove link">
              {p.name} ×
            </button>
          ) : null;
        })}
      </div>
    </div>
  );
}

function GoalDialog({ state, year, all, onClose }: { state: { goal?: Goal; parent?: Goal; horizon?: GoalHorizon } | null; year: number; all: Goal[]; onClose: () => void }) {
  const qc = useQueryClient();
  const g = state?.goal;
  const [title, setTitle] = useState(g?.title ?? "");
  const [emoji, setEmoji] = useState(g?.emoji ?? "");
  const [horizon, setHorizon] = useState<GoalHorizon>(g?.horizon ?? state?.horizon ?? "quarter");
  const [period, setPeriod] = useState(g?.period ?? (state?.parent?.horizon === "quarter" && horizon === "month" ? `${state.parent.period.slice(0, 4)}-${String((Number(state.parent.period.slice(-1)) - 1) * 3 + 1).padStart(2, "0")}` : currentPeriod(g?.horizon ?? state?.horizon ?? "quarter", year)));
  const [parentId, setParentId] = useState(g?.parent_id ?? state?.parent?.id ?? "");
  const [description, setDescription] = useState(g?.description ?? "");
  const [mode, setMode] = useState<GoalMode>(g?.progress_mode ?? "auto");
  const [unit, setUnit] = useState(g?.metric_unit ?? "");
  const [start, setStart] = useState(String(g?.metric_start ?? 0));
  const [target, setTarget] = useState(g?.metric_target != null ? String(g.metric_target) : "");
  const rank = { year: 0, quarter: 1, month: 2 };
  const parents = all.filter((p) => rank[p.horizon] < rank[horizon] && p.id !== g?.id && p.status !== "dropped");

  const pickHorizon = (h: GoalHorizon) => {
    setHorizon(h);
    setPeriod(currentPeriod(h, year));
    if (parentId && !all.some((p) => p.id === parentId && rank[p.horizon] < rank[h])) setParentId("");
  };
  const save = async () => {
    const body: Partial<Goal> & { title: string; horizon: GoalHorizon } = {
      title,
      horizon,
      period,
      emoji: emoji || null,
      description,
      parent_id: parentId || null,
      progress_mode: mode,
      metric_unit: mode === "metric" ? unit || null : null,
      metric_start: mode === "metric" ? Number(start) || 0 : null,
      metric_target: mode === "metric" && target !== "" ? Number(target) : null,
    };
    try {
      if (g) await api.updateGoal(g.id, body);
      else await api.createGoal(body);
      toast.success(g ? "Goal updated" : "Goal added 🎯", { description: title });
      invalidate(qc);
      onClose();
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  return (
    <Dialog open={!!state} onClose={onClose} label={g ? "Edit goal" : "New goal"} width={600}>
      {state && (
        <form
          className="log-call goal-form"
          onSubmit={(e) => {
            e.preventDefault();
            if (title.trim()) void save();
          }}
        >
          <div className="lc-head">
            <Target size={18} />
            <h3>{g ? "Edit goal" : "New goal"}</h3>
          </div>
          <div className="lc-row">
            <label className="lc-field" style={{ maxWidth: "5rem" }}>
              <span>Emoji</span>
              <input className="input" value={emoji} maxLength={4} placeholder="🎯" onChange={(e) => setEmoji(e.target.value)} />
            </label>
            <label className="lc-field" style={{ flex: 1 }}>
              <span>Goal</span>
              <input className="input" autoFocus value={title} placeholder="e.g. Lead the retrieval launch end to end" onChange={(e) => setTitle(e.target.value)} />
            </label>
          </div>
          <div className="lc-row">
            <div className="lc-field">
              <span>Horizon</span>
              <div className="segmented" role="group" aria-label="Horizon">
                {(["year", "quarter", "month"] as GoalHorizon[]).map((h) => (
                  <button type="button" key={h} aria-pressed={horizon === h} onClick={() => pickHorizon(h)}>
                    {HORIZON_LABEL[h]}
                  </button>
                ))}
              </div>
            </div>
            <label className="lc-field">
              <span>Period</span>
              <select className="select" value={period} onChange={(e) => setPeriod(e.target.value)} aria-label="Period">
                {periodOptions(horizon, year).map(([v, l]) => (
                  <option key={v} value={v}>
                    {l}
                  </option>
                ))}
              </select>
            </label>
          </div>
          {horizon !== "year" && (
            <label className="lc-field">
              <span>Part of</span>
              <select className="select" value={parentId} onChange={(e) => setParentId(e.target.value)} aria-label="Parent goal">
                <option value="">— standalone —</option>
                {parents.map((p) => (
                  <option key={p.id} value={p.id}>
                    {HORIZON_LABEL[p.horizon]} {periodLabel(p.period)} · {p.title}
                  </option>
                ))}
              </select>
            </label>
          )}
          <label className="lc-field">
            <span>Why it matters / what done looks like</span>
            <textarea className="input" rows={2} value={description} onChange={(e) => setDescription(e.target.value)} />
          </label>
          <div className="lc-field">
            <span>Measure progress by</span>
            <div className="segmented" role="group" aria-label="Progress">
              {(
                [
                  ["auto", "Linked tasks"],
                  ["metric", "A number"],
                  ["manual", "My estimate"],
                ] as [GoalMode, string][]
              ).map(([m, l]) => (
                <button type="button" key={m} aria-pressed={mode === m} onClick={() => setMode(m)}>
                  {l}
                </button>
              ))}
            </div>
          </div>
          {mode === "metric" && (
            <div className="lc-row">
              <label className="lc-field">
                <span>Start</span>
                <input className="input" type="number" step="any" value={start} onChange={(e) => setStart(e.target.value)} />
              </label>
              <label className="lc-field">
                <span>Target</span>
                <input className="input" type="number" step="any" value={target} placeholder="e.g. 4" onChange={(e) => setTarget(e.target.value)} aria-label="Target" />
              </label>
              <label className="lc-field">
                <span>Unit</span>
                <input className="input" value={unit} placeholder="e.g. talks, % recall" onChange={(e) => setUnit(e.target.value)} />
              </label>
            </div>
          )}
          <div className="lc-foot">
            {g && (
              <button
                type="button"
                className="btn ghost danger"
                style={{ marginRight: "auto" }}
                onClick={async () => {
                  if (!confirm(`Delete “${g.title}”? Its tasks and sub-goals are kept.`)) return;
                  await api.deleteGoal(g.id);
                  invalidate(qc);
                  onClose();
                }}
              >
                <Trash2 /> Delete
              </button>
            )}
            {g && g.status === "active" && (
              <button type="button" className="btn ghost" onClick={() => void api.updateGoal(g.id, { status: "paused" }).then(() => (invalidate(qc), onClose()))}>
                Pause
              </button>
            )}
            {g && g.status === "active" && (
              <button type="button" className="btn ghost" onClick={() => void api.updateGoal(g.id, { status: "dropped" }).then(() => (invalidate(qc), onClose()))}>
                Drop
              </button>
            )}
            <button type="button" className="btn ghost" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="btn primary" disabled={!title.trim()}>
              {g ? "Save" : "Add goal"}
            </button>
          </div>
        </form>
      )}
    </Dialog>
  );
}

