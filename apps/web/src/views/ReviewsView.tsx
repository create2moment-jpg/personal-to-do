import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarRange, Check, ClipboardCopy, FileText, Loader2, Lock, RefreshCw, ShieldCheck, Sparkles, Trash2, Unlock, XCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { RankBars } from "../components/charts";
import { EmptyState } from "../components/primitives";
import { api } from "../lib/api";
import type { DueReview, Review, ReviewDraft, ReviewKind, ReviewSection } from "../lib/types";
import { useUi } from "../lib/ui-store";
import { cx, formatMinutes, relativeTime } from "../lib/util";
import { Kpi } from "./WeekView";

const KIND_LABEL: Record<ReviewKind, string> = { month: "Monthly", bimonth: "Bi-monthly", quarter: "Quarterly", year: "Annual" };
const SECTIONS: { key: ReviewSection; label: string; placeholder: string }[] = [
  { key: "highlights", label: "Highlights", placeholder: "What went well? What are you proud of?" },
  { key: "challenges", label: "Challenges", placeholder: "What was hard, slow or blocked?" },
  { key: "learnings", label: "Learnings", placeholder: "What did you learn about the work, or about how you work?" },
  { key: "next_focus", label: "Next focus", placeholder: "What will you focus on next period?" },
];

export function ReviewsView({ reviewId }: { reviewId?: string }) {
  const ui = useUi();
  const qc = useQueryClient();
  const { data: due = [] } = useQuery({ queryKey: ["reviews", "due"], queryFn: api.dueReviews });
  const { data: all = [] } = useQuery({ queryKey: ["reviews", "all"], queryFn: api.reviews });
  const selected = reviewId ?? all[0]?.id;

  const open = async (d: DueReview) => {
    if (d.review_id) return ui.navigate("reviews", d.review_id);
    const r = await api.openReview(d.kind, d.period);
    void qc.invalidateQueries({ queryKey: ["reviews"] });
    ui.navigate("reviews", r.id);
  };

  return (
    <div className="knowledge-layout reviews-layout">
      <aside className="notes-sidebar">
        <div className="notes-sidebar-head">
          <h1 className="page-title" style={{ fontSize: "1.43rem" }}>
            Reviews
          </h1>
        </div>
        <div className="notes-items">
          <div className="section-label review-group">Due & in progress</div>
          {due.map((d) => (
            <button key={`${d.kind}-${d.period}`} className={cx("note-item", d.review_id === selected && "active")} onClick={() => void open(d)}>
              <span className="n-title">{d.label}</span>
              <span className="n-meta">
                {KIND_LABEL[d.kind]} ·{" "}
                <span className={cx("chip", d.status === "final" ? "green" : d.status === "draft" ? "accent" : d.in_progress ? "" : "orange")} style={{ height: "1.15rem" }}>
                  {d.status === "final" ? "Final" : d.status === "draft" ? "Draft" : d.in_progress ? "In progress" : "Due"}
                </span>
              </span>
            </button>
          ))}
          {all.filter((r) => !due.some((d) => d.review_id === r.id)).length > 0 && <div className="section-label review-group">Earlier</div>}
          {all
            .filter((r) => !due.some((d) => d.review_id === r.id))
            .map((r) => (
              <button key={r.id} className={cx("note-item", r.id === selected && "active")} onClick={() => ui.navigate("reviews", r.id)}>
                <span className="n-title">{r.label}</span>
                <span className="n-meta">
                  {KIND_LABEL[r.kind]} · {r.status === "final" ? "Final" : "Draft"}
                </span>
              </button>
            ))}
        </div>
      </aside>
      <div className="editor-wrap">
        {selected ? (
          <ReviewDoc key={selected} id={selected} />
        ) : (
          <div className="page" style={{ maxWidth: "52rem" }}>
            <EmptyState icon={CalendarRange} title="Look back, then decide what's next">
              Pick a month, two months, a quarter or the year on the left. The numbers come from your own tasks, meetings, sprints, goals, skills and daily reviews; the words are yours — or a draft from your local AI that has to cite your records.
            </EmptyState>
          </div>
        )}
      </div>
    </div>
  );
}

