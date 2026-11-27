/** Repeating tasks: the same small RRULE subset the server accepts (FREQ, INTERVAL, BYDAY). */
export interface Repeat {
  freq: "daily" | "weekly" | "monthly";
  interval: number;
  days: number[]; // 0 = Monday (weekly only)
}

const CODES = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"];
const NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export function parseRepeat(rule: string | null | undefined): Repeat | null {
  if (!rule) return null;
  const parts = Object.fromEntries(
    rule
      .toUpperCase()
      .split(";")
      .map((p) => p.split("=") as [string, string]),
  );
  const freq = ({ DAILY: "daily", WEEKLY: "weekly", MONTHLY: "monthly" } as const)[parts.FREQ as "DAILY"];
  if (!freq) return null;
  const days = (parts.BYDAY ?? "")
    .split(",")
    .filter(Boolean)
    .map((d: string) => CODES.indexOf(d))
    .filter((i: number) => i >= 0);
  return { freq, interval: Math.max(1, Number(parts.INTERVAL ?? 1) || 1), days };
}

export function toRule(r: Repeat | null): string | null {
  if (!r) return null;
  let s = `FREQ=${r.freq.toUpperCase()}`;
  if (r.interval !== 1) s += `;INTERVAL=${r.interval}`;
  if (r.freq === "weekly" && r.days.length) s += `;BYDAY=${[...r.days].sort().map((d) => CODES[d]).join(",")}`;
  return s;
}

export function describeRepeat(rule: string | null | undefined): string {
  const r = parseRepeat(rule);
  if (!r) return "";
  const unit = { daily: "day", weekly: "week", monthly: "month" }[r.freq];
  if (r.freq === "weekly" && r.interval === 1 && r.days.join() === "0,1,2,3,4") return "Every weekday";
  let s = r.interval === 1 ? { daily: "Daily", weekly: "Weekly", monthly: "Monthly" }[r.freq] : `Every ${r.interval} ${unit}s`;
  if (r.freq === "weekly" && r.days.length) s += ` on ${[...r.days].sort().map((d) => NAMES[d]).join(", ")}`;
  return s;
}

export const WEEKDAY_SHORT = NAMES;
