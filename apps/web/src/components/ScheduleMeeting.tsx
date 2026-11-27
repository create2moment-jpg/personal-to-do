import { useQueryClient } from "@tanstack/react-query";
import { CalendarPlus, Check, Clock, MapPin, Repeat, UserRound } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { api } from "../lib/api";
import { invalidateTime, usePeople, useTopics } from "../lib/queries";
import type { MeetingSeries, RecurrenceRule } from "../lib/types";
import type { ScheduleOptions } from "../lib/ui-store";
import { cx, formatMinutes, isoDay, parseDuration } from "../lib/util";
import { Dialog } from "./primitives";

type Repeat = "never" | "daily" | "weekdays" | "weekly" | "monthly";
type Ends = "never" | "on" | "after";
const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const QUICK = [15, 25, 30, 45, 60, 90];

/** Add a meeting yourself — once or recurring — or edit a series you created. */
export function ScheduleMeetingDialog({ open, options, onClose }: { open: boolean; options: ScheduleOptions; onClose: () => void }) {
  const series = options.series ?? null;
  return (
    <Dialog open={open} onClose={onClose} label={series ? "Edit recurring meeting" : "New meeting"} width={600}>
      {open && <Body series={series} initialDay={options.day} recurring={!!options.recurring} onClose={onClose} />}
    </Dialog>
  );
}

function repeatOf(r: RecurrenceRule | undefined): Repeat {
  if (!r) return "never";
  if (r.freq === "weekly" && r.interval === 1 && r.weekdays.join() === "0,1,2,3,4") return "weekdays";
  return r.freq;
}

