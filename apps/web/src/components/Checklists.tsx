import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ListChecks, Pencil, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { api, type ChecklistRow } from "../lib/api";
import { invalidateTasks } from "../lib/queries";
import { useUi } from "../lib/ui-store";
import { addDays, isoDay } from "../lib/util";
import { Dialog } from "./primitives";

/** Reusable checklists: apply one to get a parent task with a subtask per line. */
export function ChecklistsDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  return (
    <Dialog open={open} onClose={onClose} label="Checklists" width={620}>
      {open && <Body onClose={onClose} />}
    </Dialog>
  );
}

function Body({ onClose }: { onClose: () => void }) {
  const ui = useUi();
  const qc = useQueryClient();
  const { data: lists = [], isLoading } = useQuery({ queryKey: ["checklists"], queryFn: api.checklists });
  const [edit, setEdit] = useState<{ id?: string; name: string; lines: string } | null>(null);
  const refresh = () => void qc.invalidateQueries({ queryKey: ["checklists"] });

  const apply = async (c: ChecklistRow, day: string | null) => {
    try {
      const t = await api.applyChecklist(c.id, day);
      invalidateTasks(qc);
      refresh();
      onClose();
      toast.success(`“${t.title}” added with ${c.lines.length} step${c.lines.length === 1 ? "" : "s"}`, { action: { label: "Open", onClick: () => ui.openTask(t.id) } });
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  if (edit)
    return (
      <form
        className="checklist-edit"
        onSubmit={async (e) => {
          e.preventDefault();
          try {
            await api.saveChecklist(edit.name, edit.lines, edit.id);
            refresh();
            setEdit(null);
          } catch (err) {
            toast.error((err as Error).message);
          }
        }}
      >
        <h3>{edit.id ? "Edit checklist" : "New checklist"}</h3>
        <input className="input" autoFocus placeholder="Name, e.g. Release checklist" value={edit.name} onChange={(e) => setEdit({ ...edit, name: e.target.value })} aria-label="Checklist name" />
        <textarea className="input checklist-lines" placeholder={"One step per line — quick-capture syntax works:\nTag the release ~15m !1 #release\nAnnounce in the channel ~10m"} value={edit.lines} onChange={(e) => setEdit({ ...edit, lines: e.target.value })} aria-label="Steps, one per line" />
        <div className="lc-foot">
          <span className="faint" style={{ fontSize: "0.82rem" }}>~30m time · !1 priority · #tag</span>
          <button type="button" className="btn ghost" onClick={() => setEdit(null)}>
            Cancel
          </button>
          <button type="submit" className="btn primary">
            Save
          </button>
        </div>
      </form>
    );

  return (
    <div className="checklists">
      <div className="lc-head">
        <ListChecks size={18} />
        <h3>Checklists</h3>
        <button className="btn sm" style={{ marginLeft: "auto" }} onClick={() => setEdit({ name: "", lines: "" })}>
          <Plus /> New
        </button>
      </div>
      <p className="faint" style={{ marginTop: 0, fontSize: "0.88rem" }}>Apply a checklist to get one task with a subtask for each step — for today, tomorrow or the backlog.</p>
      {!isLoading && lists.length === 0 && (
        <div className="checklist-empty">
          <p>No checklists yet.</p>
          <button
            className="btn primary"
            onClick={async () => {
              await api.checklistStarters();
              refresh();
            }}
          >
            Add starters: release, 1:1 prep, onboarding, weekly shutdown
          </button>
        </div>
      )}
      <ul className="checklist-list">
        {lists.map((c) => (
          <li key={c.id}>
            <div className="cl-main">
              <strong>{c.name}</strong>
              <span className="faint">
                {c.lines.length} steps{c.uses ? ` · used ${c.uses}×` : ""} · {c.lines.slice(0, 3).join(" · ")}
                {c.lines.length > 3 ? " …" : ""}
              </span>
            </div>
            <div className="cl-actions">
              <button className="btn sm primary" onClick={() => void apply(c, isoDay())}>
                Today
              </button>
              <button className="btn sm" onClick={() => void apply(c, addDays(isoDay(), 1))}>
                Tomorrow
              </button>
              <button className="btn sm ghost" onClick={() => void apply(c, null)}>
                Backlog
              </button>
              <button className="btn icon sm ghost" aria-label={`Edit ${c.name}`} onClick={() => setEdit({ id: c.id, name: c.name, lines: c.lines.join("\n") })}>
                <Pencil />
              </button>
              <button
                className="btn icon sm ghost danger"
                aria-label={`Delete ${c.name}`}
                onClick={async () => {
                  if (!confirm(`Delete the checklist “${c.name}”? Tasks made from it stay.`)) return;
                  await api.deleteChecklist(c.id);
                  refresh();
                }}
              >
                <Trash2 />
              </button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
