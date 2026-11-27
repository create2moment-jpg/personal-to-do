import { useQuery } from "@tanstack/react-query";
import { Loader2, ShieldCheck, Sparkles, XCircle } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { api } from "../lib/api";
import type { ReviewDraft, ReviewSection } from "../lib/types";

export interface DraftField<K extends string> {
  key: K;
  label: string;
  from: ReviewSection[]; // which draft sections feed this field
}

/**
 * "Draft with AI" for any review form: suggestions come from your own records,
 * each cites them, and unsupported ones are dropped and listed. Nothing is
 * written into the form until you press Use.
 */
export function GroundedDraft<K extends string>({ fetchDraft, fields, onUse }: { fetchDraft: () => Promise<ReviewDraft>; fields: DraftField<K>[]; onUse: (key: K, bullets: string[]) => void }) {
  const { data: ai } = useQuery({ queryKey: ["ai-status"], queryFn: api.aiStatus, staleTime: 60_000 });
  const [draft, setDraft] = useState<ReviewDraft | null>(null);
  const [used, setUsed] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);

  return (
    <div className="grounded-draft">
      <button
        type="button"
        className="btn sm"
        disabled={busy || !ai?.enabled}
        title={ai?.enabled ? "Suggestions from your own records" : "Turn on Local AI in Settings to draft"}
        onClick={async () => {
          setBusy(true);
          try {
            const d = await fetchDraft();
            setDraft(d);
            setUsed(new Set());
            const kept = Object.values(d.sections).reduce((a, b) => a + (b?.length ?? 0), 0);
            toast.success(`Draft ready: ${kept} suggestion(s)`, { description: d.dropped.length ? `${d.dropped.length} dropped — not supported by your records` : "Every suggestion cites your records" });
          } catch (e) {
            toast.error((e as Error).message);
          } finally {
            setBusy(false);
          }
        }}
      >
        {busy ? <Loader2 className="spin" /> : <Sparkles />} Draft with AI
      </button>
      {draft && (
        <div className="grounded-suggestions">
          {fields.map((f) => {
            const bullets = f.from.flatMap((s) => draft.sections[s] ?? []).filter((b) => !used.has(b));
            if (bullets.length === 0) return null;
            return (
              <div key={f.key} className="ai-suggestions">
                <div className="section-label">
                  <Sparkles size={11} /> {f.label} · suggested from your records
                </div>
                {bullets.map((b) => (
                  <div key={b} className="ai-suggestion">
                    <span>{b}</span>
                    <button
                      type="button"
                      className="btn sm ghost"
                      onClick={() => {
                        onUse(f.key, [b]);
                        setUsed(new Set([...used, b]));
                      }}
                    >
                      Use
                    </button>
                  </div>
                ))}
              </div>
            );
          })}
          {draft.dropped.length > 0 && (
            <details className="dropped-box">
              <summary>
                <ShieldCheck size={14} /> {draft.dropped.length} suggestion(s) dropped because your records don’t support them
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
        </div>
      )}
    </div>
  );
}

/** Append bullets to a text field's value ("- …" per line). */
export const appendBullets = (current: string, bullets: string[]) => [current.trim(), ...bullets.map((b) => `- ${b}`)].filter(Boolean).join("\n");
