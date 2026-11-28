import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { ArrowRight, CalendarPlus, ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight, Pause, Phone, Play, RotateCcw, Search, Settings2, Sparkles, Square, Star, Timer, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { api } from "../lib/api";
import { GADGETS, type GadgetId, useGadgetPrefs } from "../lib/gadgets";
import { useSettings, useToday } from "../lib/queries";
import type { ViewId } from "../lib/ui-store";
import { useUi } from "../lib/ui-store";
import { addDays, clockTime, cx, formatMinutes, getWorkspaceTimeZone, isoDay } from "../lib/util";

const CALL_KEY = "ppos.callStartedAt";

/** Minutes since midnight in the workspace time zone. */
const nowMinutes = (d: Date) => {
  const [h, m] = clockTime(d).split(":").map(Number);
  return h! * 60 + m!;
};
const toMin = (hhmm: string) => {
  const [h, m] = hhmm.split(":").map(Number);
  return h! * 60 + m!;
};

const NARROW = "(max-width: 1440px)";

/** True on laptop-width screens, where the expanded dock is a drawer over the page. */
function useNarrow() {
  const [narrow, setNarrow] = useState(() => window.matchMedia?.(NARROW).matches ?? false);
  useEffect(() => {
    const mq = window.matchMedia?.(NARROW);
    if (!mq) return;
    const on = () => setNarrow(mq.matches);
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);
  return narrow;
}

function useNow(ms = 10_000) {
  const [now, setNow] = useState(new Date());
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), ms);
    return () => clearInterval(t);
  }, [ms]);
  return now;
}

/**
 * The gadget dock: clock, today's meetings, calendar, up next, priorities, calls,
 * focus timer and assistant — on every page. Collapses to a slim strip; which
 * gadgets show and their order are set in Settings → Gadgets.
 */