function ReviewDoc({ id }: { id: string }) {
  const ui = useUi();
  const qc = useQueryClient();
  const { data: r } = useQuery({ queryKey: ["reviews", "one", id], queryFn: () => api.review(id) });
  const { data: ai } = useQuery({ queryKey: ["ai-status"], queryFn: api.aiStatus, staleTime: 60_000 });
  const [draft, setDraft] = useState<ReviewDraft | null>(null);
  const [drafting, setDrafting] = useState(false);
  if (!r) return <div className="page faint">Loading…</div>;
  const s = r.snapshot;
  const final = r.status === "final";
  const items = Object.fromEntries(s.items.map((i) => [i.id, i.text]));
  const reload = (next: Review) => {
    qc.setQueryData(["reviews", "one", id], next);
    void qc.invalidateQueries({ queryKey: ["reviews", "due"] });
    void qc.invalidateQueries({ queryKey: ["reviews", "all"] });
  };
  const goalsAchieved = s.goals.filter((g) => g.achieved_in_period).length;
  const skillsUp = s.skills.filter((k) => k.from !== null && k.to > k.from).length;

  return (
    <div className="page review-doc">
      <header className="page-head">
        <div>
          <div className="section-label">
            {KIND_LABEL[r.kind]} review · {s.start} → {s.end}
            {!s.complete && " · period still running"}
          </div>
          <h1 className="page-title">{r.label}</h1>
          <div className="page-sub">
            {final ? (
              <>
                <Lock size={13} /> Final since {relativeTime(r.finalized_at!)} — numbers frozen
              </>
            ) : (
              <>Numbers as of {relativeTime(s.computed_at)}</>
            )}
            {r.ai_model && <span className="faint"> · AI draft used ({r.ai_model})</span>}
          </div>
        </div>
        <div className="review-actions">
          {!final && (
            <button className="btn sm ghost" onClick={async () => reload(await api.refreshReview(id))} title="Recompute from your records">
              <RefreshCw /> Refresh numbers
            </button>
          )}
          {!final && (
            <button
              className="btn sm"
              disabled={drafting || !ai?.enabled}
              title={ai?.enabled ? "Draft bullets from your records with your local model" : "Turn on Local AI in Settings to draft"}
              onClick={async () => {
                setDrafting(true);
                try {
                  const d = await api.draftReview(id);
                  setDraft(d);
                  const kept = Object.values(d.sections).reduce((a, b) => a + (b?.length ?? 0), 0);
                  toast.success(`Draft ready: ${kept} suggestion(s)`, { description: d.dropped.length ? `${d.dropped.length} dropped — not supported by your records` : "Every suggestion cites your records" });
                } catch (e) {
                  toast.error((e as Error).message);
                } finally {
                  setDrafting(false);
                }
              }}
            >
              {drafting ? <Loader2 className="spin" /> : <Sparkles />} Draft with AI
            </button>
          )}
          <button
            className="btn sm ghost"
            onClick={async () => {
              await navigator.clipboard.writeText(await api.reviewMarkdown(id));
              toast.success("Copied as Markdown");
            }}
          >
            <ClipboardCopy /> Copy
          </button>
          <button className={cx("btn sm", !final && "primary")} onClick={async () => reload(await api.finalizeReview(id, !final))}>
            {final ? <Unlock /> : <Check />} {final ? "Reopen" : "Finalize"}
          </button>
          <button
            className="btn icon sm ghost danger"
            aria-label="Delete review"
            onClick={async () => {
              if (!confirm(`Delete the ${r.label} review?`)) return;
              await api.deleteReview(id);
              void qc.invalidateQueries({ queryKey: ["reviews"] });
              ui.navigate("reviews");
            }}
          >
            <Trash2 />
          </button>
        </div>
      </header>

      <div className="kpis">
        <Kpi label="Tasks completed" value={String(s.tasks.completed)} sub={`${formatMinutes(s.tasks.actual_minutes)} logged · ${formatMinutes(s.tasks.estimated_minutes)} estimated`} />
        <Kpi label="Estimate accuracy" value={s.tasks.accuracy === null ? "—" : `${Math.round(s.tasks.accuracy * 100)}%`} sub="time logged ÷ estimate" warn={s.tasks.accuracy !== null && s.tasks.accuracy > 1.3} />
        <Kpi label="On time" value={s.tasks.with_due ? `${s.tasks.on_time}/${s.tasks.with_due}` : "—"} sub="tasks with a due date" />
        <Kpi label="In meetings" value={s.time.meeting_share !== undefined ? `${s.time.meeting_share}%` : "—"} sub={s.time.meeting_minutes !== undefined ? `${formatMinutes(s.time.meeting_minutes)} of ${formatMinutes(s.time.work_minutes ?? 0)}` : undefined} warn={(s.time.meeting_share ?? 0) > 40} />
        <Kpi label="Goals achieved" value={String(goalsAchieved)} sub={`${s.goals.length} goals in this period`} />
        <Kpi label="Evidence · skills" value={`${s.evidence.length} · ${skillsUp}↑`} sub="evidence accepted · skills rated up" />
      </div>

      <div className="review-grid">
        <section className="card panel">
          <h3>Work by project</h3>
          <RankBars items={s.tasks.by_project.map(([name, count, minutes]) => ({ name, minutes, count }))} empty="No completed tasks in this period." />
        </section>
        <section className="card panel">
          <h3>Time with people</h3>
          <RankBars items={(s.time.by_person ?? []).map(([name, minutes, count]) => ({ name, minutes, count }))} empty="No meetings or calls with people recorded." />
        </section>
        {s.goals.length > 0 && (
          <section className="card panel">
            <h3>Goals</h3>
            {s.goals.map((g) => (
              <div key={`${g.title}-${g.period}`} className="review-goal">
                <span className={cx(g.status === "achieved" && "done-text")}>{g.title}</span>
                <span className={cx("chip", g.status === "achieved" ? "green" : g.pace === "behind" ? "orange" : "")}>{g.status === "achieved" ? "achieved" : g.progress === null ? "unmeasured" : `${g.progress}% · ${g.pace}`}</span>
              </div>
            ))}
          </section>
        )}
        {(s.sprints.length > 0 || s.skills.length > 0) && (
          <section className="card panel">
            {s.sprints.length > 0 && <h3>Sprints</h3>}
            {s.sprints.map((sp) => (
              <div key={sp.name} className="review-goal">
                <span>{sp.name}</span>
                <span className="chip">
                  {sp.done}/{sp.committed} committed done
                </span>
              </div>
            ))}
            {s.skills.length > 0 && <h3 style={{ marginTop: s.sprints.length ? 12 : 0 }}>Skills rated</h3>}
            {s.skills.map((k) => (
              <div key={k.name} className="review-goal">
                <span>{k.name}</span>
                <span className={cx("chip", k.from !== null && k.to > k.from && "green")}>{k.from === null ? `rated ${k.to}` : `${k.from} → ${k.to}`}</span>
              </div>
            ))}
          </section>
        )}
      </div>

      {(s.notes.wins.length > 0 || s.notes.learnings.length > 0 || s.notes.blockers.length > 0) && (
        <details className="card panel review-notes">
          <summary>
            From your daily and weekly reviews · {s.notes.wins.length} wins, {s.notes.learnings.length} learnings, {s.notes.blockers.length} blockers
          </summary>
          {(["wins", "learnings", "blockers"] as const).map((k) =>
            s.notes[k].length ? (
              <div key={k}>
                <div className="section-label" style={{ marginTop: 10 }}>
                  {k}
                </div>
                <ul>
                  {s.notes[k].map(([d, t]) => (
                    <li key={`${d}-${t}`}>
                      <span className="faint">{d}</span> {t}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null,
          )}
        </details>
      )}

      {draft && draft.dropped.length > 0 && (
        <details className="dropped-box">
          <summary>
            <ShieldCheck size={14} /> {draft.dropped.length} AI suggestion(s) dropped because your records don’t support them
          </summary>
          <ul>
            {draft.dropped.map(([b, why]) => (
              <li key={b}>
                <XCircle size={12} /> <s>{b}</s> <span className="faint">— {why}</span>
              </li>
            ))}
          </ul>
        </details>
      )}

      {SECTIONS.map((sec) => (
        <SectionEditor key={sec.key} review={r} section={sec} suggestions={draft?.sections[sec.key] ?? []} items={items} onSaved={reload} onUsed={() => setDraft((d) => (d ? { ...d, sections: { ...d.sections, [sec.key]: [] } } : d))} draftMeta={draft} />
      ))}
      <p className="faint review-foot">
        <FileText size={13} /> Numbers are computed from your own records only. AI suggestions must cite those records and only use numbers they contain — anything else is dropped before you see it.
      </p>
    </div>
  );
}

function SectionEditor({
  review,
  section,
  suggestions,
  items,
  onSaved,
  onUsed,
  draftMeta,
}: {
  review: Review;
  section: (typeof SECTIONS)[number];
  suggestions: string[];
  items: Record<string, string>;
  onSaved: (r: Review) => void;
  onUsed: () => void;
  draftMeta: ReviewDraft | null;
}) {
  const [text, setText] = useState(review[section.key]);
  useEffect(() => setText(review[section.key]), [review, section.key]);
  const final = review.status === "final";
  const save = async (value: string, extra: Partial<Review> = {}) => {
    if (value === review[section.key] && !Object.keys(extra).length) return;
    onSaved(await api.updateReview(review.id, { [section.key]: value, ...extra }));
  };
  const use = async (bullets: string[]) => {
    const add = bullets.map((b) => `- ${b}`).join("\n");
    const next = text.trim() ? `${text.trim()}\n${add}` : add;
    setText(next);
    await save(next, draftMeta ? { ai_model: draftMeta.model, ai_template: draftMeta.template } : {});
    onUsed();
  };
  return (
    <section className="review-section">
      <label className="review-section-label" htmlFor={`sec-${section.key}`}>
        {section.label}
      </label>
      {suggestions.length > 0 && (
        <div className="ai-suggestions">
          <div className="section-label">
            <Sparkles size={11} /> Suggested from your records · you decide
          </div>
          {suggestions.map((b) => (
            <div key={b} className="ai-suggestion">
              <span>
                {b.split(/(\[[A-Z]\d+\])/).map((part, i) =>
                  /^\[[A-Z]\d+\]$/.test(part) ? (
                    <span key={i} className="cite" title={items[part.slice(1, -1)] ?? ""}>
                      {part.slice(1, -1)}
                    </span>
                  ) : (
                    <span key={i}>{part}</span>
                  ),
                )}
              </span>
              <button className="btn sm ghost" onClick={() => void use([b])}>
                Use
              </button>
            </div>
          ))}
          {suggestions.length > 1 && (
            <button className="btn sm" onClick={() => void use(suggestions)}>
              Use all
            </button>
          )}
        </div>
      )}
      <textarea
        id={`sec-${section.key}`}
        className="input review-text"
        rows={Math.max(3, text.split("\n").length + 1)}
        placeholder={section.placeholder}
        value={text}
        readOnly={final}
        onChange={(e) => setText(e.target.value)}
        onBlur={() => void save(text)}
      />
    </section>
  );
}
