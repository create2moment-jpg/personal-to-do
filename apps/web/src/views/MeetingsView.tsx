import { useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { BarChart3, CalendarClock, CalendarPlus, Pencil, ChevronLeft, ChevronRight, FileUp, ListChecks, Phone, Repeat, ShieldCheck, ThumbsDown, Upload } from "lucide-react";
import { useRef, useState } from "react";
import { toast } from "sonner";
import { DayTimeChart, RankBars } from "../components/charts";
import { MeetingRow, Stars } from "../components/meetings";
import { EmptyState } from "../components/primitives";
import { api } from "../lib/api";
import { invalidateTime, useInsights, useMeetings, useSeries } from "../lib/queries";
import type { Meeting, MeetingSeries } from "../lib/types";
import { useUi } from "../lib/ui-store";
import { addDays, clockTime, cx, formatMinutes, isoDay, mondayOf, relativeDay, relativeTime } from "../lib/util";
import { Kpi } from "./WeekView";

type Tab = "insights" | "recurring" | "log";

export function MeetingsView() {
  const ui = useUi();
  const [tab, setTab] = useState<Tab>("insights");
  const edit = (series: MeetingSeries | null) => ui.openScheduleMeeting(series ? { series } : {});
  return (
    <div className="page">
      <header className="page-head">
        <div>
          <h1 className="page-title">Meetings & time</h1>
          <div className="page-sub">Where your hours go — and whether they were worth it.</div>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <ImportButton />
          <button className="btn" onClick={() => ui.openLogCall()}>
            <Phone /> Log a call
          </button>
          <button className="btn primary" onClick={() => edit(null)}>
            <CalendarPlus /> New meeting
          </button>
        </div>
      </header>
      <div className="tabs" role="tablist">
        <button role="tab" aria-selected={tab === "insights"} onClick={() => setTab("insights")}>
          <BarChart3 /> Insights
        </button>
        <button role="tab" aria-selected={tab === "recurring"} onClick={() => setTab("recurring")}>
          <Repeat /> Recurring
        </button>
        <button role="tab" aria-selected={tab === "log"} onClick={() => setTab("log")}>
          <ListChecks /> Meetings & calls
        </button>
      </div>
      {tab === "insights" && <Insights />}
      {tab === "recurring" && <Recurring onEdit={edit} />}
      {tab === "log" && <MeetingLog />}
    </div>
  );
}

function Insights() {
  const [days, setDays] = useState(7);
  const { data: r } = useInsights(days);
  if (!r) return <div className="faint">Loading…</div>;
  const share = r.work_minutes ? Math.round((Math.min(r.meeting_minutes, r.work_minutes) / r.work_minutes) * 100) : 0;
  const empty = r.meetings_count + r.calls_count === 0;
  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <span className="faint" style={{ fontSize: "0.9286rem" }}>
          {relativeDay(r.start)} – {relativeDay(r.end)}
        </span>
        <div className="segmented" role="group" aria-label="Range">
          {[7, 14, 30].map((d) => (
            <button key={d} aria-pressed={days === d} onClick={() => setDays(d)}>
              {d} days
            </button>
          ))}
        </div>
      </div>
      {empty ? (
        <EmptyState icon={CalendarClock} title="No meeting time yet">
          Import your Outlook calendar for recurring meetings, and log calls as they happen — press <kbd className="kbd">C</kbd> and type <code>call: Priya / ADR review ~30m</code>.
        </EmptyState>
      ) : (
        <>
          <div className="kpis">
            <Kpi label="In meetings" value={formatMinutes(r.meeting_minutes)} sub={`${share}% of working hours`} warn={share > 50} />
            <Kpi label="Free for focus" value={formatMinutes(r.available_minutes)} sub={`of ${formatMinutes(r.work_minutes)} working`} />
            <Kpi label="Meetings / calls" value={`${r.meetings_count} / ${r.calls_count}`} />
            <Kpi label="Average value" value={r.avg_rating ? `${r.avg_rating.toFixed(1)} ★` : "—"} sub={r.rated_minutes ? `${formatMinutes(r.rated_minutes)} rated` : "rate meetings after they end"} />
          </div>
          <section className="card panel" style={{ marginBottom: 14 }}>
            <h3>Meetings vs. focus per day</h3>
            <DayTimeChart days={r.days} />
          </section>
          <div className="grid-2">
            <section className="card panel">
              <h3>Time with people</h3>
              <RankBars items={r.by_person} empty="Log calls with people to see who you spend time with." />
            </section>
            <section className="card panel">
              <h3>Time by topic</h3>
              <RankBars items={r.by_topic} empty="Add topics to calls and recurring meetings." />
            </section>
            <section className="card panel">
              <h3>Recurring meetings</h3>
              <RankBars items={r.by_series.map((s) => ({ name: s.title, minutes: s.minutes, count: s.count }))} empty="Import your calendar to see recurring meetings." />
            </section>
            <section className="card panel">
              <h3>
                <ThumbsDown size={16} /> Worth reconsidering
              </h3>
              {r.reconsider.length === 0 ? (
                <div className="faint" style={{ fontSize: "0.9286rem" }}>
                  Nothing flagged. Recurring meetings rated 1–2★ that cost over an hour show up here.
                </div>
              ) : (
                <ul className="priority-list">
                  {r.reconsider.map((x) => (
                    <li key={x.series_key}>
                      <span className="p-num" style={{ background: "color-mix(in srgb, var(--orange) 14%, transparent)", color: "var(--orange)" }}>
                        !
                      </span>
                      <span className="p-title">
                        <strong>{x.title}</strong> — {formatMinutes(x.minutes)}, rated {x.rating}★. {x.suggestion}.
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </div>
        </>
      )}
    </div>
  );
}

function Recurring({ onEdit }: { onEdit: (s: MeetingSeries | null) => void }) {
  const ui = useUi();
  const { data: series = [], isLoading } = useSeries();
  const { data: last } = useQuery({ queryKey: ["series", "last-import"], queryFn: api.lastImport });
  if (isLoading) return <div className="faint">Loading…</div>;
  if (series.length === 0)
    return (
      <>
        <AddYourOwn />
        <details className="import-optional">
          <summary>Optional: import recurring meetings from an Outlook calendar file</summary>
          <ImportPanel />
        </details>
      </>
    );
  const totalMonth = series.filter((s) => s.default_status === "attending").reduce((a, s) => a + s.minutes_per_month, 0);
  return (
    <div>
      <div className="kpis">
        <Kpi label="Recurring meetings" value={String(series.length)} sub={`${series.filter((s) => s.default_status === "skipped").length} not attending`} />
        <Kpi label="Cost per month" value={formatMinutes(totalMonth)} sub="attended recurring time" warn={totalMonth > 40 * 60} />
        <Kpi label="Calendar imported" value={last ? relativeTime(last.imported_at) : "—"} sub={last ? `${last.filename}` : undefined} />
      </div>
      <div className="series-toolbar">
        <button className="btn primary" onClick={() => ui.openScheduleMeeting({ recurring: true })}>
          <Repeat /> Add recurring meeting
        </button>
        <button className="btn" onClick={() => ui.openScheduleMeeting()}>
          <CalendarPlus /> One-time meeting
        </button>
      </div>
      <section className="card" style={{ overflow: "hidden" }}>
        {series.map((s) => (
          <SeriesRow key={s.series_key} s={s} onEdit={() => onEdit(s)} />
        ))}
      </section>
      <p className="faint" style={{ fontSize: "0.8929rem", marginTop: 10 }}>
        Marking a series as “Not attending” removes all its occurrences from your capacity and time totals. Single occurrences can still be overridden on Today or in Meetings & calls.
      </p>
    </div>
  );
}

function SeriesRow({ s, onEdit }: { s: MeetingSeries; onEdit: () => void }) {
  const qc = useQueryClient();
  const [topic, setTopic] = useState(s.topic ?? "");
  const update = (changes: Parameters<typeof api.updateSeries>[1]) =>
    api.updateSeries(s.series_key, changes).then(() => invalidateTime(qc)).catch((e: Error) => toast.error(e.message));
  const skipped = s.default_status === "skipped";
  return (
    <div className={cx("series-row", skipped && "skipped")}>
      <div style={{ minWidth: 0 }}>
        <div className="sr-title">
          {s.title}
          {s.source === "app" && (
            <span className="sr-own">
              <button className="link-btn" onClick={onEdit} aria-label={`Edit ${s.title}`}>
                <Pencil size={12} /> Edit
              </button>
              <button
                className="link-btn"
                aria-label={`End ${s.title}`}
                onClick={async () => {
                  if (!confirm(`End “${s.title}”? Future meetings are removed; past ones stay in your history.`)) return;
                  const r = await api.endSeries(s.series_key);
                  invalidateTime(qc);
                  toast.success("Series ended", { description: `${r.removed} upcoming meeting(s) removed` });
                }}
              >
                End
              </button>
            </span>
          )}
        </div>
        <div className="sr-sub">
          {s.cadence ?? "Recurring"} · {formatMinutes(s.avg_minutes)}
          {s.next_start && ` · next ${relativeDay(isoDay(new Date(s.next_start)))} ${clockTime(s.next_start)}`}
        </div>
      </div>
      <input
        className="input"
        style={{ height: 28 }}
        value={topic}
        placeholder="Topic"
        aria-label={`Topic for ${s.title}`}
        onChange={(e) => setTopic(e.target.value)}
        onBlur={() => topic !== (s.topic ?? "") && void update({ topic: topic || null })}
      />
      <div className="sr-cost">
        {skipped ? "0m" : formatMinutes(s.minutes_per_month)}
        <small>per month</small>
      </div>
      <Stars value={s.rating} onChange={(v) => void update({ rating: v })} />
      <div className="segmented mini" role="group" aria-label={`Attendance for ${s.title}`}>
        <button aria-pressed={!skipped} onClick={() => void update({ default_status: "attending" })}>
          Attending
        </button>
        <button aria-pressed={skipped} onClick={() => void update({ default_status: "skipped" })}>
          Not attending
        </button>
      </div>
    </div>
  );
}

function MeetingLog() {
  const ui = useUi();
  const [monday, setMonday] = useState(mondayOf(isoDay()));
  const { data: meetings = [] } = useMeetings(monday, addDays(monday, 6));
  const byDay = new Map<string, Meeting[]>();
  for (const m of meetings) {
    const d = isoDay(new Date(m.start_at));
    byDay.set(d, [...(byDay.get(d) ?? []), m]);
  }
  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 10 }}>
        <button className="btn icon sm ghost" aria-label="Previous week" onClick={() => setMonday(addDays(monday, -7))}>
          <ChevronLeft />
        </button>
        <strong>
          Week of {new Date(`${monday}T12:00:00Z`).toLocaleDateString(undefined, { month: "long", day: "numeric", timeZone: "UTC" })}
        </strong>
        <button className="btn icon sm ghost" aria-label="Next week" onClick={() => setMonday(addDays(monday, 7))}>
          <ChevronRight />
        </button>
        <button className="btn sm" style={{ marginLeft: "auto" }} onClick={() => ui.openScheduleMeeting()}>
          <CalendarPlus /> Add meeting
        </button>
      </div>
      {meetings.length === 0 && (
        <EmptyState icon={CalendarClock} title="No meetings or calls this week">
          <button className="btn primary" style={{ marginTop: 10 }} onClick={() => ui.openScheduleMeeting({ day: monday < isoDay() && addDays(monday, 6) >= isoDay() ? isoDay() : monday })}>
            <CalendarPlus /> Add a meeting
          </button>
        </EmptyState>
      )}
      {[...byDay.entries()].map(([d, ms]) => (
        <section key={d} style={{ marginBottom: 14 }}>
          <div className="group-head" style={{ marginTop: 8 }}>
            <h3>{relativeDay(d)}</h3>
            <span className="faint">{formatMinutes(ms.reduce((a, m) => a + m.counted_minutes, 0))} attended</span>
          </div>
          <div className="meeting-list">
            {ms.map((m) => (
              <motion.div key={m.id} layout>
                <MeetingRow m={m} />
              </motion.div>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

export function useIcsImport() {
  const qc = useQueryClient();
  return async (file: File) => {
    if (!file.name.toLowerCase().endsWith(".ics")) {
      toast.error("Choose an .ics calendar file");
      return;
    }
    try {
      const content = await file.text();
      const r = await api.importCalendar(file.name, content);
      invalidateTime(qc);
      toast.success(`Imported ${r.events} meetings`, { description: `${r.series} recurring series · ${r.created} new · ${r.cancelled} removed` });
    } catch (e) {
      toast.error((e as Error).message);
    }
  };
}

function ImportButton() {
  const ref = useRef<HTMLInputElement>(null);
  const doImport = useIcsImport();
  return (
    <>
      <input ref={ref} type="file" accept=".ics,text/calendar" hidden onChange={(e) => e.target.files?.[0] && void doImport(e.target.files[0]).then(() => { if (ref.current) ref.current.value = ""; })} />
      <button className="btn" onClick={() => ref.current?.click()}>
        <Upload /> Import calendar
      </button>
    </>
  );
}

/** The main way in: add meetings yourself; calendar import is optional. */
function AddYourOwn() {
  const ui = useUi();
  return (
    <section className="card add-own">
      <h3>
        <CalendarPlus size={16} /> Add your meetings
      </h3>
      <p>Stand-ups, 1:1s, planning, reviews — add them once or as a recurring series with their real duration. They count against your capacity and show up in Today, Week and your time insights.</p>
      <div className="add-own-actions">
        <button className="btn primary" onClick={() => ui.openScheduleMeeting({ recurring: true })}>
          <Repeat /> Add recurring meeting
        </button>
        <button className="btn" onClick={() => ui.openScheduleMeeting()}>
          <CalendarPlus /> Add one-time meeting
        </button>
        <button className="btn ghost" onClick={() => ui.openLogCall()}>
          <Phone /> Log a call that already happened
        </button>
      </div>
    </section>
  );
}

export function ImportPanel() {
  const ref = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  const doImport = useIcsImport();
  return (
    <section className="card panel" style={{ maxWidth: 760 }}>
      <h3>
        <FileUp size={16} /> Import your Outlook calendar
      </h3>
      <div
        className={cx("dropzone", over && "over")}
        onClick={() => ref.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setOver(false);
          const f = e.dataTransfer.files[0];
          if (f) void doImport(f);
        }}
      >
        <Upload size={22} />
        <div style={{ fontWeight: 600, marginTop: 6 }}>Drop an .ics file here, or click to choose</div>
        <div className="faint" style={{ fontSize: "0.8929rem", marginTop: 4 }}>
          Recurring meetings are expanded 30 days back and 4 months ahead. Re-import any time — your choices are kept.
        </div>
      </div>
      <input ref={ref} type="file" accept=".ics,text/calendar" hidden onChange={(e) => e.target.files?.[0] && void doImport(e.target.files[0])} />
      <div className="grid-2" style={{ marginTop: 14, fontSize: "0.9286rem", color: "var(--text-2)" }}>
        <div>
          <strong style={{ color: "var(--text)" }}>Outlook for Windows</strong>
          <ol style={{ margin: "6px 0 0", paddingLeft: 18 }}>
            <li>Open the Calendar, then File → Save Calendar.</li>
            <li>More Options → choose a date range (e.g. next 3 months), detail “Availability only” or “Limited details”.</li>
            <li>Save the .ics file and drop it here.</li>
          </ol>
        </div>
        <div>
          <strong style={{ color: "var(--text)" }}>Outlook on the web / Mac</strong>
          <ol style={{ margin: "6px 0 0", paddingLeft: 18 }}>
            <li>Web: Settings → Calendar → Shared calendars → Publish a calendar → ICS link → open it to download.</li>
            <li>Mac: File → Export, or drag the calendar to the desktop.</li>
          </ol>
        </div>
      </div>
      <p className="faint" style={{ fontSize: "0.8571rem", marginTop: 12, display: "flex", gap: 6, alignItems: "center" }}>
        <ShieldCheck size={13} /> Read-only. Nothing is ever written back to Outlook, and attendee lists are not imported.
      </p>
    </section>
  );
}
