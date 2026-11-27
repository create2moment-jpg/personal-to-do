import { useQueryClient } from "@tanstack/react-query";
import { NotebookPen, Plus } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { api } from "../lib/api";

const KINDS: [string, string][] = [
  ["achievement", "Achievement"],
  ["responsibility", "Responsibility"],
  ["competency", "Competency"],
  ["strength", "Strength"],
];

/**
 * Evidence you write yourself. It is saved as a small note in your Knowledge library
 * (searchable, openable) and linked right away. Labelled "Your note" wherever it shows.
 */
export function OwnEvidenceForm({ expectationId, skillId, onDone }: { expectationId?: string; skillId?: string; onDone: () => void }) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [kind, setKind] = useState("achievement");
  const [statement, setStatement] = useState("");
  const [detail, setDetail] = useState("");
  const [saving, setSaving] = useState(false);
  if (!open)
    return (
      <button className="btn sm ghost own-evidence-toggle" onClick={() => setOpen(true)}>
        <Plus /> Add evidence in your own words
      </button>
    );
  return (
    <form
      className="own-evidence"
      onSubmit={async (e) => {
        e.preventDefault();
        setSaving(true);
        try {
          await api.addOwnEvidence({ kind, statement, detail, expectation_id: expectationId ?? null, skill_id: skillId ?? null });
          toast.success("Evidence added and linked 📝", { description: "Saved as a note in your Knowledge library." });
          for (const k of ["career", "skills", "facts", "documents"]) void qc.invalidateQueries({ queryKey: [k] });
          onDone();
        } catch (err) {
          toast.error((err as Error).message);
        } finally {
          setSaving(false);
        }
      }}
    >
      <div className="section-label">
        <NotebookPen size={12} /> In your own words
      </div>
      <div className="own-evidence-row">
        <select className="select" value={kind} onChange={(e) => setKind(e.target.value)} aria-label="Evidence type">
          {KINDS.map(([v, l]) => (
            <option key={v} value={v}>
              {l}
            </option>
          ))}
        </select>
        <input className="input" autoFocus placeholder="e.g. Mentored Ana through her first design review" value={statement} onChange={(e) => setStatement(e.target.value)} aria-label="Evidence statement" />
      </div>
      <textarea className="input" rows={2} placeholder="Details, dates, links (optional)" value={detail} onChange={(e) => setDetail(e.target.value)} aria-label="Evidence details" />
      <div className="own-evidence-row" style={{ justifyContent: "flex-end" }}>
        <span className="faint" style={{ fontSize: "0.8rem", marginRight: "auto" }}>
          Marked as your own note — not a document claim.
        </span>
        <button type="button" className="btn sm ghost" onClick={() => setOpen(false)}>
          Cancel
        </button>
        <button type="submit" className="btn sm primary" disabled={saving || statement.trim().length < 8}>
          Add & link
        </button>
      </div>
    </form>
  );
}