export function RightRail({ view }: { view: ViewId }) {
  const ui = useUi();
  const { prefs, save, isCollapsed } = useGadgetPrefs();
  const narrow = useNarrow();
  const [drawer, setDrawer] = useState(false); // laptop width: a temporary drawer, never remembered
  useEffect(() => setDrawer(false), [view]);
  useEffect(() => {
    if (!drawer) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setDrawer(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [drawer]);
  const collapsed = narrow ? !drawer : isCollapsed(view);
  const now = useNow();
  const [inCall, setInCall] = useState(false);
  useEffect(() => {
    const check = () => {
      try {
        setInCall(!!localStorage.getItem(CALL_KEY));
      } catch {
        setInCall(false);
      }
    };
    check();
    const t = setInterval(check, 2000);
    return () => clearInterval(t);
  }, []);
  const setCollapsed = (v: boolean) => (narrow ? setDrawer(!v) : save({ ...prefs, collapsed: { ...prefs.collapsed, [view]: v } }));
  const visible = prefs.order.filter((g) => !prefs.hidden.includes(g));

  if (collapsed) {
    return (
      <aside className="rail slim" aria-label="Gadgets (collapsed)">
        <button className="slim-clock" title="Show gadgets" onClick={() => setCollapsed(false)}>
          {clockTime(now)}
        </button>
        {visible.map((g) => {
          const G = GADGETS[g];
          return (
            <button key={g} className={cx("btn icon ghost slim-btn", g === "calls" && inCall && "live")} aria-label={`Show ${G.label}`} title={G.label} onClick={() => setCollapsed(false)}>
              <G.icon />
            </button>
          );
        })}
        <button className="btn icon ghost slim-btn" style={{ marginTop: "auto" }} aria-label="Expand gadgets" title="Expand gadgets" onClick={() => setCollapsed(false)}>
          <ChevronsLeft />
        </button>
      </aside>
    );
  }
  const render: Record<GadgetId, () => JSX.Element | null> = {
    clock: () => <ClockGadget now={now} />,
    agenda: () => <AgendaGadget now={now} />,
    calendar: () => <CalendarGadget />,
    upnext: () => <UpNextGadget />,
    priorities: () => <PrioritiesGadget />,
    calls: () => (
      <>
        <CallTimer />
        <RecentCalls />
      </>
    ),
    focus: () => <FocusTimer />,
    assistant: () => <AssistantGadget />,
  };
  return (
    <aside className="rail" aria-label="Gadgets">
      <div className="rail-head">
        <span className="section-label">Gadgets</span>
        <button className="btn icon sm ghost" aria-label="Choose gadgets" title="Choose gadgets" onClick={() => ui.navigate("settings", "gadgets")}>
          <Settings2 />
        </button>
        <button className="btn icon sm ghost" aria-label="Collapse gadgets" title="Collapse to a slim strip" onClick={() => setCollapsed(true)}>
          <ChevronsRight />
        </button>
      </div>
      {visible.map((g) => (
        <div key={g} className="gadget" data-gadget={g}>
          {render[g]()}
        </div>
      ))}
      {visible.length === 0 && <div className="faint" style={{ fontSize: "0.86rem" }}>All gadgets are hidden — choose some in Settings → Gadgets.</div>}
    </aside>
  );
}

function ClockGadget({ now }: { now: Date }) {
  const { data: settings } = useSettings();
  const start = toMin(settings?.work_start ?? "08:00");
  const end = toMin(settings?.work_end ?? "17:00");
  const m = nowMinutes(now);
  const progress = Math.max(0, Math.min(1, (m - start) / Math.max(1, end - start)));
  const left = end - m;
  return (
    <div className="rail-card">
      <div className="clock-time">{clockTime(now)}</div>
      <div className="clock-date">{now.toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric", timeZone: getWorkspaceTimeZone() })}</div>
      <div className="day-progress" title={`Working hours ${settings?.work_start ?? "08:00"}–${settings?.work_end ?? "17:00"}`}>
        <motion.div initial={{ width: 0 }} animate={{ width: `${progress * 100}%` }} transition={{ duration: 0.8 }} />
      </div>
      <div className="faint clock-left">{m < start ? `Workday starts at ${settings?.work_start ?? "08:00"}` : left > 0 ? `${formatMinutes(left)} of the workday left` : "Workday done"}</div>
    </div>
  );
}

function AgendaGadget({ now }: { now: Date }) {
  const ui = useUi();
  const { data: today } = useToday(isoDay());
  const meetings = useMemo(
    () => (today?.meetings ?? []).filter((m) => !m.all_day && m.effective_status !== "skipped").sort((a, b) => a.start_at.localeCompare(b.start_at)),
    [today],
  );
  const t = now.getTime();
  const current = meetings.find((m) => new Date(m.start_at).getTime() <= t && new Date(m.end_at).getTime() > t);
  const next = meetings.find((m) => new Date(m.start_at).getTime() > t);
  const later = meetings.filter((m) => new Date(m.start_at).getTime() > t && m !== next).slice(0, 4);
  const mins = (iso: string) => Math.round((new Date(iso).getTime() - t) / 60000);
  return (
    <div className="rail-card">
      <div className="section-label">
        <CalendarPlus /> Today’s meetings
        <button className="btn icon sm ghost" style={{ marginLeft: "auto" }} aria-label="Schedule a meeting from the dock" title="Add meeting" onClick={() => ui.openScheduleMeeting({ day: isoDay() })}>
          <CalendarPlus />
        </button>
      </div>
      {current && (
        <div className="agenda-now">
          <span className="chip accent">Now</span> <strong>{current.title}</strong>
          <div className="faint">ends {clockTime(current.end_at)} · {formatMinutes(Math.max(0, mins(current.end_at)))} left</div>
        </div>
      )}
      {next ? (
        <div className="agenda-next">
          <div>
            <span className="faint">Next</span> <strong>{next.title}</strong>
          </div>
          <div className="faint">
            {clockTime(next.start_at)} · in {formatMinutes(Math.max(1, mins(next.start_at)))}
            {next.location ? ` · ${next.location}` : ""}
          </div>
        </div>
      ) : (
        !current && <div className="faint" style={{ fontSize: "0.86rem" }}>{meetings.length ? "No more meetings today." : "No meetings today."}</div>
      )}
      {later.length > 0 && (
        <ul className="agenda-list">
          {later.map((m) => (
            <li key={m.id}>
              <span className="mono">{clockTime(m.start_at)}</span> {m.title}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

const WEEKDAYS = ["M", "T", "W", "T", "F", "S", "S"];

function CalendarGadget() {
  const ui = useUi();
  const today = isoDay();
  const [month, setMonth] = useState(today.slice(0, 7));
  const { data: marks = [] } = useQuery({ queryKey: ["calendar", month], queryFn: () => api.calendarMonth(month), staleTime: 60_000 });
  const byDay = useMemo(() => new Map(marks.map((m) => [m.day, m])), [marks]);
  const [y, mo] = month.split("-").map(Number) as [number, number];
  const first = `${month}-01`;
  const lead = (new Date(Date.UTC(y, mo - 1, 1)).getUTCDay() + 6) % 7;
  const days = new Date(Date.UTC(y, mo, 0)).getUTCDate();
  const cells: (string | null)[] = [...Array(lead).fill(null), ...Array.from({ length: days }, (_, i) => addDays(first, i))];
  const shift = (n: number) => {
    const d = new Date(Date.UTC(y, mo - 1 + n, 1));
    setMonth(d.toISOString().slice(0, 7));
  };
  const label = new Date(Date.UTC(y, mo - 1, 1)).toLocaleDateString(undefined, { month: "long", year: "numeric", timeZone: "UTC" });
  return (
    <div className="rail-card cal-card">
      <div className="cal-head">
        <button className="btn icon sm ghost" aria-label="Previous month" onClick={() => shift(-1)}>
          <ChevronLeft />
        </button>
        <button className="cal-title" onClick={() => setMonth(today.slice(0, 7))} title="Back to this month">
          {label}
        </button>
        <button className="btn icon sm ghost" aria-label="Next month" onClick={() => shift(1)}>
          <ChevronRight />
        </button>
      </div>
      <div className="cal-grid" role="grid" aria-label={label}>
        {WEEKDAYS.map((w, i) => (
          <span key={i} className="cal-dow">
            {w}
          </span>
        ))}
        {cells.map((d, i) => {
          if (!d) return <span key={`e${i}`} />;
          const mk = byDay.get(d);
          const parts = mk ? [mk.meetings && `${mk.meetings} meeting(s)`, mk.planned && `${mk.planned} planned`, mk.due && `${mk.due} due`, mk.done && `${mk.done} done`].filter(Boolean) : [];
          return (
            <button key={d} className={cx("cal-day", d === today && "today", d < today && "past")} title={`${d}${parts.length ? ` · ${parts.join(", ")}` : ""}`} aria-label={`${d}${parts.length ? `: ${parts.join(", ")}` : ""}`} onClick={() => ui.navigate("today", d)}>
              <span>{Number(d.slice(8))}</span>
              {mk && (
                <i className="cal-dots" aria-hidden>
                  {mk.meetings > 0 && <b className="m" />}
                  {mk.planned > 0 && <b className="p" />}
                  {mk.due > 0 && <b className="d" />}
                </i>
              )}
            </button>
          );
        })}
      </div>
      <div className="cal-legend faint">
        <b className="m" /> meetings <b className="p" /> planned <b className="d" /> due
      </div>
    </div>
  );
}

function UpNextGadget() {
  const ui = useUi();
  const { data: today } = useToday(isoDay());
  const next =
    today?.tasks.find((t) => t.status === "in_progress" && t.parent_id === null) ??
    today?.tasks.find((t) => t.status === "planned" && t.parent_id === null && today.plan.top_priority_ids.includes(t.id)) ??
    today?.tasks.find((t) => t.status === "planned" && t.parent_id === null);
  return (
    <div className="rail-card">
      <div className="section-label">
        <ArrowRight /> Up next
      </div>
      {next ? (
        <>
          <button className="btn ghost block" style={{ justifyContent: "flex-start", height: "auto", padding: "4px 0", whiteSpace: "normal", textAlign: "left", color: "var(--text)" }} onClick={() => ui.openTask(next.id)}>
            {next.title}
          </button>
          <div className="faint" style={{ fontSize: "0.8571rem" }}>
            {next.timebox_start ? `at ${next.timebox_start} · ` : ""}
            {next.estimate_minutes !== null ? `${formatMinutes(next.estimate_minutes)} estimated` : ""}
          </div>
        </>
      ) : (
        <div className="faint" style={{ fontSize: "0.86rem" }}>Nothing planned for today.</div>
      )}
    </div>
  );
}

function PrioritiesGadget() {
  const ui = useUi();
  const { data: today } = useToday(isoDay());
  const top = today ? today.plan.top_priority_ids.map((id) => today.tasks.find((t) => t.id === id)).filter((t) => t !== undefined) : [];
  return (
    <div className="rail-card">
      <div className="section-label">
        <Star /> Top priorities
      </div>
      {top.length === 0 ? (
        <div className="faint" style={{ fontSize: "0.8929rem" }}>
          Star up to three tasks on Today to keep them in view.
        </div>
      ) : (
        <ol className="priority-list">
          {top.map((t, i) => (
            <li key={t.id} className={cx(t.status === "done" && "done")} onClick={() => ui.openTask(t.id)}>
              <span className="p-num">{t.status === "done" ? "✓" : i + 1}</span>
              <span className="p-title">{t.title}</span>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

function RecentCalls() {
  const ui = useUi();
  const today = isoDay();
  const { data: meetings = [] } = useQuery({ queryKey: ["meetings", addDays(today, -13), today], queryFn: () => api.meetings(addDays(today, -13), today), staleTime: 60_000 });
  const calls = meetings.filter((m) => m.kind === "call").sort((a, b) => b.start_at.localeCompare(a.start_at)).slice(0, 4);
  if (calls.length === 0) return null;
  return (
    <div className="rail-card">
      <div className="section-label">
        <Phone /> Recent calls
        <button className="link-btn" style={{ marginLeft: "auto", fontSize: "0.8rem" }} onClick={() => ui.navigate("meetings")}>
          All
        </button>
      </div>
      <ul className="agenda-list">
        {calls.map((c) => (
          <li key={c.id} title={c.note || undefined}>
            <span className="mono">{new Date(c.start_at).toLocaleDateString(undefined, { weekday: "short", timeZone: getWorkspaceTimeZone() })}</span> {c.title}
            <span className="faint"> · {formatMinutes(c.duration_minutes)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function AssistantGadget() {
  const ui = useUi();
  const { data: st } = useQuery({ queryKey: ["ai-status"], queryFn: api.aiStatus, staleTime: 60_000 });
  const [q, setQ] = useState("");
  const on = !!st?.enabled;
  return (
    <div className="rail-card ai-card">
      <div className="section-label">
        <Sparkles /> Assistant <span className={cx("chip", on ? "green" : "")} style={{ marginLeft: "auto", height: "1.1rem", fontSize: "0.7rem" }}>{on ? "local AI on" : "AI off"}</span>
      </div>
      <form
        className="ask-mini"
        onSubmit={(e) => {
          e.preventDefault();
          if (q.trim().length >= 3) ui.navigate("ai", q.trim());
          setQ("");
        }}
      >
        <Search size={14} />
        <input className="input" value={q} onChange={(e) => setQ(e.target.value)} placeholder={on ? "Ask about your work…" : "Search your records…"} aria-label="Ask the assistant" />
      </form>
    </div>
  );
}

function FocusTimer() {
  const [length, setLength] = useState(25);
  const [endsAt, setEndsAt] = useState<number | null>(null);
  const [pausedLeft, setPausedLeft] = useState<number | null>(null);
  const [, tick] = useState(0);

  useEffect(() => {
    if (endsAt === null) return;
    const t = setInterval(() => {
      tick((x) => x + 1);
      if (Date.now() >= endsAt) {
        setEndsAt(null);
        toast.success("Focus block complete", { description: "Take a short break." });
        try {
          if (Notification.permission === "granted") new Notification("Focus block complete");
        } catch {
          /* notifications unavailable */
        }
      }
    }, 500);
    return () => clearInterval(t);
  }, [endsAt]);

  const total = length * 60;
  const left = endsAt ? Math.max(0, Math.round((endsAt - Date.now()) / 1000)) : (pausedLeft ?? total);
  const mm = String(Math.floor(left / 60)).padStart(2, "0");
  const ss = String(left % 60).padStart(2, "0");
  const running = endsAt !== null;

  return (
    <div className="rail-card">
      <div className="section-label">
        <Timer /> Focus
      </div>
      <div className="timer-row">
        <div className="timer-face" style={{ color: running ? "var(--accent-text)" : undefined }}>
          {mm}:{ss}
        </div>
        <div style={{ display: "flex", gap: 4 }}>
          <button
            className="btn icon primary"
            aria-label={running ? "Pause" : "Start"}
            onClick={() => {
              if (running) {
                setPausedLeft(left);
                setEndsAt(null);
              } else {
                if ("Notification" in window && Notification.permission === "default") void Notification.requestPermission();
                setEndsAt(Date.now() + (pausedLeft ?? total) * 1000);
                setPausedLeft(null);
              }
            }}
          >
            {running ? <Pause /> : <Play />}
          </button>
          <button className="btn icon" aria-label="Reset" onClick={() => { setEndsAt(null); setPausedLeft(null); }}>
            <RotateCcw />
          </button>
        </div>
      </div>
      <div className="segmented" style={{ marginTop: 10 }}>
        {[25, 50, 90].map((m) => (
          <button key={m} aria-pressed={m === length} disabled={running} onClick={() => { setLength(m); setPausedLeft(null); }}>
            {m} min
          </button>
        ))}
      </div>
    </div>
  );
}


/** "In a call" stopwatch: stopping it opens Log call pre-filled. */
export function CallTimer() {
  const ui = useUi();
  const [startedAt, setStartedAt] = useState<number | null>(() => {
    try {
      const v = localStorage.getItem(CALL_KEY);
      return v ? Number(v) : null;
    } catch {
      return null;
    }
  });
  const [, tick] = useState(0);
  useEffect(() => {
    if (startedAt === null) return;
    const t = setInterval(() => tick((x) => x + 1), 1000);
    return () => clearInterval(t);
  }, [startedAt]);
  const persist = (v: number | null) => {
    setStartedAt(v);
    try {
      if (v === null) localStorage.removeItem(CALL_KEY);
      else localStorage.setItem(CALL_KEY, String(v));
    } catch {
      /* storage unavailable — timer still works for this session */
    }
  };
  const elapsed = startedAt ? Math.floor((Date.now() - startedAt) / 1000) : 0;
  const mm = String(Math.floor(elapsed / 60)).padStart(2, "0");
  const ss = String(elapsed % 60).padStart(2, "0");
  return (
    <div className={cx("rail-card", startedAt !== null && "in-call")}>
      <div className="section-label">
        <Phone /> {startedAt ? "In a call" : "Calls"}
      </div>
      {startedAt === null ? (
        <div className="timer-row">
          <span className="faint" style={{ fontSize: "0.8929rem" }}>
            Track an unplanned call as it happens.
          </span>
          <button className="btn sm" onClick={() => persist(Date.now())}>
            <Play /> Start
          </button>
        </div>
      ) : (
        <div className="timer-row">
          <div className="timer-face" style={{ color: "var(--accent-text)" }}>
            {mm}:{ss}
          </div>
          <div style={{ display: "flex", gap: 4 }}>
            <button
              className="btn primary sm"
              onClick={() => {
                const start = new Date(startedAt).toISOString();
                const minutes = Math.max(1, Math.round(elapsed / 60));
                persist(null);
                ui.openLogCall({ start, minutes });
              }}
            >
              <Square /> Stop & log
            </button>
            <button className="btn icon sm ghost" aria-label="Discard call timer" onClick={() => persist(null)}>
              <X />
            </button>
          </div>
        </div>
      )}
      <button className="btn ghost sm block" style={{ marginTop: 8 }} onClick={() => ui.openLogCall()}>
        Log a past call…
      </button>
    </div>
  );
}
