/** ⌘K actions (B-025): turn what you type into one concrete, previewable action. Pure. */

export interface TaskRef {
  id: string;
  title: string;
  status: string;
}

export type Action =
  | { kind: "done"; task: TaskRef; label: string }
  | { kind: "move"; task: TaskRef; day: string; label: string }
  | { kind: "timebox"; task: TaskRef; day: string; start: string; label: string }
  | { kind: "note"; title: string; label: string }
  | { kind: "board"; title: string; label: string }
  | { kind: "call"; line: string; label: string }
  | { kind: "capture"; line: string; label: string };

const WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"];

const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

/** "today", "tomorrow", "mon"/"monday" (next one), "next week" (Monday), or an ISO date. */
export function resolveDay(word: string, today: Date): string | null {
  const w = word.trim().toLowerCase();
  const d = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  if (w === "today") return iso(d);
  if (w === "tomorrow" || w === "tmrw") return iso(new Date(d.getFullYear(), d.getMonth(), d.getDate() + 1));
  if (w === "next week") {
    const add = ((8 - d.getDay()) % 7) || 7;
    return iso(new Date(d.getFullYear(), d.getMonth(), d.getDate() + add));
  }
  const idx = WEEKDAYS.findIndex((x) => x === w || x.slice(0, 3) === w);
  if (idx >= 0) {
    const target = (idx + 1) % 7; // JS: Sunday = 0
    const add = ((target - d.getDay() + 7) % 7) || 7;
    return iso(new Date(d.getFullYear(), d.getMonth(), d.getDate() + add));
  }
  return /^\d{4}-\d{2}-\d{2}$/.test(w) ? w : null;
}

/** Best open task for a typed name: exact, then prefix, then contains (case-insensitive). */
export function findTask(name: string, tasks: TaskRef[]): TaskRef | null {
  const n = name.trim().toLowerCase().replace(/^["“]|["”]$/g, "");
  if (n.length < 2) return null;
  const open = tasks.filter((t) => t.status !== "done");
  return (
    open.find((t) => t.title.toLowerCase() === n) ??
    open.find((t) => t.title.toLowerCase().startsWith(n)) ??
    open.find((t) => t.title.toLowerCase().includes(n)) ??
    null
  );
}

const q = (t: TaskRef) => `“${t.title}”`;

export function parseCommand(input: string, tasks: TaskRef[], today: Date): Action | null {
  const s = input.trim();
  let m: RegExpExecArray | null;
  if ((m = /^(?:done|finish|complete)\s+(.+)$/i.exec(s))) {
    const t = findTask(m[1]!, tasks);
    return t ? { kind: "done", task: t, label: `Mark ${q(t)} done` } : null;
  }
  if ((m = /^(?:move|schedule|plan)\s+(.+?)\s+(?:to|for|on)\s+(today|tomorrow|tmrw|next week|\w+|\d{4}-\d{2}-\d{2})$/i.exec(s))) {
    const t = findTask(m[1]!, tasks);
    const day = resolveDay(m[2]!, today);
    return t && day ? { kind: "move", task: t, day, label: `Move ${q(t)} to ${m[2]!.toLowerCase()} (${day})` } : null;
  }
  if ((m = /^timebox\s+(.+?)\s+(?:at\s+)?([01]?\d|2[0-3])[:.]([0-5]\d)(?:\s+(today|tomorrow|tmrw|\w+))?$/i.exec(s))) {
    const t = findTask(m[1]!, tasks);
    const day = resolveDay(m[4] ?? "today", today);
    const start = `${m[2]!.padStart(2, "0")}:${m[3]}`;
    return t && day ? { kind: "timebox", task: t, day, start, label: `Timebox ${q(t)} at ${start} on ${day}` } : null;
  }
  if ((m = /^(?:new\s+)?note\s+(.+)$/i.exec(s))) return { kind: "note", title: m[1]!.trim(), label: `New note “${m[1]!.trim()}”` };
  if ((m = /^(?:new\s+)?board\s+(.+)$/i.exec(s))) return { kind: "board", title: m[1]!.trim(), label: `New board “${m[1]!.trim()}”` };
  if ((m = /^(?:log\s+)?call\s+(?:with\s+)?(.+)$/i.exec(s))) return { kind: "call", line: `call: ${m[1]!.trim()}`, label: `Log a call: ${m[1]!.trim()}` };
  if ((m = /^(?:add|task|todo)\s+(.+)$/i.exec(s))) return { kind: "capture", line: m[1]!.trim(), label: `Add task “${m[1]!.trim()}”` };
  return null;
}
