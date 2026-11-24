import { useEffect, useState } from "react";
import { api } from "../api";
import type { Today } from "../types";
import { formatMinutes, isoDay } from "../util";

interface Props {
  revision: number;
  onCapture: () => void;
  onOpenTask: (id: string) => void;
}

export function RightRail({ revision, onCapture, onOpenTask }: Props) {
  const [now, setNow] = useState(new Date());
  const [today, setToday] = useState<Today | null>(null);

  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 15_000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    api.today(isoDay()).then(setToday).catch(() => setToday(null));
  }, [revision]);

  const top = today
    ? today.plan.top_priority_ids
        .map((id) => today.tasks.find((t) => t.id === id))
        .filter((t): t is NonNullable<typeof t> => t !== undefined)
    : [];
  const next = today?.tasks.find((t) => t.status === "in_progress") ?? today?.tasks.find((t) => t.status === "planned");

  return (
    <aside className="rail" aria-label="Utilities">
      <div className="clock">
        <div className="time">{now.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })}</div>
        <div className="date">{now.toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" })}</div>
      </div>

      <button className="primary wide" onClick={onCapture}>
        + Quick capture <kbd>c</kbd>
      </button>

      {today && (
        <section>
          <h3>Capacity</h3>
          <div className={today.capacity.overcommitted ? "over-text" : ""}>
            {formatMinutes(today.capacity.planned_minutes)} planned / {formatMinutes(today.capacity.capacity_minutes)}
          </div>
          <div className="hint">{formatMinutes(today.capacity.done_minutes)} done</div>
        </section>
      )}

      <section>
        <h3>Top priorities</h3>
        {top.length === 0 && <div className="hint">Star up to three tasks on Today.</div>}
        <ol className="top-list">
          {top.map((t) => (
            <li key={t.id} className={t.status === "done" ? "done" : ""}>
              <button className="link" onClick={() => onOpenTask(t.id)}>
                {t.title}
              </button>
            </li>
          ))}
        </ol>
      </section>

      {next && (
        <section>
          <h3>What next?</h3>
          <button className="link" onClick={() => onOpenTask(next.id)}>
            {next.title}
          </button>
        </section>
      )}

      <FocusTimer />

      <section className="ai-slot">
        <h3>AI assistant</h3>
        <div className="hint">Local LLM (Ollama/vLLM) arrives in Phase 5. Everything here works without it.</div>
      </section>
    </aside>
  );
}

function FocusTimer() {
  const [length, setLength] = useState(25);
  const [endsAt, setEndsAt] = useState<number | null>(null);
  const [, tick] = useState(0);

  useEffect(() => {
    if (endsAt === null) return;
    const t = setInterval(() => {
      tick((x) => x + 1);
      if (Date.now() >= endsAt) {
        setEndsAt(null);
        try {
          new Notification("Focus block finished");
        } catch {
          /* notifications unavailable */
        }
      }
    }, 1000);
    return () => clearInterval(t);
  }, [endsAt]);

  const remaining = endsAt ? Math.max(0, Math.round((endsAt - Date.now()) / 1000)) : length * 60;
  const mm = String(Math.floor(remaining / 60)).padStart(2, "0");
  const ss = String(remaining % 60).padStart(2, "0");

  return (
    <section>
      <h3>Focus timer</h3>
      <div className="timer">
        {mm}:{ss}
      </div>
      <div className="timer-actions">
        {endsAt ? (
          <button onClick={() => setEndsAt(null)}>Stop</button>
        ) : (
          <>
            {[25, 50, 90].map((m) => (
              <button key={m} className={m === length ? "primary" : ""} onClick={() => setLength(m)}>
                {m}
              </button>
            ))}
            <button
              onClick={() => {
                if ("Notification" in window && Notification.permission === "default") void Notification.requestPermission();
                setEndsAt(Date.now() + length * 60_000);
              }}
            >
              Start
            </button>
          </>
        )}
      </div>
    </section>
  );
}
