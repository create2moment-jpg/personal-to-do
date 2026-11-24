import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Info, Link2, ListPlus, Plus, Quote, Search, Sparkles, Trash2, TrendingUp, X } from "lucide-react";
import { type ReactNode, useMemo, useState } from "react";
import { toast } from "sonner";
import { Dialog, EmptyState } from "../components/primitives";
import { api } from "../lib/api";
import type { CareerLevel, CareerRow, Fact } from "../lib/types";
import { useUi } from "../lib/ui-store";
import { cx } from "../lib/util";

const KIND_ONE: Record<string, string> = { achievement: "Achievement", responsibility: "Responsibility", competency: "Competency", strength: "Strength" };
const EVIDENCE_KINDS = Object.keys(KIND_ONE);

export function CareerView() {
  const ui = useUi();
  const { data: m, isLoading } = useQuery({ queryKey: ["career"], queryFn: api.career });
  const [adding, setAdding] = useState(false);
  const [linking, setLinking] = useState<CareerRow | null>(null);
  const levels = m?.levels ?? [];

  return (
    <div className="page career">
      <header className="page-head">
        <div>
          <h1 className="page-title">Career</h1>
          <div className="page-sub">Your level framework, and the evidence you’ve accepted for each expectation.</div>
        </div>
        <button className="btn primary" onClick={() => setAdding((a) => !a)}>
          <Plus /> Add expectation
        </button>
      </header>

      {adding && <AddExpectation levels={levels.map((l) => l.level)} onDone={() => setAdding(false)} />}

      {m && levels.length > 0 && (
        <>
          <div className="career-note">
            <Info /> <span>{m.disclaimer}</span>
          </div>
          <div className="level-overview">
            {levels.map((l) => (
              <LevelCard key={l.level} l={l} />
            ))}
            <div className="card level-card pool">
              <div className="section-label">Evidence on file</div>
              <div className="level-num">{m.evidence_pool}</div>
              <div className="faint">accepted achievements, responsibilities, competencies and strengths</div>
            </div>
          </div>
          {levels.map((l) => (
            <section key={l.level} className="level-section" aria-label={`Level ${l.level}`}>
              <h2 className="level-head">
                <span className="level-badge">{l.level}</span>
                <span className="faint">
                  {l.covered} of {l.total} with evidence
                </span>
              </h2>
              {l.rows.map((r) => (
                <ExpectationCard key={r.expectation.id} row={r} onLink={() => setLinking(r)} />
              ))}
            </section>
          ))}
        </>
      )}

      {!isLoading && levels.length === 0 && !adding && (
        <EmptyState icon={TrendingUp} title="Map your evidence to your level framework">
          Add your company’s level framework in{" "}
          <button className="link-btn" onClick={() => ui.navigate("knowledge")}>
            Knowledge
          </button>
          , extract its level expectations and accept the ones that are right — they appear here, grouped by level. Or add expectations by hand. Accepted achievements and strengths from your reviews can then be linked as evidence.
        </EmptyState>
      )}

      <LinkDialog row={linking} onClose={() => setLinking(null)} />
    </div>
  );
}

function LevelCard({ l }: { l: CareerLevel }) {
  const pct = l.total ? Math.round((l.covered / l.total) * 100) : 0;
  return (
    <div className="card level-card">
      <div className="section-label">{l.level}</div>
      <div className="level-num">
        {pct}
        <small>%</small>
      </div>
      <div className="capacity-track" role="meter" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} aria-label={`${l.level} evidence coverage`}>
        <i style={{ width: `${pct}%`, background: "var(--series-1)" }} />
      </div>
      <div className="faint">
        Evidence covers {l.covered} of {l.total} expectation{l.total === 1 ? "" : "s"}
      </div>
    </div>
  );
}

