import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowDownRight, ArrowUpRight, Brain, Check, ChevronDown, Info, Link2, Plus, Quote, Search, Sparkles, Sprout, Trash2, X } from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "sonner";
import { MatchWhy, OwnEvidenceForm } from "../components/OwnEvidence";
import { Dialog, EmptyState } from "../components/primitives";
import { api } from "../lib/api";
import type { Fact, SkillMatrix, SkillRow } from "../lib/types";
import { useUi } from "../lib/ui-store";
import { cx, relativeTime } from "../lib/util";
import { Kpi } from "./WeekView";

const EVIDENCE_KINDS = ["achievement", "responsibility", "competency", "strength"];

const refresh = (qc: ReturnType<typeof useQueryClient>) => {
  void qc.invalidateQueries({ queryKey: ["skills"] });
  void qc.invalidateQueries({ queryKey: ["goals"] });
};

export function SkillsView() {
  const qc = useQueryClient();
  const { data: m, isLoading } = useQuery({ queryKey: ["skills"], queryFn: api.skills });
  const [adding, setAdding] = useState(false);
  const [linking, setLinking] = useState<SkillRow | null>(null);
  const levels = m?.levels ?? {};
  const rows = m?.categories.flatMap((c) => c.rows) ?? [];
  const rated = rows.filter((r) => r.level !== null);
  const gaps = rows.filter((r) => (r.gap ?? 0) > 0);
  const withEvidence = rows.filter((r) => r.evidence.length > 0);

  return (
    <div className="page skills-page">
      <header className="page-head">
        <div>
          <h1 className="page-title">Skills</h1>
          <div className="page-sub">Where you are, where you want to be, and the evidence behind it.</div>
        </div>
        <button className="btn primary" onClick={() => setAdding((a) => !a)}>
          <Plus /> Add skill
        </button>
      </header>

      <div className="career-note">
        <Info />
        <span>
          Self-assessment on a 1–5 scale: {Object.entries(levels).map(([n, [label]]) => `${n} ${label}`).join(" · ")}. Filled dots are where you are; the orange ring is your target. It’s your own view, backed by evidence you choose — not a rating by anyone else.
        </span>
      </div>

      {adding && <AddSkill matrix={m} onDone={() => setAdding(false)} />}

      {m && m.candidates.length > 0 && (
        <section className="card candidates">
          <div className="section-label">
            <Sparkles size={12} /> From competencies you accepted in Knowledge
          </div>
          <div className="candidate-chips">
            {m.candidates.slice(0, 12).map((f) => (
              <button
                key={f.id}
                className="filter-chip"
                title={`“${f.quote}”`}
                onClick={async () => {
                  try {
                    await api.createSkill({ name: f.statement.slice(0, 120), category: "From reviews", from_fact_id: f.id });
                    toast.success("Skill added — now rate yourself", { description: f.statement });
                    refresh(qc);
                  } catch (e) {
                    toast.error((e as Error).message);
                  }
                }}
              >
                <Plus /> {f.statement.length > 50 ? `${f.statement.slice(0, 49)}…` : f.statement}
              </button>
            ))}
          </div>
        </section>
      )}

      {rows.length > 0 && (
        <div className="kpis">
          <Kpi label="Skills" value={String(rows.length)} sub={`${rated.length} rated`} />
          <Kpi label="Below your target" value={String(gaps.length)} sub="gap between today and target" />
          <Kpi label="Backed by evidence" value={String(withEvidence.length)} sub={`of ${rows.length} skills`} />
        </div>
      )}

      {m?.categories.map((cat) => (
        <section key={cat.category} className="skill-group" aria-label={`Skills: ${cat.category}`}>
          <h2 className="level-head">
            <span className="level-badge">{cat.category}</span>
          </h2>
          <div className="card skill-table">
            {cat.rows.map((r) => (
              <SkillLine key={r.skill.id} row={r} levels={levels} categories={m.categories.map((c) => c.category)} onLink={() => setLinking(r)} />
            ))}
          </div>
        </section>
      ))}

      {!isLoading && rows.length === 0 && !adding && (
        <EmptyState icon={Brain} title="Build your skills matrix">
          Add the skills that matter for your role — system design, mentoring, a language, stakeholder communication — rate where you are today and where you want to be. Link accepted evidence from your reviews, and turn gaps into goals.
          <div style={{ marginTop: 12 }}>
            <button className="btn primary" onClick={() => setAdding(true)}>
              <Plus /> Add your first skill
            </button>
          </div>
        </EmptyState>
      )}

      <LinkDialog row={linking} onClose={() => setLinking(null)} />
    </div>
  );
}

