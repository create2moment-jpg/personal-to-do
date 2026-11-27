import { useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { AlarmClock, CalendarClock, CalendarPlus, CheckCircle2, Repeat, Clock, Flag, FolderKanban, Hash, Lightbulb, NotebookPen, Phone, Sparkles, SquareCheck, UserRound } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { api } from "../lib/api";
import { invalidateTasks, invalidateTime } from "../lib/queries";
import type { CapturePreview } from "../lib/types";
import { clockTime, formatMinutes, isoDay, relativeDay } from "../lib/util";
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
      const label = r.series
        ? `Recurring meeting added · ${r.series.title} · ${r.series.cadence}`
        : r.meeting && r.kind === "meeting"
          ? `Meeting added · ${r.meeting.title} · ${relativeDay(isoDay(new Date(r.meeting.start_at)))} ${clockTime(r.meeting.start_at)} · ${formatMinutes(r.meeting.duration_minutes)}`
          : r.meeting
        ? `Call logged · ${r.meeting.people.join(", ") || r.meeting.title} · ${formatMinutes(r.meeting.duration_minutes)}`
        : r.task
          ? `${r.task.title} → ${r.task.scheduled_date ? relativeDay(r.task.scheduled_date) : "Backlog"}`
          : `${r.kind === "idea" ? "Idea" : "Note"} saved`;
      if (r.meeting || r.series) invalidateTime(qc);
      r.warnings.forEach((w) => toast.warning(w));
      invalidateTasks(qc);
      void qc.invalidateQueries({ queryKey: ["notes"] });
      setText("");
      if (keepOpen) setLog((l) => [{ id: Date.now(), text: label }, ...l].slice(0, 4));
      else {
        toast.success(r.task ? "Task captured" : r.series || r.kind === "meeting" ? "Meeting added 📅" : "Captured", { description: label });
        onClose();
      }
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  const kindIcon = preview?.kind === "idea" ? Lightbulb : preview?.kind === "note" ? NotebookPen : preview?.kind === "call" ? Phone : preview?.kind === "meeting" ? CalendarPlus : SquareCheck;
  const KindIcon = text ? kindIcon : Sparkles;

  return (
    <div>
      <div className="capture-input-row">
        <KindIcon />
        <input
          ref={ref}
          className="capture-input"
          value={text}
          placeholder="Capture a task, idea:, note:, call: or meeting: …"
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
        <span><code>every mon</code> <code>every weekday</code> repeat</span>
        <span><code>+project</code> project</span>
        <span><code>idea:</code> ideas inbox</span>
        <span><code>note:</code> quick note</span>
        <span><code>call: Priya / topic ~30m</code> log a call</span>
        <span className="wide"><code>meeting: Planning @mon @10:00 ~1h every 2 weeks with Ana</code> add a meeting · repeats: <code>daily</code> <code>weekdays</code> <code>weekly</code> <code>monthly</code> <code>every tue,thu</code> <code>until 2027-03-01</code> <code>6 times</code></span>
        <span><Kbd>⌘</Kbd><Kbd>↵</Kbd> save &amp; keep open</span>
      </div>
    </div>
  );
}

function PreviewChips({ p }: { p: CapturePreview }) {
  const chips: { icon: typeof Flag; text: string; tone?: string }[] = [];
  if (p.kind === "call") {
    chips.push({ icon: Phone, text: "Call", tone: "accent" });
    (p.people ?? []).forEach((n) => chips.push({ icon: UserRound, text: n }));
    if (p.title) chips.push({ icon: NotebookPen, text: p.title });
    chips.push({ icon: Clock, text: formatMinutes(p.estimate_minutes ?? 30) });
    chips.push({ icon: CalendarClock, text: p.start_time ? `at ${p.start_time}` : "just ended", tone: "green" });
    p.tags.slice(0, 1).forEach((t) => chips.push({ icon: Hash, text: `topic: ${t}` }));
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
  if (p.kind === "meeting") {
    chips.push({ icon: CalendarPlus, text: p.repeat ? "Recurring meeting" : "Meeting", tone: "accent" });
    chips.push(p.title ? { icon: NotebookPen, text: p.title } : { icon: NotebookPen, text: "needs a title", tone: "red" });
    if (p.scheduled_date) chips.push({ icon: CalendarClock, text: `${p.repeat ? "from " : ""}${relativeDay(p.scheduled_date)} at ${p.start_time ?? "?"}`, tone: "green" });
    chips.push({ icon: Clock, text: formatMinutes(p.estimate_minutes ?? 30) });
    if (p.repeat) chips.push({ icon: Repeat, text: p.repeat, tone: "accent" });
    (p.people ?? []).forEach((n) => chips.push({ icon: UserRound, text: n }));
    p.tags.slice(0, 1).forEach((t) => chips.push({ icon: Hash, text: `topic: ${t}` }));
    return <ChipRow chips={chips} />;
  }
  if (p.kind !== "task") chips.push({ icon: p.kind === "idea" ? Lightbulb : NotebookPen, text: p.kind === "idea" ? "Ideas inbox" : "Note", tone: "accent" });
  else chips.push({ icon: SquareCheck, text: p.scheduled_date ? "Task" : "Task → Backlog", tone: "accent" });
  if (p.priority < 4) chips.push({ icon: Flag, text: `P${p.priority}`, tone: p.priority === 1 ? "red" : "orange" });
  if (p.estimate_minutes) chips.push({ icon: Clock, text: formatMinutes(p.estimate_minutes) });
  if (p.repeat) chips.push({ icon: Repeat, text: p.repeat, tone: "accent" });
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

function ChipRow({ chips }: { chips: { icon: typeof Flag; text: string; tone?: string }[] }) {
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
