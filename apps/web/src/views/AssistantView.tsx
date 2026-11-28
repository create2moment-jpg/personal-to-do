import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, BookOpenText, CheckCircle2, FileText, Loader2, NotebookPen, RefreshCw, Search, ShieldCheck, Sparkles, SquareCheck, Star, Wand2 } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api } from "../lib/api";
import { invalidateTasks } from "../lib/queries";
import type { AssistantAnswer, AssistantSource, DayPlanProposal } from "../lib/types";
import type { ViewId } from "../lib/ui-store";
import { useUi } from "../lib/ui-store";
import { cx, formatMinutes, isoDay } from "../lib/util";

const KIND: Record<AssistantSource["kind"], { label: string; icon: typeof FileText }> = {
  note: { label: "Note", icon: NotebookPen },
  page: { label: "Prompt", icon: BookOpenText },
  chunk: { label: "Document", icon: FileText },
  task: { label: "Task", icon: SquareCheck },
};

function useOpenSource() {
  const ui = useUi();
  return (s: AssistantSource) => {
    const [view, ...rest] = s.link.split("/");
    const arg = rest.join("/");
    if (view === "task") ui.openTask(arg);
    else ui.navigate(view as ViewId, arg);
  };
}

export function AssistantView({ initialQuestion }: { initialQuestion?: string } = {}) {
  const qc = useQueryClient();
  const { data: st } = useQuery({ queryKey: ["assistant-status"], queryFn: api.assistantStatus, refetchInterval: (q) => (q.state.data?.running ? 1500 : false) });
  const [q, setQ] = useState(initialQuestion ?? "");
  useEffect(() => {
    if (initialQuestion) setQ(initialQuestion); // from the Assistant gadget
  }, [initialQuestion]);
  const [busy, setBusy] = useState(false);
  const [answers, setAnswers] = useState<AssistantAnswer[]>([]);
  const [results, setResults] = useState<{ q: string; sources: AssistantSource[]; semantic: boolean } | null>(null);
  const ai = st?.ai ?? false;

  const submit = async (mode: "ask" | "search") => {
    const text = q.trim();
    if (text.length < 3) return;
    setBusy(true);
    try {
      if (mode === "ask") {
        const a = await api.ask(text);
        setAnswers((xs) => [a, ...xs].slice(0, 10));
        setResults(null);
      } else {
        const r = await api.assistantSearch(text);
        setResults({ q: text, ...r });
      }
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="page assistant-page">
      <header className="page-head">
        <div>
          <h1 className="page-title">Assistant</h1>
          <div className="page-sub">Answers from your own notes, documents, tasks and prompts — every answer cites its sources. Runs on your local model only.</div>
        </div>
        <div className="assistant-status">
          <span className={cx("chip", ai ? "green" : "")}>{ai ? "Local AI on" : "Local AI off"}</span>
          {st && (
            <span className={cx("chip", st.model ? "accent" : "")} title={st.model ? `Embedding model: ${st.model}` : "Set an embedding model in Settings → Local AI"}>
              {st.model ? `Search by meaning · ${st.indexed}/${st.total}` : "Keyword search"}
              {st.running && <Loader2 className="spin" />}
            </span>
          )}
          {st?.model && (
            <button
              className="btn icon sm ghost"
              aria-label="Update the search index"
              title="Update the search index"
              onClick={async () => {
                await api.assistantIndex();
                void qc.invalidateQueries({ queryKey: ["assistant-status"] });
              }}
            >
              <RefreshCw />
            </button>
          )}
        </div>
      </header>
      {st?.error && (
        <div className="alert-strip" style={{ marginBottom: 12 }}>
          <AlertTriangle /> Search by meaning stopped: {st.error}
        </div>
      )}

      <div className="assistant-layout">
        <div>
          <form
            className="card ask-box"
            onSubmit={(e) => {
              e.preventDefault();
              void submit(ai ? "ask" : "search");
            }}
          >
            <textarea
              className="ask-input"
              rows={2}
              value={q}
              placeholder={ai ? "Ask about your work — e.g. What did I decide about hybrid retrieval?" : "Search everything you've written — notes, documents, tasks, prompts"}
              aria-label="Ask the assistant"
              onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  void submit(ai ? "ask" : "search");
                }
              }}
            />
            <div className="ask-actions">
              <span className="faint">
                <ShieldCheck size={13} /> Uses only your records on this machine
              </span>
              <button type="button" className="btn sm ghost" disabled={busy || q.trim().length < 3} onClick={() => void submit("search")}>
                <Search /> Search
              </button>
              {ai && (
                <button type="submit" className="btn sm primary" disabled={busy || q.trim().length < 3}>
                  {busy ? <Loader2 className="spin" /> : <Sparkles />} Ask
                </button>
              )}
            </div>
          </form>

          {results && <SearchResults {...results} />}
          {answers.map((a, i) => (
            <AnswerCard key={`${a.question}-${i}`} a={a} />
          ))}
          {!results && answers.length === 0 && (
            <div className="assistant-hints">
              {["What did I decide about hybrid retrieval?", "Who did I mentor this quarter?", "Which tasks are blocked and why?", "Summarise my notes on the eval harness"].map((h) => (
                <button key={h} className="filter-chip" onClick={() => setQ(h)}>
                  {h}
                </button>
              ))}
            </div>
          )}
        </div>
        <PlanDayCard enabled={ai} />
      </div>
    </div>
  );
}