function ExpectationCard({ row, onLink }: { row: CareerRow; onLink: () => void }) {
  const ui = useUi();
  const qc = useQueryClient();
  const e = row.expectation;
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(e.text);
  const refresh = () => void qc.invalidateQueries({ queryKey: ["career"] });

  const save = async () => {
    setEditing(false);
    if (text.trim() && text !== e.text) {
      await api.updateExpectation(e.id, { text });
      refresh();
    } else setText(e.text);
  };
  const gapTask = async () => {
    const t = await api.gapTask(e.id);
    void qc.invalidateQueries({ queryKey: ["tasks"] });
    toast.success("Task added to your backlog 🌱", { description: t.title, action: { label: "Open", onClick: () => ui.openTask(t.id) } });
  };
  const remove = async () => {
    const msg = e.source_fact_id
      ? "Remove this expectation? Its framework fact will be marked rejected so it doesn’t come back."
      : "Remove this expectation?";
    if (!confirm(msg)) return;
    await api.deleteExpectation(e.id);
    void qc.invalidateQueries({ queryKey: ["facts"] });
    refresh();
  };

  return (
    <article className={cx("card expectation", row.evidence.length ? "has-evidence" : "gap")}>
      <div className="exp-top">
        <span className={cx("exp-dot", row.evidence.length > 0 && "on")} aria-hidden />
        {editing ? (
          <input
            className="input exp-edit"
            autoFocus
            value={text}
            aria-label="Expectation"
            onChange={(ev) => setText(ev.target.value)}
            onBlur={() => void save()}
            onKeyDown={(ev) => {
              if (ev.key === "Enter") void save();
              if (ev.key === "Escape") {
                setText(e.text);
                setEditing(false);
              }
            }}
          />
        ) : (
          <button className="exp-text" title="Click to edit" onClick={() => setEditing(true)}>
            {e.text}
          </button>
        )}
        <div className="exp-tags">
          {e.competency && <span className="chip">{e.competency}</span>}
          <span className="chip" title={e.source_fact_id ? "Accepted from a framework document" : "Added by you"}>
            {e.source_fact_id ? "Framework" : "Yours"}
          </span>
          <button className="btn icon sm ghost danger" aria-label="Remove expectation" onClick={() => void remove()}>
            <Trash2 />
          </button>
        </div>
      </div>

      {row.evidence.map((ev) => (
        <div key={ev.fact.id} className="evidence">
          <div className="evidence-main">
            <span className="fact-statement">{ev.fact.statement}</span>
            <button className="fact-quote" onClick={() => ui.navigate("knowledge", `${ev.fact.document_id}${ev.fact.chunk_id ? `~${ev.fact.chunk_id}` : ""}`)} title="Open the source passage">
              <Quote size={11} /> “{ev.fact.quote}” — {ev.document_title}
              {ev.fact.page ? `, p. ${ev.fact.page}` : ""}
            </button>
          </div>
          <span className="chip" title={ev.origin === "suggestion" ? "Suggested by word overlap, confirmed by you" : "Linked by you"}>
            {KIND_ONE[ev.fact.kind] ?? ev.fact.kind}
          </span>
          <button
            className="btn icon sm ghost"
            aria-label="Unlink evidence"
            onClick={async () => {
              await api.unlinkEvidence(e.id, ev.fact.id);
              refresh();
            }}
          >
            <X />
          </button>
        </div>
      ))}

      <div className="exp-actions">
        {row.evidence.length === 0 && <span className="faint gap-label">No evidence yet</span>}
        <button className="btn sm" onClick={onLink}>
          <Link2 /> Link evidence
          {row.suggestion_count > 0 && (
            <span className="chip accent" style={{ height: "1.1rem" }}>
              <Sparkles /> {row.suggestion_count} suggested
            </span>
          )}
        </button>
        {row.evidence.length === 0 && (
          <button className="btn sm ghost" onClick={() => void gapTask()}>
            <ListPlus /> Create a task to build evidence
          </button>
        )}
      </div>
    </article>
  );
}