function SkillLine({ row, levels, categories, onLink }: { row: SkillRow; levels: SkillMatrix["levels"]; categories: string[]; onLink: () => void }) {
  const ui = useUi();
  const qc = useQueryClient();
  const s = row.skill;
  const [open, setOpen] = useState(false);
  const trend = row.level !== null && row.previous !== null ? row.level - row.previous : 0;

  const rate = async (level: number) => {
    await api.rateSkill(s.id, level);
    toast.success(`${s.name}: ${levels[level]?.[0]} (${level})`, { description: "Saved — earlier ratings stay in the history." });
    refresh(qc);
  };

  return (
    <div className={cx("skill-line", open && "open")}>
      <div className="skill-main">
        <button className="btn icon sm ghost" aria-label={open ? `Collapse ${s.name}` : `Expand ${s.name}`} aria-expanded={open} onClick={() => setOpen(!open)}>
          <ChevronDown style={{ transform: open ? undefined : "rotate(-90deg)", transition: "transform .15s" }} />
        </button>
        <div className="skill-name">
          <strong>{s.name}</strong>
          {s.description && <span className="faint">{s.description}</span>}
        </div>
        <div className="level-dots" role="group" aria-label={`Rate ${s.name}`}>
          {[1, 2, 3, 4, 5].map((n) => (
            <button
              key={n}
              className={cx("dot", row.level !== null && n <= row.level && "on", s.target_level === n && "target")}
              title={`${n} · ${levels[n]?.[0]} — ${levels[n]?.[1]}${s.target_level === n ? " (your target)" : ""}`}
              aria-label={`${n} ${levels[n]?.[0]}`}
              aria-pressed={row.level === n}
              onClick={() => void rate(n)}
            />
          ))}
          <span className="level-label">{row.level ? levels[row.level]?.[0] : "Not rated"}</span>
        </div>
        <span className={cx("chip trend", trend > 0 && "green", trend < 0 && "orange")} title="Compared with your rating about three months ago">
          {trend > 0 ? <ArrowUpRight /> : trend < 0 ? <ArrowDownRight /> : null}
          {trend > 0 ? `+${trend}` : trend < 0 ? trend : row.history.length > 1 ? "steady" : row.history.length === 1 ? "1 rating" : "—"}
        </span>
        <button className={cx("btn sm", row.evidence.length ? "" : "ghost")} onClick={onLink} aria-label={`Evidence for ${s.name}`}>
          <Link2 /> {row.evidence.length}
          {row.suggestion_count > 0 && (
            <span className="chip accent" style={{ height: "1.1rem" }}>
              <Sparkles /> {row.suggestion_count}
            </span>
          )}
        </button>
        <div className="skill-goal">
          {row.goal_ids.length > 0 ? (
            <button className="chip green" onClick={() => ui.navigate("goals")}>
              <Sprout /> growth goal
            </button>
          ) : (row.gap ?? 0) > 0 ? (
            <button
              className="btn sm ghost"
              onClick={async () => {
                const g = await api.skillGoal(s.id);
                toast.success("Goal added for this quarter 🌱", { description: g.title, action: { label: "Open Goals", onClick: () => ui.navigate("goals") } });
                refresh(qc);
              }}
            >
              <Sprout /> Make it a goal
            </button>
          ) : (
            <span className="faint" style={{ fontSize: "0.8rem" }}>
              {s.target_level ? "at target" : "no target"}
            </span>
          )}
        </div>
      </div>

      {open && (
        <div className="skill-details">
          <div className="skill-settings">
            <label className="inline-field">
              Target
              <select className="select" value={s.target_level ?? ""} aria-label={`Target for ${s.name}`} onChange={(e) => void api.updateSkill(s.id, { target_level: e.target.value ? Number(e.target.value) : null }).then(() => refresh(qc))}>
                <option value="">none</option>
                {[1, 2, 3, 4, 5].map((n) => (
                  <option key={n} value={n}>
                    {n} · {levels[n]?.[0]}
                  </option>
                ))}
              </select>
            </label>
            <label className="inline-field">
              Category
              <input
                className="input"
                list="skill-categories"
                defaultValue={s.category}
                aria-label={`Category for ${s.name}`}
                onBlur={(e) => e.target.value.trim() && e.target.value !== s.category && void api.updateSkill(s.id, { category: e.target.value }).then(() => refresh(qc))}
              />
              <datalist id="skill-categories">
                {categories.map((c) => (
                  <option key={c} value={c} />
                ))}
              </datalist>
            </label>
            <button
              className="btn sm ghost danger"
              style={{ marginLeft: "auto" }}
              onClick={async () => {
                if (!confirm(`Remove “${s.name}” and its rating history?`)) return;
                await api.deleteSkill(s.id);
                refresh(qc);
              }}
            >
              <Trash2 /> Remove
            </button>
          </div>
          <div className="skill-cols">
            <div>
              <div className="section-label">Rating history</div>
              {row.history.length === 0 && <div className="faint">Click a dot above to rate yourself.</div>}
              <ul className="rating-history">
                {row.history.map((h) => (
                  <li key={h.id}>
                    <span className="tnum">
                      {h.level} · {levels[h.level]?.[0]}
                    </span>
                    <span className="faint">{relativeTime(h.rated_at)}</span>
                    {h.note && <span className="faint">— {h.note}</span>}
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <div className="section-label">Evidence</div>
              {row.evidence.length === 0 && <div className="faint">No evidence linked yet.</div>}
              {row.evidence.map((ev) => (
                <div key={ev.fact.id} className="evidence" style={{ marginLeft: 0, marginTop: 6 }}>
                  <div className="evidence-main">
                    <span className="fact-statement">{ev.fact.statement}</span>
                    <button className="fact-quote" onClick={() => ui.navigate("knowledge", `${ev.fact.document_id}${ev.fact.chunk_id ? `~${ev.fact.chunk_id}` : ""}`)}>
                      <Quote size={11} /> “{ev.fact.quote}” — {ev.document_title}
                      {ev.fact.page ? `, p. ${ev.fact.page}` : ""}
                    </button>
                  </div>
                  {ev.fact.epistemic === "self_reported" && (
                    <span className="chip" title="Written by you, not taken from a document">
                      Your note
                    </span>
                  )}
                  <button className="btn icon sm ghost" aria-label="Unlink evidence" onClick={() => void api.linkSkillEvidence(s.id, ev.fact.id, false).then(() => refresh(qc))}>
                    <X />
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function AddSkill({ matrix, onDone }: { matrix?: SkillMatrix; onDone: () => void }) {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [category, setCategory] = useState(matrix?.categories[0]?.category ?? "Engineering");
  const [level, setLevel] = useState("");
  const [target, setTarget] = useState("");
  const levels = matrix?.levels ?? {};
  return (
    <form
      className="card add-expectation"
      onSubmit={async (e) => {
        e.preventDefault();
        if (!name.trim()) return;
        try {
          await api.createSkill({ name, category, level: level ? Number(level) : null, target_level: target ? Number(target) : null });
          refresh(qc);
          setName("");
          toast.success("Skill added", { description: name });
        } catch (err) {
          toast.error((err as Error).message);
        }
      }}
    >
      <input className="input" autoFocus placeholder="Skill, e.g. System design" value={name} onChange={(e) => setName(e.target.value)} aria-label="Skill name" style={{ flex: 1, minWidth: "12rem" }} />
      <input className="input" list="skill-cat-add" placeholder="Category" value={category} onChange={(e) => setCategory(e.target.value)} aria-label="Category" style={{ width: "10rem" }} />
      <datalist id="skill-cat-add">
        {(matrix?.categories ?? []).map((c) => (
          <option key={c.category} value={c.category} />
        ))}
      </datalist>
      <select className="select" value={level} onChange={(e) => setLevel(e.target.value)} aria-label="Current level" style={{ width: "auto" }}>
        <option value="">Today: not rated</option>
        {[1, 2, 3, 4, 5].map((n) => (
          <option key={n} value={n}>
            Today: {n} {levels[n]?.[0]}
          </option>
        ))}
      </select>
      <select className="select" value={target} onChange={(e) => setTarget(e.target.value)} aria-label="Target level" style={{ width: "auto" }}>
        <option value="">Target: none</option>
        {[1, 2, 3, 4, 5].map((n) => (
          <option key={n} value={n}>
            Target: {n} {levels[n]?.[0]}
          </option>
        ))}
      </select>
      <button className="btn primary" type="submit" disabled={!name.trim()}>
        Add
      </button>
      <button className="btn ghost" type="button" onClick={onDone}>
        Done
      </button>
    </form>
  );
}

function LinkDialog({ row, onClose }: { row: SkillRow | null; onClose: () => void }) {
  const qc = useQueryClient();
  const id = row?.skill.id;
  const { data: hints = [] } = useQuery({ queryKey: ["skill-suggestions", id], queryFn: () => api.skillSuggestions(id!), enabled: !!id });
  const { data: accepted = [] } = useQuery({ queryKey: ["facts", "accepted"], queryFn: () => api.facts({ status: "accepted" }), enabled: !!id });
  const { data: docs = [] } = useQuery({ queryKey: ["documents"], queryFn: api.documents, enabled: !!id });
  const titles = useMemo(() => Object.fromEntries(docs.map((d) => [d.id, d.title])), [docs]);
  const [q, setQ] = useState("");
  const linked = new Set(row?.evidence.map((e) => e.fact.id));
  const hinted = new Set(hints.map((h) => h.fact.id));
  const others = accepted.filter((f) => EVIDENCE_KINDS.includes(f.kind) && !linked.has(f.id) && !hinted.has(f.id) && (!q || `${f.statement} ${f.quote}`.toLowerCase().includes(q.toLowerCase())));

  const link = async (f: Fact) => {
    if (!id) return;
    try {
      await api.linkSkillEvidence(id, f.id);
      toast.success("Evidence linked ✨");
      refresh(qc);
      void qc.invalidateQueries({ queryKey: ["skill-suggestions"] });
      onClose();
    } catch (e) {
      toast.error((e as Error).message);
    }
  };
  const pick = (f: Fact, doc?: string, extra?: React.ReactNode) => (
    <div key={f.id} className="fact-pick">
      <div className="evidence-main">
        <span className="fact-statement">{f.statement}</span>
        <span className="fact-quote" style={{ cursor: "default" }}>
          “{f.quote}”{doc ? ` — ${doc}` : ""}
          {f.page ? `, p. ${f.page}` : ""}
        </span>
        {extra}
      </div>
      <button className="btn sm primary" onClick={() => void link(f)} aria-label={`Link: ${f.statement}`}>
        <Check /> Link
      </button>
    </div>
  );

  return (
    <Dialog open={!!row} onClose={onClose} label="Link skill evidence" width={680}>
      {row && (
        <div className="link-dialog">
          <div className="section-label">Evidence for</div>
          <h3 className="link-dialog-title">{row.skill.name}</h3>
          {hints.length > 0 && (
            <>
              <div className="section-label" style={{ marginTop: "1rem" }}>
                Suggestions · you decide
              </div>
              {hints.map((h) =>
                pick(
                  h.fact,
                  h.document_title,
                  <span className="why">
                    <MatchWhy shared={h.shared} similarity={h.similarity} />
                  </span>,
                ),
              )}
            </>
          )}
          <OwnEvidenceForm skillId={row.skill.id} onDone={onClose} />
          <div className="section-label" style={{ marginTop: "1rem" }}>
            All accepted evidence
          </div>
          <div className="search-input" style={{ maxWidth: "none", margin: "0.4rem 0" }}>
            <Search />
            <input className="input" placeholder="Filter" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Filter evidence" />
          </div>
          <div className="pick-list">
            {others.map((f) => pick(f, titles[f.document_id]))}
            {others.length === 0 && <div className="faint" style={{ padding: "0.6rem 0", fontSize: "0.9rem" }}>Nothing else to link. Accept achievements or strengths from your documents in Knowledge.</div>}
          </div>
        </div>
      )}
    </Dialog>
  );
}
