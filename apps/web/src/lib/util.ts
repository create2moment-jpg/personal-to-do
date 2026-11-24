/** Workspace time zone (from settings); "today" and clock times follow it. */
let workspaceTz: string | undefined;
export function setWorkspaceTimeZone(tz: string | undefined) {
  workspaceTz = tz;
}
export function getWorkspaceTimeZone(): string {
  return workspaceTz ?? Intl.DateTimeFormat().resolvedOptions().timeZone;
}

/** Calendar date (YYYY-MM-DD) of an instant in the workspace time zone. */
export function isoDay(d: Date = new Date()): string {
  const parts = new Intl.DateTimeFormat("en-CA", { timeZone: getWorkspaceTimeZone(), year: "numeric", month: "2-digit", day: "2-digit" }).format(d);
  return parts; // en-CA formats as YYYY-MM-DD
}

/** Pure calendar arithmetic on YYYY-MM-DD strings (no time zone involved). */
export function addDays(iso: string, n: number): string {
  const [y, m, d] = iso.split("-").map(Number) as [number, number, number];
  const dt = new Date(Date.UTC(y, m - 1, d + n));
  return dt.toISOString().slice(0, 10);
}

export function mondayOf(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number) as [number, number, number];
  const wd = (new Date(Date.UTC(y, m - 1, d)).getUTCDay() + 6) % 7;
  return addDays(iso, -wd);
}

/** Clock time (HH:MM) of an instant in the workspace time zone. */
export function clockTime(isoTs: string | Date): string {
  const d = typeof isoTs === "string" ? new Date(isoTs) : isoTs;
  return new Intl.DateTimeFormat(undefined, { timeZone: getWorkspaceTimeZone(), hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).format(d);
}

/** Build an ISO instant from a local date + HH:MM in the workspace zone. */
export function zonedInstant(day: string, hhmm: string): string {
  const [y, m, d] = day.split("-").map(Number) as [number, number, number];
  const [hh, mm] = hhmm.split(":").map(Number) as [number, number];
  const guess = Date.UTC(y, m - 1, d, hh, mm);
  const offset = tzOffsetMinutes(new Date(guess));
  return new Date(guess - offset * 60_000).toISOString();
}

function tzOffsetMinutes(at: Date): number {
  const f = new Intl.DateTimeFormat("en-US", { timeZone: getWorkspaceTimeZone(), hourCycle: "h23", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
  const p = Object.fromEntries(f.formatToParts(at).map((x) => [x.type, x.value]));
  const asUtc = Date.UTC(Number(p.year), Number(p.month) - 1, Number(p.day), Number(p.hour), Number(p.minute));
  return Math.round((asUtc - at.getTime()) / 60_000);
}

export function formatMinutes(min: number | null | undefined): string {
  if (min === null || min === undefined) return "–";
  const h = Math.floor(min / 60);
  const m = min % 60;
  if (h && m) return `${h}h ${m}m`;
  return h ? `${h}h` : `${m}m`;
}

export function prettyDay(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number) as [number, number, number];
  return new Date(y, m - 1, d, 12).toLocaleDateString(undefined, {
    weekday: "long",
    month: "short",
    day: "numeric",
  });
}

/** Debounce that also exposes flush() so pending autosaves are never dropped. */
export function debounce<A extends unknown[]>(fn: (...args: A) => void, ms: number) {
  let timer: ReturnType<typeof setTimeout> | undefined;
  let lastArgs: A | undefined;
  const run = (...args: A) => {
    lastArgs = args;
    clearTimeout(timer);
    timer = setTimeout(() => {
      timer = undefined;
      fn(...args);
    }, ms);
  };
  run.flush = () => {
    if (timer !== undefined && lastArgs) {
      clearTimeout(timer);
      timer = undefined;
      fn(...lastArgs);
    }
  };
  return run;
}

export function isTypingTarget(el: EventTarget | null): boolean {
  if (!(el instanceof HTMLElement)) return false;
  return el.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName);
}

export function greeting(d: Date = new Date()): string {
  const h = d.getHours();
  if (h < 5) return "Working late";
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  return "Good evening";
}

export function relativeDay(iso: string, today: string = isoDay()): string {
  if (iso === today) return "Today";
  if (iso === addDays(today, 1)) return "Tomorrow";
  if (iso === addDays(today, -1)) return "Yesterday";
  const [y, m, d] = iso.split("-").map(Number) as [number, number, number];
  return new Date(y, m - 1, d).toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
}

export function relativeTime(isoTs: string, now: number = Date.now()): string {
  const diff = (now - new Date(isoTs).getTime()) / 1000;
  if (diff < 45) return "just now";
  if (diff < 3600) return `${Math.round(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.round(diff / 3600)}h ago`;
  if (diff < 86400 * 7) return `${Math.round(diff / 86400)}d ago`;
  return new Date(isoTs).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

/** Midpoint ordering so a drop never needs to renumber siblings. */
export function positionBetween(before: number | undefined, after: number | undefined): number {
  if (before === undefined && after === undefined) return 1;
  if (before === undefined) return (after as number) - 1;
  if (after === undefined) return before + 1;
  return (before + after) / 2;
}

export const cx = (...parts: (string | false | null | undefined)[]) => parts.filter(Boolean).join(" ");
