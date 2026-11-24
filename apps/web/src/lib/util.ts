export function isoDay(d: Date = new Date()): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export function addDays(iso: string, n: number): string {
  const [y, m, d] = iso.split("-").map(Number) as [number, number, number];
  return isoDay(new Date(y, m - 1, d + n));
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
  return new Date(y, m - 1, d).toLocaleDateString(undefined, {
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
