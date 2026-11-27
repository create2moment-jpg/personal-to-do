import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CalendarCheck2, CheckCircle2, ClipboardCheck, Loader2, MinusCircle, Play, ShieldCheck, TrendingUp, XCircle } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { api } from "../lib/api";
import { invalidateTasks } from "../lib/queries";
import type { WorkflowRun } from "../lib/types";
import { useUi } from "../lib/ui-store";
import { cx, relativeTime } from "../lib/util";

const CARDS: { id: string; icon: typeof Play; title: string; what: string; when: string }[] = [
  {
    id: "plan_week",
    icon: CalendarCheck2,
    title: "Plan my week",
    what: "Fits overdue work, tasks due this week and unscheduled sprint work into each day's free capacity — earliest day first, never after a due date — and suggests weekly objectives from your goals.",
    when: "Monday morning",
  },
  {
    id: "week_review",
    icon: ClipboardCheck,
    title: "Prepare my weekly review",
    what: "Moves unfinished work to next Monday and fills the review: wins from what you finished, plus lessons, risks and focus drafted by your local AI with citations (if it is on).",
    when: "Friday afternoon",
  },
  {
    id: "evidence_pack",
    icon: TrendingUp,
    title: "Build a promotion evidence pack",
    what: "For the next level you're working towards: links the best-matching accepted evidence to each uncovered expectation, turns real gaps into tasks, and writes the pack as a note with quotes.",
    when: "Before a 1:1 or review",
  },
];

/** Agentic workflows: each proposes a checklist; nothing changes until you apply. */
export function WorkflowsView() {
  const qc = useQueryClient();
  const ui = useUi();
  const { data: runs = [] } = useQuery({ queryKey: ["workflow-runs"], queryFn: api.workflowRuns });
  const [busy, setBusy] = useState<string | null>(null);
  const [current, setCurrent] = useState<WorkflowRun | null>(null);
  const [keep, setKeep] = useState<Set<string>>(new Set());

  const open = (r: WorkflowRun) => {
    setCurrent(r);
    setKeep(new Set(r.actions.filter((a) => a.selected).map((a) => a.id)));
  };
  const start = async (id: string) => {
    setBusy(id);
    try {
      open(await api.runWorkflow(id));
      void qc.invalidateQueries({ queryKey: ["workflow-runs"] });
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusy(null);
    }
  };
  const apply = async () => {
    if (!current) return;
    setBusy("apply");
    try {
      const r = await api.applyWorkflow(current.id, [...keep]);
      setCurrent(r);
      const ok = r.actions.filter((a) => a.outcome === "applied").length;
      const failed = r.actions.filter((a) => a.outcome?.startsWith("failed")).length;
      if (failed) toast.warning(`${ok} applied, ${failed} could not be applied — see the list`);
      else toast.success(`${ok} change(s) applied`);
      invalidateTasks(qc);
      for (const k of ["workflow-runs", "career", "notes", "week"]) void qc.invalidateQueries({ queryKey: [k] });
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="page workflows-page">
      <header className="page-head">
        <div>
          <h1 className="page-title">Workflows</h1>
          <div className="page-sub">Multi-step helpers that read your records and propose a checklist. Nothing changes until you tick what to keep and apply it.</div>
        </div>
      </header>

      <div className="wf-cards">
        {CARDS.map((c) => (
          <article key={c.id} className="card wf-card" aria-label={c.title}>
            <div className="wf-card-head">
              <c.icon size={18} />
              <h3>{c.title}</h3>
              <span className="chip">{c.when}</span>
            </div>
            <p>{c.what}</p>
            <button className="btn primary" disabled={busy !== null} onClick={() => void start(c.id)}>
              {busy === c.id ? <Loader2 className="spin" /> : <Play />} Run
            </button>
          </article>
        ))}
      </div>

      {current && (
        <section className="card wf-run" aria-label={`Proposal: ${current.title}`}>
          <div className="wf-run-head">
            <div>
              <h3>{current.title}</h3>
              <div className="faint">{current.summary}</div>
            </div>
            <span className={cx("chip", current.status === "applied" ? "green" : current.status === "dismissed" ? "" : "accent")}>{current.status}</span>
          </div>
          {current.notes.map((n) => (
            <div key={n} className="wf-note">
              <AlertTriangle size={14} /> {n}
            </div>
          ))}
          {current.actions.length === 0 && <div className="faint" style={{ margin: "10px 0" }}>Nothing to propose right now.</div>}
          <ul className="wf-actions">
            {current.actions.map((a) => (
              <li key={a.id} className={cx(a.outcome && `out-${a.outcome.split(":")[0]}`)}>
                {current.status === "proposed" ? (
                  <input
                    type="checkbox"
                    className="check"
                    checked={keep.has(a.id)}
                    aria-label={a.label}
                    onChange={() => {
                      const next = new Set(keep);
                      if (next.has(a.id)) next.delete(a.id);
                      else next.add(a.id);
                      setKeep(next);
                    }}
                  />
                ) : a.outcome === "applied" ? (
                  <CheckCircle2 className="ok" size={16} aria-label="applied" />
                ) : a.outcome?.startsWith("failed") ? (
                  <XCircle className="bad" size={16} aria-label="failed" />
                ) : (
                  <MinusCircle className="faint" size={16} aria-label="skipped" />
                )}
                <div>
                  <div className="wf-label">{a.label}</div>
                  <div className="faint wf-detail">{a.outcome?.startsWith("failed") ? a.outcome : a.detail}</div>
                </div>
              </li>
            ))}
          </ul>
          {current.status === "proposed" ? (
            <div className="wf-foot">
              <span className="faint">
                <ShieldCheck size={13} /> Applied through the same rules as everywhere else, and recorded.
              </span>
              <button
                className="btn ghost"
                onClick={async () => {
                  setCurrent(await api.dismissWorkflow(current.id));
                  void qc.invalidateQueries({ queryKey: ["workflow-runs"] });
                }}
              >
                Dismiss
              </button>
              <button className="btn primary" disabled={keep.size === 0 || busy !== null} onClick={() => void apply()}>
                {busy === "apply" ? <Loader2 className="spin" /> : <CheckCircle2 />} Apply {keep.size}
              </button>
            </div>
          ) : (
            current.workflow === "evidence_pack" &&
            current.status === "applied" && (
              <div className="wf-foot">
                <button className="btn" onClick={() => ui.navigate("notes")}>
                  Open Notes
                </button>
                <button className="btn" onClick={() => ui.navigate("career")}>
                  Open Career
                </button>
              </div>
            )
          )}
        </section>
      )}

      {runs.length > 0 && (
        <section className="wf-history" aria-label="Recent runs">
          <div className="section-label">Recent runs</div>
          {runs.map((r) => (
            <button key={r.id} className={cx("wf-hist", current?.id === r.id && "on")} onClick={() => open(r)}>
              <span>{r.title}</span>
              <span className="faint">
                {r.status} · {relativeTime(r.applied_at ?? r.created_at)}
              </span>
            </button>
          ))}
        </section>
      )}
    </div>
  );
}
