import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Loader2, Quote, ShieldCheck, Sparkles, X } from "lucide-react";
import { toast } from "sonner";
import { api } from "../lib/api";
import type { DocumentInfo, Fact } from "../lib/types";
import { useUi } from "../lib/ui-store";
import { cx } from "../lib/util";

export const FACT_KIND_LABEL: Record<string, string> = {
  responsibility: "Responsibilities",
  achievement: "Achievements",
  competency: "Competencies",
  strength: "Strengths",
  development_area: "Development areas",
  goal: "Goals",
  level_expectation: "Level expectations",
};

/** AI-extracted facts for one document: proposals the user accepts or rejects. */
export function FactsPanel({ doc }: { doc: DocumentInfo }) {
  const ui = useUi();
  const qc = useQueryClient();
  const { data: ai } = useQuery({ queryKey: ["ai-status"], queryFn: api.aiStatus, staleTime: 60_000 });
  const { data } = useQuery({
    queryKey: ["facts", doc.id],
    queryFn: () => api.documentFacts(doc.id),
    refetchInterval: (q) => (["queued", "running"].includes(q.state.data?.run?.status ?? "") ? 1000 : false),
  });
  const run = data?.run;
  const facts = data?.facts ?? [];
  const busy = run?.status === "queued" || run?.status === "running";
  const grouped = Object.keys(FACT_KIND_LABEL)
    .map((k) => [k, facts.filter((f) => f.kind === k && f.status !== "rejected")] as const)
    .filter(([, fs]) => fs.length > 0);
  const rejected = facts.filter((f) => f.status === "rejected").length;

  const start = async () => {
    try {
      await api.extractFacts(doc.id);
      void qc.invalidateQueries({ queryKey: ["facts", doc.id] });
    } catch (e) {
      toast.error((e as Error).message);
    }
  };
  const review = async (f: Fact, status: Fact["status"]) => {
    await api.reviewFact(f.id, { status });
    void qc.invalidateQueries({ queryKey: ["facts"] });
  };

  return (
    <section className="card facts-panel">
      <div className="facts-head">
        <h3>
          <Sparkles size={16} /> Facts from this document
        </h3>
        <button className="btn sm primary" disabled={busy || !ai?.enabled || doc.status !== "ready"} onClick={() => void start()} title={ai?.enabled ? "" : "Configure a local model in .env to enable"}>
          {busy ? <Loader2 className="spin" /> : <Sparkles />} {run ? "Extract again" : "Extract facts with AI"}
        </button>
      </div>
      {!ai?.enabled && (
        <p className="faint" style={{ fontSize: "0.9rem", margin: "0.3rem 0 0" }}>
          Needs your local model (Ollama / vLLM) — see{" "}
          <button className="link-btn" onClick={() => ui.navigate("settings")}>
            Settings → Local AI
          </button>
          . Nothing leaves this machine.
        </p>
      )}
      {run && (
        <div className="facts-run">
          {busy ? (
            <>
              <div className="capacity-track" style={{ marginTop: 0 }}>
                <i style={{ width: `${run.chunks_total ? (run.chunks_done / run.chunks_total) * 100 : 5}%`, background: "var(--accent)" }} />
              </div>
              <span>
                Reading passage {Math.min(run.chunks_done + 1, run.chunks_total)} of {run.chunks_total}…
              </span>
            </>
          ) : run.status === "failed" ? (
            <span className="red-text">Extraction failed: {run.error}</span>
          ) : (
            <span>
              <ShieldCheck size={13} /> {run.facts_found} grounded fact{run.facts_found === 1 ? "" : "s"} · {run.facts_dropped} dropped (no verbatim quote in the source) · {run.model} · {run.prompt_template}
            </span>
          )}
        </div>
      )}
      {grouped.map(([kind, fs]) => (
        <div key={kind} className="fact-group">
          <div className="section-label">{FACT_KIND_LABEL[kind]}</div>
          {fs.map((f) => (
            <div key={f.id} className={cx("fact", f.status)}>
              <div className="fact-main">
                <div className="fact-statement">{f.statement}</div>
                <button className="fact-quote" onClick={() => f.chunk_id && ui.navigate("knowledge", `${f.document_id}~${f.chunk_id}`)} title="Show in the document">
                  <Quote size={12} /> “{f.quote}” <span className="faint">· p. {f.page ?? "–"}</span>
                </button>
              </div>
              <span className="chip" title="Model confidence">
                {Math.round(f.confidence * 100)}%
              </span>
              {f.status === "accepted" ? (
                <span className="chip green">
                  <Check /> Accepted
                </span>
              ) : (
                <div style={{ display: "flex", gap: 4 }}>
                  <button className="btn icon sm" aria-label="Accept fact" title="Accept" onClick={() => void review(f, "accepted")}>
                    <Check />
                  </button>
                  <button className="btn icon sm ghost" aria-label="Reject fact" title="Reject" onClick={() => void review(f, "rejected")}>
                    <X />
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      ))}
      {run?.status === "done" && grouped.length === 0 && <p className="faint">No facts found in this document.</p>}
      {rejected > 0 && <p className="faint" style={{ fontSize: "0.82rem" }}>{rejected} rejected fact(s) hidden.</p>}
      <p className="faint" style={{ fontSize: "0.78rem", marginBottom: 0 }}>
        AI-extracted document claims. Only accepted facts will be used as career evidence.
      </p>
    </section>
  );
}
