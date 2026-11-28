import { CalendarDays, CalendarClock, Clock, Flame, ListTodo, Phone, Sparkles, Star, Timer, type LucideIcon } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import type { ViewId } from "./ui-store";

export type GadgetId = "clock" | "agenda" | "calendar" | "upnext" | "priorities" | "habits" | "calls" | "focus" | "assistant";

export const GADGETS: Record<GadgetId, { label: string; icon: LucideIcon; hint: string }> = {
  clock: { label: "Clock", icon: Clock, hint: "Time, date and how far through your working day you are" },
  agenda: { label: "Today's meetings", icon: CalendarClock, hint: "Next meeting with a countdown, and the rest of today" },
  calendar: { label: "Calendar", icon: CalendarDays, hint: "Month view with meetings, planned and due work per day" },
  upnext: { label: "Up next", icon: ListTodo, hint: "The task to pick up now" },
  priorities: { label: "Top priorities", icon: Star, hint: "Today's three starred tasks" },
  habits: { label: "Habits", icon: Flame, hint: "Small daily or weekly habits and their streaks (off until you turn it on)" },
  calls: { label: "Calls", icon: Phone, hint: "Call timer and your recent calls" },
  focus: { label: "Focus timer", icon: Timer, hint: "25 / 50 / 90 minute focus blocks" },
  assistant: { label: "Assistant", icon: Sparkles, hint: "Local AI status and a quick question box" },
};

export const DEFAULT_ORDER: GadgetId[] = ["clock", "agenda", "calendar", "upnext", "priorities", "habits", "calls", "focus", "assistant"];
/** Opt-in gadgets: hidden until turned on in Settings → Gadgets (also for existing setups). */
const DEFAULT_HIDDEN: GadgetId[] = ["habits"];

/** Pages with wide content start with the dock collapsed to a slim strip. */
const WIDE_VIEWS: ViewId[] = ["notes", "week", "book", "knowledge", "career", "board", "goals", "skills", "reviews", "analytics", "ai", "workflows", "settings", "boards", "people"];

export interface GadgetPrefs {
  order: GadgetId[];
  hidden: GadgetId[];
  collapsed: Partial<Record<ViewId, boolean>>; // per page; missing = default for that page
}

const KEY = "ppos.gadgets.v1";
const EVENT = "ppos-gadgets-changed";

function load(): GadgetPrefs {
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) {
      const p = JSON.parse(raw) as Partial<GadgetPrefs>;
      const known = (p.order ?? []).filter((g): g is GadgetId => g in GADGETS);
      // gadgets added in a later version appear at the end
      const added = DEFAULT_ORDER.filter((g) => !known.includes(g));
      const order = [...known, ...added];
      const hidden = [...(p.hidden ?? []).filter((g) => g in GADGETS), ...added.filter((g) => DEFAULT_HIDDEN.includes(g))];
      return { order, hidden, collapsed: p.collapsed ?? {} };
    }
  } catch {
    /* storage unavailable or corrupt: defaults */
  }
  return { order: DEFAULT_ORDER, hidden: DEFAULT_HIDDEN, collapsed: {} };
}

/** Per-device preferences (a convenience, not data): shared by the dock and Settings. */
export function useGadgetPrefs() {
  const [prefs, setPrefs] = useState<GadgetPrefs>(load);
  useEffect(() => {
    const sync = () => setPrefs(load());
    window.addEventListener(EVENT, sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener(EVENT, sync);
      window.removeEventListener("storage", sync);
    };
  }, []);
  const save = useCallback((next: GadgetPrefs) => {
    setPrefs(next);
    try {
      localStorage.setItem(KEY, JSON.stringify(next));
    } catch {
      /* not persisted this time */
    }
    window.dispatchEvent(new Event(EVENT));
  }, []);
  const isCollapsed = (view: ViewId) => prefs.collapsed[view] ?? WIDE_VIEWS.includes(view);
  return { prefs, save, isCollapsed };
}
