import { useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { AlarmClock, CalendarClock, CheckCircle2, Clock, Flag, FolderKanban, Hash, Lightbulb, NotebookPen, Sparkles, SquareCheck } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { api } from "../lib/api";
import { invalidateTasks } from "../lib/queries";
import type { CapturePreview } from "../lib/types";
import { formatMinutes, relativeDay } from "../lib/util";
import { Dialog, Kbd } from "./primitives";

export function QuickCapture({ open, initial, onClose }: { open: boolean; initial?: string; onClose: () => void }) {
  return (
    <Dialog open={open} onClose={onClose} label="Quick capture" width={680}>
      {open && <CaptureBody initial={initial} onClose={onClose} />}
    </Dialog>
  );
}

function CaptureBody({ initial, onClose }: { initial?: string; onClose: () => void }) {
  const qc = useQueryClient();
  const [text, setText] = useState(initial ?? "");
  const [preview, setPreview] = useState<CapturePreview | null>(null);
  const [log, setLog] = useState<{ id: number; text: string }[]>([]);
  const ref = useRef<HTMLInputElement>(null);

  useEffect(() => ref.current?.focus(), []);

  // Live, server-side parse preview (same deterministic parser that saves).
  useEffect(() => {
    if (!text.trim()) {
      setPreview(null);
      return;
    }
    const t = setTimeout(() => {
      api.capturePreview(text).then(setPreview).catch(() => setPreview(null));
    }, 90);
    return () => clearTimeout(t);
  }, [text]);

  const submit = async (keepOpen: boolean) => {
    if (!text.trim()) return;
    try {
      const r = await api.capture(text);
      const label = r.task
        ? `${r.task.title} → ${r.task.scheduled_date ? relativeDay(r.task.scheduled_date) : "Backlog"}`
        : `${r.kind === "idea" ? "Idea" : "Note"} saved`;
      r.warnings.forEach((w) => toast.warning(w));
      invalidateTasks(qc);
      void qc.invalidateQueries({ queryKey: ["notes"] });
      setText("");
      if (keepOpen) setLog((l) => [{ id: Date.now(), text: label }, ...l].slice(0, 4));
      else {
        toast.success(r.task ? "Task captured" : "Captured", { description: label });
        onClose();
      }
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  const kindIcon = preview?.kind === "idea" ? Lightbulb : preview?.kind === "note" ? NotebookPen : SquareCheck;
  const KindIcon = text ? kindIcon : Sparkles;

  return (
    <div>
      <div className="capture-input-row">
        <KindIcon />
        <input
          ref={ref}
          className="capture-input"
          value={text}
          placeholder="Capture a task, an idea: or a note: …"
          aria-label="Capture text"
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              void submit(e.metaKey || e.ctrlKey || e.shiftKey);
            }
          }}
        />
        <Kbd>↵</Kbd>
      </div>

      <div className="capture-preview" aria-live="polite">
        <AnimatePresence initial={false}>
          {preview && <PreviewChips key="chips" p={preview} />}
        </AnimatePresence>
      </div>

      {log.length > 0 && (
        <ul className="capture-log">
          {log.map((l) => (
            <motion.li key={l.id} initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }}>
              <CheckCircle2 /> {l.text}
            </motion.li>
          ))}
        </ul>
      )}

      <div className="capture-help">
        <span><code>#tag</code> tag</span>
        <span><code>!1</code>–<code>!4</code> priority</span>
        <span><code>~45m</code> <code>~1h30m</code> estimate</span>
        <span><code>@today</code> <code>@fri</code> schedule</span>
        <span><code>due:fri</code> due date</span>
        <span><code>+project</code> project</span>
        <span><code>idea:</code> ideas inbox</span>
        <span><code>note:</code> quick note</span>
        <span><Kbd>⌘</Kbd><Kbd>↵</Kbd> save &amp; keep open</span>
      </div>
    </div>
  );
}

function PreviewChips({ p }: { p: CapturePreview }) {
  const chips: { icon: typeof Flag; text: string; tone?: string }[] = [];
  if (p.kind !== "task") chips.push({ icon: p.kind === "idea" ? Lightbulb : NotebookPen, text: p.kind === "idea" ? "Ideas inbox" : "Note", tone: "accent" });
  else chips.push({ icon: SquareCheck, text: p.scheduled_date ? "Task" : "Task → Backlog", tone: "accent" });
  if (p.priority < 4) chips.push({ icon: Flag, text: `P${p.priority}`, tone: p.priority === 1 ? "red" : "orange" });
  if (p.estimate_minutes) chips.push({ icon: Clock, text: formatMinutes(p.estimate_minutes) });
  if (p.scheduled_date) chips.push({ icon: CalendarClock, text: relativeDay(p.scheduled_date), tone: "green" });
  if (p.due_date) chips.push({ icon: AlarmClock, text: `Due ${relativeDay(p.due_date)}` });
  if (p.project_hint) chips.push({ icon: FolderKanban, text: p.project_name ?? `${p.project_hint} (unknown)`, tone: p.project_name ? undefined : "red" });
  p.tags.forEach((t) => chips.push({ icon: Hash, text: t }));
  return (
    <motion.div style={{ display: "flex", gap: 6, flexWrap: "wrap" }} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
      {chips.map((c, i) => (
        <motion.span key={`${c.text}-${i}`} layout className={`chip ${c.tone ?? ""}`} initial={{ scale: 0.9, opacity: 0 }} animate={{ scale: 1, opacity: 1 }}>
          <c.icon /> {c.text}
        </motion.span>
      ))}
    </motion.div>
  );
}
