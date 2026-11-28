import { BellRing } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { useSettings, useToday } from "../lib/queries";
import { DEFAULT_PREFS, dueReminders, type Reminder, type ReminderPrefs } from "../lib/reminders";
import { useUi } from "../lib/ui-store";
import { clockTime, isoDay } from "../lib/util";

const PREFS_KEY = "ppos.reminders.v1";
const FIRED_KEY = "ppos.reminders.fired";
const EVENT = "ppos-reminders-changed";

function loadPrefs(): ReminderPrefs {
  try {
    return { ...DEFAULT_PREFS, ...(JSON.parse(localStorage.getItem(PREFS_KEY) ?? "{}") as Partial<ReminderPrefs>) };
  } catch {
    return DEFAULT_PREFS;
  }
}

export function useReminderPrefs() {
  const [prefs, setPrefs] = useState<ReminderPrefs>(loadPrefs);
  useEffect(() => {
    const sync = () => setPrefs(loadPrefs());
    window.addEventListener(EVENT, sync);
    return () => window.removeEventListener(EVENT, sync);
  }, []);
  const save = useCallback((next: ReminderPrefs) => {
    setPrefs(next);
    try {
      localStorage.setItem(PREFS_KEY, JSON.stringify(next));
    } catch {
      /* per-device convenience: not persisted this time */
    }
    window.dispatchEvent(new Event(EVENT));
  }, []);
  return [prefs, save] as const;
}

function loadFired(day: string): Set<string> {
  try {
    const raw = JSON.parse(localStorage.getItem(FIRED_KEY) ?? "{}") as { day?: string; keys?: string[] };
    return new Set(raw.day === day ? raw.keys : []);
  } catch {
    return new Set();
  }
}

const toMin = (hhmm: string) => {
  const [h, m] = hhmm.split(":").map(Number);
  return h! * 60 + m!;
};

/** Sends due reminders while the app is open (desktop notification, else an in-app toast). */
export function ReminderRunner() {
  const ui = useUi();
  const [prefs] = useReminderPrefs();
  const day = isoDay();
  const { data: today } = useToday(day);
  const { data: settings } = useSettings();
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setTick((x) => x + 1), 30_000);
    return () => clearInterval(t);
  }, []);
  useEffect(() => {
    if (!prefs.enabled || !today) return;
    const now = new Date();
    const fired = loadFired(day);
    const due = dueReminders({
      now,
      day,
      localMinutes: toMin(clockTime(now)),
      workStart: toMin(settings?.work_start ?? "08:00"),
      meetings: today.meetings,
      tasks: today.tasks,
      dueToday: today.due_today_unscheduled,
      prefs,
      fired,
    });
    if (!due.length) return;
    for (const r of due) {
      fired.add(r.key);
      notify(r, () => {
        if (r.target.kind === "task") ui.openTask(r.target.id);
        else ui.navigate(r.target.kind === "meetings" ? "meetings" : "today");
      });
    }
    try {
      localStorage.setItem(FIRED_KEY, JSON.stringify({ day, keys: [...fired] }));
    } catch {
      /* may repeat after a reload */
    }
  }, [tick, today, prefs, settings, day, ui]);
  return null;
}

export function notify(r: Pick<Reminder, "title" | "body">, onClick?: () => void) {
  if ("Notification" in window && Notification.permission === "granted" && document.visibilityState !== "visible") {
    try {
      const n = new Notification(r.title, { body: r.body, tag: r.title });
      n.onclick = () => {
        window.focus();
        onClick?.();
        n.close();
      };
      return;
    } catch {
      /* fall back to an in-app message */
    }
  }
  toast(r.title, { description: r.body, icon: <BellRing size={16} />, duration: 15_000, action: onClick ? { label: "Open", onClick } : undefined });
}

/** Settings → Reminders. */
export function ReminderSettings() {
  const [prefs, save] = useReminderPrefs();
  const [perm, setPerm] = useState<string>(() => ("Notification" in window ? Notification.permission : "unsupported"));
  const set = (p: Partial<ReminderPrefs>) => save({ ...prefs, ...p });
  return (
    <section className="card settings-section" aria-label="Reminders">
      <h3 style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <BellRing size={16} /> Reminders
      </h3>
      <p>Gentle reminders while the app is open: desktop notifications when it is in the background, a small message when you are looking at it. Stored in this browser only.</p>
      <label className="setting-row">
        <div>
          <div className="s-label">Remind me</div>
          <div className="s-help">Off by default.</div>
        </div>
        <input type="checkbox" className="check" checked={prefs.enabled} onChange={(e) => set({ enabled: e.target.checked })} aria-label="Turn reminders on" />
      </label>
      <fieldset className="reminder-opts" disabled={!prefs.enabled}>
        <label>
          <input type="checkbox" checked={prefs.meetings} onChange={(e) => set({ meetings: e.target.checked })} /> Before meetings I attend:
          <select className="select" value={prefs.meetingLead} onChange={(e) => set({ meetingLead: Number(e.target.value) })} aria-label="Minutes before a meeting">
            {[1, 2, 5, 10, 15].map((m) => (
              <option key={m} value={m}>
                {m} min
              </option>
            ))}
          </select>
        </label>
        <label>
          <input type="checkbox" checked={prefs.timeboxes} onChange={(e) => set({ timeboxes: e.target.checked })} /> When a timeboxed task starts
        </label>
        <label>
          <input type="checkbox" checked={prefs.dueToday} onChange={(e) => set({ dueToday: e.target.checked })} /> What is due today, at the start of my workday
        </label>
      </fieldset>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        {perm !== "granted" && perm !== "unsupported" && (
          <button className="btn sm" onClick={async () => setPerm(await Notification.requestPermission())}>
            Allow desktop notifications
          </button>
        )}
        <span className="faint" style={{ fontSize: "0.82rem" }}>
          Desktop notifications: {perm === "granted" ? "allowed" : perm === "denied" ? "blocked in the browser settings" : perm === "unsupported" ? "not supported here" : "not allowed yet"}
        </span>
        <button className="btn sm ghost" onClick={() => notify({ title: "Reminder test", body: "This is how reminders look." })}>
          Send a test
        </button>
      </div>
    </section>
  );
}