function AnswerCard({ a }: { a: AssistantAnswer }) {
  const open = useOpenSource();
  const [focus, setFocus] = useState<number | null>(null);
  const cited = new Set(a.cited);
  return (
    <article className="card answer-card" aria-label={`Answer: ${a.question}`}>
      <div className="answer-q">{a.question}</div>
      <div className="answer-text">
        {a.text.split(/(\[\d{1,2}\])/).map((part, i) => {
          const m = /^\[(\d{1,2})\]$/.exec(part);
          if (!m) return <span key={i}>{part}</span>;
          const n = Number(m[1]);
          const ok = n >= 1 && n <= a.sources.length;
          return (
            <button key={i} className={cx("cite", !ok && "bad")} title={ok ? a.sources[n - 1]!.title : "This source does not exist"} onMouseEnter={() => ok && setFocus(n)} onMouseLeave={() => setFocus(null)} onClick={() => ok && open(a.sources[n - 1]!)}>
              {n}
            </button>
          );
        })}
      </div>
      <div className={cx("grounding", a.grounded ? "ok" : "warn")}>
        {a.grounded ? <CheckCircle2 size={14} /> : <AlertTriangle size={14} />}
        {a.sources.length === 0
          ? "Nothing in your records matched."
          : a.grounded
            ? `Cites ${a.cited.length} of ${a.sources.length} sources from your records`
            : a.invalid.length
              ? `Cites a source that doesn't exist ([${a.invalid.join("], [")}]) — check before relying on it`
              : "No citations — treat this answer with care"}
        <span className="faint"> · {a.model}{a.semantic ? " · keyword + meaning" : " · keyword search"}</span>
      </div>
      {a.sources.length > 0 && (
        <div className="source-list">
          {a.sources.map((s) => (
            <SourceCard key={`${s.kind}-${s.id}`} s={s} dim={!cited.has(s.n)} focus={focus === s.n} />
          ))}
        </div>
      )}
    </article>
  );
}

function SourceCard({ s, dim, focus }: { s: AssistantSource; dim?: boolean; focus?: boolean }) {
  const open = useOpenSource();
  const K = KIND[s.kind];
  return (
    <button className={cx("source", dim && "dim", focus && "focus")} onClick={() => open(s)}>
      <span className="source-head">
        {s.n > 0 && <span className="cite">{s.n}</span>}
        <K.icon size={13} /> <strong>{s.title}</strong>
        <span className="faint">{K.label}</span>
        {s.via.map((v) => (
          <span key={v} className="chip" style={{ height: "1.05rem", fontSize: "0.7rem" }}>
            {v}
          </span>
        ))}
      </span>
      <span className="source-text">{s.text.length > 220 ? `${s.text.slice(0, 219)}…` : s.text}</span>
    </button>
  );
}

function SearchResults({ q, sources, semantic }: { q: string; sources: AssistantSource[]; semantic: boolean }) {
  return (
    <section className="search-results" aria-label="Search results">
      <div className="section-label">
        {sources.length} result{sources.length === 1 ? "" : "s"} for “{q}” · {semantic ? "keyword + meaning" : "keyword"}
      </div>
      {sources.map((s) => (
        <SourceCard key={`${s.kind}-${s.id}`} s={s} />
      ))}
      {sources.length === 0 && <div className="faint">Nothing matched.</div>}
    </section>
  );
}

function PlanDayCard({ enabled }: { enabled: boolean }) {
  const ui = useUi();
  const qc = useQueryClient();
  const [p, setP] = useState<DayPlanProposal | null>(null);
  const [busy, setBusy] = useState(false);
  return (
    <aside className="card plan-card" aria-label="Plan my day">
      <h3>
        <Wand2 size={16} /> Plan my day
      </h3>
      <p className="faint">Proposes up to three top priorities from today’s open, overdue and due tasks. Nothing changes until you approve.</p>
      {!p && (
        <button
          className="btn primary"
          disabled={!enabled || busy}
          title={enabled ? "" : "Turn on Local AI in Settings"}
          onClick={async () => {
            setBusy(true);
            try {
              setP(await api.planDay(isoDay()));
            } catch (e) {
              toast.error((e as Error).message);
            } finally {
              setBusy(false);
            }
          }}
        >
          {busy ? <Loader2 className="spin" /> : <Sparkles />} Propose a plan
        </button>
      )}
      {p && (
        <div className="plan-proposal">
          <div className="faint" style={{ fontSize: "0.82rem" }}>
            Capacity {formatMinutes(p.capacity_minutes)} · meetings {formatMinutes(p.meeting_minutes)}
          </div>
          <ol>
            {p.top.map((t) => (
              <li key={t.id}>
                <button className="link-btn" onClick={() => ui.openTask(t.id)}>
                  {t.title}
                </button>
                {t.why && <div className="faint">{t.why}</div>}
              </li>
            ))}
          </ol>
          {p.note && <p className="plan-note">{p.note}</p>}
          {p.dropped.length > 0 && (
            <div className="faint" style={{ fontSize: "0.8rem" }}>
              <ShieldCheck size={12} /> {p.dropped.length} suggestion(s) ignored — not in your task list
            </div>
          )}
          {p.current_top.length > 0 && (
            <div className="faint" style={{ fontSize: "0.8rem" }}>
              Replaces today’s current top: {p.current_top.map((t) => t.title).join(", ")}
            </div>
          )}
          <div className="plan-actions">
            <button className="btn ghost" onClick={() => setP(null)}>
              Dismiss
            </button>
            <button
              className="btn primary"
              disabled={p.top.length === 0}
              onClick={async () => {
                await api.applyDayPlan(p.day, p.top.map((t) => t.id));
                invalidateTasks(qc);
                toast.success("Today’s top priorities set ⭐", { action: { label: "Open Today", onClick: () => ui.navigate("today") } });
                setP(null);
              }}
            >
              <Star /> Approve
            </button>
          </div>
        </div>
      )}
    </aside>
  );
}
