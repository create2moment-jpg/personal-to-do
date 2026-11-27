import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarRange, Check, Clock, Wand2, X } from "lucide-react";
import { useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { api } from "../lib/api";
import { invalidateTasks } from "../lib/queries";
import type { Task, TimeboxProposal, TimeSpan } from "../lib/types";
import { useUi } from "../lib/ui-store";
import { cx, formatMinutes, isoDay } from "../lib/util";

const SNAP = 15;
const toMin = (hhmm: string) => {
  const [h, m] = hhmm.split(":").map(Number);
  return h! * 60 + m!;
};
const toHhmm = (m: number) => `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;

/**
 * Timeboxing: the working day as a strip — meetings, timeboxed tasks and the free
 * time between. Drag a task onto the strip (or pick a free slot) to give it a start
 * time; "Fill my free time" proposes a plan you can apply or dismiss.
 */
export function DayTimeline({ day }: { day: string }) {
  const ui = useUi();
  const qc = useQueryClient();
  const { data: tl } = useQuery({ queryKey: ["timeline", day], queryFn: () => api.timeline(day) });
  const [open, setOpen] = useState(true);
  const [proposal, setProposal] = useState<TimeboxProposal | null>(null);
  const [slotMenu, setSlotMenu] = useState<TimeSpan | null>(null);
  const [dropAt, setDropAt] = useState<number | null>(null);
  const strip = useRef<HTMLDivElement>(null);

  const range = useMemo(() => {
    if (!tl) return { start: 480, end: 1020 };
    const spans = [...tl.meetings, ...tl.boxes, ...(proposal?.placements ?? [])];
    let start = tl.window ? toMin(tl.window.start) : 480;
    let end = tl.window ? toMin(tl.window.end) : 1020;
    for (const s of spans) {
      start = Math.min(start, toMin(s.start));
      end = Math.max(end, toMin(s.end));
    }
    return { start: Math.floor(start / 60) * 60, end: Math.min(24 * 60, Math.ceil(end / 60) * 60) };
  }, [tl, proposal]);

  if (!tl) return null;
  const span = range.end - range.start || 60;
  const pos = (s: { start: string; end: string }) => ({
    left: `${((toMin(s.start) - range.start) / span) * 100}%`,
    width: `${Math.max(0.6, ((toMin(s.end) - toMin(s.start)) / span) * 100)}%`,
  });
  const hours: number[] = [];
  for (let h = range.start; h <= range.end; h += 60) hours.push(h);
  const now = new Date();
  const nowMin = day === isoDay() ? now.getHours() * 60 + now.getMinutes() : null;

  const refresh = () => {
    invalidateTasks(qc);
    void qc.invalidateQueries({ queryKey: ["timeline", day] });
  };
  const place = async (taskId: string, start: string | null) => {
    try {
      await api.timebox(taskId, day, start);
      refresh();
    } catch (e) {
      toast.error((e as Error).message);
    }
  };
  const minuteAt = (clientX: number) => {
    const r = strip.current!.getBoundingClientRect();
    const m = range.start + ((clientX - r.left) / r.width) * span;
    return Math.max(range.start, Math.min(range.end - SNAP, Math.round(m / SNAP) * SNAP));
  };
  const propose = async () => {
    try {
      const p = await api.proposeTimeboxes(day);
      if (p.placements.length === 0) toast.info(tl.unboxed.length ? "None of the remaining tasks fits into the free time left today" : "Every task on this day already has a time");
      else setProposal(p);
    } catch (e) {
      toast.error((e as Error).message);
    }
  };
  const apply = async () => {
    if (!proposal) return;
    try {
      await api.applyTimeboxes(day, proposal.placements.map((p) => ({ task_id: p.task.id, start: p.start })));
      toast.success(`${proposal.placements.length} task(s) timeboxed`);
      setProposal(null);
      refresh();
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  return (
    <section className="card timeline-card" aria-label="Day timeline">
      <div className="tray-head" style={{ padding: "0 2px 6px" }}>
        <button className="btn sm ghost" style={{ paddingLeft: 2 }} onClick={() => setOpen((o) => !o)} aria-expanded={open}>
          <CalendarRange /> <strong>Timeline</strong>
          <span className="faint">
            {tl.window ? `${tl.window.start}–${tl.window.end} · ${formatMinutes(tl.free_minutes)} free` : "not a working day"}
            {tl.boxes.length > 0 && ` · ${tl.boxes.length} timeboxed`}
          </span>
        </button>
        {open && !proposal && (
          <button className="btn sm" disabled={tl.unboxed.length === 0 || tl.free.length === 0} onClick={() => void propose()} title="Proposes start times for this day's open tasks — most important first. Nothing changes until you apply.">
            <Wand2 /> Fill my free time
          </button>
        )}
        {proposal && (
          <div style={{ display: "flex", gap: 4 }}>
            <button className="btn sm ghost" onClick={() => setProposal(null)}>
              Dismiss
            </button>
            <button className="btn sm primary" onClick={() => void apply()}>
              <Check /> Apply {proposal.placements.length}
            </button>
          </div>
        )}
      </div>
      {open && (
        <>
          <div
            ref={strip}
            className={cx("tl-strip", dropAt !== null && "drop-active")}
            onDragOver={(e) => {
              if (!e.dataTransfer.types.includes("application/x-ppos-task")) return;
              e.preventDefault();
              setDropAt(minuteAt(e.clientX));
            }}
            onDragLeave={() => setDropAt(null)}
            onDrop={(e) => {
              const id = e.dataTransfer.getData("application/x-ppos-task");
              const at = minuteAt(e.clientX);
              setDropAt(null);
              if (id) void place(id, toHhmm(at));
            }}
          >
            {hours.map((h) => (
              <span key={h} className="tl-hour" style={{ left: `${((h - range.start) / span) * 100}%` }}>
                {toHhmm(h).replace(/:00$/, "")}
              </span>
            ))}
            {tl.window && <div className="tl-work" style={pos(tl.window)} aria-hidden />}
            {tl.free.map((f) => (
              <button key={f.start} className="tl-free" style={pos(f)} title={`Free ${f.start}–${f.end} (${formatMinutes(f.minutes)}) — place a task here`} aria-label={`Free ${f.start} to ${f.end}`} onClick={() => setSlotMenu(slotMenu?.start === f.start ? null : f)} />
            ))}
            {tl.meetings.map((m) => (
              <div key={m.id} className={cx("tl-block meeting", !m.attending && "skipped")} style={pos(m)} title={`${m.start}–${m.end} ${m.title}${m.attending ? "" : " (not attending)"}`}>
                <span>{m.title}</span>
              </div>
            ))}
            {tl.boxes.map((b) => (
              <div
                key={b.task.id}
                className={cx("tl-block task", b.task.status === "done" && "done")}
                style={pos(b)}
                draggable
                onDragStart={(e) => e.dataTransfer.setData("application/x-ppos-task", b.task.id)}
                title={`${b.start}–${b.end} ${b.task.title}`}
              >
                <button className="tl-open" onClick={() => ui.openTask(b.task.id)}>
                  {b.task.title}
                </button>
                <button className="tl-x" aria-label={`Remove the time from ${b.task.title}`} onClick={() => void place(b.task.id, null)}>
                  <X size={11} />
                </button>
              </div>
            ))}
            {proposal?.placements.map((p) => (
              <div key={p.task.id} className="tl-block proposed" style={pos(p)} title={`Proposed ${p.start}–${p.end} ${p.task.title}`}>
                <span>{p.task.title}</span>
              </div>
            ))}
            {dropAt !== null && <div className="tl-drop" style={{ left: `${((dropAt - range.start) / span) * 100}%` }}>{toHhmm(dropAt)}</div>}
            {nowMin !== null && nowMin >= range.start && nowMin <= range.end && <div className="tl-now" style={{ left: `${((nowMin - range.start) / span) * 100}%` }} aria-hidden />}
          </div>

          {slotMenu && (
            <div className="tl-menu" role="menu" aria-label={`Place a task at ${slotMenu.start}`}>
              <span className="faint">
                <Clock size={12} /> {slotMenu.start}–{slotMenu.end}:
              </span>
              {tl.unboxed.length === 0 && <span className="faint">no open task without a time on this day</span>}
              {tl.unboxed.map((t) => (
                <button
                  key={t.id}
                  role="menuitem"
                  className="filter-chip"
                  onClick={() => {
                    setSlotMenu(null);
                    void place(t.id, slotMenu.start);
                  }}
                >
                  {t.title} · {formatMinutes(t.estimate_minutes ?? tl.default_minutes)}
                </button>
              ))}
            </div>
          )}

          {proposal && proposal.unplaced.length > 0 && <div className="faint tl-note">Doesn’t fit today: {proposal.unplaced.map((t) => t.title).join(", ")}</div>}

          {tl.unboxed.length > 0 && !slotMenu && (
            <div className="tl-unboxed" aria-label="Tasks without a time">
              <span className="faint">Drag onto the timeline:</span>
              {tl.unboxed.map((t) => (
                <UnboxedChip key={t.id} t={t} minutes={t.estimate_minutes ?? tl.default_minutes} />
              ))}
            </div>
          )}
        </>
      )}
    </section>
  );
}

function UnboxedChip({ t, minutes }: { t: Task; minutes: number }) {
  return (
    <span className="tl-chip" draggable onDragStart={(e) => e.dataTransfer.setData("application/x-ppos-task", t.id)} title="Drag onto the timeline to give it a start time">
      {t.title} <span className="faint">{formatMinutes(minutes)}</span>
    </span>
  );
}
