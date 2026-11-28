import { describe, expect, it } from "vitest";
import { DEFAULT_PREFS, dueReminders } from "./reminders";
import type { Meeting, Task } from "./types";

const on = { ...DEFAULT_PREFS, enabled: true };
const meeting = (start: string, extra: Partial<Meeting> = {}) => ({ id: "m1", title: "Design sync", start_at: start, end_at: start, all_day: false, effective_status: "attended", location: null, ...extra }) as unknown as Meeting;
const task = (extra: Partial<Task>) => ({ id: "t1", title: "Write ADR", status: "planned", scheduled_date: "2026-11-28", timebox_start: null, due_date: null, estimate_minutes: 60, ...extra }) as unknown as Task;
const base = { day: "2026-11-28", workStart: 480, meetings: [] as Meeting[], tasks: [] as Task[], dueToday: [] as Task[], fired: new Set<string>() };

describe("dueReminders", () => {
  it("is silent when turned off", () => {
    const now = new Date("2026-11-28T09:56:00Z");
    expect(dueReminders({ ...base, now, localMinutes: 596, meetings: [meeting("2026-11-28T10:00:00Z")], prefs: DEFAULT_PREFS })).toEqual([]);
  });

  it("warns before a meeting once, not when skipped, not when long past", () => {
    const m = meeting("2026-11-28T10:00:00Z");
    const at = (iso: string, fired = new Set<string>()) => dueReminders({ ...base, now: new Date(iso), localMinutes: 0, meetings: [m], prefs: on, fired });
    expect(at("2026-11-28T09:50:00Z")).toEqual([]); // too early
    const [r] = at("2026-11-28T09:56:00Z");
    expect(r!.title).toBe("Design sync in 4 min");
    expect(at("2026-11-28T09:56:00Z", new Set([r!.key]))).toEqual([]); // already sent
    expect(at("2026-11-28T10:30:00Z")).toEqual([]); // stale after waking up
    expect(dueReminders({ ...base, now: new Date("2026-11-28T09:56:00Z"), localMinutes: 0, meetings: [meeting("2026-11-28T10:00:00Z", { effective_status: "skipped" })], prefs: on })).toEqual([]);
  });

  it("starts timeboxes and summarises work due today at the start of the day", () => {
    const now = new Date("2026-11-28T08:31:00Z");
    const tasks = [task({ timebox_start: "08:30" }), task({ id: "t2", title: "Send deck", due_date: "2026-11-28" })];
    const out = dueReminders({ ...base, now, localMinutes: 8 * 60 + 31, tasks, prefs: on });
    expect(out.map((r) => r.title)).toEqual(["Time for “Write ADR”", "1 due today"]);
    expect(dueReminders({ ...base, now, localMinutes: 7 * 60, tasks, prefs: on })).toEqual([]); // before work
  });
});
