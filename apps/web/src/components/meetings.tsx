import { useQueryClient } from "@tanstack/react-query";
import { Check, Clock, Phone, Repeat, Star, Trash2, UserRound, Users, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { api } from "../lib/api";
import { invalidateTime, usePeople, useTopics } from "../lib/queries";
import type { Attendance, Meeting } from "../lib/types";
import { clockTime, cx, formatMinutes, isoDay, zonedInstant } from "../lib/util";
import { Dialog, Kbd } from "./primitives";

const ATTENDANCE: { value: Attendance; label: string }[] = [
  { value: "attended", label: "Attend" },
  { value: "partial", label: "Partly" },
  { value: "skipped", label: "Skip" },
];

export function Stars({ value, onChange, size = 15 }: { value: number | null; onChange: (v: number | null) => void; size?: number }) {
  const [hover, setHover] = useState<number | null>(null);
  const shown = hover ?? value ?? 0;
  return (
    <span className="stars" role="radiogroup" aria-label="Value rating" onMouseLeave={() => setHover(null)}>
      {[1, 2, 3, 4, 5].map((n) => (
        <button
          key={n}
          type="button"
          role="radio"
          aria-checked={value === n}
          aria-label={`${n} of 5`}
          className={cx(n <= shown && "on")}
          onMouseEnter={() => setHover(n)}
          onClick={(e) => {
            e.stopPropagation();
            onChange(value === n ? null : n);
          }}
        >
          <Star size={size} fill={n <= shown ? "currentColor" : "none"} />
        </button>
      ))}
    </span>
  );
}

export function MeetingRow({ m, compact }: { m: Meeting; compact?: boolean }) {
  const qc = useQueryClient();
  const ended = new Date(m.end_at).getTime() < Date.now();
  const update = async (changes: Parameters<typeof api.updateMeeting>[1]) => {
    try {
      await api.updateMeeting(m.id, changes);
      invalidateTime(qc);
    } catch (e) {
      toast.error((e as Error).message);
    }
  };
  const skipped = m.effective_status === "skipped";

  return (
    <div className={cx("meeting-row", skipped && "skipped", m.kind === "call" && "call")} data-meeting-id={m.id}>
      <div className="m-time tnum">
        {m.all_day ? "All day" : clockTime(m.start_at)}
        {!m.all_day && <span>{formatMinutes(m.duration_minutes)}</span>}
      </div>
      <div className="m-main">
        <div className="m-title">
          {m.kind === "call" ? <Phone size={13} /> : m.series_key ? <Repeat size={13} /> : null}
          <span>{m.title}</span>
        </div>
        {!compact && (
          <div className="m-meta">
            {m.people.length > 0 && (
              <span>
                <Users size={12} /> {m.people.join(", ")}
              </span>
            )}
            {m.topic && <span className="chip accent">{m.topic}</span>}
            {m.cadence && <span>{m.cadence}</span>}
            {m.series_default_status === "skipped" && m.status === null && <span className="chip">Series skipped</span>}
            {m.location && <span>{m.location}</span>}
          </div>
        )}
      </div>
      {!m.all_day && (
        <div className="m-actions">
          <div className="segmented mini" role="group" aria-label={`Attendance for ${m.title}`}>
            {ATTENDANCE.map((a) => (
              <button
                key={a.value}
                aria-pressed={m.effective_status === a.value}
                onClick={() => {
                  if (a.value === "partial") {
                    const v = prompt("How many minutes did you attend?", String(Math.round(m.duration_minutes / 2)));
                    if (v === null) return;
                    void update({ status: "partial", attended_minutes: Math.max(0, Number(v) || 0) });
                  } else void update({ status: a.value });
                }}
              >
                {a.label}
              </button>
            ))}
          </div>
          {(ended || m.rating !== null) && !skipped && <Stars value={m.rating} onChange={(v) => void update({ rating: v })} />}
          {m.source === "manual" && (
            <button
              className="btn icon sm ghost"
              aria-label="Delete"
              onClick={async () => {
                await api.deleteMeeting(m.id);
                invalidateTime(qc);
                toast(`Removed “${m.title}”`);
              }}
            >
              <Trash2 />
            </button>
          )}
        </div>
      )}
    </div>
  );
}

export interface CallDraft {
  start?: string; // ISO instant
  minutes?: number;
}

/** Log a call or ad-hoc meeting: who, what, when, how long — keyboard friendly. */
export function LogCallDialog({ open, draft, onClose }: { open: boolean; draft?: CallDraft; onClose: () => void }) {
  return (
    <Dialog open={open} onClose={onClose} label="Log a call" width={560}>
      {open && <LogCallBody draft={draft} onClose={onClose} />}
    </Dialog>
  );
}

function LogCallBody({ draft, onClose }: { draft?: CallDraft; onClose: () => void }) {
  const qc = useQueryClient();
  const { data: people = [] } = usePeople();
  const { data: topics = [] } = useTopics();
  const startDate = draft?.start ? new Date(draft.start) : new Date(Date.now() - 30 * 60_000);
  const [who, setWho] = useState<string[]>([]);
  const [whoInput, setWhoInput] = useState("");
  const [title, setTitle] = useState("");
  const [topic, setTopic] = useState("");
  const [day, setDay] = useState(isoDay(startDate));
  const [time, setTime] = useState(clockTime(startDate).replace(/\s?[AP]M$/i, ""));
  const [minutes, setMinutes] = useState(draft?.minutes ?? 30);
  const [rating, setRating] = useState<number | null>(null);
  const [kind, setKind] = useState<"call" | "meeting">("call");
  const whoRef = useRef<HTMLInputElement>(null);

  useEffect(() => whoRef.current?.focus(), []);

  const addPerson = (name: string) => {
    const n = name.trim().replace(/,$/, "");
    if (n && !who.some((w) => w.toLowerCase() === n.toLowerCase())) setWho([...who, n]);
    setWhoInput("");
  };

  const save = async () => {
    const people = whoInput.trim() ? [...who, whoInput.trim()] : who;
    if (people.length === 0 && !title.trim()) {
      toast.error("Add who you talked to or what it was about");
      return;
    }
    try {
      const hhmm = /^\d{1,2}:\d{2}$/.test(time) ? time : "09:00";
      await api.logCall({ title, people, topic: topic || null, start_at: zonedInstant(day, hhmm), minutes, rating, kind });
      invalidateTime(qc);
      toast.success(kind === "call" ? "Call logged" : "Meeting logged", { description: `${people.join(", ") || title} · ${formatMinutes(minutes)}` });
      onClose();
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  const recentPeople = people.filter((p) => !who.includes(p.name)).slice(0, 6);
  return (
    <form
      className="log-call"
      onSubmit={(e) => {
        e.preventDefault();
        void save();
      }}
      onKeyDown={(e) => {
        if ((e.metaKey || e.ctrlKey) && e.key === "Enter") void save();
      }}
    >
      <div className="lc-head">
        <Phone size={18} />
        <h3>Log a call</h3>
        <div className="segmented" style={{ marginLeft: "auto" }}>
          {(["call", "meeting"] as const).map((k) => (
            <button type="button" key={k} aria-pressed={kind === k} onClick={() => setKind(k)}>
              {k === "call" ? "Call" : "Meeting"}
            </button>
          ))}
        </div>
      </div>

      <label className="lc-field">
        <span>
          <UserRound size={14} /> With
        </span>
        <div className="people-input">
          {who.map((w) => (
            <span key={w} className="chip accent">
              {w}
              <button type="button" aria-label={`Remove ${w}`} onClick={() => setWho(who.filter((x) => x !== w))}>
                <X size={11} />
              </button>
            </span>
          ))}
          <input
            ref={whoRef}
            value={whoInput}
            list="people-list"
            placeholder={who.length ? "Add another…" : "Name — Enter or comma to add"}
            onChange={(e) => (e.target.value.endsWith(",") ? addPerson(e.target.value) : setWhoInput(e.target.value))}
            onKeyDown={(e) => {
              if (e.key === "Enter" && whoInput.trim()) {
                e.preventDefault();
                addPerson(whoInput);
              } else if (e.key === "Backspace" && !whoInput && who.length) setWho(who.slice(0, -1));
            }}
          />
          <datalist id="people-list">
            {people.map((p) => (
              <option key={p.id} value={p.name} />
            ))}
          </datalist>
        </div>
      </label>
      {recentPeople.length > 0 && (
        <div className="lc-recent">
          {recentPeople.map((p) => (
            <button type="button" key={p.id} className="filter-chip" onClick={() => addPerson(p.name)}>
              + {p.name}
            </button>
          ))}
        </div>
      )}

      <label className="lc-field">
        <span>Purpose</span>
        <input className="input" value={title} placeholder="e.g. ADR review, 1:1, debugging session" onChange={(e) => setTitle(e.target.value)} />
      </label>
      <label className="lc-field">
        <span>Topic</span>
        <input className="input" value={topic} list="topic-list" placeholder="e.g. Retrieval, Hiring, Career" onChange={(e) => setTopic(e.target.value)} />
        <datalist id="topic-list">
          {topics.map((t) => (
            <option key={t.id} value={t.name} />
          ))}
        </datalist>
      </label>
      <div className="lc-row">
        <label className="lc-field">
          <span>Day</span>
          <input className="input" type="date" value={day} onChange={(e) => setDay(e.target.value)} />
        </label>
        <label className="lc-field">
          <span>
            <Clock size={14} /> Start
          </span>
          <input className="input" type="time" value={time} onChange={(e) => setTime(e.target.value)} />
        </label>
        <label className="lc-field">
          <span>Minutes</span>
          <input className="input" type="number" min={1} max={720} step={1} value={minutes} onChange={(e) => setMinutes(Number(e.target.value))} />
        </label>
      </div>
      <div className="lc-quick">
        {[15, 30, 45, 60, 90].map((m) => (
          <button type="button" key={m} className={cx("filter-chip")} aria-pressed={minutes === m} onClick={() => setMinutes(m)}>
            {formatMinutes(m)}
          </button>
        ))}
      </div>
      <div className="lc-field">
        <span>Was it worth it?</span>
        <Stars value={rating} onChange={setRating} size={18} />
      </div>
      <div className="lc-foot">
        <span className="faint" style={{ fontSize: 12 }}>
          <Kbd>⌘</Kbd>
          <Kbd>↵</Kbd> save
        </span>
        <button type="button" className="btn ghost" onClick={onClose}>
          Cancel
        </button>
        <button type="submit" className="btn primary">
          <Check /> Log {kind}
        </button>
      </div>
    </form>
  );
}