function Body({ series, initialDay, recurring, onClose }: { series: MeetingSeries | null; initialDay?: string; recurring: boolean; onClose: () => void }) {
  const qc = useQueryClient();
  const { data: people = [] } = usePeople();
  const { data: topics = [] } = useTopics();
  const plan = series?.plan ?? null;
  const today = isoDay();
  const [title, setTitle] = useState(series?.title ?? "");
  const [kind, setKind] = useState<"meeting" | "call">(plan?.kind ?? "meeting");
  const [day, setDay] = useState(initialDay ?? today);
  const [time, setTime] = useState(plan?.start_time ?? "10:00");
  const [duration, setDuration] = useState(plan ? formatMinutes(plan.minutes) : "30m");
  const [who, setWho] = useState((plan?.people ?? []).join(", "));
  const [topic, setTopic] = useState(plan?.topic ?? "");
  const [location, setLocation] = useState(plan?.location ?? "");
  const [repeat, setRepeat] = useState<Repeat>(series ? repeatOf(plan?.recurrence) : recurring ? "weekly" : "never");
  const [interval, setInterval] = useState(plan?.recurrence.interval ?? 1);
  const [weekdays, setWeekdays] = useState<number[]>(plan?.recurrence.weekdays.length ? plan.recurrence.weekdays : [new Date().getDay() === 0 ? 6 : new Date().getDay() - 1]);
  const [ends, setEnds] = useState<Ends>(plan?.recurrence.until ? "on" : plan?.recurrence.count ? "after" : "never");
  const [until, setUntil] = useState(plan?.recurrence.until ?? "");
  const [count, setCount] = useState(plan?.recurrence.count ?? 10);
  const [saving, setSaving] = useState(false);
  const minutes = parseDuration(duration);

  const recurrence = (): RecurrenceRule | null => {
    if (repeat === "never") return null;
    const freq = repeat === "weekdays" ? "weekly" : repeat;
    return {
      freq,
      interval: repeat === "weekdays" ? 1 : Math.max(1, interval),
      weekdays: repeat === "weekdays" ? [0, 1, 2, 3, 4] : repeat === "weekly" ? weekdays : [],
      until: ends === "on" && until ? until : null,
      count: ends === "after" ? Math.max(1, count) : null,
    };
  };
  const summary = (() => {
    const r = recurrence();
    if (!r) return `Once · ${day === today ? "today" : day}`;
    const unit = { daily: "day", weekly: "week", monthly: "month" }[r.freq];
    let s = repeat === "weekdays" ? "Every weekday" : r.interval === 1 ? `Every ${unit}` : `Every ${r.interval} ${unit}s`;
    if (repeat === "weekly" && r.weekdays.length) s += ` on ${r.weekdays.map((d) => DAYS[d]).join(", ")}`;
    if (r.until) s += ` until ${r.until}`;
    if (r.count) s += `, ${r.count} times`;
    return s;
  })();

  const save = async () => {
    if (!title.trim()) return toast.error("Give the meeting a title");
    if (!minutes) return toast.error("Duration: use minutes or hours, e.g. 50, 1h20, 1.5h");
    if (repeat === "weekly" && weekdays.length === 0) return toast.error("Pick at least one weekday");
    const peopleList = who.split(",").map((p) => p.trim()).filter(Boolean);
    setSaving(true);
    try {
      if (series) {
        await api.editSeriesPlan(series.series_key, { title, start_time: time, minutes, people: peopleList, topic: topic || null, location: location || null, kind, recurrence: recurrence() ?? undefined });
        toast.success("Series updated", { description: "Future meetings changed; past ones kept as they were." });
      } else {
        const r = await api.scheduleMeeting({ title, day, start_time: time, minutes, people: peopleList, topic: topic || null, location: location || null, kind, recurrence: recurrence() });
        toast.success(r.series_key ? "Recurring meeting added 🔁" : "Meeting added 📅", { description: `${title} · ${r.cadence ?? day} · ${formatMinutes(minutes)} at ${time}` });
      }
      invalidateTime(qc);
      void qc.invalidateQueries({ queryKey: ["series"] });
      onClose();
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <form
      className="log-call schedule"
      onSubmit={(e) => {
        e.preventDefault();
        void save();
      }}
      onKeyDown={(e) => (e.metaKey || e.ctrlKey) && e.key === "Enter" && void save()}
    >
      <div className="lc-head">
        <CalendarPlus size={18} />
        <h3>{series ? "Edit recurring meeting" : "New meeting"}</h3>
        <div className="segmented" style={{ marginLeft: "auto" }}>
          {(["meeting", "call"] as const).map((k) => (
            <button type="button" key={k} aria-pressed={kind === k} onClick={() => setKind(k)}>
              {k === "meeting" ? "Meeting" : "Call"}
            </button>
          ))}
        </div>
      </div>

      <label className="lc-field">
        <span>Title</span>
        <input className="input" autoFocus value={title} placeholder="e.g. Team stand-up, 1:1 with Priya, Sprint planning" onChange={(e) => setTitle(e.target.value)} />
      </label>

      <div className="lc-row">
        {!series && (
          <label className="lc-field">
            <span>{repeat === "never" ? "Day" : "Starts"}</span>
            <input className="input" type="date" value={day} onChange={(e) => setDay(e.target.value)} />
          </label>
        )}
        <label className="lc-field">
          <span>
            <Clock size={14} /> Start
          </span>
          <input className="input" type="time" value={time} onChange={(e) => setTime(e.target.value)} />
        </label>
        <label className="lc-field">
          <span>Duration</span>
          <input className={cx("input", !minutes && duration && "invalid")} value={duration} onChange={(e) => setDuration(e.target.value)} placeholder="e.g. 50, 1h20" aria-label="Duration" />
        </label>
      </div>
      <div className="lc-quick">
        {QUICK.map((m) => (
          <button type="button" key={m} className="filter-chip" aria-pressed={minutes === m} onClick={() => setDuration(formatMinutes(m))}>
            {formatMinutes(m)}
          </button>
        ))}
        {minutes && !QUICK.includes(minutes) && <span className="chip accent">{formatMinutes(minutes)}</span>}
      </div>

      <div className="lc-field">
        <span>
          <Repeat size={14} /> Repeat
        </span>
        <div className="segmented" role="group" aria-label="Repeat">
          {(["never", "daily", "weekdays", "weekly", "monthly"] as Repeat[]).map((r) => (
            <button type="button" key={r} aria-pressed={repeat === r} onClick={() => setRepeat(r)} disabled={!!series && r === "never"}>
              {{ never: "Once", daily: "Daily", weekdays: "Weekdays", weekly: "Weekly", monthly: "Monthly" }[r]}
            </button>
          ))}
        </div>
      </div>
      {repeat !== "never" && (
        <div className="repeat-box">
          {repeat !== "weekdays" && (
            <label className="inline-field">
              Every
              <input className="input" type="number" min={1} max={52} value={interval} onChange={(e) => setInterval(Number(e.target.value) || 1)} aria-label="Repeat interval" />
              {{ daily: "day(s)", weekly: "week(s)", monthly: "month(s)" }[repeat as "daily" | "weekly" | "monthly"]}
            </label>
          )}
          {repeat === "weekly" && (
            <div className="weekday-picker" role="group" aria-label="Weekdays">
              {DAYS.map((d, i) => (
                <button type="button" key={d} aria-pressed={weekdays.includes(i)} onClick={() => setWeekdays(weekdays.includes(i) ? weekdays.filter((x) => x !== i) : [...weekdays, i].sort())}>
                  {d.slice(0, 2)}
                </button>
              ))}
            </div>
          )}
          <div className="inline-field">
            Ends
            <select className="select" value={ends} onChange={(e) => setEnds(e.target.value as Ends)} aria-label="Ends">
              <option value="never">never</option>
              <option value="on">on a date</option>
              <option value="after">after a number of times</option>
            </select>
            {ends === "on" && <input className="input" type="date" value={until} min={day} onChange={(e) => setUntil(e.target.value)} aria-label="End date" />}
            {ends === "after" && (
              <>
                <input className="input" type="number" min={1} max={1000} value={count} onChange={(e) => setCount(Number(e.target.value) || 1)} aria-label="Number of times" />
                times
              </>
            )}
          </div>
        </div>
      )}

      <div className="lc-row">
        <label className="lc-field">
          <span>
            <UserRound size={14} /> With
          </span>
          <input className="input" list="schedule-people" value={who} placeholder="Names, comma separated" onChange={(e) => setWho(e.target.value)} />
          <datalist id="schedule-people">
            {people.map((p) => (
              <option key={p.id} value={p.name} />
            ))}
          </datalist>
        </label>
        <label className="lc-field">
          <span>Topic</span>
          <input className="input" list="schedule-topics" value={topic} placeholder="e.g. Retrieval" onChange={(e) => setTopic(e.target.value)} />
          <datalist id="schedule-topics">
            {topics.map((t) => (
              <option key={t.id} value={t.name} />
            ))}
          </datalist>
        </label>
      </div>
      <label className="lc-field">
        <span>
          <MapPin size={14} /> Where
        </span>
        <input className="input" value={location} placeholder="Room, Teams link … (optional)" onChange={(e) => setLocation(e.target.value)} />
      </label>

      <div className="lc-foot">
        <span className="schedule-summary">
          {summary} · {minutes ? formatMinutes(minutes) : "?"} at {time}
        </span>
        <button type="button" className="btn ghost" onClick={onClose}>
          Cancel
        </button>
        <button type="submit" className="btn primary" disabled={saving}>
          <Check /> {series ? "Save changes" : "Add meeting"}
        </button>
      </div>
    </form>
  );
}
