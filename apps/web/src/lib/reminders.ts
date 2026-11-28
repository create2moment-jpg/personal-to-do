/** Reminders (B-024): what to notify about now. Pure, so it is unit-tested. */
import type { Meeting, Task } from "./types";

export interface ReminderPrefs {
  enabled: boolean;
  meetings: boolean;
  meetingLead: number; // minutes before
  timeboxes: boolean;
  dueToday: boolean; // once, at the start of the workday
}

export const DEFAULT_PREFS: ReminderPrefs = { enabled: false, meetings: true, meetingLead: 5, timeboxes: true, dueToday: true };

export interface Reminder {
  key: string; // unique per occurrence, so it fires once
  title: string;
  body: string;
  target: { kind: "task"; id: string } | { kind: "today" } | { kind: "meetings" };
}

/**
 * Reminders that are due at ``now`` and have not fired yet.
 * ``localMinutes`` is now as minutes since midnight in the workspace time zone;
 * ``day`` is today's ISO date there. A reminder is only sent inside a short
 * window after its moment (no burst of stale ones after a laptop wakes up).
 */
export function dueReminders(args: {
  now: Date;
  day: string;
  localMinutes: number;
  workStart: number; // minutes
  meetings: Meeting[];
  tasks: Task[];
  dueToday: Task[];
  prefs: ReminderPrefs;
  fired: Set<string>;
  windowMinutes?: number;
}): Reminder[] {
  const { now, day, localMinutes, workStart, prefs, fired } = args;
  const window = args.windowMinutes ?? 10;
  if (!prefs.enabled) return [];
  const out: Reminder[] = [];
  const t = now.getTime();
  if (prefs.meetings) {
    for (const m of args.meetings) {
      if (m.all_day || m.effective_status === "skipped") continue;
      const start = new Date(m.start_at).getTime();
      const at = start - prefs.meetingLead * 60_000;
      const key = `meeting:${m.id}:${m.start_at}`;
      if (t >= at && t <= at + window * 60_000 && t < start + 60_000 && !fired.has(key)) {
        const mins = Math.max(0, Math.round((start - t) / 60_000));
        out.push({ key, title: mins > 0 ? `${m.title} in ${mins} min` : `${m.title} is starting`, body: m.location ? `Location: ${m.location}` : "Meeting", target: { kind: "meetings" } });
      }
    }
  }
  if (prefs.timeboxes) {
    for (const task of args.tasks) {
      if (!task.timebox_start || task.status === "done" || task.scheduled_date !== day) continue;
      const [h, mi] = task.timebox_start.split(":").map(Number) as [number, number];
      const at = h * 60 + mi;
      const key = `timebox:${task.id}:${day}:${task.timebox_start}`;
      if (localMinutes >= at && localMinutes <= at + window && !fired.has(key)) {
        out.push({ key, title: `Time for “${task.title}”`, body: `Timeboxed at ${task.timebox_start}${task.estimate_minutes ? ` · ${task.estimate_minutes} min` : ""}`, target: { kind: "task", id: task.id } });
      }
    }
  }
  if (prefs.dueToday) {
    const key = `due:${day}`;
    const due = [...args.dueToday, ...args.tasks.filter((x) => x.due_date === day && x.status !== "done")];
    const unique = [...new Map(due.map((x) => [x.id, x])).values()];
    if (unique.length && localMinutes >= workStart && localMinutes <= workStart + 120 && !fired.has(key)) {
      const names = unique.slice(0, 3).map((x) => x.title).join(", ");
      out.push({ key, title: `${unique.length} due today`, body: names + (unique.length > 3 ? "…" : ""), target: { kind: "today" } });
    }
  }
  return out;
}