function LinkDialog({ row, onClose }: { row: CareerRow | null; onClose: () => void }) {
  const qc = useQueryClient();
  const id = row?.expectation.id;
  const { data: suggestions = [] } = useQuery({ queryKey: ["career-suggestions", id], queryFn: () => api.evidenceSuggestions(id!), enabled: !!id });
  const { data: accepted = [] } = useQuery({ queryKey: ["facts", "accepted"], queryFn: () => api.facts({ status: "accepted" }), enabled: !!id });
  const { data: docs = [] } = useQuery({ queryKey: ["documents"], queryFn: api.documents, enabled: !!id });
  const titles = useMemo(() => Object.fromEntries(docs.map((d) => [d.id, d.title])), [docs]);
  const [q, setQ] = useState("");
  const linked = new Set(row?.evidence.map((e) => e.fact.id));
  const suggested = new Set(suggestions.map((s) => s.fact.id));
  const others = useMemo(
    () =>
      accepted.filter(
        (f) => EVIDENCE_KINDS.includes(f.kind) && !linked.has(f.id) && !suggested.has(f.id) && (!q || `${f.statement} ${f.quote}`.toLowerCase().includes(q.toLowerCase())),
      ),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [accepted, q, row, suggestions],
  );

  const link = async (f: Fact) => {
    if (!id) return;
    try {
      await api.linkEvidence(id, f.id);
      toast.success("Evidence linked ✨");
      void qc.invalidateQueries({ queryKey: ["career"] });
      void qc.invalidateQueries({ queryKey: ["career-suggestions"] });
      onClose();
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  return (
    <Dialog open={!!row} onClose={onClose} label="Link evidence" width={680}>
      {row && (
        <div className="link-dialog">
          <div className="section-label">{row.expectation.level} expectation</div>
          <h3 className="link-dialog-title">{row.expectation.text}</h3>
          {suggestions.length > 0 && (
            <>
              <div className="section-label" style={{ marginTop: "1rem" }}>
                Suggestions · you decide
              </div>
              {suggestions.map((s) => (
                <FactPick key={s.fact.id} f={s.fact} doc={s.document_title} onPick={() => void link(s.fact)}>
                  <span className="why">
                    Shares: {s.shared.map((w) => <mark key={w}>{w}</mark>)}
                  </span>
                </FactPick>
              ))}
            </>
          )}
          <div className="section-label" style={{ marginTop: "1rem" }}>
            All accepted evidence
          </div>
          <div className="search-input" style={{ maxWidth: "none", margin: "0.4rem 0" }}>
            <Search />
            <input className="input" placeholder="Filter" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Filter evidence" />
          </div>
          <div className="pick-list">
            {others.map((f) => (
              <FactPick key={f.id} f={f} doc={titles[f.document_id]} onPick={() => void link(f)} />
            ))}
            {others.length === 0 && (
              <div className="faint" style={{ padding: "0.6rem 0", fontSize: "0.9rem" }}>
                Nothing else to link. Accept achievements or strengths from your documents in Knowledge to grow this list.
              </div>
            )}
          </div>
        </div>
      )}
    </Dialog>
  );
}

function FactPick({ f, doc, onPick, children }: { f: Fact; doc?: string; onPick: () => void; children?: ReactNode }) {
  return (
    <div className="fact-pick">
      <div className="evidence-main">
        <span className="fact-statement">{f.statement}</span>
        <span className="fact-quote" style={{ cursor: "default" }}>
          “{f.quote}”{doc ? ` — ${doc}` : ""}
          {f.page ? `, p. ${f.page}` : ""}
        </span>
        {children}
      </div>
      <button className="btn sm primary" onClick={onPick} aria-label={`Link: ${f.statement}`}>
        <Check /> Link
      </button>
    </div>
  );
}

function AddExpectation({ levels, onDone }: { levels: string[]; onDone: () => void }) {
  const qc = useQueryClient();
  const [level, setLevel] = useState(levels[0] ?? "L5");
  const [text, setText] = useState("");
  const [competency, setCompetency] = useState("");
  const submit = async () => {
    if (!text.trim() || !level.trim()) return;
    try {
      await api.addExpectation({ level, text, competency: competency || null });
      void qc.invalidateQueries({ queryKey: ["career"] });
      onDone();
    } catch (e) {
      toast.error((e as Error).message);
    }
  };
  return (
    <form
      className="card add-expectation"
      onSubmit={(e) => {
        e.preventDefault();
        void submit();
      }}
    >
      <input className="input" list="career-levels" value={level} onChange={(e) => setLevel(e.target.value)} aria-label="Level" style={{ width: "6rem" }} />
      <datalist id="career-levels">
        {levels.map((l) => (
          <option key={l} value={l} />
        ))}
      </datalist>
      <input className="input" autoFocus placeholder="What is expected at this level?" value={text} onChange={(e) => setText(e.target.value)} aria-label="Expectation text" style={{ flex: 1 }} />
      <input className="input" placeholder="Competency (optional)" value={competency} onChange={(e) => setCompetency(e.target.value)} aria-label="Competency" style={{ width: "12rem" }} />
      <button className="btn primary" type="submit" disabled={!text.trim()}>
        Add
      </button>
    </form>
  );
}
