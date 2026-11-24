import { motion } from "framer-motion";
import { ArrowRight, Pause, Phone, Play, RotateCcw, Sparkles, Square, Star, Timer, X } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { useToday } from "../lib/queries";
import { useUi } from "../lib/ui-store";
import { clockTime, cx, formatMinutes, getWorkspaceTimeZone, isoDay } from "../lib/util";

export function RightRail() {
  const ui = useUi();
  const [now, setNow] = useState(new Date());
  const { data: today } = useToday(isoDay());

  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 10_000);
    return () => clearInterval(t);
  }, []);

  const minutes = now.getHours() * 60 + now.getMinutes();
  const workday = Math.max(0, Math.min(1, (minutes - 8 * 60) / (10 * 60))); // 08:00–18:00

  const top = today
    ? today.plan.top_priority_ids.map((id) => today.tasks.find((t) => t.id === id)).filter((t) => t !== undefined)
    : [];
  const next =
    today?.tasks.find((t) => t.status === "in_progress" && t.parent_id === null) ??
    today?.tasks.find((t) => t.status === "planned" && t.parent_id === null && today.plan.top_priority_ids.includes(t.id)) ??
    today?.tasks.find((t) => t.status === "planned" && t.parent_id === null);

  return (
    <aside className="rail" aria-label="Utilities">
      <div className="rail-card">
        <div className="clock-time">{clockTime(now)}</div>
        <div className="clock-date">{now.toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric", timeZone: getWorkspaceTimeZone() })}</div>
        <div className="day-progress" title="Workday progress (08:00–18:00)">
          <motion.div initial={{ width: 0 }} animate={{ width: `${workday * 100}%` }} transition={{ duration: 0.8 }} />
        </div>
      </div>

      {next && (
        <div className="rail-card">
          <div className="section-label">
            <ArrowRight /> Up next
          </div>
          <button className="btn ghost block" style={{ justifyContent: "flex-start", height: "auto", padding: "4px 0", whiteSpace: "normal", textAlign: "left", color: "var(--text)" }} onClick={() => ui.openTask(next.id)}>
            {next.title}
          </button>
          {next.estimate_minutes !== null && <div className="faint" style={{ fontSize: 12 }}>{formatMinutes(next.estimate_minutes)} estimated</div>}
        </div>
      )}

      <div className="rail-card">
        <div className="section-label">
          <Star /> Top priorities
        </div>
        {top.length === 0 ? (
          <div className="faint" style={{ fontSize: 12.5 }}>
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

      <CallTimer />

      <FocusTimer />

      <div className="rail-card ai-card" style={{ marginTop: "auto" }}>
        <div className="section-label">
          <Sparkles /> Assistant
        </div>
        <div style={{ fontSize: 12.5, color: "var(--text-2)" }}>
          A private, on-device AI that drafts plans and reviews from your own records arrives in Phase 5. Everything works without it.
        </div>
      </div>
    </aside>
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

const CALL_KEY = "ppos.callStartedAt";

/** "In a call" stopwatch: stopping it opens Log call pre-filled. */
function CallTimer() {
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
          <span className="faint" style={{ fontSize: 12.5 }}>
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
